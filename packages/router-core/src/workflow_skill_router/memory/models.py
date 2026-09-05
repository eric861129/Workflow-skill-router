from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Mapping


class MemoryPolicyError(ValueError):
    """Raised when a memory policy or source violates the strict contract."""


class MemoryMode(str, Enum):
    DISABLED = "disabled"
    OBSERVE = "observe"
    REVIEWED = "reviewed"
    AUTOMATIC = "automatic"


class MemoryScope(str, Enum):
    PERSONAL = "personal"
    WORKSPACE = "workspace"


@dataclass(frozen=True, slots=True)
class StoragePolicy:
    backend: str
    retention_days: int
    max_observations: int
    candidate_retention_days: int
    rejected_suppression_days: int
    max_revisions_per_profile: int
    purge_on_disable: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "retention_days": self.retention_days,
            "max_observations": self.max_observations,
            "candidate_retention_days": self.candidate_retention_days,
            "rejected_suppression_days": self.rejected_suppression_days,
            "max_revisions_per_profile": self.max_revisions_per_profile,
            "purge_on_disable": self.purge_on_disable,
        }


@dataclass(frozen=True, slots=True)
class PrivacyPolicy:
    objective: str
    workspace_identity: str
    raw_prompt: str
    file_paths: str
    file_content: str
    tool_arguments: str
    secrets: str
    free_text_feedback: str
    export_redaction: str

    def to_dict(self) -> dict[str, object]:
        return {
            "objective": self.objective,
            "workspace_identity": self.workspace_identity,
            "raw_prompt": self.raw_prompt,
            "file_paths": self.file_paths,
            "file_content": self.file_content,
            "tool_arguments": self.tool_arguments,
            "secrets": self.secrets,
            "free_text_feedback": self.free_text_feedback,
            "export_redaction": self.export_redaction,
        }


@dataclass(frozen=True, slots=True)
class EligibilityPolicy:
    require_terminal_success: bool
    require_required_gate_pass: bool
    reject_unknown_side_effects: bool
    exclude_risk_levels: tuple[str, ...]
    minimum_distinct_runs_reviewed: int
    minimum_distinct_runs_automatic: int
    minimum_distinct_days_reviewed: int
    minimum_distinct_days_automatic: int
    minimum_success_rate_reviewed: float
    minimum_success_rate_automatic: float
    maximum_correction_rate_reviewed: float
    maximum_correction_rate_automatic: float
    minimum_route_consistency_reviewed: float
    minimum_route_consistency_automatic: float

    def to_dict(self) -> dict[str, object]:
        return {
            "require_terminal_success": self.require_terminal_success,
            "require_required_gate_pass": self.require_required_gate_pass,
            "reject_unknown_side_effects": self.reject_unknown_side_effects,
            "exclude_risk_levels": list(self.exclude_risk_levels),
            "minimum_distinct_runs_reviewed": self.minimum_distinct_runs_reviewed,
            "minimum_distinct_runs_automatic": self.minimum_distinct_runs_automatic,
            "minimum_distinct_days_reviewed": self.minimum_distinct_days_reviewed,
            "minimum_distinct_days_automatic": self.minimum_distinct_days_automatic,
            "minimum_success_rate_reviewed": self.minimum_success_rate_reviewed,
            "minimum_success_rate_automatic": self.minimum_success_rate_automatic,
            "maximum_correction_rate_reviewed": self.maximum_correction_rate_reviewed,
            "maximum_correction_rate_automatic": self.maximum_correction_rate_automatic,
            "minimum_route_consistency_reviewed": self.minimum_route_consistency_reviewed,
            "minimum_route_consistency_automatic": self.minimum_route_consistency_automatic,
        }


@dataclass(frozen=True, slots=True)
class RememberWorkflowPolicy:
    mode: str
    eligible_event: str
    default_target: str

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "eligible_event": self.eligible_event,
            "default_target": self.default_target,
        }


@dataclass(frozen=True, slots=True)
class RouteFeedbackPolicy:
    mode: str
    allow_standard_reason_codes: bool
    allow_free_text: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "allow_standard_reason_codes": self.allow_standard_reason_codes,
            "allow_free_text": self.allow_free_text,
        }


@dataclass(frozen=True, slots=True)
class HistoryAnalyticsPolicy:
    mode: str
    run: str

    def to_dict(self) -> dict[str, object]:
        return {"mode": self.mode, "run": self.run}


