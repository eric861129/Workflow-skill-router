from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import re

from workflow_skill_router.profiles.contract import is_canonical_skill_id
from workflow_skill_router.schemas.artifacts import canonical_json

from .feedback import RouteFeedback
from .models import MemoryMode, MemoryScope
from .observations import MatcherSeed, RouteObservation, RouteObservationPhase
from .policy_resolver import EffectiveMemoryPolicy

PATTERN_SCHEMA_ID = "workflow-skill-router/workflow-pattern"
CANDIDATE_SCHEMA_ID = "workflow-skill-router/workflow-candidate"
SCHEMA_VERSION = "1.0.0"
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_CANDIDATE_STATUSES = (
    "proposed", "approved", "rejected", "expired", "suppressed", "superseded", "auto-promoted",
)
_TARGET_SCOPE = {
    "managed-personal": MemoryScope.PERSONAL,
    "user-personal": MemoryScope.PERSONAL,
    "managed-workspace-local": MemoryScope.WORKSPACE,
    "workspace-file": MemoryScope.WORKSPACE,
}


class CandidateError(ValueError):
    """Raised when candidate evidence or a persisted candidate is invalid."""


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _time(value: datetime | str) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise CandidateError("candidate-time-must-be-aware")
        return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CandidateError("invalid-candidate-time")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise CandidateError("invalid-candidate-time") from error
    return value


@dataclass(frozen=True, slots=True)
class PatternMetrics:
    distinct_runs: int
    distinct_days: int
    completion_rate: float
    required_gate_pass_rate: float
    manual_correction_rate: float
    route_consistency: float
    canonical_skill_ids: bool
    hard_contract_violations: int

    def to_dict(self) -> dict[str, object]:
        return {
            "distinct_runs": self.distinct_runs,
            "distinct_days": self.distinct_days,
            "completion_rate": self.completion_rate,
            "required_gate_pass_rate": self.required_gate_pass_rate,
            "manual_correction_rate": self.manual_correction_rate,
            "route_consistency": self.route_consistency,
            "canonical_skill_ids": self.canonical_skill_ids,
            "hard_contract_violations": self.hard_contract_violations,
        }


@dataclass(frozen=True, slots=True)
class WorkflowPattern:
    pattern_id: str
    scope: MemoryScope
    matcher_seed: MatcherSeed
    work_mode: str
    phases: tuple[RouteObservationPhase, ...]
    workspace_identity_digest: str | None
    profile_source_class: str
    target_profile_class: str
    metrics: PatternMetrics
    material_evidence_digest: str
    observation_ids: tuple[str, ...]
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": PATTERN_SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "artifact_kind": "workflow-pattern",
            "pattern_id": self.pattern_id,
            "scope": self.scope.value,
            "matcher_seed": self.matcher_seed.to_dict(),
            "work_mode": self.work_mode,
            "phases": [item.to_dict() for item in self.phases],
            "workspace_identity_digest": self.workspace_identity_digest,
            "profile_source_class": self.profile_source_class,
            "target_profile_class": self.target_profile_class,
            "metrics": self.metrics.to_dict(),
            "material_evidence_digest": self.material_evidence_digest,
            "observation_ids": list(self.observation_ids),
            "updated_at": self.updated_at,
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True, slots=True)
class WorkflowCandidate:
    candidate_id: str
    candidate_digest: str
    pattern_id: str
    status: str
    recommendation_mode: str
    confidence: str
    scope: MemoryScope
    matcher_seed: MatcherSeed
    work_mode: str
    phases: tuple[RouteObservationPhase, ...]
    workspace_identity_digest: str | None
    profile_source_class: str
    target_profile_class: str
    metrics: PatternMetrics
    material_evidence_digest: str
    policy_digest: str
    reason_codes: tuple[str, ...]
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": CANDIDATE_SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "artifact_kind": "workflow-candidate",
            "candidate_id": self.candidate_id,
            "candidate_digest": self.candidate_digest,
            "pattern_id": self.pattern_id,
            "status": self.status,
            "recommendation_mode": self.recommendation_mode,
            "confidence": self.confidence,
            "scope": self.scope.value,
            "matcher_seed": self.matcher_seed.to_dict(),
            "work_mode": self.work_mode,
            "phases": [item.to_dict() for item in self.phases],
            "workspace_identity_digest": self.workspace_identity_digest,
            "profile_source_class": self.profile_source_class,
            "target_profile_class": self.target_profile_class,
            "metrics": self.metrics.to_dict(),
            "material_evidence_digest": self.material_evidence_digest,
            "policy_digest": self.policy_digest,
            "reason_codes": list(self.reason_codes),
            "created_at": self.created_at,
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


