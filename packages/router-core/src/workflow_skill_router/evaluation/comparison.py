from __future__ import annotations

from .contracts import EvaluationComparison, EvaluationScore


def compare_scores(baseline: EvaluationScore, candidate: EvaluationScore,
                   *, baseline_case_ids: tuple[str, ...], candidate_case_ids: tuple[str, ...]) -> EvaluationComparison:
    if baseline_case_ids != candidate_case_ids:
        raise ValueError("paired_manifest_mismatch")
    return EvaluationComparison(
        baseline.run_id, candidate.run_id, len(candidate_case_ids),
        candidate.pass_rate - baseline.pass_rate,
        len(candidate.hard_violations) - len(baseline.hard_violations),
        candidate.release_eligible,
    )
