import sqlite3
from contextlib import closing
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.schemas.artifacts import canonical_json_bytes
from workflow_skill_router.persistence.migrator import migrate
from workflow_skill_router.persistence.sqlite_store import (
    ConcurrencyConflict, IdempotencyConflict, SQLiteEventStore,
)
from workflow_skill_router.workflow.events import EventDraft


class FixedClock:
    def __init__(self, value: str) -> None:
        self._value = datetime.fromisoformat(value)

    def now_utc(self) -> datetime:
        return self._value


class SequenceIdFactory:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._next = 0

    def new_event_id(self) -> str:
        self._next += 1
        return f"{self._prefix}-{self._next:04d}"


class SQLiteEventStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "router.db"
        migrate(self.database)
        self.store = SQLiteEventStore(
            self.database,
            clock=FixedClock("2026-07-15T00:00:00+00:00"),
            id_factory=SequenceIdFactory("event"),
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def draft(self, event_type: str = "WORKFLOW_CREATED") -> EventDraft:
        return EventDraft(
            workflow_run_id="wf-1",
            event_type=event_type,
            actor="orchestrator",
            plan_revision=1,
            inline_payload={"objective_digest": "sha256:abc"},
            payload_ref=None,
            correlation_id="corr-1",
            causation_id=None,
        )

    def test_append_assigns_server_event_identity_and_monotonic_version(self) -> None:
        result = self.store.append("workflow", "wf-1", [self.draft()], 0, "create-1")
        self.assertFalse(result.replayed)
        self.assertEqual(1, result.resulting_state_version)
        self.assertEqual((0, 1), (
            result.events[0].state_version_before,
            result.events[0].state_version_after,
        ))
        self.assertTrue(result.events[0].event_id)

    def test_same_idempotency_key_replays_original_receipt(self) -> None:
        first = self.store.append("workflow", "wf-1", [self.draft()], 0, "create-1")
        replay = self.store.append("workflow", "wf-1", [self.draft()], 0, "create-1")
        self.assertTrue(replay.replayed)
        self.assertEqual(first.events[0].event_id, replay.events[0].event_id)
        self.assertEqual(1, len(self.store.read_stream("workflow", "wf-1")))

    def test_fixed_clock_and_id_factory_make_fresh_exports_byte_identical(self) -> None:
        exports = []
        for suffix in ("a", "b"):
            database = Path(self.directory.name) / f"router-{suffix}.db"
            migrate(database)
            store = SQLiteEventStore(
                database,
                clock=FixedClock("2026-07-15T00:00:00+00:00"),
                id_factory=SequenceIdFactory("event"),
            )
            store.append("workflow", "wf-1", [self.draft()], 0, "create-1")
            exports.append(canonical_json_bytes({
                "events": [item.to_dict() for item in store.read_stream("workflow", "wf-1")],
            }))
        self.assertEqual(exports[0], exports[1])

    def test_same_idempotency_key_with_different_command_is_rejected(self) -> None:
        self.store.append("workflow", "wf-1", [self.draft()], 0, "create-1")
        with self.assertRaises(IdempotencyConflict):
            self.store.append(
                "workflow", "wf-1", [self.draft("WORKFLOW_TRANSITIONED")], 0, "create-1",
            )

    def test_stale_expected_version_is_rejected(self) -> None:
        self.store.append("workflow", "wf-1", [self.draft()], 0, "create-1")
        with self.assertRaises(ConcurrencyConflict):
            self.store.append(
                "workflow", "wf-1", [self.draft("WORKFLOW_TRANSITIONED")], 0, "run-1",
            )

    def test_database_rejects_update_or_delete_of_event(self) -> None:
        event = self.store.append("workflow", "wf-1", [self.draft()], 0, "create-1").events[0]
        with closing(sqlite3.connect(self.database)) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE workflow_events SET actor='竄改' WHERE event_id=?",
                    (event.event_id,),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "DELETE FROM workflow_events WHERE event_id=?",
                    (event.event_id,),
                )


if __name__ == "__main__":
    unittest.main()
