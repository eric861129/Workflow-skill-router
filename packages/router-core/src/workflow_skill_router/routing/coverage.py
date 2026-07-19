from __future__ import annotations

from collections.abc import Mapping

from .models import (
    CoverageStatus,
    ExplicitSemantics,
    ExplicitSkillCoverage,
    ExplicitSkillDisposition,
    SkillDisposition,
    SkillSelectionPolicy,
)


_ACTIVE = {
    SkillDisposition.ACTIVE_REQUIRED,
    SkillDisposition.ACTIVE_PRIMARY,
    SkillDisposition.ACTIVE_SUPPORT,
}


def evaluate_explicit_coverage(
    policy: SkillSelectionPolicy,
    dispositions: tuple[ExplicitSkillDisposition, ...],
    activation_refs: Mapping[str, tuple[str, ...]],
    primary_route_refs: Mapping[str, tuple[str, ...]],
    user_waivers: Mapping[str, tuple[str, ...]],
) -> tuple[ExplicitSkillCoverage, ...]:
    by_skill: dict[str, list[ExplicitSkillDisposition]] = {}
    for item in dispositions:
        if item.scope_anchor_id == policy.scope_anchor_id:
            by_skill.setdefault(item.skill_id, []).append(item)

    coverage = []
    for skill_id in policy.explicit_skill_ids:
        waivers = tuple(user_waivers.get(skill_id, ()))
        if waivers:
            coverage.append(ExplicitSkillCoverage(
                skill_id,
                policy.scope_anchor_id,
                CoverageStatus.WAIVED,
                waivers,
                "user-waiver",
            ))
            continue
        skill_dispositions = tuple(by_skill.get(skill_id, ()))
        active = any(item.disposition in _ACTIVE for item in skill_dispositions)
        activations = tuple(activation_refs.get(skill_id, ()))
        primary_routes = tuple(primary_route_refs.get(skill_id, ()))

        satisfied = False
        evidence: tuple[str, ...] = ()
        reason = "explicit-skill-not-covered"
        if policy.explicit_semantics is ExplicitSemantics.REQUIRED_ALL:
            satisfied = active and bool(activations)
            evidence = activations
            reason = "required-skill-activated" if satisfied else "required-skill-not-activated"
        elif policy.explicit_semantics is ExplicitSemantics.PREFERRED_PRIMARY:
            satisfied = active and bool(activations) and bool(primary_routes)
            evidence = tuple(dict.fromkeys((*primary_routes, *activations)))
            reason = "preferred-primary-activated" if satisfied else "preferred-primary-missing"
        elif policy.explicit_semantics is ExplicitSemantics.ALLOWED_SET:
            satisfied = active and bool(activations)
            evidence = activations
            reason = "allowed-skill-activated" if satisfied else "allowed-skill-not-selected"

        coverage.append(ExplicitSkillCoverage(
            skill_id,
            policy.scope_anchor_id,
            CoverageStatus.SATISFIED if satisfied else CoverageStatus.UNCOVERED,
            evidence,
            reason,
        ))
    return tuple(coverage)
