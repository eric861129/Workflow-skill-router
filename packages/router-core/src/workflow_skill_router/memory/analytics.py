from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import hashlib
import re

from workflow_skill_router.schemas.artifacts import canonical_json

from .feedback import RouteFeedback
from .observations import RouteObservation
from .workflow_reader import MemoryRequestContext


_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_PURGE_SCOPES = (
    "history-only",
    "analytics-only",
    "candidates-only",
    "revisions-only",
    "managed-profiles-only",
    "all-memory-data",
)


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class HistorySummaryQuery:
    context: MemoryRequestContext
    workspace_identity_digest: str | None = None
    route_signature_digest: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.context, MemoryRequestContext):
            raise TypeError("context must be MemoryRequestContext")
        for field, value in (
            ("workspace_identity_digest", self.workspace_identity_digest),
            ("route_signature_digest", self.route_signature_digest),
        ):
            if value is not None and (not isinstance(value, str) or _DIGEST.fullmatch(value) is None):
                raise ValueError(f"invalid-history-query:{field}")


@dataclass(frozen=True, slots=True)
class HistorySummary:
    eligible_workflow_count: int
    route_signature_frequency: Mapping[str, int]
    completion_rate: float
    required_gate_pass_rate: float
    manual_correction_rate: float
    consent_rejection_rate: float
    capability_unavailable_rate: float
    reported_route_consistency: float
    actual_skill_consistency: str
    distinct_active_days: int
    workspace_distribution: Mapping[str, int]
    profile_source_distribution: Mapping[str, int]
    confidence: str
    summary_digest: str

    @classmethod
    def empty(cls) -> "HistorySummary":
        return cls.create((), ())

    @classmethod
    def create(
        cls,
        observations: Iterable[RouteObservation],
        feedback: Iterable[RouteFeedback],
    ) -> "HistorySummary":
        observation_by_id = {item.observation_id: item for item in observations}
        feedback_by_observation: dict[str, list[RouteFeedback]] = {
            observation_id: [] for observation_id in observation_by_id
        }
        for item in feedback:
            if item.observation_id in feedback_by_observation:
                feedback_by_observation[item.observation_id].append(item)
        ordered = tuple(sorted(observation_by_id.values(), key=lambda item: (item.observed_at, item.observation_id)))
        count = len(ordered)
        route_frequency = Counter(item.route_signature_digest for item in ordered)
        workspace_frequency = Counter(item.workspace_identity_digest or "none" for item in ordered)
        profile_frequency = Counter(item.route_source for item in ordered)
        dates = {item.observed_at[:10] for item in ordered}

        def has(observation_id: str, kind: str) -> bool:
            return any(item.feedback_type == kind for item in feedback_by_observation[observation_id])

        completion_count = sum(1 for item in ordered if not has(item.observation_id, "abandoned"))
        gate_pass_count = sum(1 for item in ordered if not has(item.observation_id, "gate-failed"))
        correction_count = sum(1 for item in ordered if has(item.observation_id, "corrected"))
        rejection_count = sum(1 for item in ordered if has(item.observation_id, "support-rejected"))
        unavailable_count = sum(1 for item in ordered if has(item.observation_id, "capability-unavailable"))
        route_consistency = 0.0 if count == 0 else max(route_frequency.values(), default=0) / count
        if count == 0:
            confidence = "insufficient-evidence"
        elif count >= 5 and len(dates) >= 3:
            confidence = "high"
        elif count >= 3 and len(dates) >= 2:
            confidence = "medium"
        else:
            confidence = "low"
        payload = {
            "eligible_workflow_count": count,
            "route_signature_frequency": dict(sorted(route_frequency.items())),
            "completion_rate": 0.0 if count == 0 else completion_count / count,
            "required_gate_pass_rate": 0.0 if count == 0 else gate_pass_count / count,
            "manual_correction_rate": 0.0 if count == 0 else correction_count / count,
            "consent_rejection_rate": 0.0 if count == 0 else rejection_count / count,
            "capability_unavailable_rate": 0.0 if count == 0 else unavailable_count / count,
            "reported_route_consistency": route_consistency,
            "actual_skill_consistency": "unavailable",
            "distinct_active_days": len(dates),
            "workspace_distribution": dict(sorted(workspace_frequency.items())),
            "profile_source_distribution": dict(sorted(profile_frequency.items())),
            "confidence": confidence,
        }
        return cls(
            eligible_workflow_count=count,
            route_signature_frequency=payload["route_signature_frequency"],
            completion_rate=float(payload["completion_rate"]),
            required_gate_pass_rate=float(payload["required_gate_pass_rate"]),
            manual_correction_rate=float(payload["manual_correction_rate"]),
            consent_rejection_rate=float(payload["consent_rejection_rate"]),
            capability_unavailable_rate=float(payload["capability_unavailable_rate"]),
            reported_route_consistency=float(payload["reported_route_consistency"]),
            actual_skill_consistency="unavailable",
            distinct_active_days=len(dates),
            workspace_distribution=payload["workspace_distribution"],
            profile_source_distribution=payload["profile_source_distribution"],
            confidence=confidence,
            summary_digest=_digest(payload),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "eligible_workflow_count": self.eligible_workflow_count,
            "route_signature_frequency": dict(self.route_signature_frequency),
            "completion_rate": self.completion_rate,
            "required_gate_pass_rate": self.required_gate_pass_rate,
            "manual_correction_rate": self.manual_correction_rate,
            "consent_rejection_rate": self.consent_rejection_rate,
            "capability_unavailable_rate": self.capability_unavailable_rate,
            "reported_route_consistency": self.reported_route_consistency,
            "actual_skill_consistency": self.actual_skill_consistency,
            "distinct_active_days": self.distinct_active_days,
            "workspace_distribution": dict(self.workspace_distribution),
            "profile_source_distribution": dict(self.profile_source_distribution),
            "confidence": self.confidence,
            "summary_digest": self.summary_digest,
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True, slots=True)
class RetentionResult:
    deleted_observations: int
    deleted_feedback: int
    remaining_observations: int
    applied_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "deleted_observations": self.deleted_observations,
            "deleted_feedback": self.deleted_feedback,
            "remaining_observations": self.remaining_observations,
            "applied_at": self.applied_at,
        }


