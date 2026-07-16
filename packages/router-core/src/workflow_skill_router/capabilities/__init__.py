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
from .filesystem import (
    FilesystemMetadataProvider,
    InstallerContentClaim,
    InstallerManifestIndex,
)
from .frontmatter import FrontmatterError, parse_frontmatter, read_frontmatter_stream
from .providers import (
    CapabilityObservation,
    CapabilityProvider,
    DiscoveryContext,
    ProviderResult,
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
    "CapabilityObservation",
    "CapabilityProvider",
    "CapabilitySnapshot",
    "Compatibility",
    "DriftKind",
    "Eligibility",
    "Exposure",
    "FieldObservation",
    "FilesystemMetadataProvider",
    "Freshness",
    "FrontmatterError",
    "InstallerContentClaim",
    "InstallerManifestIndex",
    "Presence",
    "ProvenanceRecord",
    "Requirement",
    "RiskAvailability",
    "RiskLevel",
    "SideEffect",
    "TrustLevel",
    "DiscoveryContext",
    "ProviderResult",
    "decode_capability",
    "decode_snapshot",
    "derive_availability",
    "encode_capability",
    "encode_snapshot",
    "parse_frontmatter",
    "read_frontmatter_stream",
]
