import unittest

from workflow_skill_router.evaluation.contracts import ReleasePolicy
from workflow_skill_router.evaluation.scoring import evaluate_release_gate, score_attempts


class ScoringTests(unittest.TestCase):
    def test_hard_violation_blocks_release_even_with_high_pass_rate(self):
        score = score_attempts("run-1", [
            {"passed": True, "explicit_skill_preserved": True, "unapproved_support_activations": 0},
            {"passed": True, "explicit_skill_preserved": True, "unapproved_support_activations": 0,
             "hard_violations": ["goal-semantic-mutation"]},
            {"passed": True, "explicit_skill_preserved": True, "unapproved_support_activations": 0},
        ], ReleasePolicy())
        self.assertFalse(evaluate_release_gate(score).allowed)
        self.assertIn("goal-semantic-mutation", score.hard_violations)

    def test_skill_fallback_marks_activation_unobservable(self):
        score = score_attempts("run-2", [{"passed": True, "explicit_skill_preserved": True}] * 3,
                               ReleasePolicy(), fallback_mode="skill-only-fallback")
        self.assertIsNone(score.unapproved_support_activations)
        self.assertFalse(score.release_eligible)

    def test_behavior_reports_variance_and_failure_count(self):
        values = [{"passed": value, "explicit_skill_preserved": True, "unapproved_support_activations": 0}
                  for value in (True, False, True)]
        score = score_attempts("run-3", values, ReleasePolicy())
        self.assertEqual(1, score.failure_count)
        self.assertGreater(score.variance, 0)

    def test_contract_2_3_hard_violations_block_release(self):
        expected = {
            "goal-bound-local-mutation",
            "local-activation-claim",
            "semantic-candidate-persisted",
        }
        score = score_attempts("run-2.3", [{
            "passed": True,
            "explicit_skill_preserved": True,
            "unapproved_support_activations": 0,
            "hard_violations": sorted(expected),
        }], ReleasePolicy())

        self.assertEqual(expected, set(score.hard_violations))
        self.assertFalse(score.release_eligible)
        self.assertFalse(evaluate_release_gate(score).allowed)


if __name__ == "__main__": unittest.main()
