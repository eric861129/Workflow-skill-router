from __future__ import annotations

from hashlib import sha256
from typing import Callable, Mapping, Sequence

from workflow_skill_router.schemas.artifacts import canonical_json_bytes

from .contracts import (
    EvaluationAttempt, EvaluationProfile, EvaluationRunResult, EvaluationStatus,
    ModelExecutionPayload, ModelTurnRequest,
)


def run_evaluation(
    payload: ModelExecutionPayload,
    driver_replies: Sequence[str],
    adapter,
    *,
    repeats: int,
    id_factory: Callable[[], str],
) -> EvaluationRunResult:
    if payload.profile in (EvaluationProfile.BEHAVIOR, EvaluationProfile.OUTCOME) and repeats < 3:
        raise ValueError("behavior/outcome evaluation 至少需要三次 attempt")
    attempts = []
    for _ in range(repeats):
        attempt_id = id_factory()
        nonce = "nonce:" + attempt_id
        fresh_context_id = adapter.start_attempt(payload, nonce)
        trace: list[Mapping[str, object]] = []
        prompts = (payload.prompt, *driver_replies)
        failure = None
        try:
            for index, prompt in enumerate(prompts):
                response = adapter.execute_turn(ModelTurnRequest(nonce, index, prompt, payload.allowed_tools))
                trace.append({"turn_index": index, "response": dict(response)})
            status = EvaluationStatus.COMPLETED
        except Exception as error:
            status = EvaluationStatus.INVALID
            failure = type(error).__name__
        raw_digest = "sha256:" + sha256(canonical_json_bytes({"trace": trace})).hexdigest()
        attempts.append(EvaluationAttempt(attempt_id, fresh_context_id, status, tuple(trace), raw_digest, failure))
    manifest = {
        "opaque_run_case_id": payload.opaque_run_case_id,
        "profile": payload.profile.value,
        "adapter_kind": adapter.kind,
        "attempts": [{"attempt_id": a.attempt_id, "fresh_context_id": a.fresh_context_id,
                      "status": a.status.value, "raw_trace_digest": a.raw_trace_digest} for a in attempts],
    }
    manifest_digest = "sha256:" + sha256(canonical_json_bytes(manifest)).hexdigest()
    result_status = EvaluationStatus.COMPLETED if all(
        item.status is EvaluationStatus.COMPLETED for item in attempts
    ) else EvaluationStatus.INVALID
    return EvaluationRunResult("run:" + id_factory(), result_status, payload.profile, adapter.kind,
                               tuple(attempts), manifest_digest, "fresh-model-execution")
