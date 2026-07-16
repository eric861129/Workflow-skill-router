from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.workflow.models import ExitGate, PhaseRun, PhaseStatus, RoutingQuery
from workflow_skill_router.workflow.transitions import (
    InvalidTransition, PhaseStateMachine, TransitionContext, TransitionRequest,
)


def phase(status: PhaseStatus) -> PhaseRun:
    return PhaseRun(
        "phase-1", "wf-1", "item-1", "實作", status,
        RoutingQuery("sha256:objective", "實作", ("可驗證程式碼",), "R1"),
        None, "snap-1", "R1", ("依賴完成",),
        ExitGate("gate-1", ("tests",), ("test-report",)),
        ("evidence-1",), False, "initial-plan", 1, 2, "sha256:e1",
        None, None, None, None,
    )


class PhaseStateMachineTests(unittest.TestCase):
    def test_completed_phase_cannot_reopen(self) -> None:
        with self.assertRaises(InvalidTransition):
            PhaseStateMachine().decide(
                phase(PhaseStatus.COMPLETED),
                TransitionRequest(PhaseStatus.ACTIVE, "agent", 2, "sha256:e1", 1),
                TransitionContext(True, True, True, False, False),
            )

    def test_unknown_side_effect_cannot_enter_verifying(self) -> None:
        with self.assertRaises(InvalidTransition):
            PhaseStateMachine().decide(
                phase(PhaseStatus.ACTIVE),
                TransitionRequest(PhaseStatus.VERIFYING, "agent", 2, "sha256:e1", 1),
                TransitionContext(True, True, True, True, False),
            )

    def test_pause_preserves_resume_origin(self) -> None:
        decision = PhaseStateMachine().decide(
            phase(PhaseStatus.ACTIVE),
            TransitionRequest(PhaseStatus.PAUSED, "host-adapter", 2, "sha256:e1", 1),
            TransitionContext(True, True, True, False, False),
        )
        self.assertEqual(PhaseStatus.ACTIVE, decision.paused_from_status)

    def test_state_drift_is_rejected_before_edge_evaluation(self) -> None:
        with self.assertRaisesRegex(InvalidTransition, "concurrency"):
            PhaseStateMachine().decide(
                phase(PhaseStatus.ACTIVE),
                TransitionRequest(PhaseStatus.VERIFYING, "agent", 1, "sha256:e1", 1),
                TransitionContext(True, True, True, False, False),
            )


if __name__ == "__main__":
    unittest.main()
