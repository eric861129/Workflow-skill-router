from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.evaluation.hybrid_consent import (
    HybridConsentEvaluationController,
)


class HybridConsentEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.controller = HybridConsentEvaluationController(
            Path(self.directory.name) / "router.db",
            session_id="evaluation-session-1",
        )
        self.proposed_route = {
            "envelope": "phased",
            "selection_mode": "explicit-locked",
            "primary_skill": "skill:api-designer",
            "support_skills": ["skill:qa-test-planner"],
            "consent_action": "proposal-required",
            "goal_relation": "none",
            "rationale": "Contract verification needs one support SKILL.",
        }

    def test_model_intent_is_applied_to_persisted_route_not_a_rewritten_route(self) -> None:
        binding, proposal_route = self.controller.persist_proposal(
            self.proposed_route,
            context_fingerprint="sha256:" + "a" * 64,
        )

        approved = self.controller.apply_intent(binding, "approved")

        self.assertEqual("proposal-required", proposal_route["consent_action"])
        self.assertEqual("approved", approved["consent_action"])
        self.assertEqual("phased", approved["envelope"])
        self.assertEqual("explicit-locked", approved["selection_mode"])
        self.assertEqual("skill:api-designer", approved["primary_skill"])
        self.assertEqual(["skill:qa-test-planner"], approved["support_skills"])

    def test_rejection_cannot_activate_or_replace_proposed_support(self) -> None:
        binding, _ = self.controller.persist_proposal(
            self.proposed_route,
            context_fingerprint="sha256:" + "a" * 64,
        )

        rejected = self.controller.apply_intent(binding, "rejected")

        self.assertEqual("rejected", rejected["consent_action"])
        self.assertEqual("skill:api-designer", rejected["primary_skill"])
        self.assertEqual([], rejected["support_skills"])

    def test_only_concrete_pending_proposals_can_enter_hybrid_state(self) -> None:
        invalid_routes = (
            {**self.proposed_route, "selection_mode": "auto"},
            {**self.proposed_route, "consent_action": "not-required"},
            {**self.proposed_route, "support_skills": []},
        )
        for route in invalid_routes:
            with self.subTest(route=route), self.assertRaises(ValueError):
                self.controller.persist_proposal(
                    route,
                    context_fingerprint="sha256:" + "a" * 64,
                )

    def test_unclear_intent_does_not_mutate_the_pending_proposal(self) -> None:
        binding, _ = self.controller.persist_proposal(
            self.proposed_route,
            context_fingerprint="sha256:" + "a" * 64,
        )

        with self.assertRaisesRegex(ValueError, "consent_intent_invalid"):
            self.controller.apply_intent(binding, "unclear")

        approved = self.controller.apply_intent(binding, "approved")
        self.assertEqual("approved", approved["consent_action"])


if __name__ == "__main__":
    unittest.main()
