from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import hashlib
import json
import math
import re
from typing import Any, Literal

from workflow_skill_router.schemas.artifacts import canonical_json

from .models import (
    CandidateGenerationPolicy,
    EligibilityPolicy,
    HistoryAnalyticsPolicy,
    MemoryFeatures,
    MemoryMode,
    MemoryNotifications,
    MemoryPolicy,
    MemoryPolicyError,
    MemoryScope,
    PrivacyPolicy,
    ProfilePromotionPolicy,
    ProfileVersioningPolicy,
    RememberWorkflowPolicy,
    RouteFeedbackPolicy,
    StoragePolicy,
)
from .safe_yaml import parse_safe_yaml


SCHEMA_ID = "workflow-skill-router/memory-policy"
SCHEMA_VERSION = "1.0.0"
ARTIFACT_KIND = "memory-policy"
_POLICY_ID = re.compile(r"^(personal|workspace):[a-z0-9][a-z0-9._-]{0,63}$")
_TOP_LEVEL_FIELDS = frozenset({
    "schema_id", "schema_version", "artifact_kind", "policy_id", "scope", "mode",
    "storage", "privacy", "eligibility", "features", "notifications",
})
_REQUIRED_TOP_LEVEL_FIELDS = frozenset({
    "schema_id", "schema_version", "artifact_kind", "policy_id", "scope", "mode",
})
_MANAGED_TARGETS = frozenset({"managed-personal", "managed-workspace-local"})
_ALL_TARGETS = frozenset({
    "managed-personal", "managed-workspace-local", "user-personal", "workspace-file",
})

