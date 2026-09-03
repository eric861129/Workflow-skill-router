from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.memory import (
    MemoryMode,
    MemoryPolicyError,
    MemoryScope,
    decode_memory_policy,
    decode_policy_text,
    memory_policy_document,
)


def minimal_policy(mode: str = "disabled", *, scope: str = "personal") -> dict[str, object]:
    return {
        "schema_id": "workflow-skill-router/memory-policy",
        "schema_version": "1.0.0",
        "artifact_kind": "memory-policy",
        "policy_id": f"{scope}:default",
        "scope": scope,
        "mode": mode,
    }


class MemoryPolicyContractTests(unittest.TestCase):
    def test_minimal_policy_uses_disabled_preset(self) -> None:
        policy = decode_memory_policy(
            minimal_policy(), expected_scope=MemoryScope.PERSONAL
        )

        self.assertEqual(MemoryMode.DISABLED, policy.mode)
        self.assertEqual(MemoryScope.PERSONAL, policy.scope)
        self.assertEqual("none", policy.capture)
        self.assertEqual("disabled", policy.features.remember_this_workflow.mode)
        self.assertEqual("disabled", policy.features.route_feedback.mode)
        self.assertEqual("disabled", policy.features.history_analytics.mode)
        self.assertEqual("disabled", policy.features.candidate_generation.mode)
        self.assertEqual("disabled", policy.features.profile_promotion.mode)
        self.assertEqual("disabled", policy.features.profile_versioning.mode)
        self.assertRegex(policy.policy_digest, r"^sha256:[0-9a-f]{64}$")

    def test_mode_presets_expand_to_expected_feature_autonomy(self) -> None:
        expectations = {
            "observe": (
                "minimal", "disabled", "automatic-metadata", "summary",
                "disabled", "disabled",
            ),
            "reviewed": (
                "minimal", "prompt", "automatic-metadata", "summary",
                "on-completion", "review-required",
            ),
            "automatic": (
                "minimal", "automatic", "automatic-metadata", "summary",
                "on-completion", "automatic-managed",
            ),
        }
        for mode, expected in expectations.items():
            with self.subTest(mode=mode):
                policy = decode_memory_policy(minimal_policy(mode))
                actual = (
                    policy.capture,
                    policy.features.remember_this_workflow.mode,
                    policy.features.route_feedback.mode,
                    policy.features.history_analytics.mode,
                    policy.features.candidate_generation.mode,
                    policy.features.profile_promotion.mode,
                )
                self.assertEqual(expected, actual)

    def test_unknown_top_level_and_nested_fields_are_rejected(self) -> None:
        top_level = minimal_policy()
        top_level["instructions"] = "remember everything"
        with self.assertRaisesRegex(MemoryPolicyError, "unknown-field"):
            decode_memory_policy(top_level)

        nested = minimal_policy("reviewed")
        nested["storage"] = {"retention_days": 90, "surprise": True}
        with self.assertRaisesRegex(MemoryPolicyError, "unknown-field"):
            decode_memory_policy(nested)

    def test_policy_id_prefix_and_expected_scope_must_match(self) -> None:
        document = minimal_policy(scope="workspace")
        document["policy_id"] = "personal:wrong"
        with self.assertRaisesRegex(MemoryPolicyError, "policy-scope-mismatch"):
            decode_memory_policy(document)

        with self.assertRaisesRegex(MemoryPolicyError, "unexpected-policy-scope"):
            decode_memory_policy(
                minimal_policy(scope="workspace"),
                expected_scope=MemoryScope.PERSONAL,
            )

    def test_feature_override_cannot_exceed_mode_ceiling(self) -> None:
        document = minimal_policy("observe")
        document["features"] = {
            "remember_this_workflow": {
                "mode": "prompt",
                "eligible_event": "terminal-success",
                "default_target": "managed-personal",
            }
        }
        with self.assertRaisesRegex(MemoryPolicyError, "feature-autonomy-exceeds-mode"):
            decode_memory_policy(document)

    def test_automatic_thresholds_cannot_be_weaker_than_reviewed(self) -> None:
        document = minimal_policy("automatic")
        document["eligibility"] = {
            "minimum_distinct_runs_reviewed": 5,
            "minimum_distinct_runs_automatic": 4,
        }
        with self.assertRaisesRegex(MemoryPolicyError, "automatic-threshold-weaker"):
            decode_memory_policy(document)

        document = minimal_policy("automatic")
        document["eligibility"] = {
            "maximum_correction_rate_reviewed": 0.10,
            "maximum_correction_rate_automatic": 0.20,
        }
        with self.assertRaisesRegex(MemoryPolicyError, "automatic-threshold-weaker"):
            decode_memory_policy(document)

    def test_automatic_managed_promotion_cannot_target_user_owned_profile(self) -> None:
        document = minimal_policy("automatic")
        document["features"] = {
            "profile_promotion": {
                "mode": "automatic-managed",
                "target": "user-personal",
                "conflict_policy": "fail-closed",
                "require_profile_lint": True,
                "require_backtest": True,
            }
        }
        with self.assertRaisesRegex(MemoryPolicyError, "automatic-target-not-managed"):
            decode_memory_policy(document)

    def test_enabled_profile_promotion_requires_versioning(self) -> None:
        document = minimal_policy("reviewed")
        document["features"] = {
            "profile_promotion": {
                "mode": "review-required",
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
        with self.assertRaisesRegex(MemoryPolicyError, "promotion-requires-versioning"):
            decode_memory_policy(document)

    def test_automatic_mode_requires_visible_auto_promotion_notification(self) -> None:
        document = minimal_policy("automatic")
        document["notifications"] = {"show_auto_promotion": False}
        with self.assertRaisesRegex(MemoryPolicyError, "automatic-notification-required"):
            decode_memory_policy(document)

    def test_privacy_contract_rejects_raw_or_executable_data_retention(self) -> None:
        for field, value in (
            ("raw_prompt", "stored"),
            ("file_paths", "digest-only"),
            ("file_content", "stored"),
            ("tool_arguments", "stored"),
            ("secrets", "encrypted"),
        ):
            with self.subTest(field=field):
                document = minimal_policy("observe")
                document["privacy"] = {field: value}
                with self.assertRaisesRegex(MemoryPolicyError, "invalid-enum"):
                    decode_memory_policy(document)

    def test_free_text_feedback_requires_explicit_privacy_opt_in(self) -> None:
        document = minimal_policy("reviewed")
        document["features"] = {
            "route_feedback": {
                "mode": "manual",
                "allow_standard_reason_codes": True,
                "allow_free_text": True,
            }
        }
        with self.assertRaisesRegex(MemoryPolicyError, "free-text-feedback-not-opted-in"):
            decode_memory_policy(document)

        document["privacy"] = {"free_text_feedback": "explicit-opt-in"}
        policy = decode_memory_policy(document)
        self.assertTrue(policy.features.route_feedback.allow_free_text)

    def test_duplicate_risk_levels_and_boolean_in_integer_field_are_rejected(self) -> None:
        document = minimal_policy("reviewed")
        document["eligibility"] = {"exclude_risk_levels": ["r3", "r3"]}
        with self.assertRaisesRegex(MemoryPolicyError, "duplicate-value"):
            decode_memory_policy(document)

        document = minimal_policy("reviewed")
        document["storage"] = {"retention_days": True}
        with self.assertRaisesRegex(MemoryPolicyError, "invalid-integer"):
            decode_memory_policy(document)

    def test_normalized_document_round_trips_with_stable_digest(self) -> None:
        first = decode_memory_policy(minimal_policy("reviewed"))
        document = memory_policy_document(first)
        second = decode_memory_policy(document)

        self.assertEqual(document, memory_policy_document(second))
        self.assertEqual(first.policy_digest, second.policy_digest)
        self.assertNotIn("policy_digest", document)

    def test_json_duplicate_keys_are_rejected_before_contract_decode(self) -> None:
        text = json.dumps(minimal_policy())[:-1] + ',"mode":"automatic"}'
        with self.assertRaisesRegex(MemoryPolicyError, "duplicate-key"):
            decode_policy_text(text, format="json")


if __name__ == "__main__":
    unittest.main()
