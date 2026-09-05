from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .contract import RoutingPreferenceProfile


_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class ProfileSourceClass(str, Enum):
    """Ownership class used before rule priority during Profile resolution."""

    USER_WORKSPACE = "user-workspace"
    MANAGED_WORKSPACE = "managed-workspace"
    USER_PERSONAL = "user-personal"
    MANAGED_PERSONAL = "managed-personal"


_SOURCE_RANK = {
    ProfileSourceClass.USER_WORKSPACE: 0,
    ProfileSourceClass.MANAGED_WORKSPACE: 1,
    ProfileSourceClass.USER_PERSONAL: 2,
    ProfileSourceClass.MANAGED_PERSONAL: 3,
}
_ROUTE_SOURCE = {
    ProfileSourceClass.USER_WORKSPACE: "workspace-profile",
    ProfileSourceClass.MANAGED_WORKSPACE: "managed-workspace-profile",
    ProfileSourceClass.USER_PERSONAL: "personal-profile",
    ProfileSourceClass.MANAGED_PERSONAL: "managed-personal-profile",
}


@dataclass(frozen=True, slots=True)
class LayeredRoutingProfile:
    profile: RoutingPreferenceProfile
    source_class: ProfileSourceClass
    source_digest: str
    workspace_identity_digest: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.source_class, ProfileSourceClass):
            raise ValueError("profile-layer-source-class-invalid")
        expected_scope = (
            "workspace"
            if self.source_class in {
                ProfileSourceClass.USER_WORKSPACE,
                ProfileSourceClass.MANAGED_WORKSPACE,
            }
            else "personal"
        )
        if self.profile.scope != expected_scope:
            raise ValueError("profile-layer-scope-mismatch")
        if self.source_digest != self.profile.profile_digest:
            raise ValueError("profile-layer-source-digest-mismatch")
        if expected_scope == "workspace":
            if (
                not isinstance(self.workspace_identity_digest, str)
                or _DIGEST.fullmatch(self.workspace_identity_digest) is None
            ):
                raise ValueError("profile-layer-workspace-digest-required")
        elif self.workspace_identity_digest is not None:
            raise ValueError("profile-layer-workspace-digest-forbidden")

    @property
    def rank(self) -> int:
        return _SOURCE_RANK[self.source_class]

    @property
    def route_source(self) -> str:
        return _ROUTE_SOURCE[self.source_class]


@dataclass(frozen=True, slots=True)
class LoadedProfileLayers:
    layers: tuple[LayeredRoutingProfile, ...]
    warnings: tuple[str, ...]
    workspace_identity_digest: str | None

    def __post_init__(self) -> None:
        if tuple(sorted(self.layers, key=lambda item: item.rank)) != self.layers:
            raise ValueError("profile-layers-not-ranked")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("profile-layer-warning-duplicate")


__all__ = [
    "LayeredRoutingProfile",
    "LoadedProfileLayers",
    "ProfileSourceClass",
]
