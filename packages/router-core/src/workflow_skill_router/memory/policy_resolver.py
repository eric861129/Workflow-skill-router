from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable

from workflow_skill_router.schemas.artifacts import canonical_json

from .models import MemoryMode, MemoryPolicy
from .policy import decode_memory_policy
from .policy_io import PolicyLoadResult


_MODE_RANK = {
    MemoryMode.DISABLED: 0,
    MemoryMode.OBSERVE: 1,
    MemoryMode.REVIEWED: 2,
    MemoryMode.AUTOMATIC: 3,
}
_FEATURE_RANKS: dict[str, tuple[str, ...]] = {
    "remember": ("disabled", "prompt", "automatic"),
    "feedback": ("disabled", "manual", "automatic-metadata"),
    "history": ("disabled", "summary", "detailed-local"),
    "candidate": ("disabled", "on-demand", "on-completion"),
    "promotion": ("disabled", "review-required", "automatic-managed"),
    "versioning": ("disabled", "required"),
    "history_run": ("on-demand", "on-completion", "scheduled-local"),
}
_TARGET_ORDER = (
    "managed-personal",
    "managed-workspace-local",
    "user-personal",
    "workspace-file",
)
_RISK_ORDER = ("r0", "r1", "r2", "r3")


@dataclass(frozen=True, slots=True)
class EffectiveMemoryPolicy:
    mode: MemoryMode
    personal_mode: MemoryMode
    workspace_requested_mode: MemoryMode | None
    policy_source: str
    policy: MemoryPolicy
    allowed_targets: tuple[str, ...]
    reason_codes: tuple[str, ...]
    policy_digest: str

    @property
    def capture_enabled(self) -> bool:
        return self.mode is not MemoryMode.DISABLED and self.policy.capture == "minimal"

    @property
    def candidate_generation_enabled(self) -> bool:
        return self.policy.features.candidate_generation.mode != "disabled"

    @property
    def profile_promotion(self) -> str:
        return self.policy.features.profile_promotion.mode

    def to_public_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "personal_mode": self.personal_mode.value,
            "workspace_requested_mode": (
                None
                if self.workspace_requested_mode is None
                else self.workspace_requested_mode.value
            ),
            "policy_source": self.policy_source,
            "policy_digest": self.policy_digest,
            "capture_enabled": self.capture_enabled,
            "candidate_generation_enabled": self.candidate_generation_enabled,
            "profile_promotion": self.profile_promotion,
            "allowed_targets": list(self.allowed_targets),
            "reason_codes": list(self.reason_codes),
            "warnings": list(self.reason_codes),
        }


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return tuple(result)


def _lower(left: str, right: str | None, ranking: tuple[str, ...]) -> str:
    if right is None:
        return left
    return left if ranking.index(left) <= ranking.index(right) else right


def _stricter_privacy(left: str, right: str | None) -> str:
    if right is None:
        return left
    ranking = {"digest-only": 0, "explicit-opt-in": 0, "never": 1}
    return left if ranking[left] >= ranking[right] else right


def _disabled_policy() -> MemoryPolicy:
    return decode_memory_policy({
        "schema_id": "workflow-skill-router/memory-policy",
        "schema_version": "1.0.0",
        "artifact_kind": "memory-policy",
        "policy_id": "personal:effective",
        "scope": "personal",
        "mode": "disabled",
    })


def _digest_document(
    *,
    policy: MemoryPolicy,
    personal_mode: MemoryMode,
    workspace_mode: MemoryMode | None,
    source: str,
    allowed_targets: tuple[str, ...],
    reason_codes: tuple[str, ...],
) -> str:
    document = {
        "schema_id": "workflow-skill-router/effective-memory-policy",
        "schema_version": "1.0.0",
        "artifact_kind": "effective-memory-policy",
        "mode": policy.mode.value,
        "personal_mode": personal_mode.value,
        "workspace_requested_mode": (
            None if workspace_mode is None else workspace_mode.value
        ),
        "policy_source": source,
        "allowed_targets": list(allowed_targets),
        "reason_codes": list(reason_codes),
        "policy": policy.to_dict(),
    }
    return "sha256:" + hashlib.sha256(
        canonical_json(document).encode("utf-8")
    ).hexdigest()


