"""User-owned deterministic routing profile contracts and resolution."""

from .contract import (
    ProfileMatch,
    ProfileRoute,
    RoutingPreferenceProfile,
    RoutingProfileContractError,
    SkillTreePhase,
    decode_routing_profile,
)
from .resolver import (
    ResolvedProfileRoute,
    RoutingMatchContext,
    RoutingProfileResolutionError,
    resolve_profile_route,
)
from .atomic_io import (
    ProfileIOError,
    atomic_write_canonical_json,
    current_json_digest,
    secure_read_json,
)
from .storage import RoutingProfileRepository, default_router_data_dir, load_profile_file

__all__ = [
    "ProfileIOError",
    "atomic_write_canonical_json",
    "current_json_digest",
    "secure_read_json",
    "ProfileMatch",
    "ProfileRoute",
    "ResolvedProfileRoute",
    "RoutingMatchContext",
    "RoutingPreferenceProfile",
    "RoutingProfileContractError",
    "RoutingProfileResolutionError",
    "RoutingProfileRepository",
    "SkillTreePhase",
    "decode_routing_profile",
    "default_router_data_dir",
    "load_profile_file",
    "resolve_profile_route",
]
