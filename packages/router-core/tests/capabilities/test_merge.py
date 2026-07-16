from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.availability import derive_availability
from workflow_skill_router.capabilities.merge import CapabilityMergeError, merge_observations
from workflow_skill_router.capabilities.models import (
    AuthState,
    Availability,
    CapabilityKind,
    Compatibility,
    Eligibility,
    Exposure,
    FieldObservation,
    Freshness,
    Presence,
    RiskLevel,
    SideEffect,
    TrustLevel,
)
from workflow_skill_router.capabilities.providers import (
    CapabilityObservation,
    ProviderResult,
)


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


def trust_for(authority: str) -> TrustLevel:
    return {
        "cache": TrustLevel.CACHE,
        "filesystem": TrustLevel.METADATA,
        "plugin-handshake": TrustLevel.HANDSHAKE,
        "native-host": TrustLevel.RUNTIME,
    }.get(authority, TrustLevel.RUNTIME)


def observed(value, authority: str, reason: str = "fixture"):
    return FieldObservation(value, authority, NOW, trust_for(authority), reason)


def provider(
    *,
    authority: str,
    canonical_id: str = "skill:filesystem/demo",
    source: str = "filesystem",
    display_name: str = "Demo",
    presence: Presence = Presence.PRESENT,
    exposure: Exposure = Exposure.EXPOSED,
    auth_state: AuthState = AuthState.NOT_REQUIRED,
    eligibility: Eligibility = Eligibility.ELIGIBLE,
    compatibility: Compatibility = Compatibility.COMPATIBLE,
    freshness: Freshness | None = None,
    fingerprint: str = "sha256:metadata",
    installer_content_digest: str = "unknown",
    installer_reason: str = "installer-content-unverified",
) -> ProviderResult:
    current_freshness = freshness or Freshness(NOW, NOW + timedelta(minutes=5), True)
    fields = {
        "display_name": observed(display_name, authority),
        "description": observed("描述", authority),
        "presence": observed(presence, authority),
        "exposure": observed(exposure, authority),
        "auth_state": observed(auth_state, authority),
        "eligibility": observed(eligibility, authority),
        "compatibility": observed(compatibility, authority),
        "freshness": observed(current_freshness, authority),
        "domains": observed(("workflow",), authority),
        "stages": observed(("planning",), authority),
        "side_effect": observed(SideEffect.NONE, authority),
        "requirements": observed((), authority),
        "aliases": observed((), authority),
        "conflicts": observed((), authority),
        "context_cost": observed(1, authority),
        "capability_fingerprint": observed(fingerprint, authority),
        "installer_content_digest": observed(
            installer_content_digest,
            authority,
            installer_reason,
        ),
    }
    observation = CapabilityObservation(
        canonical_id=canonical_id,
        kind=CapabilityKind.SKILL,
        source=source,
        fields=fields,
    )
    return ProviderResult(
        provider_id=authority,
        revision=f"{authority}@1",
        observed_at=NOW,
        observations=(observation,),
        degraded=authority == "cache",
        reasons=("cached",) if authority == "cache" else (),
    )


def filesystem_present() -> ProviderResult:
    return provider(authority="filesystem", exposure=Exposure.UNKNOWN)


def cache_exposed() -> ProviderResult:
    return provider(authority="cache", exposure=Exposure.EXPOSED)


def host_not_exposed() -> ProviderResult:
    return provider(authority="native-host", exposure=Exposure.NOT_EXPOSED)


class ProviderMergeTests(unittest.TestCase):
    def test_host_exposure_wins_over_filesystem_and_cache(self) -> None:
        merged = merge_observations(
            (filesystem_present(), cache_exposed(), host_not_exposed()),
            RiskLevel.R1,
            NOW,
        )
        self.assertEqual(Exposure.NOT_EXPOSED, merged[0].exposure.value)
        self.assertEqual(
            Availability.UNAVAILABLE,
            derive_availability(merged[0], RiskLevel.R1, NOW).primary,
        )

    def test_cache_cannot_promote_runtime_unavailable(self) -> None:
        merged = merge_observations(
            (host_not_exposed(), cache_exposed()),
            RiskLevel.R1,
            NOW,
        )
        self.assertEqual(Exposure.NOT_EXPOSED, merged[0].exposure.value)
        self.assertNotEqual(
            Availability.AVAILABLE,
            derive_availability(merged[0], RiskLevel.R1, NOW).primary,
        )

    def test_same_display_name_from_two_sources_is_not_deduplicated(self) -> None:
        merged = merge_observations(
            (
                provider(authority="filesystem", canonical_id="skill:filesystem/demo"),
                provider(
                    authority="plugin-handshake",
                    canonical_id="skill:plugin/demo",
                    source="plugin",
                ),
            ),
            RiskLevel.R0,
            NOW,
        )
        self.assertEqual(
            ["skill:filesystem/demo", "skill:plugin/demo"],
            [item.canonical_id for item in merged],
        )

    def test_every_capability_materializes_non_null_risk_availability(self) -> None:
        stale = Freshness(
            NOW - timedelta(hours=1),
            NOW - timedelta(minutes=1),
            True,
            True,
        )
        item = merge_observations(
            (provider(authority="filesystem", freshness=stale),),
            RiskLevel.R0,
            NOW,
        )[0]
        by_risk = {entry.risk: entry.result for entry in item.availability_by_risk}
        self.assertEqual(set(RiskLevel), set(by_risk))
        self.assertTrue(
            all(
                result.primary is not None and result.reasons is not None
                for result in by_risk.values()
            )
        )
        self.assertNotEqual(
            by_risk[RiskLevel.R0].primary,
            by_risk[RiskLevel.R2].primary,
        )

    def test_unverified_agent_digest_cannot_become_installer_authority(self) -> None:
        unverified = provider(
            authority="agent-runtime",
            installer_content_digest="sha256:" + "a" * 64,
            installer_reason="client-declared",
        )
        item = merge_observations((unverified,), RiskLevel.R1, NOW)[0]
        self.assertEqual("unknown", item.installer_content_digest.value)

    def test_wrong_typed_authoritative_field_fails_closed(self) -> None:
        result = provider(authority="native-host")
        observation = result.observations[0]
        fields = dict(observation.fields)
        fields["exposure"] = observed("exposed", "native-host")
        malformed = replace(
            result,
            observations=(replace(observation, fields=fields),),
        )
        with self.assertRaisesRegex(CapabilityMergeError, "exposure.*type mismatch"):
            merge_observations((malformed,), RiskLevel.R1, NOW)


if __name__ == "__main__":
    unittest.main()
