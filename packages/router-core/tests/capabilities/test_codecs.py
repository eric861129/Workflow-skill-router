from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities import CAPABILITY_SCHEMA_REGISTRY
from workflow_skill_router.capabilities.codecs import (
    decode_capability,
    encode_capability,
    encode_snapshot,
)
from workflow_skill_router.capabilities.models import (
    AuthState,
    Availability,
    AvailabilityResult,
    Capability,
    CapabilityKind,
    CapabilitySnapshot,
    Compatibility,
    Eligibility,
    Exposure,
    FieldObservation,
    Freshness,
    Presence,
    ProvenanceRecord,
    Requirement,
    RiskAvailability,
    RiskLevel,
    SideEffect,
    TrustLevel,
)
from workflow_skill_router.schemas.errors import SchemaRegistryError


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


def observed(value):
    return FieldObservation(value, "agent-runtime", NOW, TrustLevel.RUNTIME, "observed")


def risk_availability() -> tuple[RiskAvailability, ...]:
    return tuple(
        RiskAvailability(risk, AvailabilityResult(Availability.AVAILABLE, ()))
        for risk in RiskLevel
    )


CAPABILITY = Capability(
    canonical_id="skill:local/demo",
    display_name="繁體中文能力",
    kind=CapabilityKind.SKILL,
    source="local-installer",
    presence=observed(Presence.PRESENT),
    exposure=observed(Exposure.EXPOSED),
    auth_state=observed(AuthState.NOT_REQUIRED),
    eligibility=observed(Eligibility.ELIGIBLE),
    compatibility=observed(Compatibility.COMPATIBLE),
    freshness=Freshness(NOW, NOW + timedelta(minutes=5), False),
    description="協助開發者選擇正確技能",
    domains=("workflow",),
    stages=("planning",),
    side_effect=SideEffect.NONE,
    requirements=(Requirement("host:filesystem", CapabilityKind.HOST_TOOL, "read-metadata", True),),
    aliases=("router",),
    conflicts=(),
    context_cost=3,
    capability_fingerprint="sha256:capability",
    installer_content_digest=observed("sha256:installer-content"),
    availability_by_risk=risk_availability(),
    provenance=(
        ProvenanceRecord(
            "agent-runtime",
            "runtime-contract",
            "sha256:source",
            "sha256:observation",
            TrustLevel.RUNTIME,
            "observed",
        ),
    ),
)

SNAPSHOT = CapabilitySnapshot(
    snapshot_id="snapshot:demo",
    schema_version="2.0.0-alpha.1",
    created_at="2026-07-15T00:00:00Z",
    runtime_fingerprint="sha256:runtime",
    provider_revisions=("agent-runtime@1",),
    capabilities=(CAPABILITY,),
    drift_from_snapshot_id=None,
    freshness=Freshness(NOW, NOW + timedelta(minutes=5), False),
)


class CapabilityCodecTests(unittest.TestCase):
    def test_nested_snapshot_round_trips_through_default_registry(self) -> None:
        envelope = encode_snapshot(SNAPSHOT)
        decoded = CAPABILITY_SCHEMA_REGISTRY.decode(envelope.to_dict())
        self.assertEqual(SNAPSHOT, decoded)

    def test_capability_round_trips_through_strict_decoder(self) -> None:
        envelope = encode_capability(CAPABILITY)
        self.assertEqual(CAPABILITY, decode_capability(envelope.to_dict()))
        self.assertEqual(CAPABILITY, CAPABILITY_SCHEMA_REGISTRY.decode(envelope.to_dict()))

    def test_unknown_nested_capability_field_is_rejected(self) -> None:
        document = encode_snapshot(SNAPSHOT).to_dict()
        document["payload"]["capabilities"][0]["client_trusted"] = True
        with self.assertRaisesRegex(SchemaRegistryError, "unknown field"):
            CAPABILITY_SCHEMA_REGISTRY.decode(document)

    def test_missing_nested_freshness_field_is_rejected(self) -> None:
        document = encode_capability(CAPABILITY).to_dict()
        del document["payload"]["freshness"]["expires_at"]
        with self.assertRaisesRegex(SchemaRegistryError, "missing field"):
            CAPABILITY_SCHEMA_REGISTRY.decode(document)

    def test_risk_availability_requires_exact_r0_to_r3_order(self) -> None:
        document = encode_capability(CAPABILITY).to_dict()
        document["payload"]["availability_by_risk"].reverse()
        with self.assertRaisesRegex(SchemaRegistryError, "risk order"):
            CAPABILITY_SCHEMA_REGISTRY.decode(document)

    def test_encoder_rejects_snapshot_from_another_schema_version(self) -> None:
        with self.assertRaisesRegex(SchemaRegistryError, "schema_version"):
            encode_snapshot(replace(SNAPSHOT, schema_version="2.0.0-alpha.2"))

    def test_nested_identity_values_are_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            CAPABILITY.provenance[0].reason_code = "changed"
        with self.assertRaises(TypeError):
            CAPABILITY.domains[0] = "changed"


if __name__ == "__main__":
    unittest.main()
