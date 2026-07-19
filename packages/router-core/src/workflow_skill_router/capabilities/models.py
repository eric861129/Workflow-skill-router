from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar


class CapabilityKind(StrEnum):
    SKILL = "skill"
    MCP_TOOL = "mcp-tool"
    PLUGIN = "plugin"
    APP = "app"
    HOST_TOOL = "host-tool"


class Presence(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    NOT_APPLICABLE = "not-applicable"
    UNKNOWN = "unknown"


class Exposure(StrEnum):
    EXPOSED = "exposed"
    NOT_EXPOSED = "not-exposed"
    UNKNOWN = "unknown"


class AuthState(StrEnum):
    AUTHORIZED = "authorized"
    REQUIRED = "required"
    NOT_REQUIRED = "not-required"
    UNKNOWN = "unknown"


class Eligibility(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"


class Compatibility(StrEnum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


class TrustLevel(StrEnum):
    CACHE = "cache"
    METADATA = "metadata"
    HANDSHAKE = "handshake"
    RUNTIME = "runtime"


class RiskLevel(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"


class Availability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    AUTH_REQUIRED = "auth-required"
    DEGRADED = "degraded"
    STALE = "stale"
    UNKNOWN = "unknown"
    INCOMPATIBLE = "incompatible"


class SideEffect(StrEnum):
    NONE = "none"
    LOCAL = "local"
    REMOTE = "remote"
    PRIVILEGED = "privileged"


class DriftKind(StrEnum):
    ADD = "add"
    REMOVE = "remove"
    RENAME = "rename"
    SEMANTIC_METADATA = "semantic-metadata"
    INSTRUCTION_CONTENT = "instruction-content"
    TOOL_SCHEMA = "tool-schema"
    AUTH = "auth"
    POLICY = "policy"
    RUNTIME_EXPOSURE = "runtime-exposure"


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class FieldObservation(Generic[T]):
    value: T
    provider: str
    observed_at: datetime
    trust_level: TrustLevel
    reason_code: str


@dataclass(frozen=True, slots=True)
class Freshness:
    observed_at: datetime
    expires_at: datetime
    degraded_allowed: bool
    stale: bool = False


@dataclass(frozen=True, slots=True)
class Requirement:
    canonical_id: str
    kind: CapabilityKind
    purpose: str
    trusted: bool


@dataclass(frozen=True, slots=True)
class AvailabilityResult:
    primary: Availability
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RiskAvailability:
    risk: RiskLevel
    result: AvailabilityResult


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    provider_id: str
    source_kind: str
    source_ref_digest: str
    observation_digest: str
    trust_level: TrustLevel
    reason_code: str


@dataclass(frozen=True, slots=True)
class Capability:
    canonical_id: str
    display_name: str
    kind: CapabilityKind
    source: str
    presence: FieldObservation[Presence]
    exposure: FieldObservation[Exposure]
    auth_state: FieldObservation[AuthState]
    eligibility: FieldObservation[Eligibility]
    compatibility: FieldObservation[Compatibility]
    freshness: Freshness
    description: str
    domains: tuple[str, ...]
    stages: tuple[str, ...]
    side_effect: SideEffect
    requirements: tuple[Requirement, ...]
    aliases: tuple[str, ...]
    conflicts: tuple[str, ...]
    context_cost: int
    capability_fingerprint: str
    installer_content_digest: FieldObservation[str]
    availability_by_risk: tuple[RiskAvailability, ...]
    provenance: tuple[ProvenanceRecord, ...]


@dataclass(frozen=True, slots=True)
class CapabilitySnapshot:
    snapshot_id: str
    schema_version: str
    created_at: str
    runtime_fingerprint: str
    provider_revisions: tuple[str, ...]
    capabilities: tuple[Capability, ...]
    drift_from_snapshot_id: str | None
    freshness: Freshness


@dataclass(frozen=True, slots=True)
class CapabilityDrift:
    drift_id: str
    previous_snapshot_id: str | None
    current_snapshot_id: str
    capability_id: str
    kind: DriftKind
    changed_fields: tuple[str, ...]
    before_fingerprint: str | None
    after_fingerprint: str | None
    detected_at: str
