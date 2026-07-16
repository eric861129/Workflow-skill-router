from __future__ import annotations

from datetime import datetime, timezone

from .models import CapabilitySnapshot, FieldObservation, Freshness, TrustLevel
from .providers import CapabilityObservation, DiscoveryContext, ProviderResult


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class CachedSnapshotProvider:
    provider_id = "cache"

    def __init__(self, snapshot: CapabilitySnapshot) -> None:
        self._snapshot = snapshot

    def discover(self, context: DiscoveryContext) -> ProviderResult:
        del context
        now = _timestamp(self._snapshot.created_at)

        def cached(value: object) -> FieldObservation[object]:
            return FieldObservation(value, self.provider_id, now, TrustLevel.CACHE, "cached-snapshot")

        observations = []
        for item in self._snapshot.capabilities:
            fields = {
                "display_name": cached(item.display_name),
                "description": cached(item.description),
                "presence": cached(item.presence.value),
                "exposure": cached(item.exposure.value),
                "auth_state": cached(item.auth_state.value),
                "eligibility": cached(item.eligibility.value),
                "compatibility": cached(item.compatibility.value),
                "freshness": cached(Freshness(now, now, True, True)),
                "domains": cached(item.domains),
                "stages": cached(item.stages),
                "side_effect": cached(item.side_effect),
                "requirements": cached(item.requirements),
                "aliases": cached(item.aliases),
                "conflicts": cached(item.conflicts),
                "context_cost": cached(item.context_cost),
                "capability_fingerprint": cached(item.capability_fingerprint),
                "installer_content_digest": cached("unknown"),
            }
            observations.append(CapabilityObservation(item.canonical_id, item.kind, self.provider_id, fields))
        return ProviderResult(
            provider_id=self.provider_id,
            revision=self._snapshot.snapshot_id,
            observed_at=now,
            observations=tuple(observations),
            degraded=True,
            reasons=("cached-snapshot",),
        )
