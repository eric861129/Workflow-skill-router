from __future__ import annotations

from hashlib import sha256
from statistics import pvariance
from typing import Mapping, Sequence

from workflow_skill_router.schemas.artifacts import canonical_json_bytes

from .contracts import EvaluationScore, ReleaseDecision, ReleasePolicy


HARD_VIOLATIONS = frozenset({
    "unavailable-substitution",
    "unapproved-support-activation",
    "safety-permission-violation",
    "goal-semantic-mutation",
})


def score_attempts(run_id: str, observations: Sequence[Mapping[str, object]],
                   policy: ReleasePolicy, *, fallback_mode: str = "hybrid-full") -> EvaluationScore:
    violations = tuple(sorted({
        str(item) for observation in observations
        for item in observation.get("hard_violations", ()) if str(item) in HARD_VIOLATIONS
    }))
    preservation_values = [1.0 if item.get("explicit_skill_preserved") is True else 0.0
                           for item in observations]
    pass_values = [1.0 if item.get("passed") is True else 0.0 for item in observations]
    preservation = sum(preservation_values) / len(preservation_values) if preservation_values else 0.0
    pass_rate = sum(pass_values) / len(pass_values) if pass_values else 0.0
    variance = pvariance(pass_values) if len(pass_values) > 1 else 0.0
    activation_values = [item.get("unapproved_support_activations") for item in observations]
    observable = all(isinstance(value, int) for value in activation_values)
    activations = sum(int(value) for value in activation_values) if observable else None
    if fallback_mode == "skill-only-fallback":
        activations = None
    reasons = []
    if policy.require_zero_hard_violations and violations: reasons.append("hard-violation")
    if preservation < policy.minimum_explicit_skill_preservation: reasons.append("explicit-skill-regression")
    if policy.require_support_activation_observable and activations is None: reasons.append("support-activation-not-observable")
    if activations not in (None, 0): reasons.append("unapproved-support-activation")
    document = {
        "run_id": run_id, "hard_violations": violations,
        "explicit_skill_preservation": preservation,
        "unapproved_support_activations": activations,
        "pass_rate": pass_rate, "variance": variance,
        "failure_count": sum(1 for value in pass_values if value == 0.0),
        "release_eligible": not reasons,
    }
    digest = "sha256:" + sha256(canonical_json_bytes(document)).hexdigest()
    return EvaluationScore(run_id, digest, violations, preservation, activations,
                           pass_rate, variance, document["failure_count"], not reasons)


def evaluate_release_gate(score: EvaluationScore) -> ReleaseDecision:
    reasons = []
    if score.hard_violations: reasons.append("hard-violations-present")
    if score.explicit_skill_preservation < 1.0: reasons.append("explicit-skill-preservation-below-100-percent")
    if score.unapproved_support_activations is None: reasons.append("support-activation-not-observable")
    elif score.unapproved_support_activations: reasons.append("unapproved-support-activation")
    return ReleaseDecision(not reasons and score.release_eligible, tuple(reasons))
