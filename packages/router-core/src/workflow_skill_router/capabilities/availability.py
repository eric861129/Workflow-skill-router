from __future__ import annotations

from datetime import datetime

from .models import (
    AuthState,
    Availability,
    AvailabilityResult,
    Capability,
    Compatibility,
    Eligibility,
    Exposure,
    Presence,
    RiskLevel,
    TrustLevel,
)


def derive_availability(
    capability: Capability,
    risk: RiskLevel,
    now: datetime,
) -> AvailabilityResult:
    """依固定優先序推導單一風險層級的可用性。"""

    reasons: list[str] = []
    if capability.compatibility.value is Compatibility.INCOMPATIBLE:
        reasons.append("compatibility-incompatible")
    if capability.presence.value is Presence.ABSENT:
        reasons.append("presence-absent")
    if capability.exposure.value is Exposure.NOT_EXPOSED:
        reasons.append("exposure-not-exposed")
    if capability.eligibility.value is Eligibility.INELIGIBLE:
        reasons.append("policy-ineligible")
    if capability.auth_state.value is AuthState.REQUIRED:
        reasons.append("auth-required")

    unknown = (
        capability.presence.value is Presence.UNKNOWN
        or capability.exposure.value is Exposure.UNKNOWN
        or capability.auth_state.value is AuthState.UNKNOWN
        or capability.eligibility.value is Eligibility.UNKNOWN
        or capability.compatibility.value is Compatibility.UNKNOWN
    )
    stale = capability.freshness.stale or now > capability.freshness.expires_at
    degraded = any(
        field.trust_level is TrustLevel.CACHE
        for field in (
            capability.presence,
            capability.exposure,
            capability.auth_state,
            capability.eligibility,
            capability.compatibility,
        )
    )

    if reasons and reasons[0] == "compatibility-incompatible":
        primary = Availability.INCOMPATIBLE
    elif any(
        reason in reasons
        for reason in ("presence-absent", "exposure-not-exposed", "policy-ineligible")
    ):
        primary = Availability.UNAVAILABLE
    elif "auth-required" in reasons:
        primary = Availability.AUTH_REQUIRED
    elif unknown:
        primary = Availability.UNKNOWN
    elif stale and (
        risk in (RiskLevel.R2, RiskLevel.R3)
        or not capability.freshness.degraded_allowed
    ):
        primary = Availability.STALE
    elif stale or degraded:
        primary = Availability.DEGRADED
    else:
        primary = Availability.AVAILABLE

    return AvailabilityResult(primary, tuple(reasons))