def _candidate_identity(document: Mapping[str, object]) -> tuple[str, str]:
    payload = {
        key: value
        for key, value in document.items()
        if key not in {
            "schema_id", "schema_version", "artifact_kind",
            "candidate_id", "candidate_digest", "status",
        }
    }
    digest = _digest(payload)
    return "candidate:" + digest.removeprefix("sha256:")[:32], digest


def _all_skill_ids(phases: tuple[RouteObservationPhase, ...]) -> Iterable[str]:
    for phase in phases:
        if phase.primary_skill_id is not None:
            yield phase.primary_skill_id
        yield from phase.support_skill_ids


def _material_digest(observations: tuple[RouteObservation, ...], feedback: tuple[RouteFeedback, ...]) -> str:
    ids = {item.observation_id for item in observations}
    document = {
        "observations": [
            {"id": item.observation_id, "digest": item.observation_digest}
            for item in sorted(observations, key=lambda item: item.observation_id)
        ],
        "feedback": [
            {"id": item.feedback_id, "digest": item.feedback_digest}
            for item in sorted(feedback, key=lambda item: item.feedback_id)
            if item.observation_id in ids
        ],
    }
    return _digest(document)


def _metrics(observations: tuple[RouteObservation, ...], feedback: tuple[RouteFeedback, ...]) -> PatternMetrics:
    feedback_by_observation: dict[str, list[RouteFeedback]] = defaultdict(list)
    for item in feedback:
        feedback_by_observation[item.observation_id].append(item)
    count = len(observations)
    days = {item.observed_at[:10] for item in observations}
    route_counts = Counter(item.route_signature_digest for item in observations)

    def has(observation_id: str, kind: str) -> bool:
        return any(item.feedback_type == kind for item in feedback_by_observation[observation_id])

    completion = sum(1 for item in observations if not has(item.observation_id, "abandoned"))
    gates = sum(1 for item in observations if item.required_gates_passed and not has(item.observation_id, "gate-failed"))
    corrections = sum(1 for item in observations if has(item.observation_id, "corrected"))
    canonical = all(is_canonical_skill_id(skill_id) for item in observations for skill_id in _all_skill_ids(item.phases))
    hard = sum(1 for item in observations if item.risk_class == "r3" or item.side_effect_outcome in {"unknown", "known-failure"})
    return PatternMetrics(
        distinct_runs=len({item.workflow_run_digest for item in observations}),
        distinct_days=len(days),
        completion_rate=0.0 if count == 0 else completion / count,
        required_gate_pass_rate=0.0 if count == 0 else gates / count,
        manual_correction_rate=0.0 if count == 0 else corrections / count,
        route_consistency=0.0 if count == 0 else max(route_counts.values(), default=0) / count,
        canonical_skill_ids=canonical,
        hard_contract_violations=hard,
    )


def _group_key(item: RouteObservation) -> str:
    document = {
        "scope": _TARGET_SCOPE[item.target_profile_class].value,
        "matcher_seed": item.matcher_seed.to_dict(),
        "work_mode": item.work_mode,
        "phases": [phase.to_dict() for phase in item.phases],
        "workspace_identity_digest": item.workspace_identity_digest if _TARGET_SCOPE[item.target_profile_class] is MemoryScope.WORKSPACE else None,
        "profile_source_class": item.route_source,
        "target_profile_class": item.target_profile_class,
    }
    return _digest(document)


