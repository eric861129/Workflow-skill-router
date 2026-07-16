from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.persistence.migrator import migrate
from workflow_skill_router.persistence.projections import ProjectionRunner, WorkflowProjection
from workflow_skill_router.persistence.sqlite_store import SQLiteEventStore
from workflow_skill_router.workflow.events import EventDraft


class Clock:
    def now_utc(self):
        return datetime(2026, 7, 15, tzinfo=timezone.utc)


class Ids:
    value = 0
    def new_event_id(self):
        self.value += 1
        return f"event-{self.value}"


class ProjectionTests(unittest.TestCase):
    def test_rebuild_produces_same_workflow_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "router.db"
            migrate(database)
            store = SQLiteEventStore(database, clock=Clock(), id_factory=Ids())
            store.append("workflow", "wf-1", [EventDraft(
                event_type="WORKFLOW_CREATED", actor="orchestrator", plan_revision=1,
                inline_payload={
                    "objective": "完成 V2", "objective_digest": "sha256:o",
                    "envelope": "phased", "status": "draft",
                    "capability_snapshot_id": "snap-1", "scope": [], "constraints": [],
                },
                payload_ref=None, correlation_id="corr-1", causation_id=None,
                workflow_run_id="wf-1",
            )], 0, "create-1")
            runner = ProjectionRunner(database)
            runner.catch_up()
            before = WorkflowProjection(database).get_workflow("wf-1")
            runner.rebuild()
            after = WorkflowProjection(database).get_workflow("wf-1")
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