def _effective(
    *,
    policy: MemoryPolicy,
    personal_mode: MemoryMode,
    workspace_mode: MemoryMode | None,
    source: str,
    allowed_targets: tuple[str, ...],
    reason_codes: Iterable[str],
) -> EffectiveMemoryPolicy:
    codes = _unique(reason_codes)
    digest = _digest_document(
        policy=policy,
        personal_mode=personal_mode,
        workspace_mode=workspace_mode,
        source=source,
        allowed_targets=allowed_targets,
        reason_codes=codes,
    )
    return EffectiveMemoryPolicy(
        mode=policy.mode,
        personal_mode=personal_mode,
        workspace_requested_mode=workspace_mode,
        policy_source=source,
        policy=policy,
        allowed_targets=allowed_targets,
        reason_codes=codes,
        policy_digest=digest,
    )


def _valid_policy(result: PolicyLoadResult | None) -> MemoryPolicy | None:
    if result is None or result.status != "valid" or result.source is None:
        return None
    return result.source.policy


def _intersect_policy(
    personal: MemoryPolicy,
    workspace: MemoryPolicy | None,
    effective_mode: MemoryMode,
) -> tuple[MemoryPolicy, tuple[str, ...], tuple[str, ...]]:
    workspace_storage = None if workspace is None else workspace.storage
    workspace_privacy = None if workspace is None else workspace.privacy
    workspace_eligibility = None if workspace is None else workspace.eligibility
    workspace_features = None if workspace is None else workspace.features
    workspace_notifications = None if workspace is None else workspace.notifications

    storage = {
        "backend": "local-sqlite",
        "retention_days": min(
            personal.storage.retention_days,
            personal.storage.retention_days
            if workspace_storage is None
            else workspace_storage.retention_days,
        ),
        "max_observations": min(
            personal.storage.max_observations,
            personal.storage.max_observations
            if workspace_storage is None
            else workspace_storage.max_observations,
        ),
        "candidate_retention_days": min(
            personal.storage.candidate_retention_days,
            personal.storage.candidate_retention_days
            if workspace_storage is None
            else workspace_storage.candidate_retention_days,
        ),
        "rejected_suppression_days": min(
            personal.storage.rejected_suppression_days,
            personal.storage.rejected_suppression_days
            if workspace_storage is None
            else workspace_storage.rejected_suppression_days,
        ),
        "max_revisions_per_profile": min(
            personal.storage.max_revisions_per_profile,
            personal.storage.max_revisions_per_profile
            if workspace_storage is None
            else workspace_storage.max_revisions_per_profile,
        ),
        "purge_on_disable": (
            personal.storage.purge_on_disable
            if workspace_storage is None
            else personal.storage.purge_on_disable
            and workspace_storage.purge_on_disable
        ),
    }

    privacy = {
        "objective": _stricter_privacy(
            personal.privacy.objective,
            None if workspace_privacy is None else workspace_privacy.objective,
        ),
        "workspace_identity": _stricter_privacy(
            personal.privacy.workspace_identity,
            None
            if workspace_privacy is None
            else workspace_privacy.workspace_identity,
        ),
        "raw_prompt": "never",
        "file_paths": "never",
        "file_content": "never",
        "tool_arguments": "never",
        "secrets": "never",
        "free_text_feedback": _stricter_privacy(
            personal.privacy.free_text_feedback,
            None
            if workspace_privacy is None
            else workspace_privacy.free_text_feedback,
        ),
        "export_redaction": "required",
    }

    other_eligibility = personal.eligibility if workspace_eligibility is None else workspace_eligibility
    excluded = set(personal.eligibility.exclude_risk_levels)
    if workspace_eligibility is not None:
        excluded.update(workspace_eligibility.exclude_risk_levels)
    eligibility = {
        "require_terminal_success": (
            personal.eligibility.require_terminal_success
            or other_eligibility.require_terminal_success
        ),
        "require_required_gate_pass": (
            personal.eligibility.require_required_gate_pass
            or other_eligibility.require_required_gate_pass
        ),
        "reject_unknown_side_effects": (
            personal.eligibility.reject_unknown_side_effects
            or other_eligibility.reject_unknown_side_effects
        ),
        "exclude_risk_levels": [risk for risk in _RISK_ORDER if risk in excluded],
        "minimum_distinct_runs_reviewed": max(
            personal.eligibility.minimum_distinct_runs_reviewed,
            other_eligibility.minimum_distinct_runs_reviewed,
        ),
        "minimum_distinct_runs_automatic": max(
            personal.eligibility.minimum_distinct_runs_automatic,
            other_eligibility.minimum_distinct_runs_automatic,
        ),
        "minimum_distinct_days_reviewed": max(
            personal.eligibility.minimum_distinct_days_reviewed,
            other_eligibility.minimum_distinct_days_reviewed,
        ),
        "minimum_distinct_days_automatic": max(
            personal.eligibility.minimum_distinct_days_automatic,
            other_eligibility.minimum_distinct_days_automatic,
        ),
        "minimum_success_rate_reviewed": max(
            personal.eligibility.minimum_success_rate_reviewed,
            other_eligibility.minimum_success_rate_reviewed,
        ),
        "minimum_success_rate_automatic": max(
            personal.eligibility.minimum_success_rate_automatic,
            other_eligibility.minimum_success_rate_automatic,
        ),
        "maximum_correction_rate_reviewed": min(
            personal.eligibility.maximum_correction_rate_reviewed,
            other_eligibility.maximum_correction_rate_reviewed,
        ),
        "maximum_correction_rate_automatic": min(
            personal.eligibility.maximum_correction_rate_automatic,
            other_eligibility.maximum_correction_rate_automatic,
        ),
        "minimum_route_consistency_reviewed": max(
            personal.eligibility.minimum_route_consistency_reviewed,
            other_eligibility.minimum_route_consistency_reviewed,
        ),
        "minimum_route_consistency_automatic": max(
            personal.eligibility.minimum_route_consistency_automatic,
            other_eligibility.minimum_route_consistency_automatic,
        ),
    }

    pf = personal.features
    wf = workspace_features
    remember_mode = _lower(
        pf.remember_this_workflow.mode,
        None if wf is None else wf.remember_this_workflow.mode,
        _FEATURE_RANKS["remember"],
    )
    feedback_mode = _lower(
        pf.route_feedback.mode,
        None if wf is None else wf.route_feedback.mode,
        _FEATURE_RANKS["feedback"],
    )
    history_mode = _lower(
        pf.history_analytics.mode,
        None if wf is None else wf.history_analytics.mode,
        _FEATURE_RANKS["history"],
    )
    history_run = _lower(
        pf.history_analytics.run,
        None if wf is None else wf.history_analytics.run,
        _FEATURE_RANKS["history_run"],
    )
    candidate_mode = _lower(
        pf.candidate_generation.mode,
        None if wf is None else wf.candidate_generation.mode,
        _FEATURE_RANKS["candidate"],
    )
    promotion_mode = _lower(
        pf.profile_promotion.mode,
        None if wf is None else wf.profile_promotion.mode,
        _FEATURE_RANKS["promotion"],
    )
    versioning_mode = _lower(
        pf.profile_versioning.mode,
        None if wf is None else wf.profile_versioning.mode,
        _FEATURE_RANKS["versioning"],
    )

    reasons: list[str] = []
    allowed_targets: set[str] = set()
    remember_target = pf.remember_this_workflow.default_target
    if wf is not None and remember_target != wf.remember_this_workflow.default_target:
        if remember_mode != "disabled":
            reasons.append("memory-target-intersection-reduced")
        remember_mode = "disabled"
        remember_target = "managed-personal"
    elif remember_mode != "disabled":
        allowed_targets.add(remember_target)

    promotion_target = pf.profile_promotion.target
    if wf is not None and promotion_target != wf.profile_promotion.target:
        if promotion_mode != "disabled":
            reasons.append("memory-target-intersection-reduced")
        promotion_mode = "disabled"
        promotion_target = "managed-personal"
    elif promotion_mode != "disabled":
        allowed_targets.add(promotion_target)

    if not allowed_targets and (
        pf.remember_this_workflow.mode != "disabled"
        or pf.profile_promotion.mode != "disabled"
    ):
        reasons.append("memory-target-intersection-empty")
    if promotion_mode != "disabled":
        versioning_mode = "required"

    allow_free_text = pf.route_feedback.allow_free_text and (
        True if wf is None else wf.route_feedback.allow_free_text
    )
    allow_reason_codes = pf.route_feedback.allow_standard_reason_codes and (
        True if wf is None else wf.route_feedback.allow_standard_reason_codes
    )
    candidate_confidence = (
        "high"
        if pf.candidate_generation.confidence_required == "high"
        or (wf is not None and wf.candidate_generation.confidence_required == "high")
        else "medium"
    )
    features = {
        "remember_this_workflow": {
            "mode": remember_mode,
            "eligible_event": "terminal-success",
            "default_target": remember_target,
        },
        "route_feedback": {
            "mode": feedback_mode,
            "allow_standard_reason_codes": allow_reason_codes,
            "allow_free_text": allow_free_text,
        },
        "history_analytics": {"mode": history_mode, "run": history_run},
        "candidate_generation": {
            "mode": candidate_mode,
            "confidence_required": candidate_confidence,
            "backtest_required": (
                pf.candidate_generation.backtest_required
                or (wf is not None and wf.candidate_generation.backtest_required)
            ),
        },
        "profile_promotion": {
            "mode": promotion_mode,
            "target": promotion_target,
            "conflict_policy": "fail-closed",
            "require_profile_lint": (
                pf.profile_promotion.require_profile_lint
                or (wf is not None and wf.profile_promotion.require_profile_lint)
            ),
            "require_backtest": (
                pf.profile_promotion.require_backtest
                or (wf is not None and wf.profile_promotion.require_backtest)
            ),
        },
        "profile_versioning": {
            "mode": versioning_mode,
            "diff": "semantic-and-json",
            "rollback": "enabled",
            "write_strategy": "compare-and-swap",
        },
    }

    notifications = {
        "show_completion_prompt": personal.notifications.show_completion_prompt
        or (
            False
            if workspace_notifications is None
            else workspace_notifications.show_completion_prompt
        ),
        "show_candidate_created": personal.notifications.show_candidate_created
        or (
            False
            if workspace_notifications is None
            else workspace_notifications.show_candidate_created
        ),
        "show_auto_promotion": personal.notifications.show_auto_promotion
        or (
            False
            if workspace_notifications is None
            else workspace_notifications.show_auto_promotion
        ),
        "show_retention_purge": personal.notifications.show_retention_purge
        or (
            False
            if workspace_notifications is None
            else workspace_notifications.show_retention_purge
        ),
    }

    document = {
        "schema_id": "workflow-skill-router/memory-policy",
        "schema_version": "1.0.0",
        "artifact_kind": "memory-policy",
        "policy_id": "personal:effective",
        "scope": "personal",
        "mode": effective_mode.value,
        "storage": storage,
        "privacy": privacy,
        "eligibility": eligibility,
        "features": features,
        "notifications": notifications,
    }
    policy = decode_memory_policy(document)
    ordered_targets = tuple(target for target in _TARGET_ORDER if target in allowed_targets)
    return policy, ordered_targets, _unique(reasons)


