from __future__ import annotations

from dataclasses import dataclass

from .contract import RoutingPreferenceProfile, RoutingProfileRule, SkillTreePhase


class RoutingProfileResolutionError(ValueError):
    """Raised when a matched profile cannot produce an unambiguous current route."""


@dataclass(frozen=True, slots=True)
class RoutingMatchContext:
    domains: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    current_phase_id: str | None = None
    lock_work_mode: bool = False


@dataclass(frozen=True, slots=True)
class ResolvedProfileRoute:
    route_source: str
    profile_id: str
    applied_profile_ids: tuple[str, ...]
    profile_digest: str
    matched_rule_id: str
    work_mode: str
    skill_tree: tuple[SkillTreePhase, ...]
    current_phase: SkillTreePhase
    current_skill_ids: tuple[str, ...]
    activation_status: str


def _matches(
    rule: RoutingProfileRule,
    *,
    objective: str,
    work_mode: str,
    context: RoutingMatchContext,
) -> bool:
    matcher = rule.match
    if context.lock_work_mode and rule.route.work_mode != work_mode:
        return False
    objective_folded = objective.casefold()
    if matcher.objective_keywords and not any(
        keyword.casefold() in objective_folded for keyword in matcher.objective_keywords
    ):
        return False
    if matcher.domains and not set(matcher.domains).intersection(context.domains):
        return False
    if matcher.tags and not set(matcher.tags).intersection(context.tags):
        return False
    if matcher.work_modes and work_mode not in matcher.work_modes:
        return False
    return True


def resolve_profile_route(
    profiles: tuple[RoutingPreferenceProfile, ...],
    *,
    objective: str,
    default_work_mode: str,
    context: RoutingMatchContext,
) -> ResolvedProfileRoute | None:
    candidates: list[tuple[RoutingPreferenceProfile, RoutingProfileRule]] = []
    for profile in profiles:
        if not profile.enabled:
            continue
        for rule in profile.rules:
            if _matches(
                rule,
                objective=objective,
                work_mode=default_work_mode,
                context=context,
            ):
                candidates.append((profile, rule))
    if not candidates:
        return None

    profile, rule = min(
        candidates,
        key=lambda candidate: (
            -(2 if candidate[0].scope == "workspace" else 1),
            -candidate[1].priority,
            -candidate[1].match.specificity,
            candidate[0].profile_id,
            candidate[1].rule_id,
        ),
    )
    tree = rule.route.skill_tree
    if context.current_phase_id is None:
        current = tree[0]
    else:
        current = next(
            (phase for phase in tree if phase.phase_id == context.current_phase_id),
            None,
        )
        if current is None:
            raise RoutingProfileResolutionError(
                f"current phase {context.current_phase_id!r} is absent from matched profile"
            )
    return ResolvedProfileRoute(
        route_source=f"{profile.scope}-profile",
        profile_id=profile.profile_id,
        applied_profile_ids=(profile.profile_id,),
        profile_digest=profile.profile_digest,
        matched_rule_id=rule.rule_id,
        work_mode=rule.route.work_mode,
        skill_tree=tree,
        current_phase=current,
        current_skill_ids=(current.primary_skill_id, *current.support_skill_ids),
        activation_status="intended-unverified",
    )
