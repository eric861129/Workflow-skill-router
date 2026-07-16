from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
from types import MappingProxyType
from typing import Protocol

from workflow_skill_router.schemas.artifacts import canonical_json_bytes

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


def _freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError(f"unsupported JSON schema value: {type(value).__name__}")


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain_json(item) for item in value]
    return value


class PluginReceiptVerificationError(ValueError):
    def __init__(self, reason_code: str = "plugin_receipt_unverified") -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class VerifiedToolDescriptor:
    server_id: str
    tool_name: str
    display_name: str
    schema: Mapping[str, object]
    healthy: bool
    auth_state: AuthState
    aliases: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema", _freeze_json(self.schema))


@dataclass(frozen=True, slots=True)
class VerifiedPluginHandshake:
    revision: str
    observed_at: datetime
    tools: tuple[VerifiedToolDescriptor, ...]
    receipt_digest: str


class PluginHandshakeVerifier(Protocol):
    def resolve(
        self,
        reference: str,
        session_id: str,
        receipt_digest: str,
    ) -> VerifiedPluginHandshake: ...


class PluginHandshakeProvider:
    provider_id = "plugin-handshake"

    def __init__(self, verifier: PluginHandshakeVerifier, reference: str, authority: object) -> None:
        self._verifier = verifier
        self._reference = reference
        self._session_id = str(getattr(authority, "session_id"))
        self._receipt_digest = str(getattr(authority, "verification_receipt_digest"))
        self._verified: VerifiedPluginHandshake | None = None

    @classmethod
    def from_verified(cls, handshake: VerifiedPluginHandshake) -> "PluginHandshakeProvider":
        provider = cls.__new__(cls)
        provider._verifier = None
        provider._reference = "verified-test-fixture"
        provider._session_id = "verified-test-fixture"
        provider._receipt_digest = handshake.receipt_digest
        provider._verified = handshake
        return provider

    def _resolve(self) -> VerifiedPluginHandshake:
        handshake = self._verified
        if handshake is None:
            handshake = self._verifier.resolve(
                self._reference,
                self._session_id,
                self._receipt_digest,
            )
        if not isinstance(handshake, VerifiedPluginHandshake):
            raise PluginReceiptVerificationError()
        return handshake

    def discover(self, context: DiscoveryContext) -> ProviderResult:
        del context
        handshake = self._resolve()
        now = handshake.observed_at
        if now.tzinfo is None or now.utcoffset() is None:
            raise PluginReceiptVerificationError("plugin_timestamp_unverified")

        def field(value: object, reason: str) -> FieldObservation[object]:
            return FieldObservation(value, self.provider_id, now, TrustLevel.HANDSHAKE, reason)

        observations = []
        for tool in handshake.tools:
            schema_document = _plain_json(tool.schema)
            assert isinstance(schema_document, dict)
            fingerprint = "sha256:" + hashlib.sha256(
                canonical_json_bytes(schema_document)
            ).hexdigest()
            compatibility = Compatibility.COMPATIBLE if tool.healthy else Compatibility.INCOMPATIBLE
            fields = {
                "display_name": field(tool.display_name, "plugin-display-name-verified"),
                "description": field("", "plugin-description-unset"),
                "presence": field(Presence.PRESENT, "plugin-presence-verified"),
                "exposure": field(Exposure.EXPOSED, "plugin-exposure-verified"),
                "auth_state": field(tool.auth_state, "plugin-auth-verified"),
                "eligibility": field(Eligibility.UNKNOWN, "host-policy-unverified"),
                "compatibility": field(compatibility, "plugin-health-verified"),
                "freshness": field(Freshness(now, now + timedelta(seconds=30), False), "plugin-handshake-verified"),
                "domains": field((), "plugin-domains-unset"),
                "stages": field((), "plugin-stages-unset"),
                "side_effect": field(SideEffect.NONE, "plugin-side-effect-unset"),
                "requirements": field((), "plugin-requirements-unset"),
                "aliases": field(tool.aliases, "plugin-aliases-verified"),
                "conflicts": field((), "plugin-conflicts-unset"),
                "context_cost": field(1, "plugin-context-cost-default"),
                "capability_fingerprint": field(fingerprint, "plugin-schema-verified"),
                "installer_content_digest": field("unknown", "installer-content-unverified"),
            }
            observations.append(CapabilityObservation(
                canonical_id=f"mcp-tool:{tool.server_id}/{tool.tool_name}",
                kind=CapabilityKind.MCP_TOOL,
                source=self.provider_id,
                fields=fields,
            ))
        return ProviderResult(
            provider_id=self.provider_id,
            revision=handshake.revision,
            observed_at=now,
            observations=tuple(sorted(observations, key=lambda item: item.canonical_id)),
            degraded=any(not item.healthy for item in handshake.tools),
            reasons=tuple("plugin-tool-unhealthy" for item in handshake.tools if not item.healthy),
        )
