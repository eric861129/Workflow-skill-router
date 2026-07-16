import unittest

from workflow_skill_router.evaluation.contracts import EvaluationProfile, ModelExecutionPayload
from workflow_skill_router.evaluation.runner import run_evaluation


class Adapter:
    kind = "host-task"
    def __init__(self): self.contexts = set()
    def start_attempt(self, payload, nonce):
        context = "fresh:" + nonce
        if context in self.contexts: raise RuntimeError("reused")
        self.contexts.add(context); self.nonce = nonce; return context
    def execute_turn(self, request): return {"text": request.prompt, "nonce": request.attempt_nonce}


class RunnerTests(unittest.TestCase):
    def test_behavior_runs_three_fresh_attempts_with_distribution_evidence(self):
        counter = iter(str(i) for i in range(10))
        result = run_evaluation(
            ModelExecutionPayload("case-1", "任務", EvaluationProfile.BEHAVIOR, ()),
            ["拒絕輔助技能"], Adapter(), repeats=3, id_factory=lambda: next(counter),
        )
        self.assertEqual("completed", result.status)
        self.assertEqual(3, len(result.attempts))
        self.assertEqual(3, len({item.fresh_context_id for item in result.attempts}))

    def test_behavior_rejects_single_synthetic_attempt(self):
        with self.assertRaisesRegex(ValueError, "至少需要三次"):
            run_evaluation(ModelExecutionPayload("c", "p", EvaluationProfile.BEHAVIOR, ()), [], Adapter(), repeats=1, id_factory=lambda: "1")


if __name__ == "__main__": unittest.main()
