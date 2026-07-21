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
from workflow_skill_router.schemas.artifacts import canonical_json
from workflow_skill_router.service_models import (
    NextWorkQuery,
    PlanWork,
    RequestContext,
    RoutingContextInput,
)
from workflow_skill_router.tool_dispatch import ToolDispatcher


class LocalWorkLoopTests(unittest.TestCase):
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
    ) -> PlanWork:
        return PlanWork(
            context=self.context,
            objective=objective,
            goal_binding_id=goal_binding_id,
            requested_work_mode=requested_work_mode,
            explicit_skill_ids=(),
            explicit_semantics=None,
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

    def complete_item_through_storage_seam(
        self,
        workflow_run_id: str,
        item_order: int,
    ) -> None:
        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM local_work_items WHERE workflow_run_id=? AND item_order=?",
                (workflow_run_id, item_order),
            ).fetchone()
            self.assertIsNotNone(row)
            version = int(row["state_version"])
            resulting_version = version + 1
            transition_kind = "test-fixture-complete"
            request_digest = local_transition_request_digest(
                session_id=self.context.session_id,
                actor=self.context.actor,
                workflow_run_id=workflow_run_id,
                work_item_id=row["work_item_id"],
                transition_kind=transition_kind,
                from_status=row["status"],
                to_status="completed",
                expected_state_version=version,
                resulting_state_version=resulting_version,
            )
            connection.execute(
                "INSERT INTO local_work_transitions("
                "transition_id,session_id,workflow_run_id,work_item_id,transition_kind,"
                "from_status,to_status,expected_state_version,resulting_state_version,"
                "idempotency_key,request_digest,actor,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    self.public_id(
                        "work-transition", row["work_item_id"], str(resulting_version)
                    ),
                    self.context.session_id,
                    workflow_run_id,
                    row["work_item_id"],
                    transition_kind,
                    row["status"],
                    "completed",
                    version,
                    resulting_version,
                    self.public_id(
                        "test-complete", workflow_run_id, row["work_item_id"]
                    ),
                    request_digest,
                    self.context.actor,
                    "2026-07-21T00:00:00+00:00",
                ),
            )
            connection.execute(
                "UPDATE local_work_items SET status='completed',state_version=? "
                "WHERE work_item_id=? AND state_version=?",
                (resulting_version, row["work_item_id"], version),
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
        self.complete_item_through_storage_seam(plan.workflow_run_id, 0)

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


if __name__ == "__main__":
    unittest.main()
