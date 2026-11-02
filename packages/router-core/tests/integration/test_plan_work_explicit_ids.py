from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.local_control import LocalControlPlaneService  # noqa: E402
from workflow_skill_router.routing.directives import DirectiveAmbiguityError  # noqa: E402
from workflow_skill_router.service_models import PlanWork, RequestContext  # noqa: E402


class PlanWorkExplicitSkillIdTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "router.db"
        self.service = LocalControlPlaneService(self.database)
        self.context = RequestContext("session-1", "developer", "policy-1")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def command(self, skill_ids: tuple[str, ...], *, key: str = "plan-1") -> PlanWork:
        return PlanWork(
            context=self.context,
            objective="為日期解析器補上回歸測試",
            goal_binding_id=None,
            requested_work_mode=None,
            explicit_skill_ids=skill_ids,
            explicit_semantics="use",
            expected_state_version=0,
            idempotency_key=key,
            correlation_id="correlation-1",
        )

    def plan_rows(self) -> list[tuple[str, str]]:
        with closing(sqlite3.connect(self.database)) as connection:
            return connection.execute(
                "SELECT planned_skill_ids_json, explicit_skill_ids_json FROM local_control_plans"
            ).fetchall()

    def test_bare_skill_name_is_stored_and_read_back_in_canonical_form(self) -> None:
        # Before the fix the bare id was persisted, then rejected on read-back as graph corruption.
        result = self.service.plan_work(self.command(("python-test-writer",)))

        self.assertEqual("planned-local-control", result.status)
        self.assertEqual("explicit-locked", result.selection_mode)
        self.assertEqual(("skill:python-test-writer",), tuple(result.planned_skill_ids))
        self.assertEqual(
            [('["skill:python-test-writer"]', '["skill:python-test-writer"]')],
            self.plan_rows(),
        )
        replay = self.service.plan_work(self.command(("python-test-writer",)))
        self.assertEqual(result.workflow_run_id, replay.workflow_run_id)
        self.assertEqual(("skill:python-test-writer",), tuple(replay.planned_skill_ids))

    def test_non_canonical_id_is_rejected_before_anything_is_persisted(self) -> None:
        with self.assertRaises(DirectiveAmbiguityError) as caught:
            self.service.plan_work(self.command(("Bad Name",)))

        self.assertEqual("explicit-skill-id-not-canonical", caught.exception.reason)
        self.assertEqual([], self.plan_rows())


if __name__ == "__main__":
    unittest.main()
