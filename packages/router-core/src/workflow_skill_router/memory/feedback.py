from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re

from workflow_skill_router.schemas.artifacts import canonical_json

from .observations import RouteObservation
from .store import MemoryPolicySnapshot
from .workflow_reader import MemoryRequestContext


FEEDBACK_SCHEMA_ID = "workflow-skill-router/route-feedback"
FEEDBACK_SCHEMA_VERSION = "1.0.0"
FEEDBACK_ARTIFACT_KIND = "route-feedback"
FEEDBACK_TYPES = (
    "accepted",
    "corrected",
    "rejected",
    "support-rejected",
    "capability-unavailable",
    "gate-failed",
    "completed",
    "abandoned",
    "no-memory",
)
CORRECTION_DIMENSIONS = (
    "work-mode",
    "phase-order",
    "primary-skill",
    "support-skill",
    "exit-gate",
    "matcher",
    "target",
)
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_CODE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_TOP_FIELDS = frozenset({
    "schema_id",
    "schema_version",
    "artifact_kind",
    "feedback_id",
    "feedback_digest",
    "observation_id",
    "observation_digest",
    "workflow_run_digest",
    "policy_snapshot_id",
    "policy_digest",
    "feedback_type",
    "reason_code",
    "correction_dimensions",
    "original_route_digest",
    "corrected_route_digest",
    "free_text",
    "session_digest",
    "actor_digest",
    "recorded_at",
})


class RouteFeedbackError(ValueError):
    """Raised when route feedback violates the strict local contract."""


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _context_digest(kind: str, value: str) -> str:
    return _digest({kind: value})


