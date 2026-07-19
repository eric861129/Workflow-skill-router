from pathlib import Path
import unittest

from workflow_skill_router.evaluation.legacy_v1 import load_legacy_v1_contract


class LegacyTests(unittest.TestCase):
    def test_v1_fixture_is_contract_only_not_real_model_evaluation(self):
        root = Path(__file__).resolve().parents[4]
        suite = load_legacy_v1_contract(
            root / "packages" / "router-core" / "tests" / "fixtures" / "legacy-v1" / "scenarios.jsonl",
        )
        self.assertEqual(80, suite.case_count)
        self.assertEqual(("T0", "contract-only"), (suite.tier, suite.evidence_class))


if __name__ == "__main__": unittest.main()