@dataclass(frozen=True, slots=True)
class CandidateGenerationPolicy:
    mode: str
    confidence_required: str
    backtest_required: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "confidence_required": self.confidence_required,
            "backtest_required": self.backtest_required,
        }


@dataclass(frozen=True, slots=True)
class ProfilePromotionPolicy:
    mode: str
    target: str
    conflict_policy: str
    require_profile_lint: bool
    require_backtest: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "target": self.target,
            "conflict_policy": self.conflict_policy,
            "require_profile_lint": self.require_profile_lint,
            "require_backtest": self.require_backtest,
        }


@dataclass(frozen=True, slots=True)
class ProfileVersioningPolicy:
    mode: str
    diff: str
    rollback: str
    write_strategy: str

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "diff": self.diff,
            "rollback": self.rollback,
            "write_strategy": self.write_strategy,
        }


@dataclass(frozen=True, slots=True)
class MemoryFeatures:
    remember_this_workflow: RememberWorkflowPolicy
    route_feedback: RouteFeedbackPolicy
    history_analytics: HistoryAnalyticsPolicy
    candidate_generation: CandidateGenerationPolicy
    profile_promotion: ProfilePromotionPolicy
    profile_versioning: ProfileVersioningPolicy

    def to_dict(self) -> dict[str, object]:
        return {
            "remember_this_workflow": self.remember_this_workflow.to_dict(),
            "route_feedback": self.route_feedback.to_dict(),
            "history_analytics": self.history_analytics.to_dict(),
            "candidate_generation": self.candidate_generation.to_dict(),
            "profile_promotion": self.profile_promotion.to_dict(),
            "profile_versioning": self.profile_versioning.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class MemoryNotifications:
    show_completion_prompt: bool
    show_candidate_created: bool
    show_auto_promotion: bool
    show_retention_purge: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "show_completion_prompt": self.show_completion_prompt,
            "show_candidate_created": self.show_candidate_created,
            "show_auto_promotion": self.show_auto_promotion,
            "show_retention_purge": self.show_retention_purge,
        }


_AUTO_PROMOTION_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_AUTO_PROMOTION_CANDIDATE_ID = re.compile(r"^candidate:[0-9a-f]{32}$")
_AUTO_PROMOTION_PROPOSAL_ID = re.compile(r"^proposal:[0-9a-f]{32}$")
_AUTO_PROMOTION_REVISION_ID = re.compile(r"^revision:[0-9a-f]{32}$")
_AUTO_PROMOTION_REASON = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_AUTO_PROMOTION_STATUSES = frozenset({"promoted", "suppressed", "blocked"})
_AUTO_PROMOTION_TARGETS = frozenset({"managed-personal", "managed-workspace-local", "user-personal", "workspace-file"})


