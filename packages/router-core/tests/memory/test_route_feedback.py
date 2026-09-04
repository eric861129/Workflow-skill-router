from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from workflow_skill_router.memory import (
    MemoryCommandConflict,
    RecordRouteFeedbackCommand,
    RouteFeedbackError,
    WorkflowMemoryService,
    decode_route_feedback,
)

from memory.m1c_fixture import M1CHistoryFixture, write_feedback_policy


class RouteFeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.fixture = M1CHistoryFixture(self.root)
        self.plan, self.remembered = self.fixture.remember()

    def tearDown(self) -> None:
        self.directory.cleanup()

    def command(self, **changes) -> RecordRouteFeedbackCommand:
        values = {
            "context": self.fixture.memory_context,
            "workflow_run_id": self.plan.workflow_run_id,
            "workspace_root": None,
            "observation_id": self.remembered.observation_id,
            "feedback_type": "accepted",
            "reason_code": "route-useful",
            "correction_dimensions": (),
            "original_route_digest": None,
            "corrected_route_digest": None,
            "free_text": None,
            "idempotency_key": "feedback-command",
            "correlation_id": "correlation-feedback-command",
        }
        values.update(changes)
        return RecordRouteFeedbackCommand(**values)

    def test_records_typed_feedback_once_and_replays_same_command(self) -> None:
        service = WorkflowMemoryService(self.fixture.database, data_dir=self.root)
        first = service.record_route_feedback(self.command())
        replay = service.record_route_feedback(self.command())

        self.assertEqual("recorded", first.status)
        self.assertFalse(first.replayed)
        self.assertEqual(first.feedback_id, replay.feedback_id)
        self.assertTrue(replay.replayed)
        with closing(sqlite3.connect(self.root / "memory/workflow-memory.sqlite3")) as connection:
            self.assertEqual(
                1,
                connection.execute("SELECT COUNT(*) FROM route_feedback_events").fetchone()[0],
            )
            raw = connection.execute(
                "SELECT feedback_json FROM route_feedback_events"
            ).fetchone()[0]
        feedback = decode_route_feedback(json.loads(raw))
        self.assertEqual("accepted", feedback.feedback_type)
        self.assertEqual(self.remembered.observation_id, feedback.observation_id)

    def test_corrected_feedback_requires_bound_route_digests_and_dimensions(self) -> None:
        with self.assertRaisesRegex(RouteFeedbackError, "correction-binding-required"):
            self.command(feedback_type="corrected")

        original = self.remembered.route_signature_digest
        corrected = "sha256:" + "a" * 64
        command = self.command(
            feedback_type="corrected",
            correction_dimensions=("primary-skill",),
            original_route_digest=original,
            corrected_route_digest=corrected,
            reason_code="route-corrected",
            idempotency_key="corrected-feedback",
            correlation_id="correlation-corrected-feedback",
        )
        result = self.fixture.service.record_route_feedback(command)
        self.assertEqual("recorded", result.status)

    def test_free_text_requires_double_opt_in_and_never_enters_public_result(self) -> None:
        with self.assertRaisesRegex(RouteFeedbackError, "free-text-not-authorized"):
            self.fixture.service.record_route_feedback(
                self.command(
                    free_text="private student name",
                    idempotency_key="free-text-denied",
                    correlation_id="correlation-free-text-denied",
                )
            )

        write_feedback_policy(self.root, allow_free_text=True)
        result = self.fixture.service.record_route_feedback(
            self.command(
                free_text="private student name",
                idempotency_key="free-text-allowed",
                correlation_id="correlation-free-text-allowed",
            )
        )
        self.assertEqual("recorded", result.status)
        self.assertNotIn("private student name", json.dumps(result.to_dict()))


    def test_feedback_timestamp_must_be_a_real_utc_instant(self) -> None:
        result = self.fixture.service.record_route_feedback(self.command())
        with closing(sqlite3.connect(self.root / "memory/workflow-memory.sqlite3")) as connection:
            raw = connection.execute(
                "SELECT feedback_json FROM route_feedback_events WHERE feedback_id=?",
                (result.feedback_id,),
            ).fetchone()[0]
        document = json.loads(raw)
        document["recorded_at"] = "not-a-real-timeZ"
        with self.assertRaisesRegex(RouteFeedbackError, "invalid-feedback-recorded-at"):
            decode_route_feedback(document)

    def test_reason_code_requires_policy_authorization(self) -> None:
        policy_path = self.root / "config/workflow-memory.json"
        document = json.loads(policy_path.read_text(encoding="utf-8"))
        document["features"] = {
            "route_feedback": {
                "allow_standard_reason_codes": False,
            }
        }
        policy_path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaisesRegex(RouteFeedbackError, "reason-code-not-authorized"):
            self.fixture.service.record_route_feedback(
                self.command(
                    idempotency_key="reason-code-denied",
                    correlation_id="correlation-reason-code-denied",
                )
            )

    def test_context_and_idempotency_are_fail_closed(self) -> None:
        service = WorkflowMemoryService(self.fixture.database, data_dir=self.root)
        service.record_route_feedback(self.command())
        with self.assertRaisesRegex(MemoryCommandConflict, "memory-idempotency-conflict"):
            service.record_route_feedback(self.command(reason_code="different-reason"))

        with self.assertRaisesRegex(RouteFeedbackError, "feedback-workflow-context-mismatch"):
            service.record_route_feedback(
                self.command(
                    workflow_run_id="workflow:not-owned",
                    idempotency_key="wrong-workflow",
                    correlation_id="correlation-wrong-workflow",
                )
            )

    def test_feedback_contract_rejects_unknown_fields_and_tampering(self) -> None:
        result = self.fixture.service.record_route_feedback(self.command())
        with closing(sqlite3.connect(self.root / "memory/workflow-memory.sqlite3")) as connection:
            raw = connection.execute(
                "SELECT feedback_json FROM route_feedback_events WHERE feedback_id=?",
                (result.feedback_id,),
            ).fetchone()[0]
        document = json.loads(raw)
        document["reason_code"] = "tampered"
        with self.assertRaisesRegex(RouteFeedbackError, "feedback-digest-mismatch"):
            decode_route_feedback(document)
        document = json.loads(raw)
        document["metadata_json"] = "{}"
        with self.assertRaisesRegex(RouteFeedbackError, "invalid-feedback-fields"):
            decode_route_feedback(document)


if __name__ == "__main__":
    unittest.main()
