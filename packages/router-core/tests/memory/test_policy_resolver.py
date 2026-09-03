from __future__ import annotations

import json
import unittest

from workflow_skill_router.memory import MemoryMode, MemoryScope, decode_memory_policy
from workflow_skill_router.memory.policy_io import PolicyLoadResult, PolicySource
from workflow_skill_router.memory.policy_resolver import resolve_effective_policy


def valid_result(
    scope: str,
    mode: str,
    *,
    mutate=None,
) -> PolicyLoadResult:
    document: dict[str, object] = {
        "schema_id": "workflow-skill-router/memory-policy",
        "schema_version": "1.0.0",
        "artifact_kind": "memory-policy",
        "policy_id": f"{scope}:test",
        "scope": scope,
        "mode": mode,
    }
    if mutate is not None:
        document = decode_memory_policy(document).to_dict()
        mutate(document)
    policy = decode_memory_policy(document)
    return PolicyLoadResult(
        status="valid",
        source=PolicySource(
            scope=MemoryScope(scope),
            format="json",
            source_class=f"{scope}-policy",
            policy=policy,
        ),
        reason_codes=(),
    )


def missing_personal() -> PolicyLoadResult:
    return PolicyLoadResult(
        status="missing",
        source=None,
        reason_codes=("personal-policy-missing",),
    )


def invalid_workspace(code: str = "invalid-memory-policy") -> PolicyLoadResult:
    return PolicyLoadResult(status="invalid", source=None, reason_codes=(code,))


