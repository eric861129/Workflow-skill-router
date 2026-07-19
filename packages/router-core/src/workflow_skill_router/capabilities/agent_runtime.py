from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from workflow_skill_router.schemas.errors import SchemaRegistryError

from .codecs import SCHEMA_VERSION
from .models import (
    AuthState,
    CapabilityKind,
    Compatibility,
    Eligibility,
    Exposure,
    FieldObservation,
    Freshness,
    Presence,
    SideEffect,
    TrustLevel,
)
from .providers import CapabilityObservation, DiscoveryContext, ProviderResult


AGENT_RUNTIME_SCHEMA_ID = "workflow-skill-router/agent-runtime-snapshot"
AGENT_RUNTIME_ARTIFACT_KIND = "agent-runtime-snapshot"
_ROOT_FIELDS = frozenset({
    "schema_id", "schema_version", "artifact_kind", "runtime_revision", "capabilities",
})
_CAPABILITY_FIELDS = frozenset({
    "canonical_id", "kind", "display_name", "exposure", "aliases",
})


def _exact(value: object, fields: frozenset[str], context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise SchemaRegistryError(f"{context} must be object")
    keys = {str(key) for key in value}
    missing = sorted(fields - keys)
    unknown = sorted(keys - fields)
    if missing:
        raise SchemaRegistryError(f"{context} missing field: {', '.join(missing)}")
    if unknown:
        raise SchemaRegistryError(f"{context} unknown field: {', '.join(unknown)}")
    return value


@dataclass(frozen=True, slots=True)
class AgentCapabilityView:
    canonical_id: str
    kind: str
    display_name: str
    exposure: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AgentRuntimeSnapshot:
    schema_id: str
    schema_version: str
    artifact_kind: str
    runtime_revision: str
    capabilities: tuple[AgentCapabilityView, ...]


def decode_agent_runtime_snapshot(document: object) -> AgentRuntimeSnapshot:
    root = _exact(document, _ROOT_FIELDS, "agent runtime snapshot")
    if root["schema_id"] != AGENT_RUNTIME_SCHEMA_ID:
        raise SchemaRegistryError("agent runtime snapshot schema_id mismatch")
    if root["schema_version"] != SCHEMA_VERSION:
        raise SchemaRegistryError("agent runtime snapshot schema_version mismatch")
    if root["artifact_kind"] != AGENT_RUNTIME_ARTIFACT_KIND:
        raise SchemaRegistryError("agent runtime snapshot artifact_kind mismatch")
    raw_capabilities = root["capabilities"]
    if not isinstance(raw_capabilities, list):
        raise SchemaRegistryError("agent runtime snapshot capabilities must be array")
    capabilities = []
    for index, value in enumerate(raw_capabilities):
        item = _exact(value, _CAPABILITY_FIELDS, f"agent capability[{index}]")
        aliases = item["aliases"]
        if not isinstance(aliases, list) or not all(isinstance(alias, str) for alias in aliases):
            raise SchemaRegistryError(f"agent capability[{index}].aliases must be string array")
        try:
            kind = CapabilityKind(str(item["kind"]))
            exposure = Exposure(str(item["exposure"]))
        except ValueError as error:
            raise SchemaRegistryError(f"agent capability[{index}] enum mismatch") from error
        capabilities.append(AgentCapabilityView(
            canonical_id=str(item["canonical_id"]),
            kind=kind.value,
            display_name=str(item["display_name"]),
            exposure=exposure.value,
            aliases=tuple(aliases),
        ))
    return AgentRuntimeSnapshot(
        schema_id=str(root["schema_id"]),
        schema_version=str(root["schema_version"]),
        artifact_kind=str(root["artifact_kind"]),
        runtime_revision=str(root["runtime_revision"]),
        capabilities=tuple(capabilities),
    )


class AgentRuntimeSnapshotProvider:
    provider_id = "agent-runtime"

    def __init__(
        self,
        snapshot: AgentRuntimeSnapshot,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._snapshot = snapshot
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def discover(self, context: DiscoveryContext) -> ProviderResult:
        del context
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("agent runtime clock 必須回傳 timezone-aware datetime")

        def field(value: object, reason: str) -> FieldObservation[object]:
            return FieldObservation(value, self.provider_id, now, TrustLevel.RUNTIME, reason)

        observations = []
        for item in self._snapshot.capabilities:
            try:
                kind = CapabilityKind(item.kind)
                exposure = Exposure(item.exposure)
            except ValueError as error:
                raise SchemaRegistryError("agent runtime snapshot enum mismatch") from error
            fields = {
                "display_name": field(item.display_name, "agent-runtime-view"),
                "description": field("", "agent-description-unavailable"),
                "presence": field(Presence.PRESENT, "agent-runtime-listed"),
                "exposure": field(exposure, "agent-runtime-exposure"),
                "auth_state": field(AuthState.UNKNOWN, "host-auth-unverified"),
                "eligibility": field(Eligibility.UNKNOWN, "host-policy-unverified"),
                "compatibility": field(Compatibility.UNKNOWN, "handshake-unverified"),
                "freshness": field(Freshness(now, now + timedelta(seconds=15), True), "agent-runtime-snapshot"),
                "domains": field((), "agent-domains-unavailable"),
                "stages": field((), "agent-stages-unavailable"),
                "side_effect": field(SideEffect.NONE, "agent-side-effect-unavailable"),
                "requirements": field((), "agent-requirements-unavailable"),
                "aliases": field(item.aliases, "agent-runtime-aliases"),
                "conflicts": field((), "agent-conflicts-unavailable"),
                "context_cost": field(1, "agent-context-cost-default"),
                "capability_fingerprint": field("unknown", "agent-content-unverified"),
                "installer_content_digest": field("unknown", "installer-content-unverified"),
            }
            observations.append(CapabilityObservation(item.canonical_id, kind, self.provider_id, fields))
        return ProviderResult(
            provider_id=self.provider_id,
            revision=self._snapshot.runtime_revision,
            observed_at=now,
            observations=tuple(sorted(observations, key=lambda item: item.canonical_id)),
            degraded=False,
            reasons=(),
        )
