from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Protocol


class EvaluationStatus(StrEnum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    MANUAL_REQUIRED = "manual-required"
    UNSUPPORTED = "unsupported"
    COMPLETED = "completed"
    INVALID = "invalid"


class EvaluationProfile(StrEnum):
    CONTRACT = "contract"
    BEHAVIOR = "behavior"
    OUTCOME = "outcome"


class EvaluationExecutionMode(StrEnum):
    MODEL_ONLY = "model-only"
    HYBRID_ROUTER = "hybrid-router"


@dataclass(frozen=True, slots=True)
class ModelExecutionPayload:
    opaque_run_case_id: str
    prompt: str
    profile: EvaluationProfile
    allowed_tools: tuple[str, ...]
    execution_mode: EvaluationExecutionMode = EvaluationExecutionMode.MODEL_ONLY


@dataclass(frozen=True, slots=True)
class InteractionDriverSpec:
    opaque_run_case_id: str
    replies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScoringSpec:
    opaque_run_case_id: str
    scoring_spec_hash: str
    expected_envelope: str
    hard_invariants: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScoringKey:
    opaque_run_case_id: str
    execution_payload_hash: str
    driver_package_hash: str
    scoring_spec_hash: str


@dataclass(frozen=True, slots=True)
class SealingRoots:
    execution_root: Path
    driver_root: Path
    scoring_root: Path


@dataclass(frozen=True, slots=True)
class SealedCasePaths:
    opaque_run_case_id: str
    execution_dir: Path
    driver_dir: Path
    scoring_dir: Path
    execution_payload: Path
    execution_manifest: Path
    driver_package: Path
    driver_manifest: Path
    scoring_package: Path
    scoring_key: Path

    @classmethod
    def under_distinct_roots(cls, roots: SealingRoots, opaque_id: str) -> "SealedCasePaths":
        resolved = tuple(path.resolve() for path in (
            roots.execution_root, roots.driver_root, roots.scoring_root,
        ))
        if len(set(resolved)) != 3 or any(
            left in right.parents or right in left.parents
            for index, left in enumerate(resolved)
            for right in resolved[index + 1:]
        ):
            raise EvaluationIntegrityError("sealing_roots_not_disjoint")
        execution, driver, scoring = (root / opaque_id for root in resolved)
        return cls(
            opaque_id, execution, driver, scoring,
            execution / "payload.json", execution / "execution-manifest.json",
            driver / "driver.json", driver / "driver-manifest.json",
            scoring / "scoring.json", scoring / "scoring-key.json",
        )


class EvaluationIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ModelTurnRequest:
    attempt_nonce: str
    turn_index: int
    prompt: str
    allowed_tools: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AdapterSelection:
    kind: str
    status: EvaluationStatus
    evidence_class: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class EvalRunAuthorization:
    authorization_ref: str
    session_id: str
    actor: str
    runtime_policy_snapshot_id: str
    profile: EvaluationProfile
    adapter_kind: str
    suite_digest: str


@dataclass(frozen=True, slots=True)
class EvaluationAttempt:
    attempt_id: str
    fresh_context_id: str
    status: EvaluationStatus
    trace: tuple[Mapping[str, Any], ...]
    raw_trace_digest: str
    failure: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationRunResult:
    run_id: str
    status: EvaluationStatus
    profile: EvaluationProfile
    adapter_kind: str
    attempts: tuple[EvaluationAttempt, ...]
    manifest_digest: str
    evidence_class: str


class ExecutionAdapter(Protocol):
    kind: str
    def start_attempt(self, payload: ModelExecutionPayload, attempt_nonce: str) -> str: ...
    def execute_turn(self, request: ModelTurnRequest) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class ReleasePolicy:
    require_zero_hard_violations: bool = True
    minimum_explicit_skill_preservation: float = 1.0
    require_support_activation_observable: bool = True


@dataclass(frozen=True, slots=True)
class EvaluationScore:
    run_id: str
    score_digest: str
    hard_violations: tuple[str, ...]
    explicit_skill_preservation: float
    unapproved_support_activations: int | None
    pass_rate: float
    variance: float
    failure_count: int
    release_eligible: bool


@dataclass(frozen=True, slots=True)
class ReleaseDecision:
    allowed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvaluationComparison:
    baseline_run_id: str
    candidate_run_id: str
    paired_count: int
    pass_rate_difference: float
    hard_violation_difference: int
    candidate_release_eligible: bool
