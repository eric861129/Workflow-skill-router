from pathlib import Path
from contextlib import closing
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.local_control import LocalControlPlaneService
from workflow_skill_router.persistence.migrator import iter_complete_statements
from workflow_skill_router.persistence.sqlite_store import IdempotencyConflict
from workflow_skill_router.schemas.artifacts import canonical_json
from workflow_skill_router.service_models import (
    PlanWork,
    RequestContext,
    RoutingContextInput,
    RouterStatusQuery,
)


class LocalControlPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "router.db"
        self.service = LocalControlPlaneService(self.database)
        self.context = RequestContext("session-1", "developer", "policy-1")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def command(
        self,
        *,
        objective: str = "修正小型文件問題",
        explicit_skill_ids: tuple[str, ...] = (),
        explicit_semantics: str | None = None,
        idempotency_key: str = "plan-1",
        requested_work_mode: str | None = "single",
        goal_binding_id: str | None = None,
        routing_context: RoutingContextInput = RoutingContextInput(),
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
            correlation_id="correlation-1",
            routing_context=routing_context,
        )

    def test_auto_plan_persists_without_auxiliary_skill_prompt(self) -> None:
        result = self.service.plan_work(self.command())

        self.assertEqual("planned-local-control", result.status)
        self.assertEqual("auto", result.selection_mode)
        self.assertFalse(result.support_consent_required)
        self.assertEqual("single", result.routing_envelope)
        self.assertEqual("mcp-local-control-plane", result.runtime_mode)
        self.assertEqual("caller-work-mode-hint", result.classification.source)
        self.assertEqual(
            "deterministic-objective-v1",
            result.classification.classifier_revision,
        )
        self.assertNotIn("修正小型文件問題", self.database.read_text("utf-8", errors="ignore"))

        with closing(sqlite3.connect(self.database)) as connection:
            row = connection.execute(
                "SELECT objective_digest, explicit_skill_ids_json "
                "FROM local_control_plans WHERE workflow_run_id=?",
                (result.workflow_run_id,),
            ).fetchone()
        self.assertTrue(row[0].startswith("sha256:"))
        self.assertEqual("[]", row[1])

    def test_explicit_skill_lock_does_not_prompt_without_a_support_proposal(self) -> None:
        result = self.service.plan_work(self.command(
            explicit_skill_ids=("skill:skill-creator",),
            explicit_semantics="use",
        ))

        self.assertEqual("explicit-locked", result.selection_mode)
        self.assertFalse(result.support_consent_required)
        self.assertEqual(("skill:skill-creator",), result.planned_skill_ids)

    def test_phased_auto_plan_does_not_prompt_for_router_selected_support(self) -> None:
        result = self.service.plan_work(self.command(
            objective="先實作 API，再執行整合驗證",
            requested_work_mode="phased",
        ))

        self.assertEqual("phased", result.routing_envelope)
        self.assertEqual("auto", result.selection_mode)
        self.assertFalse(result.support_consent_required)

    def test_deterministic_analyzer_routes_new_multistage_plan(self) -> None:
        result = self.service.plan_work(self.command(
            objective="先規劃 API，再實作並驗證",
            requested_work_mode=None,
            idempotency_key="analyzer-plan",
        ))

        self.assertEqual("phased", result.routing_envelope)
        self.assertEqual("deterministic-analyzer", result.classification.source)
        self.assertEqual("high", result.classification.confidence)
        self.assertEqual(
            "deterministic-objective-v1",
            result.classification.classifier_revision,
        )
        self.assertEqual(
            ("multi-stage-sequence",),
            result.classification.reason_codes,
        )

    def test_native_goal_binding_precedes_hint_and_analyzer(self) -> None:
        result = self.service.plan_work(self.command(
            objective="先規劃跨儲存庫工作，再實作並驗證",
            requested_work_mode="single",
            goal_binding_id="goal-native-precedence",
            idempotency_key="native-precedence",
        ))

        self.assertEqual("managed-goal", result.routing_envelope)
        self.assertEqual("native-goal-binding", result.classification.source)

    def test_caller_work_mode_hint_precedes_analyzer(self) -> None:
        result = self.service.plan_work(self.command(
            objective="先規劃 API，再實作並驗證",
            requested_work_mode="single",
            idempotency_key="caller-precedence",
        ))

        self.assertEqual("single", result.routing_envelope)
        self.assertEqual("caller-work-mode-hint", result.classification.source)

    def test_builtin_single_fallback_is_explicit(self) -> None:
        result = self.service.plan_work(self.command(
            objective="修正登入頁空白",
            requested_work_mode=None,
            idempotency_key="builtin-fallback",
        ))

        self.assertEqual("single", result.routing_envelope)
        self.assertEqual("builtin-fallback", result.classification.source)
        self.assertEqual(("single-default",), result.classification.reason_codes)

    def test_personal_profile_routes_only_the_current_phase_without_consent(self) -> None:
        profile_dir = self.database.parent / "profiles/personal"
        profile_dir.mkdir(parents=True)
        (profile_dir / "api.json").write_text(json.dumps({
            "schema_id": "workflow-skill-router/routing-profile",
            "schema_version": "1.0.0",
            "artifact_kind": "routing-profile",
            "profile_id": "personal:api",
            "scope": "personal",
            "enabled": True,
            "rules": [{
                "rule_id": "api",
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
        }, ensure_ascii=False), encoding="utf-8")

        result = self.service.plan_work(self.command(
            objective="交付 API 並完成測試",
            requested_work_mode="phased",
            idempotency_key="profile-plan",
            routing_context=RoutingContextInput(
                workspace_root=None,
                domains=("api",),
                tags=(),
                current_phase_id="verify",
            ),
        ))

        self.assertEqual("personal-profile", result.route_source)
        self.assertEqual(("personal:api",), result.routing_profile_ids)
        self.assertEqual("api", result.matched_profile_rule_id)
        self.assertEqual(
            ("skill:qa-test-planner", "skill:playwright"),
            result.planned_skill_ids,
        )
        self.assertEqual("verify", result.planned_skill_tree[1].phase_id)
        self.assertEqual("intended-unverified", result.activation_status)
        self.assertFalse(result.support_consent_required)

    def test_profile_can_change_unlocked_envelope_and_preserves_analyzer_trace(self) -> None:
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
                    "objective_keywords": ["交付"],
                    "domains": [],
                    "tags": [],
                    "work_modes": ["single"],
                },
                "route": {
                    "work_mode": "phased",
                    "skill_tree": [{
                        "phase_id": "delivery",
                        "primary_skill_id": "skill:delivery",
                        "support_skill_ids": [],
                        "exit_gate": "delivered",
                    }],
                },
            }],
        }, ensure_ascii=False), encoding="utf-8")

        result = self.service.plan_work(self.command(
            objective="交付變更",
            requested_work_mode=None,
            idempotency_key="profile-classification",
        ))

        self.assertEqual("phased", result.routing_envelope)
        self.assertEqual("profile-route", result.classification.source)
        self.assertEqual(("single-default",), result.classification.reason_codes)
        self.assertEqual(("skill:delivery",), result.planned_skill_ids)

    def test_explicit_skill_lock_overrides_workspace_and_personal_profiles(self) -> None:
        workspace = self.database.parent / "workspace"
        profile_path = workspace / ".codex/workflow-skill-router.json"
        profile_path.parent.mkdir(parents=True)
        profile_path.write_text(json.dumps({
            "schema_id": "workflow-skill-router/routing-profile",
            "schema_version": "1.0.0",
            "artifact_kind": "routing-profile",
            "profile_id": "workspace:override",
            "scope": "workspace",
            "enabled": True,
            "rules": [{
                "rule_id": "always",
                "priority": 1000,
                "match": {
                    "objective_keywords": [], "domains": [], "tags": [], "work_modes": []
                },
                "route": {
                    "work_mode": "single",
                    "skill_tree": [{
                        "phase_id": "work",
                        "primary_skill_id": "skill:profile-choice",
                        "support_skill_ids": ["skill:profile-support"],
                        "exit_gate": "done",
                    }],
                },
            }],
        }), encoding="utf-8")

        result = self.service.plan_work(self.command(
            explicit_skill_ids=("skill:user-choice",),
            explicit_semantics="use",
            idempotency_key="explicit-over-profile",
            routing_context=RoutingContextInput(
                workspace_root=str(workspace), domains=(), tags=(), current_phase_id=None
            ),
        ))

        self.assertEqual("user-explicit", result.route_source)
        self.assertEqual(("skill:user-choice",), result.planned_skill_ids)
        self.assertEqual((), result.routing_profile_ids)
        self.assertFalse(result.support_consent_required)

    def test_routing_context_rejects_noncanonical_match_identifiers(self) -> None:
        with self.assertRaisesRegex(ValueError, "routing_context.domains"):
            self.service.plan_work(self.command(
                idempotency_key="invalid-domain",
                routing_context=RoutingContextInput(domains=("API Delivery",)),
            ))

    def test_managed_goal_preserves_native_binding_without_mutating_host_goal(self) -> None:
        result = self.service.plan_work(self.command(
            objective="繼續大型 Goal 並拆分工作項目",
            requested_work_mode="managed-goal",
            goal_binding_id="goal-native-1",
        ))
        status = self.service.get_router_status(RouterStatusQuery(
            context=self.context,
            goal_binding_id="goal-native-1",
            workflow_run_id=result.workflow_run_id,
        ))

        self.assertEqual("managed-goal", result.routing_envelope)
        self.assertEqual("goal-native-1", status.goal_binding_id)
        self.assertFalse(status.host_goal_mutated)

    def test_only_semantics_forbids_support_without_prompt(self) -> None:
        result = self.service.plan_work(self.command(
            explicit_skill_ids=("skill:skill-creator",),
            explicit_semantics="only",
        ))

        self.assertEqual("explicit-locked", result.selection_mode)
        self.assertFalse(result.support_consent_required)

    def test_idempotent_replay_returns_same_plan_and_conflict_is_rejected(self) -> None:
        first = self.service.plan_work(self.command())
        replay = self.service.plan_work(self.command())
        self.assertEqual(first, replay)

        with self.assertRaises(IdempotencyConflict):
            self.service.plan_work(self.command(objective="不同任務"))

    def test_idempotent_replay_keeps_persisted_classifier_revision(self) -> None:
        command = self.command(
            requested_work_mode=None,
            idempotency_key="classifier-replay",
        )
        first = self.service.plan_work(command)

        with patch(
            "workflow_skill_router.routing.task_signal_analyzer._CLASSIFIER_REVISION",
            "deterministic-objective-v2",
        ):
            replay = self.service.plan_work(command)
            new_plan = self.service.plan_work(self.command(
                requested_work_mode=None,
                idempotency_key="classifier-new-plan",
            ))

        self.assertEqual("deterministic-objective-v1", first.classification.classifier_revision)
        self.assertEqual(first.classification, replay.classification)
        self.assertEqual(
            "deterministic-objective-v2",
            new_plan.classification.classifier_revision,
        )

    def test_beta_1_explicit_plan_migrates_without_losing_intent_or_replay(self) -> None:
        self.directory.cleanup()
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "router.db"
        migration_dir = (
            Path(__file__).resolve().parents[2]
            / "src/workflow_skill_router/persistence/migrations"
        )
        with closing(sqlite3.connect(self.database)) as connection:
            for migration in sorted(migration_dir.glob("000[1-4]_*.sql")):
                for statement in iter_complete_statements(migration.read_text(encoding="utf-8")):
                    connection.execute(statement)
                checksum = hashlib.sha256(migration.read_bytes()).hexdigest()
                connection.execute(
                    "INSERT INTO schema_migrations(version, checksum, applied_at) VALUES (?, ?, ?)",
                    (migration.name.split("_", 1)[0], checksum, "2026-07-19T00:00:00+00:00"),
                )

            objective = "Deliver API contract"
            objective_digest = "sha256:" + hashlib.sha256(objective.encode()).hexdigest()
            legacy_request = {
                "actor": "developer",
                "correlation_id": "correlation-1",
                "explicit_semantics": "preferred-primary",
                "explicit_skill_ids": ["skill:api-designer"],
                "goal_binding_id": None,
                "objective_digest": objective_digest,
                "requested_work_mode": "single",
                "runtime_policy_snapshot_id": "policy-1",
                "session_id": "session-1",
            }
            request_digest = "sha256:" + hashlib.sha256(
                canonical_json(legacy_request).encode()
            ).hexdigest()
            connection.execute(
                "INSERT INTO local_control_plans("
                "plan_id,session_id,actor,runtime_policy_snapshot_id,idempotency_key,"
                "request_digest,workflow_run_id,work_graph_id,goal_binding_id,objective_digest,"
                "routing_envelope,selection_mode,support_policy,support_consent_required,"
                "explicit_skill_ids_json,explicit_semantics,created_work_items,state_version,created_at"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "plan:legacy", "session-1", "developer", "policy-1", "legacy-plan",
                    request_digest, "workflow:legacy", "work-graph:legacy", None,
                    objective_digest, "single", "explicit-locked", "ask", 0,
                    '["skill:api-designer"]', "use", 1, 1,
                    "2026-07-19T00:00:00+00:00",
                ),
            )
            connection.commit()

        self.service = LocalControlPlaneService(self.database)
        command = self.command(
            objective=objective,
            explicit_skill_ids=("skill:api-designer",),
            explicit_semantics="use",
            idempotency_key="legacy-plan",
        )
        replay = self.service.plan_work(command)

        self.assertEqual("user-explicit", replay.route_source)
        self.assertEqual(("skill:api-designer",), replay.planned_skill_ids)
        self.assertEqual("intended-unverified", replay.activation_status)
        self.assertEqual("legacy-replay", replay.classification.source)
        self.assertEqual("low", replay.classification.confidence)
        self.assertEqual("pre-beta.4", replay.classification.classifier_revision)
        self.assertEqual((), replay.classification.reason_codes)
        with self.assertRaises(IdempotencyConflict):
            self.service.plan_work(self.command(
                objective=objective,
                explicit_skill_ids=("skill:api-designer",),
                explicit_semantics="use",
                idempotency_key="legacy-plan",
                routing_context=RoutingContextInput(tags=("changed",)),
            ))

    def test_status_reads_persisted_plan_count(self) -> None:
        planned = self.service.plan_work(self.command())
        status = self.service.get_router_status(RouterStatusQuery(
            context=self.context,
            goal_binding_id=None,
            workflow_run_id=planned.workflow_run_id,
        ))

        self.assertEqual(1, status.created_work_items)
        self.assertEqual(planned.workflow_run_id, status.workflow_run_id)
        self.assertFalse(status.host_goal_mutated)


if __name__ == "__main__":
    unittest.main()
