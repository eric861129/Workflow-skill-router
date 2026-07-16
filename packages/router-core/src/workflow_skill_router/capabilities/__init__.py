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
from .drift import (
    CAPABILITY_DRIFT_SCHEMA_ID,
    compare_snapshots,
    decode_drift,
    encode_drift,
)
from .discovery import (
    DiscoveryResult,
    DiscoveryService,
    ProviderFailure,
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
from .merge import CapabilityMergeError, merge_observations
from .providers import (
    CapabilityObservation,
    CapabilityProvider,
    DiscoveryContext,
    ProviderResult,
)
from .snapshot import build_snapshot, rebuild_snapshot_id


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
CAPABILITY_SCHEMA_REGISTRY.register(
    CAPABILITY_DRIFT_SCHEMA_ID,
    SCHEMA_VERSION,
    "capability-drift",
    decode_drift,
)

__all__ = [
    "AuthState",
    "Availability",
    "AvailabilityResult",
    "CAPABILITY_SCHEMA_REGISTRY",
    "CAPABILITY_DRIFT_SCHEMA_ID",
    "Capability",
    "CapabilityDrift",
    "CapabilityKind",
    "CapabilityMergeError",
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
    "DiscoveryResult",
    "DiscoveryService",
    "ProviderResult",
    "ProviderFailure",
    "decode_capability",
    "decode_drift",
    "decode_snapshot",
    "derive_availability",
    "encode_capability",
    "encode_drift",
    "encode_snapshot",
    "compare_snapshots",
    "build_snapshot",
    "parse_frontmatter",
    "merge_observations",
    "read_frontmatter_stream",
    "rebuild_snapshot_id",
]