_STORAGE_DEFAULTS: dict[str, object] = {
    "backend": "local-sqlite",
    "retention_days": 90,
    "max_observations": 1000,
    "candidate_retention_days": 30,
    "rejected_suppression_days": 180,
    "max_revisions_per_profile": 20,
    "purge_on_disable": False,
}
_PRIVACY_DEFAULTS: dict[str, object] = {
    "objective": "digest-only",
    "workspace_identity": "digest-only",
    "raw_prompt": "never",
    "file_paths": "never",
    "file_content": "never",
    "tool_arguments": "never",
    "secrets": "never",
    "free_text_feedback": "never",
    "export_redaction": "required",
}
_ELIGIBILITY_DEFAULTS: dict[str, object] = {
    "require_terminal_success": True,
    "require_required_gate_pass": True,
    "reject_unknown_side_effects": True,
    "exclude_risk_levels": ["r3"],
    "minimum_distinct_runs_reviewed": 3,
    "minimum_distinct_runs_automatic": 5,
    "minimum_distinct_days_reviewed": 2,
    "minimum_distinct_days_automatic": 3,
    "minimum_success_rate_reviewed": 0.80,
    "minimum_success_rate_automatic": 0.90,
    "maximum_correction_rate_reviewed": 0.20,
    "maximum_correction_rate_automatic": 0.10,
    "minimum_route_consistency_reviewed": 0.75,
    "minimum_route_consistency_automatic": 0.85,
}
_COMMON_FEATURE_DEFAULTS: dict[str, dict[str, object]] = {
    "remember_this_workflow": {
        "mode": "disabled",
        "eligible_event": "terminal-success",
        "default_target": "managed-personal",
    },
    "route_feedback": {
        "mode": "disabled",
        "allow_standard_reason_codes": True,
        "allow_free_text": False,
    },
    "history_analytics": {"mode": "disabled", "run": "on-demand"},
    "candidate_generation": {
        "mode": "disabled",
        "confidence_required": "medium",
        "backtest_required": True,
    },
    "profile_promotion": {
        "mode": "disabled",
        "target": "managed-personal",
        "conflict_policy": "fail-closed",
        "require_profile_lint": True,
        "require_backtest": True,
    },
    "profile_versioning": {
        "mode": "disabled",
        "diff": "semantic-and-json",
        "rollback": "enabled",
        "write_strategy": "compare-and-swap",
    },
}
_MODE_FEATURE_OVERRIDES: dict[MemoryMode, dict[str, dict[str, object]]] = {
    MemoryMode.DISABLED: {},
    MemoryMode.OBSERVE: {
        "route_feedback": {"mode": "automatic-metadata"},
        "history_analytics": {"mode": "summary"},
    },
    MemoryMode.REVIEWED: {
        "remember_this_workflow": {"mode": "prompt"},
        "route_feedback": {"mode": "automatic-metadata"},
        "history_analytics": {"mode": "summary"},
        "candidate_generation": {"mode": "on-completion"},
        "profile_promotion": {"mode": "review-required"},
        "profile_versioning": {"mode": "required"},
    },
    MemoryMode.AUTOMATIC: {
        "remember_this_workflow": {"mode": "automatic"},
        "route_feedback": {"mode": "automatic-metadata"},
        "history_analytics": {"mode": "summary", "run": "on-completion"},
        "candidate_generation": {
            "mode": "on-completion",
            "confidence_required": "high",
        },
        "profile_promotion": {"mode": "automatic-managed"},
        "profile_versioning": {"mode": "required"},
    },
}
_NOTIFICATION_DEFAULTS: dict[MemoryMode, dict[str, bool]] = {
    MemoryMode.DISABLED: {
        "show_completion_prompt": False,
        "show_candidate_created": False,
        "show_auto_promotion": True,
        "show_retention_purge": True,
    },
    MemoryMode.OBSERVE: {
        "show_completion_prompt": False,
        "show_candidate_created": False,
        "show_auto_promotion": True,
        "show_retention_purge": True,
    },
    MemoryMode.REVIEWED: {
        "show_completion_prompt": True,
        "show_candidate_created": True,
        "show_auto_promotion": True,
        "show_retention_purge": True,
    },
    MemoryMode.AUTOMATIC: {
        "show_completion_prompt": False,
        "show_candidate_created": True,
        "show_auto_promotion": True,
        "show_retention_purge": True,
    },
}
_FEATURE_RANKS: dict[str, tuple[str, ...]] = {
    "remember_this_workflow": ("disabled", "prompt", "automatic"),
    "route_feedback": ("disabled", "manual", "automatic-metadata"),
    "history_analytics": ("disabled", "summary", "detailed-local"),
    "candidate_generation": ("disabled", "on-demand", "on-completion"),
    "profile_promotion": ("disabled", "review-required", "automatic-managed"),
    "profile_versioning": ("disabled", "required"),
}
_MODE_FEATURE_CEILINGS: dict[MemoryMode, dict[str, str]] = {
    MemoryMode.DISABLED: {
        "remember_this_workflow": "disabled",
        "route_feedback": "disabled",
        "history_analytics": "disabled",
        "candidate_generation": "disabled",
        "profile_promotion": "disabled",
        "profile_versioning": "disabled",
    },
    MemoryMode.OBSERVE: {
        "remember_this_workflow": "disabled",
        "route_feedback": "automatic-metadata",
        "history_analytics": "detailed-local",
        "candidate_generation": "disabled",
        "profile_promotion": "disabled",
        "profile_versioning": "disabled",
    },
    MemoryMode.REVIEWED: {
        "remember_this_workflow": "prompt",
        "route_feedback": "automatic-metadata",
        "history_analytics": "detailed-local",
        "candidate_generation": "on-completion",
        "profile_promotion": "review-required",
        "profile_versioning": "required",
    },
    MemoryMode.AUTOMATIC: {
        "remember_this_workflow": "automatic",
        "route_feedback": "automatic-metadata",
        "history_analytics": "detailed-local",
        "candidate_generation": "on-completion",
        "profile_promotion": "automatic-managed",
        "profile_versioning": "required",
    },
}


def _error(code: str, field: str | None = None) -> MemoryPolicyError:
    return MemoryPolicyError(code if field is None else f"{code}:{field}")


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise _error("invalid-object", field)
    return value


def _merge(defaults: Mapping[str, object], provided: object, field: str) -> dict[str, object]:
    if provided is None:
        return dict(defaults)
    source = _mapping(provided, field)
    unknown = sorted(set(source) - set(defaults))
    if unknown:
        raise _error("unknown-field", f"{field}.{unknown[0]}")
    merged = dict(defaults)
    merged.update(source)
    return merged


def _enum(
    value: object,
    allowed: set[str] | frozenset[str] | tuple[str, ...],
    field: str,
) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise _error("invalid-enum", field)
    return value


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise _error("invalid-boolean", field)
    return value


