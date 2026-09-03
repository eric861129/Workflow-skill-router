from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.memory import (
    MemoryMode,
    MemoryPolicyError,
    decode_policy_text,
    parse_safe_yaml,
)


REVIEWED_YAML = """
# safe block-only policy
schema_id: workflow-skill-router/memory-policy
schema_version: 1.0.0
artifact_kind: memory-policy
policy_id: personal:reviewed
scope: personal
mode: reviewed
storage:
  backend: local-sqlite
  retention_days: 90
  max_observations: 1000
  candidate_retention_days: 30
  rejected_suppression_days: 180
  max_revisions_per_profile: 20
  purge_on_disable: false
privacy:
  objective: digest-only
  workspace_identity: digest-only
  raw_prompt: never
  file_paths: never
  file_content: never
  tool_arguments: never
  secrets: never
  free_text_feedback: never
  export_redaction: required
eligibility:
  require_terminal_success: true
  require_required_gate_pass: true
  reject_unknown_side_effects: true
  exclude_risk_levels:
    - r3
  minimum_distinct_runs_reviewed: 3
  minimum_distinct_runs_automatic: 5
  minimum_distinct_days_reviewed: 2
  minimum_distinct_days_automatic: 3
  minimum_success_rate_reviewed: 0.80
  minimum_success_rate_automatic: 0.90
  maximum_correction_rate_reviewed: 0.20
  maximum_correction_rate_automatic: 0.10
  minimum_route_consistency_reviewed: 0.75
  minimum_route_consistency_automatic: 0.85
features:
  remember_this_workflow:
    mode: prompt
    eligible_event: terminal-success
    default_target: managed-personal
  route_feedback:
    mode: automatic-metadata
    allow_standard_reason_codes: true
    allow_free_text: false
  history_analytics:
    mode: summary
    run: on-demand
  candidate_generation:
    mode: on-completion
    confidence_required: medium
    backtest_required: true
  profile_promotion:
    mode: review-required
    target: managed-personal
    conflict_policy: fail-closed
    require_profile_lint: true
    require_backtest: true
  profile_versioning:
    mode: required
    diff: semantic-and-json
    rollback: enabled
    write_strategy: compare-and-swap
notifications:
  show_completion_prompt: true
  show_candidate_created: true
  show_auto_promotion: true
  show_retention_purge: true
""".strip()


class SafeYamlTests(unittest.TestCase):
    def test_repository_reviewed_example_decodes_with_expected_policy(self) -> None:
        repository_root = Path(__file__).resolve().parents[4]
        example = (
            repository_root
            / "docs/architecture/examples/workflow-memory.reviewed.yaml"
        ).read_text(encoding="utf-8")

        policy = decode_policy_text(example, format="yaml")

        self.assertEqual(MemoryMode.REVIEWED, policy.mode)
        self.assertEqual("prompt", policy.features.remember_this_workflow.mode)
        self.assertEqual("review-required", policy.features.profile_promotion.mode)
        self.assertEqual("required", policy.features.profile_versioning.mode)

    def test_parses_nested_policy_and_scalar_list(self) -> None:
        document = parse_safe_yaml(REVIEWED_YAML)

        self.assertEqual("reviewed", document["mode"])
        self.assertEqual(["r3"], document["eligibility"]["exclude_risk_levels"])
        self.assertEqual(
            0.9,
            document["eligibility"]["minimum_success_rate_automatic"],
        )
        self.assertIs(document["notifications"]["show_auto_promotion"], True)

        policy = decode_policy_text(REVIEWED_YAML, format="yaml")
        self.assertEqual(MemoryMode.REVIEWED, policy.mode)
        self.assertEqual("prompt", policy.features.remember_this_workflow.mode)

    def test_equivalent_json_and_yaml_have_same_normalized_document_and_digest(self) -> None:
        yaml_policy = decode_policy_text(REVIEWED_YAML, format="yaml")
        json_policy = decode_policy_text(
            json.dumps(parse_safe_yaml(REVIEWED_YAML), ensure_ascii=False),
            format="json",
        )

        self.assertEqual(
            yaml_policy.normalized_document,
            json_policy.normalized_document,
        )
        self.assertEqual(yaml_policy.policy_digest, json_policy.policy_digest)

    def test_comments_and_key_order_do_not_change_digest(self) -> None:
        first = decode_policy_text(
            "schema_id: workflow-skill-router/memory-policy\n"
            "schema_version: 1.0.0\n"
            "artifact_kind: memory-policy\n"
            "policy_id: personal:default\n"
            "scope: personal\n"
            "mode: disabled\n",
            format="yaml",
        )
        second = decode_policy_text(
            "# comment\n"
            "mode: disabled\n"
            "scope: personal\n"
            "policy_id: personal:default\n"
            "artifact_kind: memory-policy\n"
            "schema_version: 1.0.0\n"
            "schema_id: workflow-skill-router/memory-policy\n",
            format="yaml",
        )
        self.assertEqual(first.policy_digest, second.policy_digest)

    def test_rejects_unsafe_or_ambiguous_yaml(self) -> None:
        unsafe = (
            "defaults: &defaults\n  mode: automatic\npolicy:\n  <<: *defaults\n",
            "mode: !!python/object:example\n",
            "---\nmode: disabled\n---\nmode: automatic\n",
            "mode: disabled\nmode: automatic\n",
            "features:\n\tremember_this_workflow:\n    mode: prompt\n",
            "text: |\n  hidden\n",
            "features: {mode: automatic}\n",
            "features: [automatic]\n",
            "mode: disabled # inline comments are intentionally unsupported\n",
            "'mode': disabled\n",
            "mode:\n    nested: too-deep\n",
        )
        for text in unsafe:
            with self.subTest(text=text):
                with self.assertRaises(MemoryPolicyError):
                    parse_safe_yaml(text)

    def test_rejects_non_json_scalar_and_non_string_mapping_key(self) -> None:
        for text in (
            "mode: .nan\n",
            "mode: 2026-09-03\n",
            "1: disabled\n",
            "mode: ~\n",
        ):
            with self.subTest(text=text):
                with self.assertRaises(MemoryPolicyError):
                    parse_safe_yaml(text)

    def test_rejects_mixed_mapping_and_sequence_at_same_level(self) -> None:
        with self.assertRaisesRegex(MemoryPolicyError, "mixed-container"):
            parse_safe_yaml("mode: disabled\n- observe\n")


if __name__ == "__main__":
    unittest.main()
