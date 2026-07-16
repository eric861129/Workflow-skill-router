from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping, Protocol

from .agent_runtime import AgentRuntimeSnapshot, AgentRuntimeSnapshotProvider
from .cache import CachedSnapshotProvider
from .discovery import DiscoveryService
from .models import CapabilityDrift, CapabilitySnapshot, RiskLevel
from .native_host import HostRuntimeVerifier, NativeHostProvider
from .plugin_handshake import PluginHandshakeProvider, PluginHandshakeVerifier
from .providers import CapabilityProvider, DiscoveryContext


DEFAULT_PROVIDER_DEADLINES = {
    "native-host": 0.250,
    "agent-runtime": 0.250,
    "plugin-handshake": 0.500,
    "filesystem": 1.500,
    "cache": 0.100,
}


@dataclass(frozen=True, slots=True)
class VerifiedRuntimeAuthority:
    session_id: str
    runtime_fingerprint: str
    risk: RiskLevel
    runtime_policy_snapshot_id: str
    verification_receipt_digest: str


@dataclass(frozen=True, slots=True)
class RuntimeContextSyncRequest:
    authority: VerifiedRuntimeAuthority
    host_snapshot_ref: str | None
    plugin_handshake_ref: str | None
    agent_runtime_snapshot: AgentRuntimeSnapshot


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    provider_id: str
    reason_code: str
    timed_out: bool
    degraded: bool

    @classmethod
    def from_discovery(cls, failure: object) -> "ProviderFailure":
        return cls(
            provider_id=str(getattr(failure, "provider_id")),
            reason_code=str(getattr(failure, "reason")),
            timed_out=bool(getattr(failure, "timed_out")),
            degraded=True,
        )


@dataclass(frozen=True, slots=True)
class SyncRuntimeContextResult:
    snapshot: CapabilitySnapshot
    drift: tuple[CapabilityDrift, ...]
    provider_failures: tuple[ProviderFailure, ...]
    cache_used: bool
    degraded: bool


class SnapshotReader(Protocol):
    def latest(self, runtime_fingerprint: str) -> CapabilitySnapshot | None: ...


class RuntimeContextVerificationError(ValueError):
    pass


class RuntimeContextService:
    def __init__(
        self,
        *,
        host_verifier: HostRuntimeVerifier,
        handshake_verifier: PluginHandshakeVerifier,
        snapshot_reader: SnapshotReader,
        filesystem_providers: tuple[CapabilityProvider, ...],
        provider_deadlines: Mapping[str, float] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._host_verifier = host_verifier
        self._handshake_verifier = handshake_verifier
        self._snapshot_reader = snapshot_reader
        self._filesystem_providers = filesystem_providers
        self._deadlines = {**DEFAULT_PROVIDER_DEADLINES, **dict(provider_deadlines or {})}
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def sync_verified(self, request: RuntimeContextSyncRequest) -> SyncRuntimeContextResult:
        authority = request.authority
        if not isinstance(authority.risk, RiskLevel):
            raise RuntimeContextVerificationError("runtime_authority_invalid")
        providers: list[CapabilityProvider] = list(self._filesystem_providers)
        if request.host_snapshot_ref:
            providers.append(NativeHostProvider(
                self._host_verifier,
                request.host_snapshot_ref,
                authority,
            ))
        if request.plugin_handshake_ref:
            providers.append(PluginHandshakeProvider(
                self._handshake_verifier,
                request.plugin_handshake_ref,
                authority,
            ))
        providers.append(AgentRuntimeSnapshotProvider(
            request.agent_runtime_snapshot,
            clock=self._clock,
        ))

        previous = self._snapshot_reader.latest(authority.runtime_fingerprint)
        cache_used = previous is not None
        if previous is not None:
            providers.append(CachedSnapshotProvider(previous))

        discovered = DiscoveryService(
            tuple(providers),
            clock=self._clock,
            provider_deadlines=self._deadlines,
            provider_timeout_seconds=max(self._deadlines.values()),
        ).discover(
            DiscoveryContext(authority.runtime_fingerprint, authority.risk.value),
            previous,
        )
        failures = tuple(ProviderFailure.from_discovery(item) for item in discovered.provider_failures)
        verification_failures = {
            "host_receipt_unverified",
            "plugin_receipt_unverified",
            "host_timestamp_unverified",
            "plugin_timestamp_unverified",
        }
        rejected = next(
            (item.reason_code for item in failures if item.reason_code in verification_failures),
            None,
        )
        if rejected:
            raise RuntimeContextVerificationError(rejected)
        return SyncRuntimeContextResult(
            snapshot=discovered.snapshot,
            drift=discovered.drift,
            provider_failures=failures,
            cache_used=cache_used,
            degraded=discovered.degraded,
        )


# Alpha compatibility alias retained for callers built against the first Task 6 draft.
RuntimeContextSyncResult = SyncRuntimeContextResult
