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


@dataclass(frozen=True, slots=True)
class ProfileRuleTrace:
    rule_id: str
    matched: bool
    matched_dimensions: tuple[str, ...]
    unmatched_dimensions: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "matched": self.matched,
            "matched_dimensions": list(self.matched_dimensions),
            "unmatched_dimensions": list(self.unmatched_dimensions),
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class ProfileLintIssue:
    severity: str
    code: str
    message: str
    rule_id: str | None = None
    related_rule_id: str | None = None
    phase_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        for key, item in (
            ("rule_id", self.rule_id),
            ("related_rule_id", self.related_rule_id),
            ("phase_id", self.phase_id),
        ):
            if item is not None:
                value[key] = item
        return value


_LEXICAL_ALIAS_GROUPS = (
    ("api", "應用程式介面"),
)


def _match_trace(
    rule: RoutingProfileRule,
    *,
    objective: str,
    work_mode: str,
    context: RoutingMatchContext,
) -> ProfileRuleTrace:
    matcher = rule.match
    matched_dimensions: list[str] = []
    unmatched_dimensions: list[str] = []
    reason_codes: list[str] = []

    objective_folded = objective.casefold()
    checks = (
        (
            "objective_keywords",
            bool(matcher.objective_keywords),
            any(
                keyword.casefold() in objective_folded
                for keyword in matcher.objective_keywords
            ),
            "objective-keyword-miss",
        ),
        (
            "domains",
            bool(matcher.domains),
            bool(set(matcher.domains).intersection(context.domains)),
            "domain-miss",
        ),
        (
            "tags",
            bool(matcher.tags),
            bool(set(matcher.tags).intersection(context.tags)),
            "tag-miss",
        ),
        (
            "work_modes",
            bool(matcher.work_modes) or context.lock_work_mode,
            (
                (not matcher.work_modes or work_mode in matcher.work_modes)
                and (
                    not context.lock_work_mode
                    or rule.route.work_mode == work_mode
                )
            ),
            "work-mode-miss",
        ),
    )
    for dimension, active, matched, reason_code in checks:
        if not active:
            continue
        if matched:
            matched_dimensions.append(dimension)
        else:
            unmatched_dimensions.append(dimension)
            reason_codes.append(reason_code)
    return ProfileRuleTrace(
        rule_id=rule.rule_id,
        matched=not unmatched_dimensions,
        matched_dimensions=tuple(matched_dimensions),
        unmatched_dimensions=tuple(unmatched_dimensions),
        reason_codes=tuple(reason_codes),
    )


def _matches(
    rule: RoutingProfileRule,
    *,
    objective: str,
    work_mode: str,
    context: RoutingMatchContext,
) -> bool:
    return _match_trace(
        rule,
        objective=objective,
        work_mode=work_mode,
        context=context,
    ).matched


def explain_profile_route(
    profiles: tuple[RoutingPreferenceProfile, ...],
    *,
    objective: str,
    default_work_mode: str,
    context: RoutingMatchContext,
) -> tuple[ProfileRuleTrace, ...]:
    """Return deterministic rule evaluations without echoing sensitive inputs."""

    return tuple(
        _match_trace(
            rule,
            objective=objective,
            work_mode=default_work_mode,
            context=context,
        )
        for profile in profiles
        if profile.enabled
        for rule in profile.rules
    )


def _match_values_cover(
    higher: tuple[str, ...],
    lower: tuple[str, ...],
) -> bool:
    if not higher:
        return True
    if not lower:
        return False
    return set(lower).issubset(higher)


def _objective_keywords_cover(
    higher: tuple[str, ...],
    lower: tuple[str, ...],
) -> bool:
    if not higher:
        return True
    if not lower:
        return False
    return all(
        any(
            higher_keyword.casefold() in lower_keyword.casefold()
            for higher_keyword in higher
        )
        for lower_keyword in lower
    )


