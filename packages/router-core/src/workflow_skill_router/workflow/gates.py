from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GateCheck:
    check_type: str
    mandatory: bool
    passed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class GateEvaluationRequest:
    workflow_run_id: str
    phase_id: str
    expected_state_version: int
    expected_plan_revision: int
    expected_evidence_digest: str
    actual_state_version: int
    actual_plan_revision: int
    actual_evidence_digest: str
    checks: tuple[GateCheck, ...]


@dataclass(frozen=True, slots=True)
class GateEvaluationResult:
    status: str
    passed: bool
    mandatory_failures: tuple[str, ...]
    evidence_digest: str


class GateEvaluator:
    def evaluate(self, request: GateEvaluationRequest) -> GateEvaluationResult:
        if (
            request.expected_state_version != request.actual_state_version
            or request.expected_plan_revision != request.actual_plan_revision
            or request.expected_evidence_digest != request.actual_evidence_digest
        ):
            return GateEvaluationResult(
                "conflict",
                False,
                ("state、plan 或 evidence 已變更",),
                request.actual_evidence_digest,
            )
        failures = tuple(
            check.reason
            for check in request.checks
            if check.mandatory and not check.passed
        )
        return GateEvaluationResult(
            "evaluated",
            not failures,
            failures,
            request.actual_evidence_digest,
        )

