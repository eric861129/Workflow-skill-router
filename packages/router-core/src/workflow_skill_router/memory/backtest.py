from __future__ import annotations

from dataclasses import dataclass
import hashlib

from workflow_skill_router.profiles.contract import RoutingPreferenceProfile
from workflow_skill_router.profiles.resolver import RoutingMatchContext, lint_profile, resolve_profile_route
from workflow_skill_router.schemas.artifacts import canonical_json

from .candidates import WorkflowCandidate
from .observations import RouteObservation


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _same_pattern(observation: RouteObservation, candidate: WorkflowCandidate) -> bool:
    workspace = observation.workspace_identity_digest if candidate.scope.value == "workspace" else None
    return (
        observation.matcher_seed == candidate.matcher_seed
        and observation.work_mode == candidate.work_mode
        and observation.phases == candidate.phases
        and workspace == candidate.workspace_identity_digest
        and observation.target_profile_class == candidate.target_profile_class
    )


def _matches(profile: RoutingPreferenceProfile, observation: RouteObservation) -> bool:
    objective = " ".join(observation.matcher_seed.objective_keywords)
    result = resolve_profile_route(
        (profile,),
        objective=objective,
        default_work_mode=observation.work_mode,
        context=RoutingMatchContext(
            domains=observation.matcher_seed.domains,
            tags=observation.matcher_seed.tags,
            lock_work_mode=True,
        ),
    )
    return result is not None


@dataclass(frozen=True, slots=True)
class BacktestSummary:
    positive_observation_count: int
    positive_match_count: int
    positive_match_coverage: float
    unexpected_match_count: int
    shadowed_rule_ids: tuple[str, ...]
    equal_rank_conflicts: tuple[str, ...]
    manual_precedence: bool
    manual_profile_digests: tuple[str, ...]
    capability_gap_summary: str
    planned_route_regressions: int
    workspace_isolation: bool
    acceptable: bool
    backtest_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "positive_observation_count": self.positive_observation_count,
            "positive_match_count": self.positive_match_count,
            "positive_match_coverage": self.positive_match_coverage,
            "unexpected_match_count": self.unexpected_match_count,
            "shadowed_rule_ids": list(self.shadowed_rule_ids),
            "equal_rank_conflicts": list(self.equal_rank_conflicts),
            "manual_precedence": self.manual_precedence,
            "manual_profile_digests": list(self.manual_profile_digests),
            "capability_gap_summary": self.capability_gap_summary,
            "planned_route_regressions": self.planned_route_regressions,
            "workspace_isolation": self.workspace_isolation,
            "acceptable": self.acceptable,
            "backtest_digest": self.backtest_digest,
        }


def backtest_profile_update(
    current_profiles: tuple[RoutingPreferenceProfile, ...],
    proposed_profile: RoutingPreferenceProfile,
    observations: tuple[RouteObservation, ...],
    candidate: WorkflowCandidate,
    *,
    manual_profiles: tuple[RoutingPreferenceProfile, ...] | None = None,
) -> BacktestSummary:
    positives = tuple(item for item in observations if _same_pattern(item, candidate))
    positive_matches = sum(1 for item in positives if _matches(proposed_profile, item))
    unexpected = sum(1 for item in observations if item not in positives and _matches(proposed_profile, item))
    issues = lint_profile(proposed_profile)
    shadowed = tuple(sorted({item.rule_id for item in issues if item.code == "shadowed-rule" and item.rule_id is not None}))
    equal = tuple(sorted({item.rule_id for item in issues if item.code == "equal-rank-conflict" and item.rule_id is not None}))
    protected_profiles = current_profiles if manual_profiles is None else manual_profiles
    manual_profile_digests = tuple(
        sorted({profile.profile_digest for profile in protected_profiles})
    )
    manual_precedence = False
    for item in positives:
        objective = " ".join(item.matcher_seed.objective_keywords)
        existing = resolve_profile_route(
            protected_profiles,
            objective=objective,
            default_work_mode=item.work_mode,
            context=RoutingMatchContext(domains=item.matcher_seed.domains, tags=item.matcher_seed.tags, lock_work_mode=True),
        ) if protected_profiles else None
        if existing is not None:
            manual_precedence = True
            break
    workspace_isolation = all(
        candidate.scope.value != "workspace" or item.workspace_identity_digest == candidate.workspace_identity_digest
        for item in positives
    )
    coverage = 0.0 if not positives else positive_matches / len(positives)
    acceptable = bool(positives) and coverage == 1.0 and unexpected == 0 and not shadowed and not equal and workspace_isolation
    base = {
        "positive_observation_count": len(positives),
        "positive_match_count": positive_matches,
        "positive_match_coverage": coverage,
        "unexpected_match_count": unexpected,
        "shadowed_rule_ids": list(shadowed),
        "equal_rank_conflicts": list(equal),
        "manual_precedence": manual_precedence,
        "manual_profile_digests": list(manual_profile_digests),
        "capability_gap_summary": "unavailable",
        "planned_route_regressions": 0,
        "workspace_isolation": workspace_isolation,
        "acceptable": acceptable,
    }
    return BacktestSummary(
        len(positives), positive_matches, coverage, unexpected, shadowed, equal,
        manual_precedence, manual_profile_digests, "unavailable", 0,
        workspace_isolation, acceptable, _digest(base),
    )


__all__ = ["BacktestSummary", "backtest_profile_update"]