def _rule_covers(higher: RoutingProfileRule, lower: RoutingProfileRule) -> bool:
    if higher.route.work_mode != lower.route.work_mode:
        return False
    return (
        _objective_keywords_cover(
            higher.match.objective_keywords,
            lower.match.objective_keywords,
        )
        and _match_values_cover(higher.match.domains, lower.match.domains)
        and _match_values_cover(higher.match.tags, lower.match.tags)
        and _match_values_cover(higher.match.work_modes, lower.match.work_modes)
    )


def _rules_can_overlap(left: RoutingProfileRule, right: RoutingProfileRule) -> bool:
    left_modes = set(left.match.work_modes)
    right_modes = set(right.match.work_modes)
    return not left_modes or not right_modes or bool(left_modes.intersection(right_modes))


def _rule_rank(rule: RoutingProfileRule) -> tuple[int, int, str]:
    return (-rule.priority, -rule.match.specificity, rule.rule_id)


def lint_profile(
    profile: RoutingPreferenceProfile,
    *,
    current_phase_id: str | None = None,
) -> tuple[ProfileLintIssue, ...]:
    """Check deterministic routing ambiguities without changing schema or matching."""

    issues: list[ProfileLintIssue] = []
    for index, left in enumerate(profile.rules):
        for right in profile.rules[index + 1:]:
            if left.match == right.match and left.route == right.route:
                issues.append(ProfileLintIssue(
                    severity="error",
                    code="duplicate-rule",
                    message=(
                        f"rule {right.rule_id!r} duplicates rule {left.rule_id!r}"
                    ),
                    rule_id=right.rule_id,
                    related_rule_id=left.rule_id,
                ))
                continue
            if (
                left.priority == right.priority
                and left.match.specificity == right.match.specificity
                and left.route != right.route
                and _rules_can_overlap(left, right)
            ):
                issues.append(ProfileLintIssue(
                    severity="error",
                    code="equal-rank-conflict",
                    message=(
                        f"rules {left.rule_id!r} and {right.rule_id!r} can match "
                        "with equal priority and specificity"
                    ),
                    rule_id=left.rule_id,
                    related_rule_id=right.rule_id,
                ))
                continue
            higher, lower = sorted((left, right), key=_rule_rank)
            if _rule_covers(higher, lower):
                issues.append(ProfileLintIssue(
                    severity="error",
                    code="shadowed-rule",
                    message=(
                        f"rule {lower.rule_id!r} is permanently shadowed by "
                        f"rule {higher.rule_id!r}"
                    ),
                    rule_id=lower.rule_id,
                    related_rule_id=higher.rule_id,
                ))

    for rule in profile.rules:
        if rule.route.work_mode == "phased" and current_phase_id is not None:
            phase_ids = {phase.phase_id for phase in rule.route.skill_tree}
            if current_phase_id not in phase_ids:
                issues.append(ProfileLintIssue(
                    severity="error",
                    code="missing-current-phase",
                    message=(
                        f"phased rule {rule.rule_id!r} does not contain current phase "
                        f"{current_phase_id!r}"
                    ),
                    rule_id=rule.rule_id,
                    phase_id=current_phase_id,
                ))
        for phase in rule.route.skill_tree:
            if phase.primary_skill_id in phase.support_skill_ids:
                issues.append(ProfileLintIssue(
                    severity="error",
                    code="same-primary-support-skill",
                    message=(
                        f"phase {phase.phase_id!r} uses the same primary and support SKILL"
                    ),
                    rule_id=rule.rule_id,
                    phase_id=phase.phase_id,
                ))

        keywords = {keyword.casefold() for keyword in rule.match.objective_keywords}
        for aliases in _LEXICAL_ALIAS_GROUPS:
            folded_aliases = {alias.casefold() for alias in aliases}
            if keywords.intersection(folded_aliases) and not folded_aliases.issubset(keywords):
                omitted = [
                    alias
                    for alias in aliases
                    if alias.casefold() not in keywords
                ]
                issues.append(ProfileLintIssue(
                    severity="advisory",
                    code="lexical-alias-omission",
                    message=(
                        f"rule {rule.rule_id!r} omits common lexical alias(es): "
                        + ", ".join(omitted)
                    ),
                    rule_id=rule.rule_id,
                ))

    return tuple(issues)


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
