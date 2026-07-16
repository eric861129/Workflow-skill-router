from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.workflow.gates import GateCheck, GateEvaluationRequest, GateEvaluator


class GateEvaluatorTests(unittest.TestCase):
    def request(self, *, expected_digest="sha256:e1", actual_digest="sha256:e1"):
        return GateEvaluationRequest(
            "wf-1", "phase-1", 3, 1, expected_digest, 3, 1, actual_digest,
            (
                GateCheck("test", True, False, "測試失敗"),
                GateCheck("model-assessment", False, True, "外觀良好"),
            ),
        )

    def test_advisory_pass_cannot_offset_mandatory_failure(self) -> None:
        result = GateEvaluator().evaluate(self.request())
        self.assertFalse(result.passed)
        self.assertEqual(("測試失敗",), result.mandatory_failures)

    def test_digest_change_rejects_gate_as_concurrency_conflict(self) -> None:
        result = GateEvaluator().evaluate(self.request(
            expected_digest="sha256:old", actual_digest="sha256:new",
        ))
        self.assertEqual("conflict", result.status)


if __name__ == "__main__":
    unittest.main()