@dataclass(frozen=True, slots=True)
class PurgeMemoryCommand:
    context: MemoryRequestContext
    scope: str
    expected_summary_digest: str
    include_managed_profiles: bool
    idempotency_key: str
    correlation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.context, MemoryRequestContext):
            raise TypeError("context must be MemoryRequestContext")
        if self.scope not in _PURGE_SCOPES:
            raise ValueError("invalid-memory-purge-scope")
        if not isinstance(self.expected_summary_digest, str) or _DIGEST.fullmatch(self.expected_summary_digest) is None:
            raise ValueError("invalid-memory-summary-digest")
        if not isinstance(self.include_managed_profiles, bool):
            raise TypeError("include_managed_profiles must be bool")
        for value in (self.idempotency_key, self.correlation_id):
            if not isinstance(value, str) or not value or len(value) > 160:
                raise ValueError("invalid-memory-purge-command")

    def digest_document(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "expected_summary_digest": self.expected_summary_digest,
            "include_managed_profiles": self.include_managed_profiles,
            "session_digest": _digest({"session": self.context.session_id}),
            "actor_digest": _digest({"actor": self.context.actor}),
            "correlation_id": self.correlation_id,
        }


@dataclass(frozen=True, slots=True)
class PurgeMemoryResult:
    status: str
    scope: str
    deleted_observations: int
    deleted_feedback: int
    deleted_command_receipts: int
    summary_digest_before: str
    summary_digest_after: str
    replayed: bool
    reason_codes: tuple[str, ...] = ()
    authority_mode: str = "router-local"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "scope": self.scope,
            "deleted_observations": self.deleted_observations,
            "deleted_feedback": self.deleted_feedback,
            "deleted_command_receipts": self.deleted_command_receipts,
            "summary_digest_before": self.summary_digest_before,
            "summary_digest_after": self.summary_digest_after,
            "replayed": self.replayed,
            "reason_codes": list(self.reason_codes),
            "authority_mode": self.authority_mode,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object], *, replayed: bool | None = None) -> "PurgeMemoryResult":
        return cls(
            status=str(value["status"]),
            scope=str(value["scope"]),
            deleted_observations=int(value["deleted_observations"]),
            deleted_feedback=int(value["deleted_feedback"]),
            deleted_command_receipts=int(value["deleted_command_receipts"]),
            summary_digest_before=str(value["summary_digest_before"]),
            summary_digest_after=str(value["summary_digest_after"]),
            replayed=bool(value.get("replayed", False)) if replayed is None else replayed,
            reason_codes=tuple(str(item) for item in value.get("reason_codes", [])),
            authority_mode=str(value.get("authority_mode", "router-local")),
        )


__all__ = [
    "HistorySummary",
    "HistorySummaryQuery",
    "PurgeMemoryCommand",
    "PurgeMemoryResult",
    "RetentionResult",
]
