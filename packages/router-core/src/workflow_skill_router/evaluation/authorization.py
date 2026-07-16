from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping

from workflow_skill_router.schemas.artifacts import canonical_json_bytes
from workflow_skill_router.service_models import RequestContext

from .contracts import EvalRunAuthorization, EvaluationProfile


class EvaluationAuthorizationError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class EvalRunRequest:
    profile: EvaluationProfile
    adapter_kind: str
    suite_digest: str
    repeats: int = 3


class EvaluationAuthorizer:
    """簽發並保存 server-owned authorization；client 只能持有 opaque ref。"""

    def __init__(self) -> None:
        self._records: dict[str, EvalRunAuthorization] = {}

    def issue_run(self, context: RequestContext, request: EvalRunRequest) -> str:
        if request.repeats < 1 or request.repeats > 20:
            raise EvaluationAuthorizationError("repeat_count_invalid")
        identity = {
            "session_id": context.session_id,
            "actor": context.actor,
            "runtime_policy_snapshot_id": context.runtime_policy_snapshot_id,
            "profile": request.profile.value,
            "adapter_kind": request.adapter_kind,
            "suite_digest": request.suite_digest,
        }
        ref = "evalauth:" + sha256(canonical_json_bytes(identity)).hexdigest()
        self._records[ref] = EvalRunAuthorization(ref, context.session_id, context.actor,
            context.runtime_policy_snapshot_id, request.profile, request.adapter_kind,
            request.suite_digest)
        return ref

    def validate_run(self, context: RequestContext, ref: str, request: EvalRunRequest) -> EvalRunAuthorization:
        record = self._records.get(ref)
        if record is None:
            raise EvaluationAuthorizationError("authorization_missing")
        if (record.session_id, record.actor, record.runtime_policy_snapshot_id) != (
            context.session_id, context.actor, context.runtime_policy_snapshot_id,
        ):
            raise EvaluationAuthorizationError("request_context_mismatch")
        if (record.profile, record.adapter_kind, record.suite_digest) != (
            request.profile, request.adapter_kind, request.suite_digest,
        ):
            raise EvaluationAuthorizationError("authorization_widening")
        return record
