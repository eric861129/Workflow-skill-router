"""Runtime capability contracts、strict codecs 與 schema registry。"""

from workflow_skill_router.schemas.registry import SchemaRegistry

from .availability import derive_availability
from .codecs import (
    CAPABILITY_SCHEMA_ID,
    CAPABILITY_SNAPSHOT_SCHEMA_ID,
    SCHEMA_VERSION,
    decode_capability,
    decode_snapshot,
    encode_capability,
    encode_snapshot,
)
from .models import (
    AuthState,
    Availability,
    AvailabilityResult,
    Capability,
    CapabilityDrift,
    CapabilityKind,
    CapabilitySnapshot,
    Compatibility,
    DriftKind,
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


CAPABILITY_SCHEMA_REGISTRY = SchemaRegistry()
CAPABILITY_SCHEMA_REGISTRY.register(
    CAPABILITY_SCHEMA_ID,
    SCHEMA_VERSION,
    "capability",
    decode_capability,
)
CAPABILITY_SCHEMA_REGISTRY.register(
    CAPABILITY_SNAPSHOT_SCHEMA_ID,
    SCHEMA_VERSION,
    "capability-snapshot",
    decode_snapshot,
)

__all__ = [
    "AuthState",
    "Availability",
    "AvailabilityResult",
    "CAPABILITY_SCHEMA_REGISTRY",
    "Capability",
    "CapabilityDrift",
    "CapabilityKind",
    "CapabilitySnapshot",
    "Compatibility",
    "DriftKind",
    "Eligibility",
    "Exposure",
    "FieldObservation",
    "Freshness",
    "Presence",
    "ProvenanceRecord",
    "Requirement",
    "RiskAvailability",
    "RiskLevel",
    "SideEffect",
    "TrustLevel",
    "decode_capability",
    "decode_snapshot",
    "derive_availability",
    "encode_capability",
    "encode_snapshot",
]