def _passes(metrics: PatternMetrics, policy: EffectiveMemoryPolicy, mode: str) -> bool:
    e = policy.policy.eligibility
    if mode == "automatic":
        return (
            metrics.distinct_runs >= e.minimum_distinct_runs_automatic
            and metrics.distinct_days >= e.minimum_distinct_days_automatic
            and metrics.completion_rate >= e.minimum_success_rate_automatic
            and metrics.required_gate_pass_rate >= e.minimum_success_rate_automatic
            and metrics.manual_correction_rate <= e.maximum_correction_rate_automatic
            and metrics.route_consistency >= e.minimum_route_consistency_automatic
            and metrics.canonical_skill_ids
            and metrics.hard_contract_violations == 0
        )
    return (
        metrics.distinct_runs >= e.minimum_distinct_runs_reviewed
        and metrics.distinct_days >= e.minimum_distinct_days_reviewed
        and metrics.completion_rate >= e.minimum_success_rate_reviewed
        and metrics.required_gate_pass_rate >= e.minimum_success_rate_reviewed
        and metrics.manual_correction_rate <= e.maximum_correction_rate_reviewed
        and metrics.route_consistency >= e.minimum_route_consistency_reviewed
        and metrics.hard_contract_violations == 0
    )


class CandidateEngine:
    def __init__(self, store, policy: EffectiveMemoryPolicy) -> None:
        self._store = store
        self._policy = policy

    def rebuild(self, scope: MemoryScope, now: datetime | str) -> tuple[WorkflowCandidate, ...]:
        if not isinstance(scope, MemoryScope):
            raise TypeError("scope must be MemoryScope")
        if self._policy.mode in {MemoryMode.DISABLED, MemoryMode.OBSERVE}:
            return ()
        if not self._policy.candidate_generation_enabled:
            return ()
        now_text = _time(now)
        feedback = tuple(self._store.list_route_feedback())
        grouped: dict[str, list[RouteObservation]] = defaultdict(list)
        for item in self._store.list_route_observations():
            if _TARGET_SCOPE.get(item.target_profile_class) is scope:
                grouped[_group_key(item)].append(item)
        emitted: list[WorkflowCandidate] = []
        for key in sorted(grouped):
            observations = tuple(sorted(grouped[key], key=lambda item: (item.observed_at, item.observation_id)))
            metrics = _metrics(observations, feedback)
            material = _material_digest(observations, feedback)
            first = observations[0]
            pattern_doc = {
                "scope": scope.value,
                "matcher_seed": first.matcher_seed.to_dict(),
                "work_mode": first.work_mode,
                "phases": [item.to_dict() for item in first.phases],
                "workspace_identity_digest": first.workspace_identity_digest if scope is MemoryScope.WORKSPACE else None,
                "profile_source_class": first.route_source,
                "target_profile_class": first.target_profile_class,
            }
            pattern_id = "pattern:" + _digest(pattern_doc).removeprefix("sha256:")[:32]
            pattern = WorkflowPattern(
                pattern_id=pattern_id,
                scope=scope,
                matcher_seed=first.matcher_seed,
                work_mode=first.work_mode,
                phases=first.phases,
                workspace_identity_digest=first.workspace_identity_digest if scope is MemoryScope.WORKSPACE else None,
                profile_source_class=first.route_source,
                target_profile_class=first.target_profile_class,
                metrics=metrics,
                material_evidence_digest=material,
                observation_ids=tuple(item.observation_id for item in observations),
                updated_at=now_text,
            )
            self._store.save_workflow_pattern(pattern)

            reviewed = _passes(metrics, self._policy, "reviewed")
            automatic = (
                self._policy.mode is MemoryMode.AUTOMATIC
                and _passes(metrics, self._policy, "automatic")
                and first.automatic_promotion_eligible
                and first.target_profile_class in {"managed-personal", "managed-workspace-local"}
                and first.matcher_seed.source != "user-explicit"
            )
            if not reviewed:
                continue
            if self._store.is_candidate_suppressed(pattern_id, material, now_text):
                continue
            recommendation_mode = "automatic" if automatic else "reviewed"
            confidence = "high" if automatic else "medium"
            reason_codes: tuple[str, ...] = ()
            if first.matcher_seed.source == "user-explicit":
                reason_codes = ("explicit-route-requires-review",)
            candidate_payload = {
                "pattern_id": pattern_id,
                "recommendation_mode": recommendation_mode,
                "confidence": confidence,
                "scope": scope.value,
                "matcher_seed": first.matcher_seed.to_dict(),
                "work_mode": first.work_mode,
                "phases": [item.to_dict() for item in first.phases],
                "workspace_identity_digest": pattern.workspace_identity_digest,
                "profile_source_class": first.route_source,
                "target_profile_class": first.target_profile_class,
                "metrics": metrics.to_dict(),
                "material_evidence_digest": material,
                "policy_digest": self._policy.policy_digest,
                "reason_codes": list(reason_codes),
                "created_at": now_text,
            }
            candidate_id, candidate_digest = _candidate_identity(candidate_payload)
            candidate = WorkflowCandidate(
                candidate_id=candidate_id,
                candidate_digest=candidate_digest,
                pattern_id=pattern_id,
                status="proposed",
                recommendation_mode=recommendation_mode,
                confidence=confidence,
                scope=scope,
                matcher_seed=first.matcher_seed,
                work_mode=first.work_mode,
                phases=first.phases,
                workspace_identity_digest=pattern.workspace_identity_digest,
                profile_source_class=first.route_source,
                target_profile_class=first.target_profile_class,
                metrics=metrics,
                material_evidence_digest=material,
                policy_digest=self._policy.policy_digest,
                reason_codes=reason_codes,
                created_at=now_text,
            )
            stored = self._store.save_workflow_candidate(candidate)
            emitted.append(stored)
        return tuple(emitted)


