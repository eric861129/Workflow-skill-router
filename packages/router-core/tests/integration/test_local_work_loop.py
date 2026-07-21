from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.local_control import LocalControlPlaneService
from workflow_skill_router.local_work import (
    LocalWorkGraphCorruption,
    local_transition_request_digest,
)
from workflow_skill_router.runtime_readiness import CapabilityUnavailable
from workflow_skill_router.persistence.migrator import iter_complete_statements, migrate
from workflow_skill_router.persistence.sqlite_store import (
    ConcurrencyConflict,
    IdempotencyConflict,
)
from workflow_skill_router.schemas.artifacts import canonical_json
from workflow_skill_router.service_models import (
    EvaluateGate,
    NextWorkQuery,
    PlanWork,
    RecordWorkEvent,
    RequestContext,
    RoutingContextInput,
)
from workflow_skill_router.tool_dispatch import ToolDispatcher
from workflow_skill_router.workflow.local_observations import (
    LocalObservationPolicyError,
    LocalProgressObservation,
)
from workflow_skill_router.workflow.observations import ActivationObservation


class LocalWorkLoopTests(unittest.TestCase):
    SINGLE_COMPLETION_CHECK_ID = "router-local-single-completed"

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "router.db"
        self.service = LocalControlPlaneService(self.database)
        self.context = RequestContext("session-local", "developer", "policy-local")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def command(
        self,
        *,
        objective: str = "Fix the API response",
        idempotency_key: str = "plan-local",
        requested_work_mode: str | None = "single",
        goal_binding_id: str | None = None,
        routing_context: RoutingContextInput = RoutingContextInput(),
        explicit_skill_ids: tuple[str, ...] = (),
        explicit_semantics: str | None = None,
    ) -> PlanWork:
        return PlanWork(
            context=self.context,
            objective=objective,
            goal_binding_id=goal_binding_id,
            requested_work_mode=requested_work_mode,
            explicit_skill_ids=explicit_skill_ids,
            explicit_semantics=explicit_semantics,
            expected_state_version=0,
            idempotency_key=idempotency_key,
            correlation_id="correlation-local",
            routing_context=routing_context,
        )

    def rows(self, sql: str, values: tuple[object, ...] = ()) -> list[sqlite3.Row]:
        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            return list(connection.execute(sql, values).fetchall())

    def query(self, workflow_run_id: str) -> NextWorkQuery:
        return NextWorkQuery(self.context, workflow_run_id)

    @staticmethod
    def local_evidence_digest(check_ids: tuple[str, ...]) -> str:
        return "sha256:" + hashlib.sha256(canonical_json({
            "evidence_class": "user-or-agent-reported-local",
            "persisted_check_ids": sorted(check_ids),
        }).encode("utf-8")).hexdigest()

    def record_command(
        self,
        plan,
        item: sqlite3.Row,
        *,
        transition: str,
        check_ids: tuple[str, ...] = (),
        reported_outcome: str | None = None,
        expected_state_version: int,
        idempotency_key: str,
        workflow_run_id: str | None = None,
        phase_id: str | None = None,
        activation_receipt_ref: str | None = None,
    ) -> RecordWorkEvent:
        return RecordWorkEvent(
            context=self.context,
            workflow_run_id=workflow_run_id or plan.workflow_run_id,
            phase_id=phase_id or item["phase_id"],
            observation=LocalProgressObservation(
                item["work_item_id"], transition, check_ids, reported_outcome,
            ),
            activation_receipt_ref=activation_receipt_ref,
            expected_state_version=expected_state_version,
            idempotency_key=idempotency_key,
            correlation_id=f"correlation-{idempotency_key}",
        )

    def gate_command(
        self,
        plan,
        item: sqlite3.Row,
        *,
        expected_state_version: int,
        expected_evidence_digest: str,
        evidence_refs: tuple[str, ...] = (),
        idempotency_key: str = "gate-local",
        phase_id: str | None = None,
    ) -> EvaluateGate:
        return EvaluateGate(
            context=self.context,
            workflow_run_id=plan.workflow_run_id,
            phase_id=phase_id or item["phase_id"],
            expected_state_version=expected_state_version,
            expected_plan_revision=1,
            expected_evidence_digest=expected_evidence_digest,
            evidence_refs=evidence_refs,
            idempotency_key=idempotency_key,
            correlation_id=f"correlation-{idempotency_key}",
        )

    def mark_graph_as_v0(self, workflow_run_id: str, *, keep_rows: bool) -> None:
        with closing(sqlite3.connect(self.database)) as connection:
            if not keep_rows:
                connection.execute("DROP TRIGGER local_work_transitions_no_delete")
                connection.execute(
                    "DELETE FROM local_work_transitions WHERE workflow_run_id=?",
                    (workflow_run_id,),
                )
                connection.execute(
                    "DELETE FROM local_work_items WHERE workflow_run_id=?",
                    (workflow_run_id,),
                )
            connection.execute(
                "UPDATE local_control_plans SET local_work_graph_version=0 "
                "WHERE workflow_run_id=?",
                (workflow_run_id,),
            )
            connection.commit()

    @staticmethod
    def public_id(prefix: str, *parts: str) -> str:
        identity = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:32]
        return f"{prefix}:{identity}"

    def write_phased_profile(self) -> None:
        profile_dir = self.database.parent / "profiles/personal"
        profile_dir.mkdir(parents=True)
        (profile_dir / "delivery.json").write_text(json.dumps({
            "schema_id": "workflow-skill-router/routing-profile",
            "schema_version": "1.0.0",
            "artifact_kind": "routing-profile",
            "profile_id": "personal:delivery",
            "scope": "personal",
            "enabled": True,
            "rules": [{
                "rule_id": "delivery",
                "priority": 50,
                "match": {
                    "objective_keywords": ["api"],
                    "domains": ["api"],
                    "tags": [],
                    "work_modes": ["phased"],
                },
                "route": {
                    "work_mode": "phased",
                    "skill_tree": [
                        {
                            "phase_id": "design",
                            "primary_skill_id": "skill:api-designer",
                            "support_skill_ids": ["skill:api-guidelines-skill"],
                            "exit_gate": "contract-ready",
                        },
                        {
                            "phase_id": "verify",
                            "primary_skill_id": "skill:qa-test-planner",
                            "support_skill_ids": ["skill:playwright"],
                            "exit_gate": "tests-passed",
                        },
                    ],
                },
            }],
        }), encoding="utf-8")

    def test_fresh_and_repeated_migration_create_append_only_graph_tables(self) -> None:
        migrate(self.database)
        migrate(self.database)

        tables = {
            row["name"]
            for row in self.rows(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        self.assertIn("local_work_items", tables)
        self.assertIn("local_work_transitions", tables)
        applied = self.rows(
            "SELECT COUNT(*) AS count FROM schema_migrations WHERE version='0007'"
        )
        self.assertEqual(1, applied[0]["count"])

    def test_single_plan_persists_one_ready_router_local_item_and_initial_transition(self) -> None:
        result = self.service.plan_work(self.command())

        items = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? ORDER BY item_order",
            (result.workflow_run_id,),
        )
        transitions = self.rows(
            "SELECT * FROM local_work_transitions WHERE workflow_run_id=?",
            (result.workflow_run_id,),
        )

        self.assertEqual(1, result.created_work_items)
        self.assertEqual(1, len(items))
        self.assertEqual("single-work", items[0]["phase_id"])
        self.assertEqual("[]", items[0]["dependency_ids_json"])
        self.assertEqual("ready", items[0]["status"])
        self.assertEqual("router-local", items[0]["authority_mode"])
        self.assertEqual(1, items[0]["state_version"])
        self.assertEqual(1, len(transitions))
        self.assertIsNone(transitions[0]["from_status"])
        self.assertEqual("ready", transitions[0]["to_status"])
        self.assertEqual(0, transitions[0]["expected_state_version"])
        self.assertEqual(1, transitions[0]["resulting_state_version"])
        self.assertTrue(transitions[0]["request_digest"].startswith("sha256:"))
        self.assertEqual("developer", transitions[0]["actor"])

    def test_get_next_work_returns_only_ready_single_router_local_item(self) -> None:
        plan = self.service.plan_work(self.command(idempotency_key="next-single"))

        result = self.service.get_next_work(self.query(plan.workflow_run_id))

        self.assertEqual("ready", result.status)
        self.assertEqual((), result.refresh_requirements)
        self.assertEqual("router-local", result.authority_mode)
        self.assertFalse(result.host_goal_mutated)
        self.assertEqual("single-work", result.work_item.phase_id)
        self.assertEqual("ready", result.work_item.status)
        self.assertEqual("router-local", result.work_item.authority_mode)

    def test_get_next_work_returns_first_ready_profile_phase_only(self) -> None:
        self.write_phased_profile()
        plan = self.service.plan_work(self.command(
            objective="Design and verify the API",
            idempotency_key="next-phased",
            requested_work_mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        ))

        result = self.service.get_next_work(self.query(plan.workflow_run_id))

        self.assertEqual("ready", result.status)
        self.assertEqual("design", result.work_item.phase_id)
        self.assertEqual("skill:api-designer", result.work_item.primary_skill_id)

    def test_get_next_work_fails_closed_for_native_goal_without_host_mutation(self) -> None:
        plan = self.service.plan_work(self.command(
            objective="Continue the native Goal",
            idempotency_key="next-native-goal",
            requested_work_mode="managed-goal",
            goal_binding_id="goal-native-next",
        ))

        with self.assertRaises(CapabilityUnavailable) as direct:
            self.service.get_next_work(self.query(plan.workflow_run_id))
        direct_payload = direct.exception.public_payload()
        self.assertEqual(["verified-host-scheduler"], direct_payload["required_capabilities"])
        self.assertEqual("conditional-local", direct_payload["availability"])

        dispatcher = ToolDispatcher(self.service)
        with patch.object(
            self.service,
            "get_next_work",
            wraps=self.service.get_next_work,
        ) as body:
            with self.assertRaises(CapabilityUnavailable) as dispatched:
                dispatcher.dispatch("get_next_work", {
                    "context": {
                        "session_id": self.context.session_id,
                        "actor": self.context.actor,
                        "runtime_policy_snapshot_id": self.context.runtime_policy_snapshot_id,
                    },
                    "workflow_run_id": plan.workflow_run_id,
                })
        self.assertEqual(direct_payload, dispatched.exception.public_payload())
        body.assert_not_called()

    def test_get_next_work_returns_decomposition_boundary_without_invented_item(self) -> None:
        plan = self.service.plan_work(self.command(
            objective="Design then implement",
            idempotency_key="next-decomposition",
            requested_work_mode="phased",
        ))

        result = self.service.get_next_work(self.query(plan.workflow_run_id))

        self.assertEqual("decomposition-required", result.status)
        self.assertEqual(("local-work-graph-decomposition-required",), result.refresh_requirements)
        self.assertIsNone(result.work_item)
        self.assertEqual("router-local", result.authority_mode)
        self.assertFalse(result.host_goal_mutated)

    def test_completed_dependency_makes_next_phase_eligible_without_persisted_activation(self) -> None:
        self.write_phased_profile()
        plan = self.service.plan_work(self.command(
            objective="Design and verify the API",
            idempotency_key="next-dependency",
            requested_work_mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        ))
        first_item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? AND item_order=0",
            (plan.workflow_run_id,),
        )[0]
        self.service.record_work_event(self.record_command(
            plan, first_item, transition="start", expected_state_version=1,
            idempotency_key="dependency-start",
        ))
        self.service.record_work_event(self.record_command(
            plan, first_item, transition="submit", check_ids=("contract-ready",),
            expected_state_version=2, idempotency_key="dependency-submit",
        ))
        self.service.evaluate_gate(self.gate_command(
            plan, first_item, expected_state_version=3,
            expected_evidence_digest=self.local_evidence_digest(("contract-ready",)),
            idempotency_key="dependency-gate",
        ))

        result = self.service.get_next_work(self.query(plan.workflow_run_id))

        self.assertEqual("ready", result.status)
        self.assertEqual("verify", result.work_item.phase_id)
        self.assertEqual("ready", result.work_item.status)
        persisted = self.rows(
            "SELECT status FROM local_work_items WHERE workflow_run_id=? ORDER BY item_order",
            (plan.workflow_run_id,),
        )
        self.assertEqual(["completed", "pending"], [row["status"] for row in persisted])

    def test_get_next_work_fails_closed_when_graph_integrity_is_invalid(self) -> None:
        plan = self.service.plan_work(self.command(idempotency_key="next-corruption"))
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                "UPDATE local_work_items SET status='completed' WHERE workflow_run_id=?",
                (plan.workflow_run_id,),
            )
            connection.commit()

        with self.assertRaisesRegex(LocalWorkGraphCorruption, "local-work-graph-corruption"):
            self.service.get_next_work(self.query(plan.workflow_run_id))

    def test_get_next_work_requires_replay_for_v0_plan_without_graph(self) -> None:
        plan = self.service.plan_work(self.command(idempotency_key="next-v0-no-graph"))
        self.mark_graph_as_v0(plan.workflow_run_id, keep_rows=False)

        with self.assertRaises(CapabilityUnavailable) as direct:
            self.service.get_next_work(self.query(plan.workflow_run_id))
        expected = direct.exception.public_payload()
        self.assertEqual(["router-owned-work-graph"], expected["required_capabilities"])
        self.assertEqual(
            "Replay or create the Router-owned local work graph before scheduling.",
            expected["fallback_action"],
        )

        dispatcher = ToolDispatcher(self.service)
        with patch.object(
            self.service,
            "get_next_work",
            wraps=self.service.get_next_work,
        ) as body:
            with self.assertRaises(CapabilityUnavailable) as dispatched:
                dispatcher.dispatch("get_next_work", {
                    "context": {
                        "session_id": self.context.session_id,
                        "actor": self.context.actor,
                        "runtime_policy_snapshot_id": self.context.runtime_policy_snapshot_id,
                    },
                    "workflow_run_id": plan.workflow_run_id,
                })
        self.assertEqual(expected, dispatched.exception.public_payload())
        body.assert_not_called()

    def test_get_next_work_rejects_v0_marker_with_graph_rows(self) -> None:
        plan = self.service.plan_work(self.command(idempotency_key="next-v0-with-rows"))
        self.mark_graph_as_v0(plan.workflow_run_id, keep_rows=True)

        with self.assertRaisesRegex(
            LocalWorkGraphCorruption,
            "local-work-graph-corruption: version-marker",
        ):
            self.service.get_next_work(self.query(plan.workflow_run_id))

        dispatcher = ToolDispatcher(self.service)
        with patch.object(
            self.service,
            "get_next_work",
            wraps=self.service.get_next_work,
        ) as body:
            with self.assertRaisesRegex(
                LocalWorkGraphCorruption,
                "local-work-graph-corruption: version-marker",
            ):
                dispatcher.dispatch("get_next_work", {
                    "context": {
                        "session_id": self.context.session_id,
                        "actor": self.context.actor,
                        "runtime_policy_snapshot_id": self.context.runtime_policy_snapshot_id,
                    },
                    "workflow_run_id": plan.workflow_run_id,
                })
        body.assert_not_called()

    def test_get_next_work_rejects_v0_marker_with_only_transition_rows(self) -> None:
        plan = self.service.plan_work(self.command(
            idempotency_key="next-v0-transition-only"
        ))
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                "DELETE FROM local_work_items WHERE workflow_run_id=?",
                (plan.workflow_run_id,),
            )
            connection.execute(
                "UPDATE local_control_plans SET local_work_graph_version=0 "
                "WHERE workflow_run_id=?",
                (plan.workflow_run_id,),
            )
            connection.commit()

        with self.assertRaisesRegex(
            LocalWorkGraphCorruption,
            "local-work-graph-corruption: version-marker",
        ):
            self.service.get_next_work(self.query(plan.workflow_run_id))

    def test_phased_profile_persists_ordered_dependencies_without_activation_claims(self) -> None:
        self.write_phased_profile()

        result = self.service.plan_work(self.command(
            objective="Design and verify the API",
            idempotency_key="phased-profile",
            requested_work_mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        ))
        items = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? ORDER BY item_order",
            (result.workflow_run_id,),
        )

        self.assertEqual(2, result.created_work_items)
        self.assertEqual(["design", "verify"], [row["phase_id"] for row in items])
        self.assertEqual(["ready", "pending"], [row["status"] for row in items])
        self.assertEqual("[]", items[0]["dependency_ids_json"])
        self.assertEqual(
            [items[0]["work_item_id"]],
            json.loads(items[1]["dependency_ids_json"]),
        )
        self.assertEqual("skill:api-designer", items[0]["primary_skill_id"])
        self.assertEqual(
            ["skill:playwright"],
            json.loads(items[1]["support_skill_ids_json"]),
        )
        self.assertEqual("intended-unverified", result.activation_status)

    def test_native_goal_persists_host_scheduler_boundary_only(self) -> None:
        result = self.service.plan_work(self.command(
            objective="Continue the native Goal",
            idempotency_key="native-goal",
            requested_work_mode="managed-goal",
            goal_binding_id="goal-native-1",
        ))
        items = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=?",
            (result.workflow_run_id,),
        )

        self.assertEqual(1, result.created_work_items)
        self.assertEqual("host-scheduler-boundary", items[0]["phase_id"])
        self.assertEqual("host-scheduler-required", items[0]["status"])
        self.assertIsNone(items[0]["primary_skill_id"])
        self.assertEqual("[]", items[0]["support_skill_ids_json"])

    def test_phased_and_unbound_managed_goal_without_tree_require_decomposition(self) -> None:
        phased = self.service.plan_work(self.command(
            objective="Design then implement",
            idempotency_key="phased-no-tree",
            requested_work_mode="phased",
        ))
        managed = self.service.plan_work(self.command(
            objective="Run a large local workflow",
            idempotency_key="managed-no-tree",
            requested_work_mode="managed-goal",
        ))

        for result in (phased, managed):
            item = self.rows(
                "SELECT * FROM local_work_items WHERE workflow_run_id=?",
                (result.workflow_run_id,),
            )[0]
            self.assertEqual(1, result.created_work_items)
            self.assertEqual("decomposition-boundary", item["phase_id"])
            self.assertEqual("decomposition-required", item["status"])
            self.assertIsNone(item["primary_skill_id"])

    def test_plan_and_graph_roll_back_as_one_transaction(self) -> None:
        with patch(
            "workflow_skill_router.local_control.persist_local_work_graph",
            side_effect=RuntimeError("injected graph failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected graph failure"):
                self.service.plan_work(self.command(idempotency_key="atomic-failure"))

        self.assertEqual(0, self.rows("SELECT COUNT(*) AS count FROM local_control_plans")[0]["count"])
        self.assertEqual(0, self.rows("SELECT COUNT(*) AS count FROM local_work_items")[0]["count"])
        self.assertEqual(0, self.rows("SELECT COUNT(*) AS count FROM local_work_transitions")[0]["count"])

    def test_replay_returns_same_graph_and_fails_closed_on_corruption(self) -> None:
        command = self.command(idempotency_key="graph-replay")
        first = self.service.plan_work(command)
        first_items = [dict(row) for row in self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? ORDER BY item_order",
            (first.workflow_run_id,),
        )]

        replay = self.service.plan_work(command)
        replay_items = [dict(row) for row in self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? ORDER BY item_order",
            (first.workflow_run_id,),
        )]
        self.assertEqual(first, replay)
        self.assertEqual(first_items, replay_items)

        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                "UPDATE local_work_items SET status='active' WHERE workflow_run_id=?",
                (first.workflow_run_id,),
            )
            connection.commit()

        with self.assertRaisesRegex(LocalWorkGraphCorruption, "local-work-graph-corruption"):
            self.service.plan_work(command)

    def test_replay_fails_closed_when_append_only_transition_digest_is_corrupt(self) -> None:
        command = self.command(idempotency_key="transition-corruption")
        result = self.service.plan_work(command)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("DROP TRIGGER local_work_transitions_no_update")
            connection.execute(
                "UPDATE local_work_transitions SET request_digest=? WHERE workflow_run_id=?",
                ("sha256:" + "0" * 64, result.workflow_run_id),
            )
            connection.commit()

        with self.assertRaisesRegex(LocalWorkGraphCorruption, "local-work-graph-corruption"):
            self.service.plan_work(command)

    def test_replay_fails_closed_on_dependency_or_transition_actor_corruption(self) -> None:
        self.write_phased_profile()
        phased_command = self.command(
            objective="Design and verify the API",
            idempotency_key="dependency-corruption",
            requested_work_mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        )
        phased = self.service.plan_work(phased_command)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                "UPDATE local_work_items SET dependency_ids_json='[]' "
                "WHERE workflow_run_id=? AND item_order=1",
                (phased.workflow_run_id,),
            )
            connection.commit()
        with self.assertRaisesRegex(LocalWorkGraphCorruption, "local-work-graph-corruption"):
            self.service.plan_work(phased_command)

        actor_command = self.command(idempotency_key="transition-actor-corruption")
        actor_plan = self.service.plan_work(actor_command)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("DROP TRIGGER local_work_transitions_no_update")
            connection.execute(
                "UPDATE local_work_transitions SET actor='attacker' WHERE workflow_run_id=?",
                (actor_plan.workflow_run_id,),
            )
            connection.commit()
        with self.assertRaisesRegex(LocalWorkGraphCorruption, "local-work-graph-corruption"):
            self.service.plan_work(actor_command)

    def test_replay_reconstructs_profile_skills_and_phase_from_persisted_plan(self) -> None:
        self.write_phased_profile()
        commands = {
            kind: self.command(
                objective="Design and verify the API",
                idempotency_key=f"immutable-{kind}",
                requested_work_mode="phased",
                routing_context=RoutingContextInput(domains=("api",)),
            )
            for kind in ("primary", "support", "phase")
        }
        plans = {kind: self.service.plan_work(command) for kind, command in commands.items()}

        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute(
                "UPDATE local_work_items SET primary_skill_id='skill:other-designer' "
                "WHERE workflow_run_id=? AND item_order=0",
                (plans["primary"].workflow_run_id,),
            )
            connection.execute(
                "UPDATE local_work_items SET support_skill_ids_json='[\"skill:other-support\"]' "
                "WHERE workflow_run_id=? AND item_order=0",
                (plans["support"].workflow_run_id,),
            )

            phase_plan = plans["phase"]
            first = connection.execute(
                "SELECT * FROM local_work_items WHERE workflow_run_id=? AND item_order=0",
                (phase_plan.workflow_run_id,),
            ).fetchone()
            transition = connection.execute(
                "SELECT * FROM local_work_transitions WHERE workflow_run_id=? "
                "AND work_item_id=?",
                (phase_plan.workflow_run_id, first["work_item_id"]),
            ).fetchone()
            new_phase_id = "discovery"
            new_work_item_id = self.public_id(
                "work-item", first["work_graph_id"], "0", new_phase_id
            )
            new_transition_id = self.public_id("work-transition", new_work_item_id, "1")
            new_digest = local_transition_request_digest(
                session_id=transition["session_id"],
                actor=transition["actor"],
                workflow_run_id=transition["workflow_run_id"],
                work_item_id=new_work_item_id,
                transition_kind=transition["transition_kind"],
                from_status=transition["from_status"],
                to_status=transition["to_status"],
                expected_state_version=transition["expected_state_version"],
                resulting_state_version=transition["resulting_state_version"],
            )
            connection.execute("DROP TRIGGER local_work_transitions_no_update")
            connection.execute(
                "UPDATE local_work_items SET work_item_id=?,phase_id=? WHERE work_item_id=?",
                (new_work_item_id, new_phase_id, first["work_item_id"]),
            )
            connection.execute(
                "UPDATE local_work_items SET dependency_ids_json=? "
                "WHERE workflow_run_id=? AND item_order=1",
                (canonical_json([new_work_item_id]), phase_plan.workflow_run_id),
            )
            connection.execute(
                "UPDATE local_work_transitions SET transition_id=?,work_item_id=?,request_digest=? "
                "WHERE transition_id=?",
                (
                    new_transition_id,
                    new_work_item_id,
                    new_digest,
                    transition["transition_id"],
                ),
            )
            connection.commit()

        rejected = []
        for kind, command in commands.items():
            try:
                self.service.plan_work(command)
            except LocalWorkGraphCorruption:
                rejected.append(kind)
        self.assertEqual(["primary", "support", "phase"], rejected)

    def test_replay_binds_initial_status_semantics_for_every_boundary_branch(self) -> None:
        commands = {
            "single": self.command(idempotency_key="initial-single"),
            "native": self.command(
                objective="Continue the native Goal",
                idempotency_key="initial-native",
                requested_work_mode="managed-goal",
                goal_binding_id="goal-native-initial",
            ),
            "decomposition": self.command(
                objective="Design then implement",
                idempotency_key="initial-decomposition",
                requested_work_mode="phased",
            ),
        }
        plans = {kind: self.service.plan_work(command) for kind, command in commands.items()}
        replacements = {
            "single": "paused",
            "native": "decomposition-required",
            "decomposition": "host-scheduler-required",
        }
        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("DROP TRIGGER local_work_transitions_no_update")
            for kind, plan in plans.items():
                transition = connection.execute(
                    "SELECT * FROM local_work_transitions WHERE workflow_run_id=?",
                    (plan.workflow_run_id,),
                ).fetchone()
                new_status = replacements[kind]
                new_digest = local_transition_request_digest(
                    session_id=transition["session_id"],
                    actor=transition["actor"],
                    workflow_run_id=transition["workflow_run_id"],
                    work_item_id=transition["work_item_id"],
                    transition_kind=transition["transition_kind"],
                    from_status=transition["from_status"],
                    to_status=new_status,
                    expected_state_version=transition["expected_state_version"],
                    resulting_state_version=transition["resulting_state_version"],
                )
                connection.execute(
                    "UPDATE local_work_items SET status=? WHERE work_item_id=?",
                    (new_status, transition["work_item_id"]),
                )
                connection.execute(
                    "UPDATE local_work_transitions SET to_status=?,request_digest=? "
                    "WHERE transition_id=?",
                    (new_status, new_digest, transition["transition_id"]),
                )
            connection.commit()

        rejected = []
        for kind, command in commands.items():
            try:
                self.service.plan_work(command)
            except LocalWorkGraphCorruption:
                rejected.append(kind)
        self.assertEqual(["single", "native", "decomposition"], rejected)

    def test_replay_binds_actor_even_when_attacker_recomputes_transition_digest(self) -> None:
        command = self.command(idempotency_key="actor-and-digest-corruption")
        plan = self.service.plan_work(command)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            transition = connection.execute(
                "SELECT * FROM local_work_transitions WHERE workflow_run_id=?",
                (plan.workflow_run_id,),
            ).fetchone()
            forged_actor = "attacker"
            forged_digest = local_transition_request_digest(
                session_id=transition["session_id"],
                actor=forged_actor,
                workflow_run_id=transition["workflow_run_id"],
                work_item_id=transition["work_item_id"],
                transition_kind=transition["transition_kind"],
                from_status=transition["from_status"],
                to_status=transition["to_status"],
                expected_state_version=transition["expected_state_version"],
                resulting_state_version=transition["resulting_state_version"],
            )
            connection.execute("DROP TRIGGER local_work_transitions_no_update")
            connection.execute(
                "UPDATE local_work_transitions SET actor=?,request_digest=? "
                "WHERE transition_id=?",
                (forged_actor, forged_digest, transition["transition_id"]),
            )
            connection.commit()

        with self.assertRaisesRegex(LocalWorkGraphCorruption, "local-work-graph-corruption"):
            self.service.plan_work(command)

    def test_replay_rejects_plan_and_transition_actor_rewrite(self) -> None:
        command = self.command(idempotency_key="plan-actor-corruption")
        plan = self.service.plan_work(command)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            transition = connection.execute(
                "SELECT * FROM local_work_transitions WHERE workflow_run_id=?",
                (plan.workflow_run_id,),
            ).fetchone()
            forged_actor = "attacker"
            forged_digest = local_transition_request_digest(
                session_id=transition["session_id"],
                actor=forged_actor,
                workflow_run_id=transition["workflow_run_id"],
                work_item_id=transition["work_item_id"],
                transition_kind=transition["transition_kind"],
                from_status=transition["from_status"],
                to_status=transition["to_status"],
                expected_state_version=transition["expected_state_version"],
                resulting_state_version=transition["resulting_state_version"],
            )
            connection.execute("DROP TRIGGER local_work_transitions_no_update")
            connection.execute(
                "UPDATE local_control_plans SET actor=? WHERE workflow_run_id=?",
                (forged_actor, plan.workflow_run_id),
            )
            connection.execute(
                "UPDATE local_work_transitions SET actor=?,request_digest=? "
                "WHERE transition_id=?",
                (forged_actor, forged_digest, transition["transition_id"]),
            )
            connection.commit()

        with self.assertRaisesRegex(LocalWorkGraphCorruption, "local-work-graph-corruption"):
            self.service.plan_work(command)

    def test_transition_log_rejects_updates_deletes_and_duplicate_versions(self) -> None:
        result = self.service.plan_work(self.command(idempotency_key="append-only"))
        transition = self.rows(
            "SELECT * FROM local_work_transitions WHERE workflow_run_id=?",
            (result.workflow_run_id,),
        )[0]

        with closing(sqlite3.connect(self.database)) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE local_work_transitions SET actor='attacker' WHERE transition_id=?",
                    (transition["transition_id"],),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "DELETE FROM local_work_transitions WHERE transition_id=?",
                    (transition["transition_id"],),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO local_work_transitions("
                    "transition_id,session_id,workflow_run_id,work_item_id,transition_kind,from_status,"
                    "to_status,expected_state_version,resulting_state_version,idempotency_key,"
                    "request_digest,actor,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        "transition:duplicate", "session-local", result.workflow_run_id,
                        transition["work_item_id"], "create", None, "ready", 0, 1,
                        "duplicate-version", "sha256:" + "0" * 64, "developer",
                        "2026-07-21T00:00:00+00:00",
                    ),
                )

    def test_beta4_plan_replay_backfills_once_then_detects_missing_graph_as_corruption(self) -> None:
        self.directory.cleanup()
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "router.db"
        migration_dir = (
            Path(__file__).resolve().parents[2]
            / "src/workflow_skill_router/persistence/migrations"
        )
        with closing(sqlite3.connect(self.database)) as connection:
            for migration in sorted(migration_dir.glob("000[1-6]_*.sql")):
                for statement in iter_complete_statements(migration.read_text(encoding="utf-8")):
                    connection.execute(statement)
                checksum = hashlib.sha256(migration.read_bytes()).hexdigest()
                connection.execute(
                    "INSERT INTO schema_migrations(version,checksum,applied_at) VALUES (?,?,?)",
                    (migration.name.split("_", 1)[0], checksum, "2026-07-21T00:00:00+00:00"),
                )

            objective = "Fix the API response"
            objective_digest = "sha256:" + hashlib.sha256(objective.encode()).hexdigest()
            request_document = {
                "actor": "developer",
                "correlation_id": "correlation-local",
                "explicit_semantics": None,
                "explicit_skill_ids": [],
                "goal_binding_id": None,
                "objective_digest": objective_digest,
                "requested_work_mode": "single",
                "routing_context": {
                    "current_phase_id": None,
                    "domains": [],
                    "tags": [],
                    "workspace_root_digest": None,
                },
                "runtime_policy_snapshot_id": "policy-local",
                "session_id": "session-local",
            }
            request_digest = "sha256:" + hashlib.sha256(
                canonical_json(request_document).encode()
            ).hexdigest()
            connection.execute(
                "INSERT INTO local_control_plans("
                "plan_id,session_id,actor,runtime_policy_snapshot_id,idempotency_key,request_digest,"
                "workflow_run_id,work_graph_id,goal_binding_id,objective_digest,routing_envelope,"
                "selection_mode,support_policy,support_consent_required,explicit_skill_ids_json,"
                "explicit_semantics,created_work_items,state_version,created_at,route_source,"
                "routing_profile_ids_json,routing_profile_digest,matched_profile_rule_id,"
                "planned_skill_ids_json,planned_skill_tree_json,activation_status,profile_warnings_json,"
                "classification_source,classification_confidence,classifier_revision,"
                "classification_reason_codes_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "plan:legacy-beta4", "session-local", "developer", "policy-local", "legacy-beta4",
                    request_digest, "workflow:legacy-beta4", "work-graph:legacy-beta4", None,
                    objective_digest, "single", "auto", "auto", 0, "[]", None, 1, 1,
                    "2026-07-21T00:00:00+00:00", "builtin-default", "[]", None, None,
                    "[]", "[]", "not-planned", "[]", "caller-work-mode-hint", "low",
                    "deterministic-objective-v1", "[]",
                ),
            )
            connection.commit()

        self.service = LocalControlPlaneService(self.database)
        command = self.command(idempotency_key="legacy-beta4")
        first = self.service.plan_work(command)
        replay = self.service.plan_work(command)
        self.assertEqual(first, replay)
        self.assertEqual(1, len(self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id='workflow:legacy-beta4'"
        )))

        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                "DELETE FROM local_work_items WHERE workflow_run_id='workflow:legacy-beta4'"
            )
            connection.commit()
        with self.assertRaisesRegex(LocalWorkGraphCorruption, "local-work-graph-corruption"):
            self.service.plan_work(command)

    def test_local_start_submit_and_gate_complete_only_router_owned_phase(self) -> None:
        self.write_phased_profile()
        plan = self.service.plan_work(self.command(
            objective="Design and verify the API",
            idempotency_key="local-progress-happy",
            requested_work_mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        ))
        item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? AND item_order=0",
            (plan.workflow_run_id,),
        )[0]

        started = self.service.record_work_event(self.record_command(
            plan, item, transition="start", expected_state_version=1,
            idempotency_key="local-start",
        ))
        submitted = self.service.record_work_event(self.record_command(
            plan, item, transition="submit", check_ids=("contract-ready",),
            reported_outcome="Contract drafted locally", expected_state_version=2,
            idempotency_key="local-submit",
        ))
        gated = self.service.evaluate_gate(self.gate_command(
            plan, item, expected_state_version=3,
            expected_evidence_digest=self.local_evidence_digest(("contract-ready",)),
        ))

        self.assertEqual("router-local", started.authority_mode)
        self.assertEqual("user-or-agent-reported-local", started.evidence_class)
        self.assertFalse(started.host_transition_authorized)
        self.assertEqual(2, started.resulting_state_version)
        self.assertEqual(3, submitted.resulting_state_version)
        self.assertEqual("router-local", gated.gate_scope)
        self.assertEqual("router-local", gated.authority_mode)
        self.assertEqual("user-or-agent-reported-local", gated.evidence_class)
        self.assertFalse(gated.host_transition_authorized)
        self.assertTrue(gated.passed)
        self.assertEqual(4, gated.resulting_state_version)
        current = self.rows(
            "SELECT status,state_version FROM local_work_items WHERE work_item_id=?",
            (item["work_item_id"],),
        )[0]
        self.assertEqual(("completed", 4), (current["status"], current["state_version"]))
        transitions = self.rows(
            "SELECT transition_kind,observation_json FROM local_work_transitions "
            "WHERE work_item_id=? ORDER BY resulting_state_version",
            (item["work_item_id"],),
        )
        self.assertEqual(
            ["create", "start", "submit", "gate-pass"],
            [row["transition_kind"] for row in transitions],
        )
        self.assertIn("contract-ready", transitions[2]["observation_json"])
        self.assertNotIn("activation_receipt", transitions[2]["observation_json"])

    def test_profile_less_single_completes_with_bound_router_local_check(self) -> None:
        plan = self.service.plan_work(self.command(
            idempotency_key="profile-less-single-completion",
            requested_work_mode=None,
        ))
        item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=?",
            (plan.workflow_run_id,),
        )[0]

        self.assertEqual("single", plan.routing_envelope)
        self.assertEqual("builtin-fallback", plan.classification.source)
        self.assertEqual(
            "deterministic-objective-v1",
            plan.classification.classifier_revision,
        )
        self.service.record_work_event(self.record_command(
            plan, item, transition="start", expected_state_version=1,
            idempotency_key="profile-less-single-start",
        ))
        self.service.record_work_event(self.record_command(
            plan, item, transition="submit",
            check_ids=(self.SINGLE_COMPLETION_CHECK_ID,),
            reported_outcome="Task completed locally",
            expected_state_version=2,
            idempotency_key="profile-less-single-submit",
        ))
        result = self.service.evaluate_gate(self.gate_command(
            plan, item, expected_state_version=3,
            expected_evidence_digest=self.local_evidence_digest(
                (self.SINGLE_COMPLETION_CHECK_ID,)
            ),
            idempotency_key="profile-less-single-gate",
        ))

        self.assertTrue(result.passed)
        self.assertEqual("router-local", result.authority_mode)
        self.assertEqual("user-or-agent-reported-local", result.evidence_class)
        self.assertFalse(result.host_transition_authorized)
        self.assertEqual("completed", self.rows(
            "SELECT status FROM local_work_items WHERE work_item_id=?",
            (item["work_item_id"],),
        )[0]["status"])

    def test_explicit_skill_single_completes_with_same_bound_router_local_check(self) -> None:
        plan = self.service.plan_work(self.command(
            idempotency_key="explicit-single-completion",
            explicit_skill_ids=("skill:security-review",),
            explicit_semantics="only",
        ))
        item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=?",
            (plan.workflow_run_id,),
        )[0]

        self.assertEqual("explicit-locked", plan.selection_mode)
        self.service.record_work_event(self.record_command(
            plan, item, transition="start", expected_state_version=1,
            idempotency_key="explicit-single-start",
        ))
        self.service.record_work_event(self.record_command(
            plan, item, transition="submit",
            check_ids=(self.SINGLE_COMPLETION_CHECK_ID,),
            reported_outcome="Explicit Skill task completed locally",
            expected_state_version=2,
            idempotency_key="explicit-single-submit",
        ))
        result = self.service.evaluate_gate(self.gate_command(
            plan, item, expected_state_version=3,
            expected_evidence_digest=self.local_evidence_digest(
                (self.SINGLE_COMPLETION_CHECK_ID,)
            ),
            idempotency_key="explicit-single-gate",
        ))

        self.assertTrue(result.passed)
        self.assertEqual("completed", self.rows(
            "SELECT status FROM local_work_items WHERE work_item_id=?",
            (item["work_item_id"],),
        )[0]["status"])

    def test_local_gate_reports_missing_required_check_without_host_authority(self) -> None:
        self.write_phased_profile()
        plan = self.service.plan_work(self.command(
            objective="Design and verify the API",
            idempotency_key="local-missing-check",
            requested_work_mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        ))
        item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? AND item_order=0",
            (plan.workflow_run_id,),
        )[0]
        self.service.record_work_event(self.record_command(
            plan, item, transition="start", expected_state_version=1,
            idempotency_key="missing-start",
        ))
        self.service.record_work_event(self.record_command(
            plan, item, transition="submit", reported_outcome="Looks done",
            expected_state_version=2, idempotency_key="missing-submit",
        ))

        result = self.service.evaluate_gate(self.gate_command(
            plan, item, expected_state_version=3,
            expected_evidence_digest=self.local_evidence_digest(()),
            idempotency_key="missing-gate",
        ))

        self.assertFalse(result.passed)
        self.assertEqual(("missing-local-check:contract-ready",), result.failures)
        self.assertFalse(result.host_transition_authorized)
        self.assertEqual("verifying", self.rows(
            "SELECT status FROM local_work_items WHERE work_item_id=?",
            (item["work_item_id"],),
        )[0]["status"])

    def test_local_record_rejects_forged_receipt_formal_observation_and_native_goal(self) -> None:
        plan = self.service.plan_work(self.command(idempotency_key="reject-local-input"))
        item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=?",
            (plan.workflow_run_id,),
        )[0]
        forged = self.record_command(
            plan, item, transition="start", expected_state_version=1,
            idempotency_key="forged-receipt", activation_receipt_ref="receipt:forged",
        )
        formal = RecordWorkEvent(
            self.context, plan.workflow_run_id, item["phase_id"],
            ActivationObservation("skill:test", "receipt:forged"), None, 1,
            "formal-observation", "correlation-formal",
        )
        native = self.service.plan_work(self.command(
            objective="Continue the native Goal", idempotency_key="native-local-event",
            requested_work_mode="managed-goal", goal_binding_id="goal-native-event",
        ))
        native_item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=?",
            (native.workflow_run_id,),
        )[0]

        with self.assertRaises(LocalObservationPolicyError):
            self.service.record_work_event(forged)
        with self.assertRaises(LocalObservationPolicyError):
            self.service.record_work_event(formal)
        with self.assertRaises(CapabilityUnavailable):
            self.service.record_work_event(self.record_command(
                native, native_item, transition="start", expected_state_version=1,
                idempotency_key="native-start",
            ))

    def test_local_record_rejects_cross_workflow_phase_drift_and_unknown_check(self) -> None:
        self.write_phased_profile()
        first = self.service.plan_work(self.command(
            objective="Design and verify the API", idempotency_key="first-workflow",
            requested_work_mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        ))
        second = self.service.plan_work(self.command(idempotency_key="second-workflow"))
        first_item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? AND item_order=0",
            (first.workflow_run_id,),
        )[0]

        with self.assertRaises(LocalObservationPolicyError):
            self.service.record_work_event(self.record_command(
                second, first_item, transition="start", expected_state_version=1,
                idempotency_key="cross-workflow",
            ))
        with self.assertRaises(LocalObservationPolicyError):
            self.service.record_work_event(self.record_command(
                first, first_item, transition="start", expected_state_version=1,
                idempotency_key="phase-drift", phase_id="verify",
            ))
        self.service.record_work_event(self.record_command(
            first, first_item, transition="start", expected_state_version=1,
            idempotency_key="unknown-start",
        ))
        with self.assertRaises(LocalObservationPolicyError):
            self.service.record_work_event(self.record_command(
                first, first_item, transition="submit", check_ids=("fabricated-check",),
                expected_state_version=2, idempotency_key="unknown-submit",
            ))

    def test_local_record_enforces_stale_version_idempotency_and_transition_matrix(self) -> None:
        plan = self.service.plan_work(self.command(idempotency_key="record-cas"))
        item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=?",
            (plan.workflow_run_id,),
        )[0]
        command = self.record_command(
            plan, item, transition="start", expected_state_version=1,
            idempotency_key="record-once",
        )
        first = self.service.record_work_event(command)
        replay = self.service.record_work_event(command)
        self.assertEqual(first.event_ids, replay.event_ids)
        self.assertTrue(replay.replayed)
        with self.assertRaises(IdempotencyConflict):
            self.service.record_work_event(self.record_command(
                plan, item, transition="fail", expected_state_version=1,
                idempotency_key="record-once",
            ))
        with self.assertRaises(ConcurrencyConflict):
            self.service.record_work_event(self.record_command(
                plan, item, transition="submit", expected_state_version=1,
                idempotency_key="record-stale",
            ))
        with self.assertRaises(LocalObservationPolicyError):
            self.service.record_work_event(self.record_command(
                plan, item, transition="resume", expected_state_version=2,
                idempotency_key="record-illegal-transition",
            ))

    def test_local_pause_resume_and_fail_follow_deterministic_matrix(self) -> None:
        plan = self.service.plan_work(self.command(idempotency_key="record-matrix"))
        item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=?",
            (plan.workflow_run_id,),
        )[0]
        sequence = (
            ("start", 1, "active"),
            ("pause", 2, "paused"),
            ("resume", 3, "active"),
            ("submit", 4, "verifying"),
            ("pause", 5, "paused"),
            ("resume", 6, "active"),
            ("fail", 7, "failed"),
        )
        for transition, expected_version, expected_status in sequence:
            result = self.service.record_work_event(self.record_command(
                plan, item, transition=transition,
                expected_state_version=expected_version,
                idempotency_key=f"matrix-{transition}-{expected_version}",
            ))
            self.assertEqual(expected_version + 1, result.resulting_state_version)
            self.assertEqual(expected_status, self.rows(
                "SELECT status FROM local_work_items WHERE work_item_id=?",
                (item["work_item_id"],),
            )[0]["status"])

    def test_local_gate_rejects_fabricated_refs_phase_drift_and_missing_single_check(self) -> None:
        plan = self.service.plan_work(self.command(idempotency_key="gate-boundaries"))
        item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=?",
            (plan.workflow_run_id,),
        )[0]
        self.service.record_work_event(self.record_command(
            plan, item, transition="start", expected_state_version=1,
            idempotency_key="gate-boundary-start",
        ))
        self.service.record_work_event(self.record_command(
            plan, item, transition="submit", expected_state_version=2,
            idempotency_key="gate-boundary-submit",
        ))

        with self.assertRaises(LocalObservationPolicyError):
            self.service.evaluate_gate(self.gate_command(
                plan, item, expected_state_version=3,
                expected_evidence_digest=self.local_evidence_digest(()),
                evidence_refs=("evidence:forged",), idempotency_key="forged-gate-ref",
            ))
        with self.assertRaises(LocalObservationPolicyError):
            self.service.evaluate_gate(self.gate_command(
                plan, item, expected_state_version=3,
                expected_evidence_digest=self.local_evidence_digest(()),
                phase_id="other-phase", idempotency_key="gate-phase-drift",
            ))
        missing = self.service.evaluate_gate(self.gate_command(
            plan, item, expected_state_version=3,
            expected_evidence_digest=self.local_evidence_digest(()),
            idempotency_key="gate-missing-single-check",
        ))
        self.assertFalse(missing.passed)
        self.assertEqual(
            (f"missing-local-check:{self.SINGLE_COMPLETION_CHECK_ID}",),
            missing.failures,
        )
        self.assertFalse(missing.host_transition_authorized)
        self.assertEqual("verifying", self.rows(
            "SELECT status FROM local_work_items WHERE work_item_id=?",
            (item["work_item_id"],),
        )[0]["status"])

    def test_local_record_rejects_v0_marker_when_graph_rows_exist(self) -> None:
        plan = self.service.plan_work(self.command(idempotency_key="record-v0-rows"))
        item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=?",
            (plan.workflow_run_id,),
        )[0]
        self.mark_graph_as_v0(plan.workflow_run_id, keep_rows=True)

        with self.assertRaisesRegex(
            LocalWorkGraphCorruption,
            "local-work-graph-corruption: version-marker",
        ):
            self.service.record_work_event(self.record_command(
                plan, item, transition="start", expected_state_version=1,
                idempotency_key="record-v0-start",
            ))

    def test_local_gate_rejects_recomputed_unknown_persisted_check(self) -> None:
        self.write_phased_profile()
        plan = self.service.plan_work(self.command(
            objective="Design and verify the API",
            idempotency_key="forged-persisted-check",
            requested_work_mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        ))
        item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? AND item_order=0",
            (plan.workflow_run_id,),
        )[0]
        self.service.record_work_event(self.record_command(
            plan, item, transition="start", expected_state_version=1,
            idempotency_key="forged-check-start",
        ))
        self.service.record_work_event(self.record_command(
            plan, item, transition="submit", check_ids=("contract-ready",),
            expected_state_version=2, idempotency_key="forged-check-submit",
        ))
        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            transition = connection.execute(
                "SELECT * FROM local_work_transitions WHERE work_item_id=? "
                "AND transition_kind='submit'",
                (item["work_item_id"],),
            ).fetchone()
            document = json.loads(transition["observation_json"])
            document["check_ids"] = ["fabricated-check"]
            forged_digest = local_transition_request_digest(
                session_id=transition["session_id"],
                actor=transition["actor"],
                workflow_run_id=transition["workflow_run_id"],
                work_item_id=transition["work_item_id"],
                transition_kind=transition["transition_kind"],
                from_status=transition["from_status"],
                to_status=transition["to_status"],
                expected_state_version=transition["expected_state_version"],
                resulting_state_version=transition["resulting_state_version"],
                observation_document=document,
            )
            connection.execute("DROP TRIGGER local_work_transitions_no_update")
            connection.execute(
                "UPDATE local_work_transitions SET observation_json=?,request_digest=? "
                "WHERE transition_id=?",
                (canonical_json(document), forged_digest, transition["transition_id"]),
            )
            connection.commit()

        with self.assertRaisesRegex(
            LocalWorkGraphCorruption,
            "local-work-graph-corruption: unknown-local-check",
        ):
            self.service.evaluate_gate(self.gate_command(
                plan, item, expected_state_version=3,
                expected_evidence_digest=self.local_evidence_digest(("fabricated-check",)),
                idempotency_key="forged-check-gate",
            ))

    def test_plan_replay_rejects_recomputed_local_gate_phase_binding(self) -> None:
        self.write_phased_profile()
        command = self.command(
            objective="Design and verify the API",
            idempotency_key="forged-gate-phase",
            requested_work_mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        )
        plan = self.service.plan_work(command)
        item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? AND item_order=0",
            (plan.workflow_run_id,),
        )[0]
        self.service.record_work_event(self.record_command(
            plan, item, transition="start", expected_state_version=1,
            idempotency_key="forged-phase-start",
        ))
        self.service.record_work_event(self.record_command(
            plan, item, transition="submit", check_ids=("contract-ready",),
            expected_state_version=2, idempotency_key="forged-phase-submit",
        ))
        self.service.evaluate_gate(self.gate_command(
            plan, item, expected_state_version=3,
            expected_evidence_digest=self.local_evidence_digest(("contract-ready",)),
            idempotency_key="forged-phase-gate",
        ))
        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            transition = connection.execute(
                "SELECT * FROM local_work_transitions WHERE work_item_id=? "
                "AND transition_kind='gate-pass'",
                (item["work_item_id"],),
            ).fetchone()
            document = json.loads(transition["observation_json"])
            document["phase_id"] = "verify"
            forged_digest = local_transition_request_digest(
                session_id=transition["session_id"],
                actor=transition["actor"],
                workflow_run_id=transition["workflow_run_id"],
                work_item_id=transition["work_item_id"],
                transition_kind=transition["transition_kind"],
                from_status=transition["from_status"],
                to_status=transition["to_status"],
                expected_state_version=transition["expected_state_version"],
                resulting_state_version=transition["resulting_state_version"],
                observation_document=document,
            )
            connection.execute("DROP TRIGGER local_work_transitions_no_update")
            connection.execute(
                "UPDATE local_work_transitions SET observation_json=?,request_digest=? "
                "WHERE transition_id=?",
                (canonical_json(document), forged_digest, transition["transition_id"]),
            )
            connection.commit()

        with self.assertRaisesRegex(
            LocalWorkGraphCorruption,
            "local-work-graph-corruption: gate-binding",
        ):
            self.service.plan_work(command)

    def test_local_commands_reject_boolean_versions_from_direct_callers(self) -> None:
        plan = self.service.plan_work(self.command(idempotency_key="bool-version"))
        item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=?",
            (plan.workflow_run_id,),
        )[0]
        invalid_record = self.record_command(
            plan, item, transition="start", expected_state_version=True,
            idempotency_key="bool-record",
        )
        invalid_gate = EvaluateGate(
            self.context, plan.workflow_run_id, item["phase_id"], True, True,
            self.local_evidence_digest(()), (), "bool-gate", "correlation-bool-gate",
        )

        with self.assertRaises(LocalObservationPolicyError):
            self.service.record_work_event(invalid_record)
        with self.assertRaises(LocalObservationPolicyError):
            self.service.evaluate_gate(invalid_gate)

    def test_local_gate_replay_returns_original_result_after_later_evidence_changes(self) -> None:
        self.write_phased_profile()
        plan = self.service.plan_work(self.command(
            objective="Design and verify the API",
            idempotency_key="gate-replay-stable",
            requested_work_mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        ))
        item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? AND item_order=0",
            (plan.workflow_run_id,),
        )[0]
        self.service.record_work_event(self.record_command(
            plan, item, transition="start", expected_state_version=1,
            idempotency_key="gate-replay-start",
        ))
        self.service.record_work_event(self.record_command(
            plan, item, transition="submit", expected_state_version=2,
            idempotency_key="gate-replay-empty-submit",
        ))
        original_command = self.gate_command(
            plan, item, expected_state_version=3,
            expected_evidence_digest=self.local_evidence_digest(()),
            idempotency_key="gate-replay-original",
        )
        original = self.service.evaluate_gate(original_command)
        self.assertFalse(original.passed)
        self.service.record_work_event(self.record_command(
            plan, item, transition="pause", expected_state_version=4,
            idempotency_key="gate-replay-pause",
        ))
        self.service.record_work_event(self.record_command(
            plan, item, transition="resume", expected_state_version=5,
            idempotency_key="gate-replay-resume",
        ))
        self.service.record_work_event(self.record_command(
            plan, item, transition="submit", check_ids=("contract-ready",),
            expected_state_version=6, idempotency_key="gate-replay-checked-submit",
        ))
        passed = self.service.evaluate_gate(self.gate_command(
            plan, item, expected_state_version=7,
            expected_evidence_digest=self.local_evidence_digest(("contract-ready",)),
            idempotency_key="gate-replay-pass",
        ))
        self.assertTrue(passed.passed)

        replay = self.service.evaluate_gate(original_command)

        self.assertTrue(replay.replayed)
        self.assertFalse(replay.passed)
        self.assertEqual(original.failures, replay.failures)
        self.assertEqual(original.evidence_digest, replay.evidence_digest)
        self.assertEqual(original.resulting_state_version, replay.resulting_state_version)

    def test_projected_second_phase_can_start_only_after_persisted_dependency_completion(self) -> None:
        self.write_phased_profile()
        plan = self.service.plan_work(self.command(
            objective="Design and verify the API",
            idempotency_key="two-phase-local-loop",
            requested_work_mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        ))
        items = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? ORDER BY item_order",
            (plan.workflow_run_id,),
        )
        first, second = items
        with self.assertRaises(LocalObservationPolicyError):
            self.service.record_work_event(self.record_command(
                plan, second, transition="start", expected_state_version=1,
                idempotency_key="second-premature-start",
            ))

        self.service.record_work_event(self.record_command(
            plan, first, transition="start", expected_state_version=1,
            idempotency_key="first-start-for-second",
        ))
        self.service.record_work_event(self.record_command(
            plan, first, transition="submit", check_ids=("contract-ready",),
            expected_state_version=2, idempotency_key="first-submit-for-second",
        ))
        self.service.evaluate_gate(self.gate_command(
            plan, first, expected_state_version=3,
            expected_evidence_digest=self.local_evidence_digest(("contract-ready",)),
            idempotency_key="first-gate-for-second",
        ))

        projected = self.service.get_next_work(self.query(plan.workflow_run_id))
        self.assertEqual(second["work_item_id"], projected.work_item.work_item_id)
        self.assertEqual("ready", projected.work_item.status)
        self.assertEqual("pending", self.rows(
            "SELECT status FROM local_work_items WHERE work_item_id=?",
            (second["work_item_id"],),
        )[0]["status"])

        started = self.service.record_work_event(self.record_command(
            plan, second, transition="start", expected_state_version=1,
            idempotency_key="second-start-after-dependency",
        ))
        self.assertEqual(2, started.resulting_state_version)
        transition = self.rows(
            "SELECT * FROM local_work_transitions WHERE work_item_id=? "
            "AND transition_kind='start'",
            (second["work_item_id"],),
        )[0]
        self.assertEqual("pending", transition["from_status"])
        self.assertEqual("active", transition["to_status"])
        self.assertEqual(
            [first["work_item_id"]],
            json.loads(transition["observation_json"])["satisfied_dependency_ids"],
        )
        self.service.record_work_event(self.record_command(
            plan, second, transition="submit", check_ids=("tests-passed",),
            expected_state_version=2, idempotency_key="second-submit-after-dependency",
        ))
        result = self.service.evaluate_gate(self.gate_command(
            plan, second, expected_state_version=3,
            expected_evidence_digest=self.local_evidence_digest(("tests-passed",)),
            idempotency_key="second-gate-after-dependency",
        ))
        self.assertTrue(result.passed)
        self.assertEqual("completed", self.rows(
            "SELECT status FROM local_work_items WHERE work_item_id=?",
            (second["work_item_id"],),
        )[0]["status"])

    def test_pending_start_rejects_cross_graph_dependency_and_boundary_items(self) -> None:
        self.write_phased_profile()
        first_plan = self.service.plan_work(self.command(
            objective="Design and verify the API", idempotency_key="cross-graph-first",
            requested_work_mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        ))
        second_plan = self.service.plan_work(self.command(
            objective="Design and verify the API", idempotency_key="cross-graph-second",
            requested_work_mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        ))
        first_pending = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? AND item_order=1",
            (first_plan.workflow_run_id,),
        )[0]
        foreign_dependency = self.rows(
            "SELECT work_item_id FROM local_work_items WHERE workflow_run_id=? "
            "AND item_order=0",
            (second_plan.workflow_run_id,),
        )[0]["work_item_id"]
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                "UPDATE local_work_items SET dependency_ids_json=? WHERE work_item_id=?",
                (canonical_json([foreign_dependency]), first_pending["work_item_id"]),
            )
            connection.commit()
        with self.assertRaisesRegex(
            LocalWorkGraphCorruption,
            "local-work-graph-corruption: item-state",
        ):
            self.service.record_work_event(self.record_command(
                first_plan, first_pending, transition="start", expected_state_version=1,
                idempotency_key="cross-graph-pending-start",
            ))

        boundary_plan = self.service.plan_work(self.command(
            objective="Design then implement", idempotency_key="boundary-start",
            requested_work_mode="phased",
        ))
        boundary = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=?",
            (boundary_plan.workflow_run_id,),
        )[0]
        with self.assertRaises(LocalObservationPolicyError):
            self.service.record_work_event(self.record_command(
                boundary_plan, boundary, transition="start", expected_state_version=1,
                idempotency_key="decomposition-boundary-start",
            ))

        native_plan = self.service.plan_work(self.command(
            objective="Continue native Goal", idempotency_key="native-boundary-start",
            requested_work_mode="managed-goal", goal_binding_id="goal-boundary-start",
        ))
        native_boundary = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=?",
            (native_plan.workflow_run_id,),
        )[0]
        with self.assertRaises(CapabilityUnavailable):
            self.service.record_work_event(self.record_command(
                native_plan, native_boundary, transition="start",
                expected_state_version=1, idempotency_key="native-item-start",
            ))

    def test_local_gate_rejects_stale_bool_and_recomputed_plan_revision(self) -> None:
        self.write_phased_profile()
        command = self.command(
            objective="Design and verify the API",
            idempotency_key="gate-plan-revision",
            requested_work_mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        )
        plan = self.service.plan_work(command)
        item = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? AND item_order=0",
            (plan.workflow_run_id,),
        )[0]
        self.service.record_work_event(self.record_command(
            plan, item, transition="start", expected_state_version=1,
            idempotency_key="revision-start",
        ))
        self.service.record_work_event(self.record_command(
            plan, item, transition="submit", check_ids=("contract-ready",),
            expected_state_version=2, idempotency_key="revision-submit",
        ))
        digest = self.local_evidence_digest(("contract-ready",))
        with self.assertRaises(LocalObservationPolicyError):
            self.service.evaluate_gate(EvaluateGate(
                self.context, plan.workflow_run_id, item["phase_id"], 3, True,
                digest, (), "revision-bool", "correlation-revision-bool",
            ))
        with self.assertRaises(ConcurrencyConflict):
            self.service.evaluate_gate(EvaluateGate(
                self.context, plan.workflow_run_id, item["phase_id"], 3, 2,
                digest, (), "revision-stale", "correlation-revision-stale",
            ))
        original_command = self.gate_command(
            plan, item, expected_state_version=3,
            expected_evidence_digest=digest, idempotency_key="revision-gate",
        )
        original = self.service.evaluate_gate(original_command)
        replay = self.service.evaluate_gate(original_command)
        self.assertEqual(original, replay.__class__(
            replay.status, replay.passed, replay.failures, replay.evidence_digest,
            replay.resulting_state_version, False,
        ))
        self.assertTrue(replay.replayed)
        with self.assertRaises(IdempotencyConflict):
            self.service.evaluate_gate(EvaluateGate(
                self.context, plan.workflow_run_id, item["phase_id"], 4, 1,
                digest, (), "revision-gate", "correlation-revision-collision",
            ))

        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            transition = connection.execute(
                "SELECT * FROM local_work_transitions WHERE work_item_id=? "
                "AND transition_kind='gate-pass'",
                (item["work_item_id"],),
            ).fetchone()
            document = json.loads(transition["observation_json"])
            document["expected_plan_revision"] = 2
            forged_digest = local_transition_request_digest(
                session_id=transition["session_id"],
                actor=transition["actor"],
                workflow_run_id=transition["workflow_run_id"],
                work_item_id=transition["work_item_id"],
                transition_kind=transition["transition_kind"],
                from_status=transition["from_status"],
                to_status=transition["to_status"],
                expected_state_version=transition["expected_state_version"],
                resulting_state_version=transition["resulting_state_version"],
                observation_document=document,
            )
            connection.execute("DROP TRIGGER local_work_transitions_no_update")
            connection.execute(
                "UPDATE local_work_transitions SET observation_json=?,request_digest=? "
                "WHERE transition_id=?",
                (canonical_json(document), forged_digest, transition["transition_id"]),
            )
            connection.commit()

        with self.assertRaisesRegex(
            LocalWorkGraphCorruption,
            "local-work-graph-corruption: gate-plan-revision",
        ):
            self.service.plan_work(command)


if __name__ == "__main__":
    unittest.main()
