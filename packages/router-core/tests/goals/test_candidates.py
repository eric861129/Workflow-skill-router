from dataclasses import replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.goals.candidates import (
    AcceptanceCompletionRecord, Blocker, BlockedAudit, CandidateFactory,
    CandidateRequest, CompletionEvidenceSnapshot,
)
from workflow_skill_router.routing.models import RoutingEnvelope


REQUEST = CandidateRequest(
    "wf-1", "sha256:o", RoutingEnvelope.PHASED, 2, 8, "snap-2",
)


class Repository:
    def __init__(self, snapshot): self.snapshot = snapshot
    def load(self, request):
        del request
        return self.snapshot


def snapshot_without_acceptance_evidence(request=REQUEST):
    return CompletionEvidenceSnapshot(
        request,
        (AcceptanceCompletionRecord("gate-1", True, "passed", (), "sha256:e", 2, 8),),
        (), (), (), (), "sha256:a", "sha256:x", "sha256:e", "sha256:s",
    )


class CandidateTests(unittest.TestCase):
    def test_complete_candidate_requires_evidence_and_explicit_coverage(self) -> None:
        result = CandidateFactory(Repository(snapshot_without_acceptance_evidence())).workflow_complete(REQUEST)
        self.assertIsNone(result)

    def test_status_and_side_question_do_not_count_as_blocked_turns(self) -> None:
        blocker = Blocker("auth", "provider", "user-login", "sha256:d")
        audit = BlockedAudit().observe(blocker, "progress", True, False)
        audit = audit.observe(blocker, "status", True, False)
        audit = audit.observe(blocker, "side-question", True, False)
        self.assertEqual(1, audit.consecutive_goal_turns)

    def test_non_countable_message_with_new_blocker_does_not_rebind_old_turns(self) -> None:
        first = Blocker("auth", "provider-a", "user-login", "sha256:a")
        second = Blocker("network", "provider-b", "external-change", "sha256:b")
        audit = BlockedAudit().observe(first, "progress", True, False)
        audit = audit.observe(first, "progress", True, False)
        audit = audit.observe(second, "status", True, False)
        audit = audit.observe(second, "progress", True, False)
        self.assertEqual(second.identity, audit.blocker_identity)
        self.assertEqual(1, audit.consecutive_goal_turns)

    def test_blocked_requires_three_same_goal_turns_and_no_runnable_required_item(self) -> None:
        blocker = Blocker("auth", "provider", "user-login", "sha256:d")
        audit = BlockedAudit()
        for _ in range(3):
            audit = audit.observe(blocker, "progress", True, False)
        self.assertTrue(audit.eligible)
        self.assertFalse(audit.observe(blocker, "progress", True, True).eligible)


if __name__ == "__main__": unittest.main()
