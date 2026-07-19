from pathlib import Path
from contextlib import closing
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.local_control import LocalControlPlaneService
from workflow_skill_router.persistence.sqlite_store import IdempotencyConflict
from workflow_skill_router.service_models import (
    PlanWork,
    RequestContext,
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
        )

    def test_auto_plan_persists_without_auxiliary_skill_prompt(self) -> None:
        result = self.service.plan_work(self.command())

        self.assertEqual("planned-local-control", result.status)
        self.assertEqual("auto", result.selection_mode)
        self.assertFalse(result.support_consent_required)
        self.assertEqual("single", result.routing_envelope)
        self.assertEqual("mcp-local-control-plane", result.runtime_mode)
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
