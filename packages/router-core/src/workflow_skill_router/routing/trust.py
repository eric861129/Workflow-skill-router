from __future__ import annotations

from dataclasses import dataclass

from workflow_skill_router.capabilities.models import (
    CapabilityKind,
    CapabilitySnapshot,
    Requirement,
    SideEffect,
)


@dataclass(frozen=True, slots=True)
class RequirementTrustPolicy:
    base_runtime_ids: tuple[str, ...]
    allowed_non_skill_kinds: tuple[CapabilityKind, ...]
    trusted_provider_ids: tuple[str, ...]
    allowed_purposes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RequirementTrustDecision:
    trusted_as_base_requirement: bool
    requires_support_consent: bool
    requires_capability_consent: bool
    requires_runtime_approval: bool
    reason_code: str


def assess_requirement(
    requirement: Requirement,
    parent_skill: str,
    snapshot: CapabilitySnapshot,
    policy: RequirementTrustPolicy,
) -> RequirementTrustDecision:
    del parent_skill
    if requirement.kind is CapabilityKind.SKILL:
        return RequirementTrustDecision(
            False,
            True,
            False,
            False,
            "skill-requirement-needs-support-consent",
        )

    capability = next(
        (item for item in snapshot.capabilities if item.canonical_id == requirement.canonical_id),
        None,
    )
    if capability is None or capability.kind is not requirement.kind:
        return RequirementTrustDecision(False, False, True, False, "requirement-not-in-snapshot")

    provider_trusted = any(
        item.provider_id in policy.trusted_provider_ids
        for item in capability.provenance
    )
    kind_allowed = (
        requirement.canonical_id in policy.base_runtime_ids
        or requirement.kind in policy.allowed_non_skill_kinds
    )
    purpose_allowed = requirement.purpose in policy.allowed_purposes
    fingerprint_verified = capability.capability_fingerprint != "unknown"
    trusted = (
        requirement.trusted
        and provider_trusted
        and kind_allowed
        and purpose_allowed
        and fingerprint_verified
    )
    elevated = capability.side_effect in (SideEffect.REMOTE, SideEffect.PRIVILEGED)
    if not trusted:
        return RequirementTrustDecision(
            False,
            False,
            True,
            elevated,
            "requirement-untrusted",
        )
    return RequirementTrustDecision(
        True,
        False,
        elevated,
        elevated,
        "requirement-trusted-with-runtime-boundary" if elevated else "requirement-trusted",
    )