class EffectiveMemoryPolicyTests(unittest.TestCase):
    def test_missing_personal_policy_is_disabled_without_capture(self) -> None:
        effective = resolve_effective_policy(personal=missing_personal(), workspace=None)

        self.assertEqual(MemoryMode.DISABLED, effective.mode)
        self.assertEqual(MemoryMode.DISABLED, effective.personal_mode)
        self.assertIsNone(effective.workspace_requested_mode)
        self.assertEqual("personal-policy-missing", effective.policy_source)
        self.assertFalse(effective.capture_enabled)
        self.assertFalse(effective.candidate_generation_enabled)
        self.assertEqual("disabled", effective.profile_promotion)
        self.assertEqual((), effective.allowed_targets)
        self.assertEqual(("personal-policy-missing",), effective.reason_codes)

    def test_workspace_cannot_elevate_personal_ceiling(self) -> None:
        effective = resolve_effective_policy(
            personal=valid_result("personal", "observe"),
            workspace=valid_result("workspace", "automatic"),
        )

        self.assertEqual(MemoryMode.OBSERVE, effective.mode)
        self.assertEqual(MemoryMode.OBSERVE, effective.personal_mode)
        self.assertEqual(MemoryMode.AUTOMATIC, effective.workspace_requested_mode)
        self.assertEqual("personal-ceiling", effective.policy_source)
        self.assertIn("workspace-policy-exceeds-ceiling", effective.reason_codes)
        self.assertTrue(effective.capture_enabled)
        self.assertFalse(effective.candidate_generation_enabled)

    def test_workspace_can_reduce_personal_autonomy(self) -> None:
        effective = resolve_effective_policy(
            personal=valid_result("personal", "automatic"),
            workspace=valid_result("workspace", "reviewed"),
        )

        self.assertEqual(MemoryMode.REVIEWED, effective.mode)
        self.assertEqual("workspace-restriction", effective.policy_source)
        self.assertEqual("review-required", effective.profile_promotion)
        self.assertIn("workspace-policy-reduced-autonomy", effective.reason_codes)

    def test_invalid_or_ambiguous_workspace_policy_disables_memory_for_that_workspace(self) -> None:
        for status, code in (
            ("invalid", "invalid-memory-policy"),
            ("ambiguous", "ambiguous-memory-policy"),
        ):
            with self.subTest(status=status):
                workspace = PolicyLoadResult(status=status, source=None, reason_codes=(code,))
                effective = resolve_effective_policy(
                    personal=valid_result("personal", "automatic"),
                    workspace=workspace,
                )
                self.assertEqual(MemoryMode.DISABLED, effective.mode)
                self.assertEqual("invalid-workspace-policy", effective.policy_source)
                self.assertIn(code, effective.reason_codes)
                self.assertFalse(effective.capture_enabled)

    def test_numeric_privacy_exclusion_and_feature_intersection_are_stricter(self) -> None:
        def personal(document: dict[str, object]) -> None:
            storage = document["storage"]
            assert isinstance(storage, dict)
            storage["retention_days"] = 180
            storage["max_observations"] = 1000
            eligibility = document["eligibility"]
            assert isinstance(eligibility, dict)
            eligibility["minimum_distinct_runs_reviewed"] = 3
            eligibility["minimum_distinct_runs_automatic"] = 5
            eligibility["maximum_correction_rate_reviewed"] = 0.20
            eligibility["maximum_correction_rate_automatic"] = 0.10

        def workspace(document: dict[str, object]) -> None:
            storage = document["storage"]
            assert isinstance(storage, dict)
            storage["retention_days"] = 30
            storage["max_observations"] = 200
            privacy = document["privacy"]
            assert isinstance(privacy, dict)
            privacy["objective"] = "never"
            eligibility = document["eligibility"]
            assert isinstance(eligibility, dict)
            eligibility["exclude_risk_levels"] = ["r2", "r3"]
            eligibility["minimum_distinct_runs_reviewed"] = 4
            eligibility["minimum_distinct_runs_automatic"] = 7
            eligibility["maximum_correction_rate_reviewed"] = 0.15
            eligibility["maximum_correction_rate_automatic"] = 0.05
            features = document["features"]
            assert isinstance(features, dict)
            route_feedback = features["route_feedback"]
            assert isinstance(route_feedback, dict)
            route_feedback["mode"] = "manual"

        effective = resolve_effective_policy(
            personal=valid_result("personal", "automatic", mutate=personal),
            workspace=valid_result("workspace", "reviewed", mutate=workspace),
        )

        self.assertEqual(30, effective.policy.storage.retention_days)
        self.assertEqual(200, effective.policy.storage.max_observations)
        self.assertEqual("never", effective.policy.privacy.objective)
        self.assertEqual(("r2", "r3"), effective.policy.eligibility.exclude_risk_levels)
        self.assertEqual(4, effective.policy.eligibility.minimum_distinct_runs_reviewed)
        self.assertEqual(7, effective.policy.eligibility.minimum_distinct_runs_automatic)
        self.assertEqual(0.15, effective.policy.eligibility.maximum_correction_rate_reviewed)
        self.assertEqual(0.05, effective.policy.eligibility.maximum_correction_rate_automatic)
        self.assertEqual("manual", effective.policy.features.route_feedback.mode)
        self.assertEqual(("managed-personal",), effective.allowed_targets)

    def test_host_disable_and_explicit_no_memory_are_hard_reductions(self) -> None:
        personal = valid_result("personal", "automatic")
        host_disabled = resolve_effective_policy(
            personal=personal,
            workspace=None,
            host_disabled=True,
        )
        explicit = resolve_effective_policy(
            personal=personal,
            workspace=None,
            explicit_no_memory=True,
        )

        self.assertEqual(MemoryMode.DISABLED, host_disabled.mode)
        self.assertEqual("host-memory-disabled", host_disabled.policy_source)
        self.assertEqual(MemoryMode.DISABLED, explicit.mode)
        self.assertEqual("explicit-no-memory", explicit.policy_source)

    def test_empty_target_intersection_disables_promotion_without_disabling_observation(self) -> None:
        def workspace(document: dict[str, object]) -> None:
            features = document["features"]
            assert isinstance(features, dict)
            remember = features["remember_this_workflow"]
            promotion = features["profile_promotion"]
            assert isinstance(remember, dict)
            assert isinstance(promotion, dict)
            remember["default_target"] = "workspace-file"
            promotion["target"] = "workspace-file"

        effective = resolve_effective_policy(
            personal=valid_result("personal", "automatic"),
            workspace=valid_result("workspace", "reviewed", mutate=workspace),
        )

        self.assertEqual(MemoryMode.REVIEWED, effective.mode)
        self.assertTrue(effective.capture_enabled)
        self.assertEqual((), effective.allowed_targets)
        self.assertEqual("disabled", effective.profile_promotion)
        self.assertIn("memory-target-intersection-empty", effective.reason_codes)

    def test_no_workspace_policy_preserves_personal_policy(self) -> None:
        effective = resolve_effective_policy(
            personal=valid_result("personal", "reviewed"),
            workspace=None,
        )

        self.assertEqual(MemoryMode.REVIEWED, effective.mode)
        self.assertEqual("personal-policy", effective.policy_source)
        self.assertIsNone(effective.workspace_requested_mode)
        self.assertEqual(("managed-personal",), effective.allowed_targets)

    def test_effective_digest_is_stable_and_public_document_contains_no_source_path(self) -> None:
        first = resolve_effective_policy(
            personal=valid_result("personal", "automatic"),
            workspace=valid_result("workspace", "reviewed"),
        )
        second = resolve_effective_policy(
            personal=valid_result("personal", "automatic"),
            workspace=valid_result("workspace", "reviewed"),
        )

        self.assertEqual(first.policy_digest, second.policy_digest)
        self.assertRegex(first.policy_digest, r"^sha256:[0-9a-f]{64}$")
        public = json.dumps(first.to_public_dict(), sort_keys=True)
        self.assertNotIn("source_path", public)
        self.assertNotIn("policy_document", public)
        self.assertEqual("reviewed", first.to_public_dict()["mode"])


if __name__ == "__main__":
    unittest.main()
