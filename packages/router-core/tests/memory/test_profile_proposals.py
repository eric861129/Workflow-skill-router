from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.memory.candidates import CandidateEngine
from workflow_skill_router.memory.policy_io import MemoryPolicyRepository
from workflow_skill_router.memory.policy_resolver import resolve_effective_policy
from workflow_skill_router.memory.proposals import (
    ProfileProposalError,
    create_profile_update_proposal,
    transition_profile_update,
)
from workflow_skill_router.memory.store import MemoryStore
from workflow_skill_router.memory.models import MemoryScope

from memory.m1c_fixture import M1CHistoryFixture, write_feedback_policy


class ProfileProposalTests(unittest.TestCase):
    def test_proposal_binds_candidate_diff_backtest_and_approval_only_changes_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_feedback_policy(root, mode="reviewed")
            fixture = M1CHistoryFixture(root)
            fixture.insert_observations(count=3, dates=("2026-09-01T00:00:00.000Z", "2026-09-02T00:00:00.000Z"))
            policy = resolve_effective_policy(personal=MemoryPolicyRepository(root).inspect_personal(), workspace=None)
            store = MemoryStore.open_if_enabled(root, policy)
            assert store is not None
            with store:
                candidate = CandidateEngine(store, policy).rebuild(MemoryScope.PERSONAL, "2026-09-04T00:00:00.000Z")[0]
                proposal = create_profile_update_proposal(store, candidate, current_profile=None, policy=policy, now="2026-09-04T00:00:00.000Z")
                self.assertEqual("pending", proposal.status)
                self.assertEqual("missing", proposal.expected_profile_digest)
                self.assertRegex(proposal.proposal_digest, r"^sha256:[0-9a-f]{64}$")
                approved = transition_profile_update(store, proposal.proposal_id, action="approve", expected_state_version=1, idempotency_key="approve-1", correlation_id="corr-1")
                self.assertEqual("approved", approved.status)
                self.assertEqual(2, approved.state_version)
                self.assertIsNotNone(store.load_profile_update_proposal(proposal.proposal_id))

    def test_transition_cannot_change_bound_proposal_and_conflicting_replay_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_feedback_policy(root, mode="reviewed")
            fixture = M1CHistoryFixture(root)
            fixture.insert_observations(count=3, dates=("2026-09-01T00:00:00.000Z", "2026-09-02T00:00:00.000Z"))
            policy = resolve_effective_policy(personal=MemoryPolicyRepository(root).inspect_personal(), workspace=None)
            store = MemoryStore.open_if_enabled(root, policy)
            assert store is not None
            with store:
                candidate = CandidateEngine(store, policy).rebuild(MemoryScope.PERSONAL, "2026-09-04T00:00:00.000Z")[0]
                proposal = create_profile_update_proposal(store, candidate, current_profile=None, policy=policy, now="2026-09-04T00:00:00.000Z")
                first = transition_profile_update(store, proposal.proposal_id, action="reject", expected_state_version=1, idempotency_key="decision", correlation_id="corr")
                replay = transition_profile_update(store, proposal.proposal_id, action="reject", expected_state_version=1, idempotency_key="decision", correlation_id="corr")
                self.assertEqual(first.to_dict(), replay.to_dict())
                with self.assertRaisesRegex(ProfileProposalError, "idempotency-conflict"):
                    transition_profile_update(store, proposal.proposal_id, action="approve", expected_state_version=1, idempotency_key="decision", correlation_id="corr")


if __name__ == "__main__":
    unittest.main()