def _automatic_promotion_digest(value: object, field: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or _AUTO_PROMOTION_DIGEST.fullmatch(value) is None:
        raise ValueError(f"invalid-automatic-promotion-{field}")
    return value


def _automatic_promotion_optional_id(
    value: object, field: str, pattern: re.Pattern[str]
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"invalid-automatic-promotion-{field}")
    return value


def _automatic_promotion_reasons(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple) or not value:
        raise ValueError("invalid-automatic-promotion-reason-codes")
    if len(value) > 16 or len(set(value)) != len(value):
        raise ValueError("invalid-automatic-promotion-reason-codes")
    if any(
        not isinstance(item, str) or _AUTO_PROMOTION_REASON.fullmatch(item) is None
        for item in value
    ):
        raise ValueError("invalid-automatic-promotion-reason-codes")
    return value


@dataclass(frozen=True, slots=True)
class AutomaticPromotionNotification:
    """Public-safe disclosure for one explicit local automatic-promotion decision."""

    status: str
    candidate_id: str
    candidate_digest: str
    policy_digest: str
    target_profile_class: str
    proposal_id: str | None
    proposal_digest: str | None
    revision_id: str | None
    revision_digest: str | None
    new_profile_digest: str | None
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in _AUTO_PROMOTION_STATUSES:
            raise ValueError("invalid-automatic-promotion-status")
        if (
            not isinstance(self.candidate_id, str)
            or _AUTO_PROMOTION_CANDIDATE_ID.fullmatch(self.candidate_id) is None
        ):
            raise ValueError("invalid-automatic-promotion-candidate-id")
        _automatic_promotion_digest(self.candidate_digest, "candidate-digest")
        _automatic_promotion_digest(self.policy_digest, "policy-digest")
        if self.target_profile_class not in _AUTO_PROMOTION_TARGETS:
            raise ValueError("invalid-automatic-promotion-target")
        proposal_id = _automatic_promotion_optional_id(
            self.proposal_id, "proposal-id", _AUTO_PROMOTION_PROPOSAL_ID
        )
        proposal_digest = _automatic_promotion_digest(
            self.proposal_digest, "proposal-digest", nullable=True
        )
        if (proposal_id is None) != (proposal_digest is None):
            raise ValueError("invalid-automatic-promotion-proposal-binding")
        revision_id = _automatic_promotion_optional_id(
            self.revision_id, "revision-id", _AUTO_PROMOTION_REVISION_ID
        )
        revision_digest = _automatic_promotion_digest(
            self.revision_digest, "revision-digest", nullable=True
        )
        new_profile_digest = _automatic_promotion_digest(
            self.new_profile_digest, "new-profile-digest", nullable=True
        )
        revision_values = (revision_id, revision_digest, new_profile_digest)
        if any(item is None for item in revision_values) and any(
            item is not None for item in revision_values
        ):
            raise ValueError("invalid-automatic-promotion-revision-binding")
        if self.status == "promoted":
            if proposal_id is None or any(item is None for item in revision_values):
                raise ValueError("automatic-promotion-evidence-required")
        elif any(item is not None for item in revision_values):
            raise ValueError("automatic-promotion-revision-forbidden")
        _automatic_promotion_reasons(self.reason_codes)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "candidate_id": self.candidate_id,
            "candidate_digest": self.candidate_digest,
            "policy_digest": self.policy_digest,
            "target_profile_class": self.target_profile_class,
            "proposal_id": self.proposal_id,
            "proposal_digest": self.proposal_digest,
            "revision_id": self.revision_id,
            "revision_digest": self.revision_digest,
            "new_profile_digest": self.new_profile_digest,
            "reason_codes": list(self.reason_codes),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "AutomaticPromotionNotification":
        expected = {
            "status", "candidate_id", "candidate_digest", "policy_digest",
            "target_profile_class", "proposal_id", "proposal_digest",
            "revision_id", "revision_digest", "new_profile_digest", "reason_codes",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ValueError("invalid-automatic-promotion-notification")
        required_strings = (
            "status",
            "candidate_id",
            "candidate_digest",
            "policy_digest",
            "target_profile_class",
        )
        optional_strings = (
            "proposal_id",
            "proposal_digest",
            "revision_id",
            "revision_digest",
            "new_profile_digest",
        )
        if any(not isinstance(value[field], str) for field in required_strings):
            raise ValueError("invalid-automatic-promotion-notification")
        if any(
            value[field] is not None and not isinstance(value[field], str)
            for field in optional_strings
        ):
            raise ValueError("invalid-automatic-promotion-notification")
        raw_reasons = value["reason_codes"]
        if (
            not isinstance(raw_reasons, list)
            or any(not isinstance(item, str) for item in raw_reasons)
        ):
            raise ValueError("invalid-automatic-promotion-notification")
        return cls(
            status=value["status"],
            candidate_id=value["candidate_id"],
            candidate_digest=value["candidate_digest"],
            policy_digest=value["policy_digest"],
            target_profile_class=value["target_profile_class"],
            proposal_id=value["proposal_id"],
            proposal_digest=value["proposal_digest"],
            revision_id=value["revision_id"],
            revision_digest=value["revision_digest"],
            new_profile_digest=value["new_profile_digest"],
            reason_codes=tuple(raw_reasons),
        )


@dataclass(frozen=True, slots=True)
class AutomaticPromotionResult:
    """Bounded result for the explicit local ``promote-eligible`` operation."""

    status: str
    scope: MemoryScope
    promoted_count: int
    suppressed_count: int
    skipped_count: int
    notifications: tuple[AutomaticPromotionNotification, ...]
    reason_codes: tuple[str, ...] = ()
    operation_mode: str = "explicit-local"
    authority_mode: str = "router-local"
    replayed: bool = False

    def __post_init__(self) -> None:
        if self.status not in {"completed", "memory-disabled", "not-automatic"}:
            raise ValueError("invalid-automatic-promotion-result-status")
        if not isinstance(self.scope, MemoryScope):
            raise TypeError("scope must be MemoryScope")
        for field, value in (
            ("promoted-count", self.promoted_count),
            ("suppressed-count", self.suppressed_count),
            ("skipped-count", self.skipped_count),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"invalid-automatic-promotion-{field}")
        if not isinstance(self.notifications, tuple) or any(
            not isinstance(item, AutomaticPromotionNotification)
            for item in self.notifications
        ):
            raise TypeError("notifications must contain AutomaticPromotionNotification")
        if len(self.notifications) > 16:
            raise ValueError("automatic-promotion-notification-limit")
        if self.promoted_count != sum(
            item.status == "promoted" for item in self.notifications
        ):
            raise ValueError("automatic-promotion-promoted-count-mismatch")
        if self.suppressed_count != sum(
            item.status == "suppressed" for item in self.notifications
        ):
            raise ValueError("automatic-promotion-suppressed-count-mismatch")
        if self.skipped_count != sum(
            item.status == "blocked" for item in self.notifications
        ):
            raise ValueError("automatic-promotion-skipped-count-mismatch")
        if self.reason_codes:
            _automatic_promotion_reasons(self.reason_codes)
        if self.operation_mode != "explicit-local":
            raise ValueError("invalid-automatic-promotion-operation-mode")
        if self.authority_mode != "router-local":
            raise ValueError("invalid-automatic-promotion-authority-mode")
        if not isinstance(self.replayed, bool):
            raise TypeError("replayed must be bool")

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "scope": self.scope.value,
            "promoted_count": self.promoted_count,
            "suppressed_count": self.suppressed_count,
            "skipped_count": self.skipped_count,
            "notifications": [item.to_dict() for item in self.notifications],
            "reason_codes": list(self.reason_codes),
            "operation_mode": self.operation_mode,
            "authority_mode": self.authority_mode,
            "replayed": self.replayed,
        }

    @classmethod
    def from_dict(
        cls, value: Mapping[str, object], *, replayed: bool | None = None
    ) -> "AutomaticPromotionResult":
        expected = {
            "status", "scope", "promoted_count", "suppressed_count",
            "skipped_count", "notifications", "reason_codes", "operation_mode",
            "authority_mode", "replayed",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ValueError("invalid-automatic-promotion-result")
        raw_notifications = value["notifications"]
        raw_reasons = value["reason_codes"]
        if (
            not isinstance(value["status"], str)
            or not isinstance(value["scope"], str)
            or any(
                isinstance(value[field], bool) or not isinstance(value[field], int)
                for field in (
                    "promoted_count",
                    "suppressed_count",
                    "skipped_count",
                )
            )
            or not isinstance(raw_notifications, list)
            or any(not isinstance(item, Mapping) for item in raw_notifications)
            or not isinstance(raw_reasons, list)
            or any(not isinstance(item, str) for item in raw_reasons)
            or not isinstance(value["operation_mode"], str)
            or not isinstance(value["authority_mode"], str)
            or not isinstance(value["replayed"], bool)
            or (replayed is not None and not isinstance(replayed, bool))
        ):
            raise ValueError("invalid-automatic-promotion-result")
        return cls(
            status=value["status"],
            scope=MemoryScope(value["scope"]),
            promoted_count=value["promoted_count"],
            suppressed_count=value["suppressed_count"],
            skipped_count=value["skipped_count"],
            notifications=tuple(
                AutomaticPromotionNotification.from_dict(item)
                for item in raw_notifications
            ),
            reason_codes=tuple(raw_reasons),
            operation_mode=value["operation_mode"],
            authority_mode=value["authority_mode"],
            replayed=value["replayed"] if replayed is None else replayed,
        )


@dataclass(frozen=True, slots=True)
class MemoryPolicy:
    schema_id: str
    schema_version: str
    artifact_kind: str
    policy_id: str
    scope: MemoryScope
    mode: MemoryMode
    capture: str
    storage: StoragePolicy
    privacy: PrivacyPolicy
    eligibility: EligibilityPolicy
    features: MemoryFeatures
    notifications: MemoryNotifications
    policy_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "artifact_kind": self.artifact_kind,
            "policy_id": self.policy_id,
            "scope": self.scope.value,
            "mode": self.mode.value,
            "storage": self.storage.to_dict(),
            "privacy": self.privacy.to_dict(),
            "eligibility": self.eligibility.to_dict(),
            "features": self.features.to_dict(),
            "notifications": self.notifications.to_dict(),
        }

    @property
    def normalized_document(self) -> dict[str, Any]:
        return self.to_dict()