def _integer(value: object, minimum: int, maximum: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _error("invalid-integer", field)
    if value < minimum or value > maximum:
        raise _error("integer-out-of-range", field)
    return value


def _ratio(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error("invalid-number", field)
    result = float(value)
    if not math.isfinite(result) or result < 0.0 or result > 1.0:
        raise _error("number-out-of-range", field)
    return result


def _feature_defaults(mode: MemoryMode) -> dict[str, dict[str, object]]:
    features = {name: dict(values) for name, values in _COMMON_FEATURE_DEFAULTS.items()}
    for name, values in _MODE_FEATURE_OVERRIDES[mode].items():
        features[name].update(values)
    return features


def _decode_storage(value: object) -> StoragePolicy:
    data = _merge(_STORAGE_DEFAULTS, value, "storage")
    return StoragePolicy(
        backend=_enum(data["backend"], {"local-sqlite"}, "storage.backend"),
        retention_days=_integer(
            data["retention_days"], 1, 3650, "storage.retention_days"
        ),
        max_observations=_integer(
            data["max_observations"], 1, 100000, "storage.max_observations"
        ),
        candidate_retention_days=_integer(
            data["candidate_retention_days"],
            1,
            365,
            "storage.candidate_retention_days",
        ),
        rejected_suppression_days=_integer(
            data["rejected_suppression_days"],
            1,
            3650,
            "storage.rejected_suppression_days",
        ),
        max_revisions_per_profile=_integer(
            data["max_revisions_per_profile"],
            2,
            1000,
            "storage.max_revisions_per_profile",
        ),
        purge_on_disable=_boolean(
            data["purge_on_disable"], "storage.purge_on_disable"
        ),
    )


def _decode_privacy(value: object) -> PrivacyPolicy:
    data = _merge(_PRIVACY_DEFAULTS, value, "privacy")
    return PrivacyPolicy(
        objective=_enum(
            data["objective"], {"digest-only", "never"}, "privacy.objective"
        ),
        workspace_identity=_enum(
            data["workspace_identity"],
            {"digest-only", "never"},
            "privacy.workspace_identity",
        ),
        raw_prompt=_enum(data["raw_prompt"], {"never"}, "privacy.raw_prompt"),
        file_paths=_enum(data["file_paths"], {"never"}, "privacy.file_paths"),
        file_content=_enum(
            data["file_content"], {"never"}, "privacy.file_content"
        ),
        tool_arguments=_enum(
            data["tool_arguments"], {"never"}, "privacy.tool_arguments"
        ),
        secrets=_enum(data["secrets"], {"never"}, "privacy.secrets"),
        free_text_feedback=_enum(
            data["free_text_feedback"],
            {"never", "explicit-opt-in"},
            "privacy.free_text_feedback",
        ),
        export_redaction=_enum(
            data["export_redaction"], {"required"}, "privacy.export_redaction"
        ),
    )


def _decode_risk_levels(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise _error("invalid-array", "eligibility.exclude_risk_levels")
    if len(value) > 4:
        raise _error("array-too-large", "eligibility.exclude_risk_levels")
    result = tuple(
        _enum(
            item,
            {"r0", "r1", "r2", "r3"},
            "eligibility.exclude_risk_levels",
        )
        for item in value
    )
    if len(set(result)) != len(result):
        raise _error("duplicate-value", "eligibility.exclude_risk_levels")
    return result


def _decode_eligibility(value: object) -> EligibilityPolicy:
    data = _merge(_ELIGIBILITY_DEFAULTS, value, "eligibility")
    policy = EligibilityPolicy(
        require_terminal_success=_boolean(
            data["require_terminal_success"],
            "eligibility.require_terminal_success",
        ),
        require_required_gate_pass=_boolean(
            data["require_required_gate_pass"],
            "eligibility.require_required_gate_pass",
        ),
        reject_unknown_side_effects=_boolean(
            data["reject_unknown_side_effects"],
            "eligibility.reject_unknown_side_effects",
        ),
        exclude_risk_levels=_decode_risk_levels(data["exclude_risk_levels"]),
        minimum_distinct_runs_reviewed=_integer(
            data["minimum_distinct_runs_reviewed"],
            1,
            100000,
            "eligibility.minimum_distinct_runs_reviewed",
        ),
        minimum_distinct_runs_automatic=_integer(
            data["minimum_distinct_runs_automatic"],
            1,
            100000,
            "eligibility.minimum_distinct_runs_automatic",
        ),
        minimum_distinct_days_reviewed=_integer(
            data["minimum_distinct_days_reviewed"],
            1,
            3650,
            "eligibility.minimum_distinct_days_reviewed",
        ),
        minimum_distinct_days_automatic=_integer(
            data["minimum_distinct_days_automatic"],
            1,
            3650,
            "eligibility.minimum_distinct_days_automatic",
        ),
        minimum_success_rate_reviewed=_ratio(
            data["minimum_success_rate_reviewed"],
            "eligibility.minimum_success_rate_reviewed",
        ),
        minimum_success_rate_automatic=_ratio(
            data["minimum_success_rate_automatic"],
            "eligibility.minimum_success_rate_automatic",
        ),
        maximum_correction_rate_reviewed=_ratio(
            data["maximum_correction_rate_reviewed"],
            "eligibility.maximum_correction_rate_reviewed",
        ),
        maximum_correction_rate_automatic=_ratio(
            data["maximum_correction_rate_automatic"],
            "eligibility.maximum_correction_rate_automatic",
        ),
        minimum_route_consistency_reviewed=_ratio(
            data["minimum_route_consistency_reviewed"],
            "eligibility.minimum_route_consistency_reviewed",
        ),
        minimum_route_consistency_automatic=_ratio(
            data["minimum_route_consistency_automatic"],
            "eligibility.minimum_route_consistency_automatic",
        ),
    )
    minimum_pairs = (
        (
            policy.minimum_distinct_runs_reviewed,
            policy.minimum_distinct_runs_automatic,
        ),
        (
            policy.minimum_distinct_days_reviewed,
            policy.minimum_distinct_days_automatic,
        ),
        (
            policy.minimum_success_rate_reviewed,
            policy.minimum_success_rate_automatic,
        ),
        (
            policy.minimum_route_consistency_reviewed,
            policy.minimum_route_consistency_automatic,
        ),
    )
    maximum_pairs = (
        (
            policy.maximum_correction_rate_reviewed,
            policy.maximum_correction_rate_automatic,
        ),
    )
    if any(automatic < reviewed for reviewed, automatic in minimum_pairs) or any(
        automatic > reviewed for reviewed, automatic in maximum_pairs
    ):
        raise MemoryPolicyError("automatic-threshold-weaker")
    return policy


def _decode_features(mode: MemoryMode, value: object) -> MemoryFeatures:
    defaults = _feature_defaults(mode)
    provided = {} if value is None else dict(_mapping(value, "features"))
    unknown = sorted(set(provided) - set(defaults))
    if unknown:
        raise _error("unknown-field", f"features.{unknown[0]}")
    merged = {
        name: _merge(default, provided.get(name), f"features.{name}")
        for name, default in defaults.items()
    }
    remember_data = merged["remember_this_workflow"]
    feedback_data = merged["route_feedback"]
    history_data = merged["history_analytics"]
    candidate_data = merged["candidate_generation"]
    promotion_data = merged["profile_promotion"]
    versioning_data = merged["profile_versioning"]
    features = MemoryFeatures(
        remember_this_workflow=RememberWorkflowPolicy(
            mode=_enum(
                remember_data["mode"],
                _FEATURE_RANKS["remember_this_workflow"],
                "features.remember_this_workflow.mode",
            ),
            eligible_event=_enum(
                remember_data["eligible_event"],
                {"terminal-success"},
                "features.remember_this_workflow.eligible_event",
            ),
            default_target=_enum(
                remember_data["default_target"],
                _ALL_TARGETS,
                "features.remember_this_workflow.default_target",
            ),
        ),
        route_feedback=RouteFeedbackPolicy(
            mode=_enum(
                feedback_data["mode"],
                _FEATURE_RANKS["route_feedback"],
                "features.route_feedback.mode",
            ),
            allow_standard_reason_codes=_boolean(
                feedback_data["allow_standard_reason_codes"],
                "features.route_feedback.allow_standard_reason_codes",
            ),
            allow_free_text=_boolean(
                feedback_data["allow_free_text"],
                "features.route_feedback.allow_free_text",
            ),
        ),
        history_analytics=HistoryAnalyticsPolicy(
            mode=_enum(
                history_data["mode"],
                _FEATURE_RANKS["history_analytics"],
                "features.history_analytics.mode",
            ),
            run=_enum(
                history_data["run"],
                {"on-demand", "on-completion", "scheduled-local"},
                "features.history_analytics.run",
            ),
        ),
        candidate_generation=CandidateGenerationPolicy(
            mode=_enum(
                candidate_data["mode"],
                _FEATURE_RANKS["candidate_generation"],
                "features.candidate_generation.mode",
            ),
            confidence_required=_enum(
                candidate_data["confidence_required"],
                {"medium", "high"},
                "features.candidate_generation.confidence_required",
            ),
            backtest_required=_boolean(
                candidate_data["backtest_required"],
                "features.candidate_generation.backtest_required",
            ),
        ),
        profile_promotion=ProfilePromotionPolicy(
            mode=_enum(
                promotion_data["mode"],
                _FEATURE_RANKS["profile_promotion"],
                "features.profile_promotion.mode",
            ),
            target=_enum(
                promotion_data["target"],
                _ALL_TARGETS,
                "features.profile_promotion.target",
            ),
            conflict_policy=_enum(
                promotion_data["conflict_policy"],
                {"fail-closed"},
                "features.profile_promotion.conflict_policy",
            ),
            require_profile_lint=_boolean(
                promotion_data["require_profile_lint"],
                "features.profile_promotion.require_profile_lint",
            ),
            require_backtest=_boolean(
                promotion_data["require_backtest"],
                "features.profile_promotion.require_backtest",
            ),
        ),
        profile_versioning=ProfileVersioningPolicy(
            mode=_enum(
                versioning_data["mode"],
                _FEATURE_RANKS["profile_versioning"],
                "features.profile_versioning.mode",
            ),
            diff=_enum(
                versioning_data["diff"],
                {"semantic-and-json"},
                "features.profile_versioning.diff",
            ),
            rollback=_enum(
                versioning_data["rollback"],
                {"enabled"},
                "features.profile_versioning.rollback",
            ),
            write_strategy=_enum(
                versioning_data["write_strategy"],
                {"compare-and-swap"},
                "features.profile_versioning.write_strategy",
            ),
        ),
    )
    for name, feature_mode in (
        ("remember_this_workflow", features.remember_this_workflow.mode),
        ("route_feedback", features.route_feedback.mode),
        ("history_analytics", features.history_analytics.mode),
        ("candidate_generation", features.candidate_generation.mode),
        ("profile_promotion", features.profile_promotion.mode),
        ("profile_versioning", features.profile_versioning.mode),
    ):
        ranking = _FEATURE_RANKS[name]
        ceiling = _MODE_FEATURE_CEILINGS[mode][name]
        if ranking.index(feature_mode) > ranking.index(ceiling):
            raise _error("feature-autonomy-exceeds-mode", f"features.{name}.mode")
    return features


def _decode_notifications(mode: MemoryMode, value: object) -> MemoryNotifications:
    data = _merge(_NOTIFICATION_DEFAULTS[mode], value, "notifications")
    notifications = MemoryNotifications(
        show_completion_prompt=_boolean(
            data["show_completion_prompt"],
            "notifications.show_completion_prompt",
        ),
        show_candidate_created=_boolean(
            data["show_candidate_created"],
            "notifications.show_candidate_created",
        ),
        show_auto_promotion=_boolean(
            data["show_auto_promotion"],
            "notifications.show_auto_promotion",
        ),
        show_retention_purge=_boolean(
            data["show_retention_purge"],
            "notifications.show_retention_purge",
        ),
    )
    if mode is MemoryMode.AUTOMATIC and not notifications.show_auto_promotion:
        raise MemoryPolicyError("automatic-notification-required")
    return notifications


def _validate_cross_fields(policy: MemoryPolicy) -> None:
    features = policy.features
    if (
        features.remember_this_workflow.mode == "automatic"
        and features.remember_this_workflow.default_target not in _MANAGED_TARGETS
    ):
        raise MemoryPolicyError("automatic-target-not-managed")
    if (
        features.profile_promotion.mode == "automatic-managed"
        and features.profile_promotion.target not in _MANAGED_TARGETS
    ):
        raise MemoryPolicyError("automatic-target-not-managed")
    if (
        features.candidate_generation.mode != "disabled"
        and not features.candidate_generation.backtest_required
    ):
        raise MemoryPolicyError("candidate-backtest-required")
    if (
        features.profile_promotion.mode != "disabled"
        and features.profile_versioning.mode != "required"
    ):
        raise MemoryPolicyError("promotion-requires-versioning")
    if features.profile_promotion.mode != "disabled" and (
        not features.profile_promotion.require_profile_lint
        or not features.profile_promotion.require_backtest
    ):
        raise MemoryPolicyError("promotion-safety-check-required")
    if (
        features.profile_promotion.mode == "automatic-managed"
        and features.candidate_generation.confidence_required != "high"
    ):
        raise MemoryPolicyError("automatic-confidence-high-required")
    if (
        features.route_feedback.allow_free_text
        and policy.privacy.free_text_feedback != "explicit-opt-in"
    ):
        raise MemoryPolicyError("free-text-feedback-not-opted-in")
    if (
        policy.mode is MemoryMode.AUTOMATIC
        and "r3" not in policy.eligibility.exclude_risk_levels
    ):
        raise MemoryPolicyError("automatic-r3-exclusion-required")


def decode_memory_policy(
    document: Mapping[str, object],
    *,
    expected_scope: MemoryScope | None = None,
) -> MemoryPolicy:
    root = _mapping(document, "policy")
    unknown = sorted(set(root) - _TOP_LEVEL_FIELDS)
    if unknown:
        raise _error("unknown-field", unknown[0])
    missing = sorted(_REQUIRED_TOP_LEVEL_FIELDS - set(root))
    if missing:
        raise _error("missing-field", missing[0])
    if root["schema_id"] != SCHEMA_ID:
        raise MemoryPolicyError("schema-id-mismatch")
    if root["schema_version"] != SCHEMA_VERSION:
        raise MemoryPolicyError("schema-version-mismatch")
    if root["artifact_kind"] != ARTIFACT_KIND:
        raise MemoryPolicyError("artifact-kind-mismatch")
    policy_id = root["policy_id"]
    if not isinstance(policy_id, str) or _POLICY_ID.fullmatch(policy_id) is None:
        raise MemoryPolicyError("policy-id-invalid")
    try:
        scope = MemoryScope(root["scope"])
    except (TypeError, ValueError) as error:
        raise _error("invalid-enum", "scope") from error
    try:
        mode = MemoryMode(root["mode"])
    except (TypeError, ValueError) as error:
        raise _error("invalid-enum", "mode") from error
    if policy_id.split(":", 1)[0] != scope.value:
        raise MemoryPolicyError("policy-scope-mismatch")
    if expected_scope is not None and scope is not expected_scope:
        raise MemoryPolicyError("unexpected-policy-scope")
    policy = MemoryPolicy(
        schema_id=SCHEMA_ID,
        schema_version=SCHEMA_VERSION,
        artifact_kind=ARTIFACT_KIND,
        policy_id=policy_id,
        scope=scope,
        mode=mode,
        capture="none" if mode is MemoryMode.DISABLED else "minimal",
        storage=_decode_storage(root.get("storage")),
        privacy=_decode_privacy(root.get("privacy")),
        eligibility=_decode_eligibility(root.get("eligibility")),
        features=_decode_features(mode, root.get("features")),
        notifications=_decode_notifications(mode, root.get("notifications")),
        policy_digest="",
    )
    _validate_cross_fields(policy)
    digest = "sha256:" + hashlib.sha256(
        canonical_json(policy.to_dict()).encode("utf-8")
    ).hexdigest()
    return replace(policy, policy_digest=digest)


def memory_policy_document(policy: MemoryPolicy) -> dict[str, Any]:
    if not isinstance(policy, MemoryPolicy):
        raise TypeError("policy must be MemoryPolicy")
    return policy.to_dict()


def _json_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MemoryPolicyError(f"duplicate-key:{key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise MemoryPolicyError(f"json-non-finite-number:{value}")


def decode_policy_text(
    text: str,
    *,
    format: Literal["json", "yaml"],
    expected_scope: MemoryScope | None = None,
) -> MemoryPolicy:
    if not isinstance(text, str):
        raise MemoryPolicyError("policy-text-invalid")
    if format == "json":
        try:
            document = json.loads(
                text,
                object_pairs_hook=_json_pairs,
                parse_constant=_reject_constant,
            )
        except MemoryPolicyError:
            raise
        except json.JSONDecodeError as error:
            raise MemoryPolicyError("invalid-json") from error
    elif format == "yaml":
        document = parse_safe_yaml(text)
    else:
        raise MemoryPolicyError("unsupported-policy-format")
    if not isinstance(document, Mapping):
        raise MemoryPolicyError("policy-root-must-be-object")
    return decode_memory_policy(document, expected_scope=expected_scope)
