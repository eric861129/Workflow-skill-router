from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


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
