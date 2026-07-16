from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.availability import derive_availability
from workflow_skill_router.capabilities.models import (
    AuthState,
    Availability,
    Capability,
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


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


def observed(value, trust_level=TrustLevel.RUNTIME):
    return FieldObservation(value, "agent-runtime", NOW, trust_level, "observed")


def capability(**changes):
    values = dict(
        canonical_id="skill:local/demo",
        display_name="Demo",
        kind=CapabilityKind.SKILL,
        source="local",
        presence=observed(Presence.PRESENT),
        exposure=observed(Exposure.EXPOSED),
        auth_state=observed(AuthState.NOT_REQUIRED),
        eligibility=observed(Eligibility.ELIGIBLE),
        compatibility=observed(Compatibility.COMPATIBLE),
        freshness=Freshness(NOW, NOW + timedelta(minutes=5), False),
        description="",
        domains=(),
        stages=(),
        side_effect=SideEffect.NONE,
        requirements=(),
        aliases=(),
        conflicts=(),
        context_cost=1,
        capability_fingerprint="abc",
        installer_content_digest=observed("unknown"),
        availability_by_risk=(),
        provenance=(),
    )
    values.update(changes)
    return Capability(**values)


class AvailabilityTests(unittest.TestCase):
    def test_incompatible_wins_over_absent_and_auth_required(self) -> None:
        item = capability(
            presence=observed(Presence.ABSENT),
            auth_state=observed(AuthState.REQUIRED),
            compatibility=observed(Compatibility.INCOMPATIBLE),
        )
        result = derive_availability(item, RiskLevel.R1, NOW)
        self.assertEqual(Availability.INCOMPATIBLE, result.primary)
        self.assertEqual(
            ("compatibility-incompatible", "presence-absent", "auth-required"),
            result.reasons,
        )

    def test_unknown_authoritative_field_is_not_available(self) -> None:
        item = capability(exposure=observed(Exposure.UNKNOWN))
        self.assertEqual(
            Availability.UNKNOWN,
            derive_availability(item, RiskLevel.R0, NOW).primary,
        )

    def test_r2_rejects_expired_freshness_while_r0_can_be_degraded(self) -> None:
        item = capability(
            freshness=Freshness(
                NOW - timedelta(hours=1),
                NOW - timedelta(minutes=1),
                True,
            )
        )
        self.assertEqual(
            Availability.DEGRADED,
            derive_availability(item, RiskLevel.R0, NOW).primary,
        )
        self.assertEqual(
            Availability.STALE,
            derive_availability(item, RiskLevel.R2, NOW).primary,
        )

    def test_cache_authority_is_degraded_even_when_other_fields_allow_use(self) -> None:
        item = capability(presence=observed(Presence.PRESENT, TrustLevel.CACHE))
        self.assertEqual(
            Availability.DEGRADED,
            derive_availability(item, RiskLevel.R0, NOW).primary,
        )


if __name__ == "__main__":
    unittest.main()
