from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities import CAPABILITY_SCHEMA_REGISTRY
from workflow_skill_router.capabilities.drift import decode_drift, encode_drift
from workflow_skill_router.capabilities.models import CapabilityDrift, DriftKind
from workflow_skill_router.schemas.errors import SchemaRegistryError


DRIFT = CapabilityDrift(
    drift_id="sha256:" + "d" * 64,
    previous_snapshot_id="sha256:" + "1" * 64,
    current_snapshot_id="sha256:" + "2" * 64,
    capability_id="skill:filesystem/demo",
    kind=DriftKind.INSTRUCTION_CONTENT,
    changed_fields=("installer_content_digest",),
    before_fingerprint="sha256:" + "3" * 64,
    after_fingerprint="sha256:" + "4" * 64,
    detected_at="2026-07-15T00:00:00Z",
)


class CapabilityDriftCodecTests(unittest.TestCase):
    def test_drift_round_trips_through_registered_versioned_envelope(self) -> None:
        envelope = encode_drift(DRIFT)
        self.assertEqual("workflow-skill-router/capability-drift", envelope.schema_id)
        self.assertEqual(DRIFT, decode_drift(envelope.to_dict()))
        self.assertEqual(DRIFT, CAPABILITY_SCHEMA_REGISTRY.decode(envelope.to_dict()))

    def test_drift_decoder_rejects_unknown_fields(self) -> None:
        document = encode_drift(DRIFT).to_dict()
        document["payload"]["runtime_fingerprint"] = "client-forged"
        with self.assertRaisesRegex(SchemaRegistryError, "unknown field"):
            CAPABILITY_SCHEMA_REGISTRY.decode(document)

    def test_drift_decoder_rejects_missing_fields(self) -> None:
        document = encode_drift(DRIFT).to_dict()
        del document["payload"]["current_snapshot_id"]
        with self.assertRaisesRegex(SchemaRegistryError, "missing field"):
            CAPABILITY_SCHEMA_REGISTRY.decode(document)


if __name__ == "__main__":
    unittest.main()