def automatic_promotion_reason_codes(
    candidate: WorkflowCandidate,
    policy: EffectiveMemoryPolicy,
) -> tuple[str, ...]:
    """Return stable fail-closed reasons for one M3-B automatic promotion."""

    if not isinstance(candidate, WorkflowCandidate):
        raise TypeError("candidate must be WorkflowCandidate")
    if not isinstance(policy, EffectiveMemoryPolicy):
        raise TypeError("policy must be EffectiveMemoryPolicy")
    reasons: list[str] = []
    if policy.mode is not MemoryMode.AUTOMATIC:
        reasons.append("memory-mode-not-automatic")
    if policy.profile_promotion != "automatic-managed":
        reasons.append("automatic-promotion-disabled")
    if candidate.status != "proposed":
        reasons.append("candidate-not-proposed")
    if candidate.policy_digest != policy.policy_digest:
        reasons.append("candidate-policy-drift")
    if candidate.target_profile_class not in {
        "managed-personal", "managed-workspace-local"
    }:
        reasons.append("automatic-user-profile-write-forbidden")
    elif candidate.target_profile_class not in policy.allowed_targets:
        reasons.append("profile-target-not-allowed")
    if candidate.recommendation_mode != "automatic":
        reasons.append("candidate-not-automatic")
    if candidate.confidence != "high":
        reasons.append("candidate-confidence-not-high")
    if (
        candidate.matcher_seed.source == "user-explicit"
        or candidate.profile_source_class == "user-explicit"
    ):
        reasons.append("candidate-explicit-route")
    actual_canonical = all(
        is_canonical_skill_id(skill_id)
        for skill_id in _all_skill_ids(candidate.phases)
    )
    if not candidate.metrics.canonical_skill_ids or not actual_canonical:
        reasons.append("candidate-skill-id-invalid")
    if candidate.metrics.hard_contract_violations != 0:
        reasons.append("candidate-hard-violation")
    if not _passes(candidate.metrics, policy, "automatic"):
        reasons.append("insufficient-evidence")

    eligibility = policy.policy.eligibility
    if (
        not eligibility.require_terminal_success
        or not eligibility.require_required_gate_pass
        or not eligibility.reject_unknown_side_effects
        or "r3" not in eligibility.exclude_risk_levels
        or eligibility.minimum_distinct_runs_automatic < 5
        or eligibility.minimum_distinct_days_automatic < 3
        or eligibility.minimum_success_rate_automatic < 0.90
        or eligibility.maximum_correction_rate_automatic > 0.10
        or eligibility.minimum_route_consistency_automatic < 0.85
    ):
        reasons.append("automatic-threshold-weaker")
    features = policy.policy.features
    if (
        not features.candidate_generation.backtest_required
        or not features.profile_promotion.require_backtest
    ):
        reasons.append("backtest-required")
    if not features.profile_promotion.require_profile_lint:
        reasons.append("profile-lint-required")
    if features.profile_versioning.mode != "required":
        reasons.append("profile-versioning-required")
    return tuple(dict.fromkeys(reasons))


