from __future__ import annotations

from dataclasses import replace
import unittest

from workflow_skill_router.memory.candidates import PatternMetrics, WorkflowCandidate
from workflow_skill_router.memory.observations import MatcherSeed, RouteObservationPhase
from workflow_skill_router.memory.profile_diff import build_profile_document, diff_profiles
from workflow_skill_router.memory.models import MemoryScope
from workflow_skill_router.profiles.contract import decode_routing_profile


def candidate() -> WorkflowCandidate:
    metrics = PatternMetrics(3, 2, 1.0, 1.0, 0.0, 1.0, True, 0)
    return WorkflowCandidate(
        candidate_id="candidate:" + "a" * 32,
        candidate_digest="sha256:" + "b" * 64,
        pattern_id="pattern:" + "c" * 32,
        status="proposed",
        recommendation_mode="reviewed",
        confidence="medium",
        scope=MemoryScope.PERSONAL,
        matcher_seed=MatcherSeed(("student api",), ("api",), (), "existing-profile"),
        work_mode="phased",
        phases=(
            RouteObservationPhase("contract", "skill:api-designer", (), ("contract-reviewed",)),
            RouteObservationPhase("implementation", "skill:csharp-developer", (), ("implementation-complete",)),
        ),
        workspace_identity_digest=None,
        profile_source_class="personal-profile",
        target_profile_class="managed-personal",
        metrics=metrics,
        material_evidence_digest="sha256:" + "d" * 64,
        policy_digest="sha256:" + "e" * 64,
        reason_codes=(),
        created_at="2026-09-04T00:00:00.000Z",
    )


class ProfileDiffTests(unittest.TestCase):
    def test_candidate_builds_strict_routing_profile_and_semantic_rule_addition(self) -> None:
        document = build_profile_document(candidate(), None)
        profile = decode_routing_profile(document, expected_scope="personal")
        self.assertEqual("personal:adaptive-memory", profile.profile_id)
        self.assertEqual(1, len(profile.rules))
        self.assertEqual("phased", profile.rules[0].route.work_mode)
        self.assertEqual("contract-reviewed", profile.rules[0].route.skill_tree[0].exit_gate)

        diff = diff_profiles(None, document)
        self.assertEqual(("rule-added",), tuple(item.change_type for item in diff.entries))
        self.assertRegex(diff.semantic_diff_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(diff.json_patch)

    def test_candidate_rejects_phase_without_one_primary_or_one_exit_gate(self) -> None:
        bad = replace(
            candidate(),
            phases=(RouteObservationPhase("contract", None, (), ("a", "b")),),
        )
        with self.assertRaisesRegex(ValueError, "candidate-phase"):
            build_profile_document(bad, None)


if __name__ == "__main__":
    unittest.main()