def _validate_digest(value: object, field: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise RouteFeedbackError(f"invalid-feedback-digest:{field}")
    return value


def _validate_recorded_at(value: object) -> str:
    if not isinstance(value, str) or not value.endswith("Z") or len(value) > 40:
        raise RouteFeedbackError("invalid-feedback-recorded-at")
    try:
        instant = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise RouteFeedbackError("invalid-feedback-recorded-at") from error
    if instant.tzinfo is None or instant.utcoffset() != timezone.utc.utcoffset(instant):
        raise RouteFeedbackError("invalid-feedback-recorded-at")
    return value


def _validate_free_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 2000:
        raise RouteFeedbackError("invalid-feedback-free-text")
    if any(ord(character) < 32 and character not in "\n\r\t" for character in value):
        raise RouteFeedbackError("invalid-feedback-free-text")
    return value


@dataclass(frozen=True, slots=True)
class RecordRouteFeedbackCommand:
    context: MemoryRequestContext
    workflow_run_id: str
    workspace_root: object | None
    observation_id: str | None
    feedback_type: str
    reason_code: str | None
    correction_dimensions: tuple[str, ...]
    original_route_digest: str | None
    corrected_route_digest: str | None
    free_text: str | None
    idempotency_key: str
    correlation_id: str

    def __post_init__(self) -> None:
        from pathlib import Path

        if not isinstance(self.context, MemoryRequestContext):
            raise TypeError("context must be MemoryRequestContext")
        if not isinstance(self.workflow_run_id, str) or not self.workflow_run_id or len(self.workflow_run_id) > 160:
            raise RouteFeedbackError("invalid-feedback-workflow-run-id")
        if self.workspace_root is not None:
            object.__setattr__(self, "workspace_root", Path(self.workspace_root))
        if not isinstance(self.observation_id, str) or not self.observation_id.startswith("observation:") or len(self.observation_id) > 128:
            raise RouteFeedbackError("invalid-feedback-observation-id")
        if self.feedback_type not in FEEDBACK_TYPES:
            raise RouteFeedbackError("invalid-feedback-type")
        if self.reason_code is not None and (
            not isinstance(self.reason_code, str)
            or _SAFE_CODE.fullmatch(self.reason_code) is None
        ):
            raise RouteFeedbackError("invalid-feedback-reason-code")
        if (
            not isinstance(self.correction_dimensions, tuple)
            or len(self.correction_dimensions) > len(CORRECTION_DIMENSIONS)
            or len(set(self.correction_dimensions)) != len(self.correction_dimensions)
            or any(item not in CORRECTION_DIMENSIONS for item in self.correction_dimensions)
        ):
            raise RouteFeedbackError("invalid-correction-dimensions")
        original = _validate_digest(self.original_route_digest, "original_route_digest", optional=True)
        corrected = _validate_digest(self.corrected_route_digest, "corrected_route_digest", optional=True)
        if self.feedback_type == "corrected":
            if not self.correction_dimensions or original is None or corrected is None or original == corrected:
                raise RouteFeedbackError("correction-binding-required")
        elif self.correction_dimensions or original is not None or corrected is not None:
            raise RouteFeedbackError("correction-fields-forbidden")
        _validate_free_text(self.free_text)
        for field, value in (
            ("idempotency-key", self.idempotency_key),
            ("correlation-id", self.correlation_id),
        ):
            if not isinstance(value, str) or _SAFE_KEY.fullmatch(value) is None:
                raise RouteFeedbackError(f"invalid-feedback-{field}")

    def digest_document(self) -> dict[str, object]:
        return {
            "context": {
                "session_digest": _context_digest("session", self.context.session_id),
                "actor_digest": _context_digest("actor", self.context.actor),
                "runtime_policy_snapshot_id": self.context.runtime_policy_snapshot_id,
            },
            "workflow_run_id": self.workflow_run_id,
            "observation_id": self.observation_id,
            "feedback_type": self.feedback_type,
            "reason_code": self.reason_code,
            "correction_dimensions": list(self.correction_dimensions),
            "original_route_digest": self.original_route_digest,
            "corrected_route_digest": self.corrected_route_digest,
            "free_text_digest": None if self.free_text is None else _digest({"free_text": self.free_text}),
            "correlation_id": self.correlation_id,
        }


@dataclass(frozen=True, slots=True)
class RouteFeedback:
    feedback_id: str
    feedback_digest: str
    observation_id: str
    observation_digest: str
    workflow_run_digest: str
    policy_snapshot_id: str
    policy_digest: str
    feedback_type: str
    reason_code: str | None
    correction_dimensions: tuple[str, ...]
    original_route_digest: str | None
    corrected_route_digest: str | None
    free_text: str | None
    session_digest: str
    actor_digest: str
    recorded_at: str

    @classmethod
    def create(
        cls,
        *,
        observation: RouteObservation,
        policy_snapshot: MemoryPolicySnapshot,
        context: MemoryRequestContext,
        feedback_type: str,
        reason_code: str | None,
        correction_dimensions: tuple[str, ...],
        original_route_digest: str | None,
        corrected_route_digest: str | None,
        free_text: str | None,
        recorded_at: str,
    ) -> "RouteFeedback":
        command = RecordRouteFeedbackCommand(
            context=context,
            workflow_run_id="feedback-validation",
            workspace_root=None,
            observation_id=observation.observation_id,
            feedback_type=feedback_type,
            reason_code=reason_code,
            correction_dimensions=correction_dimensions,
            original_route_digest=original_route_digest,
            corrected_route_digest=corrected_route_digest,
            free_text=free_text,
            idempotency_key="feedback-validation",
            correlation_id="feedback-validation",
        )
        payload: dict[str, object] = {
            "schema_id": FEEDBACK_SCHEMA_ID,
            "schema_version": FEEDBACK_SCHEMA_VERSION,
            "artifact_kind": FEEDBACK_ARTIFACT_KIND,
            "feedback_id": "",
            "feedback_digest": "",
            "observation_id": observation.observation_id,
            "observation_digest": observation.observation_digest,
            "workflow_run_digest": observation.workflow_run_digest,
            "policy_snapshot_id": policy_snapshot.snapshot_id,
            "policy_digest": policy_snapshot.policy_digest,
            "feedback_type": command.feedback_type,
            "reason_code": command.reason_code,
            "correction_dimensions": list(command.correction_dimensions),
            "original_route_digest": command.original_route_digest,
            "corrected_route_digest": command.corrected_route_digest,
            "free_text": command.free_text,
            "session_digest": _context_digest("session", context.session_id),
            "actor_digest": _context_digest("actor", context.actor),
            "recorded_at": _validate_recorded_at(recorded_at),
        }
        identity = {key: value for key, value in payload.items() if key not in {"feedback_id", "feedback_digest"}}
        feedback_digest = _digest(identity)
        payload["feedback_digest"] = feedback_digest
        payload["feedback_id"] = "feedback:" + feedback_digest.removeprefix("sha256:")[:32]
        return decode_route_feedback(payload)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": FEEDBACK_SCHEMA_ID,
            "schema_version": FEEDBACK_SCHEMA_VERSION,
            "artifact_kind": FEEDBACK_ARTIFACT_KIND,
            "feedback_id": self.feedback_id,
            "feedback_digest": self.feedback_digest,
            "observation_id": self.observation_id,
            "observation_digest": self.observation_digest,
            "workflow_run_digest": self.workflow_run_digest,
            "policy_snapshot_id": self.policy_snapshot_id,
            "policy_digest": self.policy_digest,
            "feedback_type": self.feedback_type,
            "reason_code": self.reason_code,
            "correction_dimensions": list(self.correction_dimensions),
            "original_route_digest": self.original_route_digest,
            "corrected_route_digest": self.corrected_route_digest,
            "free_text": self.free_text,
            "session_digest": self.session_digest,
            "actor_digest": self.actor_digest,
            "recorded_at": self.recorded_at,
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


def decode_route_feedback(value: Mapping[str, object]) -> RouteFeedback:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise RouteFeedbackError("invalid-feedback-document")
    if set(value) != _TOP_FIELDS:
        raise RouteFeedbackError("invalid-feedback-fields")
    if (
        value["schema_id"] != FEEDBACK_SCHEMA_ID
        or value["schema_version"] != FEEDBACK_SCHEMA_VERSION
        or value["artifact_kind"] != FEEDBACK_ARTIFACT_KIND
    ):
        raise RouteFeedbackError("invalid-feedback-contract")
    feedback_id = value["feedback_id"]
    if not isinstance(feedback_id, str) or not feedback_id.startswith("feedback:") or len(feedback_id) > 128:
        raise RouteFeedbackError("invalid-feedback-id")
    feedback_digest = _validate_digest(value["feedback_digest"], "feedback_digest")
    assert feedback_digest is not None
    observation_id = value["observation_id"]
    if not isinstance(observation_id, str) or not observation_id.startswith("observation:") or len(observation_id) > 128:
        raise RouteFeedbackError("invalid-feedback-observation-id")
    observation_digest = _validate_digest(value["observation_digest"], "observation_digest")
    workflow_run_digest = _validate_digest(value["workflow_run_digest"], "workflow_run_digest")
    policy_snapshot_id = _validate_digest(value["policy_snapshot_id"], "policy_snapshot_id")
    policy_digest = _validate_digest(value["policy_digest"], "policy_digest")
    feedback_type = value["feedback_type"]
    if feedback_type not in FEEDBACK_TYPES:
        raise RouteFeedbackError("invalid-feedback-type")
    reason_code = value["reason_code"]
    if reason_code is not None and (
        not isinstance(reason_code, str) or _SAFE_CODE.fullmatch(reason_code) is None
    ):
        raise RouteFeedbackError("invalid-feedback-reason-code")
    raw_dimensions = value["correction_dimensions"]
    if not isinstance(raw_dimensions, list) or any(not isinstance(item, str) for item in raw_dimensions):
        raise RouteFeedbackError("invalid-correction-dimensions")
    dimensions = tuple(raw_dimensions)
    if len(set(dimensions)) != len(dimensions) or any(item not in CORRECTION_DIMENSIONS for item in dimensions):
        raise RouteFeedbackError("invalid-correction-dimensions")
    original = _validate_digest(value["original_route_digest"], "original_route_digest", optional=True)
    corrected = _validate_digest(value["corrected_route_digest"], "corrected_route_digest", optional=True)
    if feedback_type == "corrected":
        if not dimensions or original is None or corrected is None or original == corrected:
            raise RouteFeedbackError("correction-binding-required")
    elif dimensions or original is not None or corrected is not None:
        raise RouteFeedbackError("correction-fields-forbidden")
    free_text = _validate_free_text(value["free_text"])
    session_digest = _validate_digest(value["session_digest"], "session_digest")
    actor_digest = _validate_digest(value["actor_digest"], "actor_digest")
    recorded_at = _validate_recorded_at(value["recorded_at"])
    identity = {key: item for key, item in value.items() if key not in {"feedback_id", "feedback_digest"}}
    expected = _digest(identity)
    if feedback_digest != expected or feedback_id != "feedback:" + expected.removeprefix("sha256:")[:32]:
        raise RouteFeedbackError("feedback-digest-mismatch")
    return RouteFeedback(
        feedback_id=feedback_id,
        feedback_digest=feedback_digest,
        observation_id=observation_id,
        observation_digest=observation_digest or "",
        workflow_run_digest=workflow_run_digest or "",
        policy_snapshot_id=policy_snapshot_id or "",
        policy_digest=policy_digest or "",
        feedback_type=str(feedback_type),
        reason_code=reason_code,
        correction_dimensions=dimensions,
        original_route_digest=original,
        corrected_route_digest=corrected,
        free_text=free_text,
        session_digest=session_digest or "",
        actor_digest=actor_digest or "",
        recorded_at=recorded_at,
    )


@dataclass(frozen=True, slots=True)
class RecordRouteFeedbackResult:
    status: str
    feedback_id: str | None
    feedback_digest: str | None
    observation_id: str | None
    policy_digest: str | None
    reason_codes: tuple[str, ...]
    replayed: bool
    authority_mode: str = "router-local"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "feedback_id": self.feedback_id,
            "feedback_digest": self.feedback_digest,
            "observation_id": self.observation_id,
            "policy_digest": self.policy_digest,
            "reason_codes": list(self.reason_codes),
            "replayed": self.replayed,
            "authority_mode": self.authority_mode,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object], *, replayed: bool | None = None) -> "RecordRouteFeedbackResult":
        return cls(
            status=str(value["status"]),
            feedback_id=None if value.get("feedback_id") is None else str(value["feedback_id"]),
            feedback_digest=None if value.get("feedback_digest") is None else str(value["feedback_digest"]),
            observation_id=None if value.get("observation_id") is None else str(value["observation_id"]),
            policy_digest=None if value.get("policy_digest") is None else str(value["policy_digest"]),
            reason_codes=tuple(str(item) for item in value.get("reason_codes", [])),
            replayed=bool(value.get("replayed", False)) if replayed is None else replayed,
            authority_mode=str(value.get("authority_mode", "router-local")),
        )


__all__ = [
    "CORRECTION_DIMENSIONS",
    "FEEDBACK_TYPES",
    "RecordRouteFeedbackCommand",
    "RecordRouteFeedbackResult",
    "RouteFeedback",
    "RouteFeedbackError",
    "decode_route_feedback",
]