def _decode_matcher(value: object) -> MatcherSeed:
    if not isinstance(value, Mapping):
        raise CandidateError("invalid-candidate-matcher")
    try:
        return MatcherSeed(
            tuple(value["objective_keywords"]),
            tuple(value["domains"]),
            tuple(value["tags"]),
            str(value["source"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise CandidateError("invalid-candidate-matcher") from error


def _decode_phase(value: object) -> RouteObservationPhase:
    if not isinstance(value, Mapping):
        raise CandidateError("invalid-candidate-phase")
    try:
        return RouteObservationPhase(
            str(value["phase_id"]),
            value["primary_skill_id"] if value["primary_skill_id"] is None else str(value["primary_skill_id"]),
            tuple(value["support_skill_ids"]),
            tuple(value["exit_gate_ids"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise CandidateError("invalid-candidate-phase") from error


def _decode_metrics(value: object) -> PatternMetrics:
    if not isinstance(value, Mapping):
        raise CandidateError("invalid-candidate-metrics")
    try:
        return PatternMetrics(
            distinct_runs=int(value["distinct_runs"]),
            distinct_days=int(value["distinct_days"]),
            completion_rate=float(value["completion_rate"]),
            required_gate_pass_rate=float(value["required_gate_pass_rate"]),
            manual_correction_rate=float(value["manual_correction_rate"]),
            route_consistency=float(value["route_consistency"]),
            canonical_skill_ids=bool(value["canonical_skill_ids"]),
            hard_contract_violations=int(value["hard_contract_violations"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise CandidateError("invalid-candidate-metrics") from error


def decode_workflow_candidate(value: object) -> WorkflowCandidate:
    if not isinstance(value, Mapping):
        raise CandidateError("invalid-candidate-document")
    required = {
        "schema_id", "schema_version", "artifact_kind", "candidate_id", "candidate_digest", "pattern_id",
        "status", "recommendation_mode", "confidence", "scope", "matcher_seed", "work_mode", "phases",
        "workspace_identity_digest", "profile_source_class", "target_profile_class", "metrics",
        "material_evidence_digest", "policy_digest", "reason_codes", "created_at",
    }
    if set(value) != required:
        raise CandidateError("candidate-fields-mismatch")
    if value["schema_id"] != CANDIDATE_SCHEMA_ID or value["schema_version"] != SCHEMA_VERSION or value["artifact_kind"] != "workflow-candidate":
        raise CandidateError("candidate-schema-mismatch")
    status = str(value["status"])
    if status not in _CANDIDATE_STATUSES:
        raise CandidateError("invalid-candidate-status")
    scope = MemoryScope(str(value["scope"]))
    phases = tuple(_decode_phase(item) for item in value["phases"])
    metrics = _decode_metrics(value["metrics"])
    candidate = WorkflowCandidate(
        candidate_id=str(value["candidate_id"]), candidate_digest=str(value["candidate_digest"]), pattern_id=str(value["pattern_id"]),
        status=status, recommendation_mode=str(value["recommendation_mode"]), confidence=str(value["confidence"]), scope=scope,
        matcher_seed=_decode_matcher(value["matcher_seed"]), work_mode=str(value["work_mode"]), phases=phases,
        workspace_identity_digest=None if value["workspace_identity_digest"] is None else str(value["workspace_identity_digest"]),
        profile_source_class=str(value["profile_source_class"]), target_profile_class=str(value["target_profile_class"]), metrics=metrics,
        material_evidence_digest=str(value["material_evidence_digest"]), policy_digest=str(value["policy_digest"]),
        reason_codes=tuple(value["reason_codes"]), created_at=_time(str(value["created_at"])),
    )
    for digest in (candidate.candidate_digest, candidate.material_evidence_digest, candidate.policy_digest):
        if _DIGEST.fullmatch(digest) is None:
            raise CandidateError("invalid-candidate-digest")
    _, expected_digest = _candidate_identity(candidate.to_dict())
    if expected_digest != candidate.candidate_digest:
        raise CandidateError("candidate-digest-mismatch")
    return candidate


def candidate_with_status(candidate: WorkflowCandidate, status: str) -> WorkflowCandidate:
    if status not in _CANDIDATE_STATUSES:
        raise CandidateError("invalid-candidate-status")
    return replace(candidate, status=status)


__all__ = [
    "CandidateEngine", "CandidateError", "PatternMetrics", "WorkflowCandidate", "WorkflowPattern",
    "automatic_promotion_reason_codes", "candidate_with_status", "decode_workflow_candidate",
]