def resolve_effective_policy(
    *,
    personal: PolicyLoadResult,
    workspace: PolicyLoadResult | None,
    host_disabled: bool = False,
    explicit_no_memory: bool = False,
) -> EffectiveMemoryPolicy:
    personal_policy = _valid_policy(personal)
    workspace_policy = _valid_policy(workspace)
    personal_mode = (
        MemoryMode.DISABLED if personal_policy is None else personal_policy.mode
    )
    workspace_mode = None if workspace_policy is None else workspace_policy.mode

    if host_disabled:
        return _effective(
            policy=_disabled_policy(),
            personal_mode=personal_mode,
            workspace_mode=workspace_mode,
            source="host-memory-disabled",
            allowed_targets=(),
            reason_codes=("host-memory-disabled",),
        )
    if explicit_no_memory:
        return _effective(
            policy=_disabled_policy(),
            personal_mode=personal_mode,
            workspace_mode=workspace_mode,
            source="explicit-no-memory",
            allowed_targets=(),
            reason_codes=("explicit-no-memory",),
        )
    if personal_policy is None:
        source = (
            "personal-policy-missing"
            if personal.status == "missing"
            else "invalid-personal-policy"
        )
        reasons = personal.reason_codes or (source,)
        return _effective(
            policy=_disabled_policy(),
            personal_mode=MemoryMode.DISABLED,
            workspace_mode=workspace_mode,
            source=source,
            allowed_targets=(),
            reason_codes=reasons,
        )
    if workspace is not None and workspace.status not in {"missing", "valid"}:
        return _effective(
            policy=_disabled_policy(),
            personal_mode=personal_policy.mode,
            workspace_mode=None,
            source="invalid-workspace-policy",
            allowed_targets=(),
            reason_codes=workspace.reason_codes or ("invalid-workspace-policy",),
        )

    reasons: list[str] = []
    source = "personal-policy"
    effective_mode = personal_policy.mode
    if workspace_policy is not None:
        if _MODE_RANK[workspace_policy.mode] > _MODE_RANK[personal_policy.mode]:
            source = "personal-ceiling"
            reasons.append("workspace-policy-exceeds-ceiling")
        elif _MODE_RANK[workspace_policy.mode] < _MODE_RANK[personal_policy.mode]:
            effective_mode = workspace_policy.mode
            source = "workspace-restriction"
            reasons.append("workspace-policy-reduced-autonomy")
        else:
            source = "personal-and-workspace"

    policy, allowed_targets, intersection_reasons = _intersect_policy(
        personal_policy,
        workspace_policy,
        effective_mode,
    )
    reasons.extend(intersection_reasons)
    return _effective(
        policy=policy,
        personal_mode=personal_policy.mode,
        workspace_mode=workspace_mode,
        source=source,
        allowed_targets=allowed_targets,
        reason_codes=reasons,
    )


def resolution_steps(
    personal: PolicyLoadResult,
    workspace: PolicyLoadResult | None,
    effective: EffectiveMemoryPolicy,
) -> tuple[str, ...]:
    steps: list[str] = []
    steps.append(
        "personal-policy-loaded"
        if personal.status == "valid"
        else f"personal-policy-{personal.status}"
    )
    if workspace is not None:
        steps.append(
            "workspace-policy-loaded"
            if workspace.status == "valid"
            else f"workspace-policy-{workspace.status}"
        )
    for code in effective.reason_codes:
        if code in {
            "workspace-policy-reduced-autonomy",
            "workspace-policy-exceeds-ceiling",
            "memory-target-intersection-reduced",
            "memory-target-intersection-empty",
        }:
            steps.append(code)
    steps.append("effective-policy-canonicalized")
    return _unique(steps)


__all__ = [
    "EffectiveMemoryPolicy",
    "resolution_steps",
    "resolve_effective_policy",
]
