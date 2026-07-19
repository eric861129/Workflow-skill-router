from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

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


class HostReceiptVerificationError(ValueError):
    def __init__(self, reason_code: str = "host_receipt_unverified") -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class VerifiedHostCapability:
    canonical_id: str
    kind: CapabilityKind
    display_name: str
    presence: Presence
    exposure: Exposure
    auth_state: AuthState
    eligibility: Eligibility
    compatibility: Compatibility
    description: str
    aliases: tuple[str, ...]
    content_digest: str


@dataclass(frozen=True, slots=True)
class VerifiedHostSnapshot:
    revision: str
    observed_at: datetime
    capabilities: tuple[VerifiedHostCapability, ...]
    receipt_digest: str


class HostRuntimeVerifier(Protocol):
    def resolve(
        self,
        reference: str,
        session_id: str,
        receipt_digest: str,
    ) -> VerifiedHostSnapshot: ...


class NativeHostProvider:
    provider_id = "native-host"

    def __init__(self, verifier: HostRuntimeVerifier, reference: str, authority: object) -> None:
        self._verifier = verifier
        self._reference = reference
        self._session_id = str(getattr(authority, "session_id"))
        self._receipt_digest = str(getattr(authority, "verification_receipt_digest"))
        self._verified: VerifiedHostSnapshot | None = None

    @classmethod
    def from_verified(cls, snapshot: VerifiedHostSnapshot) -> "NativeHostProvider":
        provider = cls.__new__(cls)
        provider._verifier = None
        provider._reference = "verified-test-fixture"
        provider._session_id = "verified-test-fixture"
        provider._receipt_digest = snapshot.receipt_digest
        provider._verified = snapshot
        return provider

    def _resolve(self) -> VerifiedHostSnapshot:
        snapshot = self._verified
        if snapshot is None:
            snapshot = self._verifier.resolve(
                self._reference,
                self._session_id,
                self._receipt_digest,
            )
        if not isinstance(snapshot, VerifiedHostSnapshot):
            raise HostReceiptVerificationError()
        return snapshot

    def discover(self, context: DiscoveryContext) -> ProviderResult:
        del context
        snapshot = self._resolve()
        now = snapshot.observed_at
        if now.tzinfo is None or now.utcoffset() is None:
            raise HostReceiptVerificationError("host_timestamp_unverified")

        def field(value: object, reason: str) -> FieldObservation[object]:
            return FieldObservation(value, self.provider_id, now, TrustLevel.RUNTIME, reason)

        observations = []
        for capability in snapshot.capabilities:
            fields = {
                "display_name": field(capability.display_name, "host-display-name-verified"),
                "description": field(capability.description, "host-description-verified"),
                "presence": field(capability.presence, "host-presence-verified"),
                "exposure": field(capability.exposure, "host-exposure-verified"),
                "auth_state": field(capability.auth_state, "host-auth-verified"),
                "eligibility": field(capability.eligibility, "host-policy-verified"),
                "compatibility": field(capability.compatibility, "host-compatibility-verified"),
                "freshness": field(Freshness(now, now + timedelta(seconds=30), False), "host-receipt-verified"),
                "domains": field((), "host-domains-unset"),
                "stages": field((), "host-stages-unset"),
                "side_effect": field(SideEffect.NONE, "host-side-effect-unset"),
                "requirements": field((), "host-requirements-unset"),
                "aliases": field(capability.aliases, "host-aliases-verified"),
                "conflicts": field((), "host-conflicts-unset"),
                "context_cost": field(1, "host-context-cost-default"),
                "capability_fingerprint": field(capability.content_digest, "host-capability-verified"),
                "installer_content_digest": field(capability.content_digest, "host-content-verified"),
            }
            observations.append(CapabilityObservation(
                canonical_id=capability.canonical_id,
                kind=capability.kind,
                source=self.provider_id,
                fields=fields,
            ))
        return ProviderResult(
            provider_id=self.provider_id,
            revision=snapshot.revision,
            observed_at=now,
            observations=tuple(sorted(observations, key=lambda item: item.canonical_id)),
            degraded=False,
            reasons=(),
        )
