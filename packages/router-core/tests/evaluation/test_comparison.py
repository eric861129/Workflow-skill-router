import unittest

from workflow_skill_router.evaluation.comparison import compare_scores
from workflow_skill_router.evaluation.contracts import ReleasePolicy
from workflow_skill_router.evaluation.scoring import score_attempts


def score(run, passes):
    return score_attempts(run, [{"passed": value, "explicit_skill_preserved": True,
        "unapproved_support_activations": 0} for value in passes], ReleasePolicy())


class ComparisonTests(unittest.TestCase):
    def test_comparison_requires_exact_paired_manifest(self):
        with self.assertRaisesRegex(ValueError, "paired_manifest_mismatch"):
            compare_scores(score("b", [False] * 3), score("c", [True] * 3),
                           baseline_case_ids=("a",), candidate_case_ids=("b",))

    def test_reports_paired_difference_without_significance_claim(self):
        result = compare_scores(score("b", [False] * 3), score("c", [True] * 3),
                                baseline_case_ids=("a",), candidate_case_ids=("a",))
        self.assertEqual(1.0, result.pass_rate_difference)
        self.assertEqual(1, result.paired_count)


if __name__ == "__main__": unittest.main()
