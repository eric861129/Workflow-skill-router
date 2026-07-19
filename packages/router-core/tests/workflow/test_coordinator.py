from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.persistence.migrator import migrate
from workflow_skill_router.persistence.sqlite_store import SQLiteEventStore
from workflow_skill_router.workflow.coordinator import (
    ObservationIntegrityError, RecordObservationCommand, WorkEventContext,
    WorkEventCoordinator, decode_record_observation,
)
from workflow_skill_router.workflow.observations import (
    EvidenceObservation, SideEffectOutcomeObservation,
)


class Clock:
    def now_utc(self): return datetime(2026, 7, 15, tzinfo=timezone.utc)
class Ids:
    value = 0
    def new_event_id(self):
        self.value += 1
        return f"event-{self.value}"
class Contexts:
    def require(self, workflow, phase, version):
        return WorkEventContext(workflow, phase, version, 1, "agent", "cause-1")
class EvidenceVerifier:
    def resolve_and_verify(self, ref, **kwargs):
        return {"evidence_receipt_ref": ref, "verified_status": "passed", "digest": "sha256:e"}
class SideEffects:
    def verify_outcome(self, ref, **kwargs):
        if kwargs["expected_action_digest"] != "sha256:expected":
            raise ObservationIntegrityError("side_effect_receipt_mismatch")
        return {"outcome_receipt_ref": ref, "status": "confirmed-success"}


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        database = Path(self.directory.name) / "router.db"
        migrate(database)
        self.store = SQLiteEventStore(database, clock=Clock(), id_factory=Ids())
        self.coordinator = WorkEventCoordinator(
            self.store, Contexts(), None, EvidenceVerifier(), SideEffects(), None,
        )

    def tearDown(self): self.directory.cleanup()

    def command(self, observation):
        return RecordObservationCommand("wf-1", "phase-1", observation, 0, "record-1", "corr-1")

    def test_decoder_rejects_raw_event_actor_plan_status_and_payload(self) -> None:
        valid = {
            "workflow_run_id": "wf-1", "phase_id": "phase-1",
            "expected_state_version": 0, "idempotency_key": "record-1",
            "correlation_id": "corr-1",
            "observation": {"kind": "evidence", "gate_id": "gate-1",
                            "evidence_kind": "test-result", "evidence_receipt_ref": "evidence-7"},
        }
        for field, value in (
            ("event_type", "PHASE_TRANSITIONED"), ("actor", "client"),
            ("plan_revision", 999), ("status", "completed"), ("payload", {"passed": True}),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "unknown field"):
                decode_record_observation({**valid, field: value})

    def test_side_effect_outcome_requires_original_intent_digest(self) -> None:
        command = self.command(SideEffectOutcomeObservation(
            "intent-1", "sha256:wrong", "host-outcome-7",
        ))
        with self.assertRaisesRegex(ObservationIntegrityError, "side_effect_receipt_mismatch"):
            self.coordinator.record(command)

    def test_evidence_pass_fail_is_derived_from_verified_receipt(self) -> None:
        command = self.command(EvidenceObservation("gate-1", "test-result", "evidence-7"))
        append = self.coordinator.record(command)
        self.assertEqual("EVIDENCE_RECORDED", append.events[0].event_type)
        self.assertEqual("passed", append.events[0].inline_payload["verified_status"])
        self.assertFalse(hasattr(command.observation, "status"))


if __name__ == "__main__": unittest.main()
