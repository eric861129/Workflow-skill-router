from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.memory.backtest import backtest_profile_update
from workflow_skill_router.memory.candidates import CandidateEngine
from workflow_skill_router.memory.policy_io import MemoryPolicyRepository
from workflow_skill_router.memory.policy_resolver import resolve_effective_policy
from workflow_skill_router.memory.profile_diff import build_profile_document
from workflow_skill_router.memory.store import MemoryStore
from workflow_skill_router.memory.models import MemoryScope
from workflow_skill_router.profiles.contract import decode_routing_profile

from memory.m1c_fixture import M1CHistoryFixture, write_feedback_policy


class ProfileBacktestTests(unittest.TestCase):
    def test_backtest_reports_coverage_without_raw_objective(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_feedback_policy(root, mode="reviewed")
            fixture = M1CHistoryFixture(root)
            fixture.insert_observations(count=3, dates=("2026-09-01T00:00:00.000Z", "2026-09-02T00:00:00.000Z"))
            policy = resolve_effective_policy(personal=MemoryPolicyRepository(root).inspect_personal(), workspace=None)
            store = MemoryStore.open_if_enabled(root, policy)
            assert store is not None
            with store:
                candidates = CandidateEngine(store, policy).rebuild(MemoryScope.PERSONAL, "2026-09-04T00:00:00.000Z")
                self.assertEqual(1, len(candidates))
                candidate = candidates[0]
                proposed = decode_routing_profile(build_profile_document(candidate, None), expected_scope="personal")
                summary = backtest_profile_update((), proposed, tuple(store.list_route_observations()), candidate)
            self.assertEqual(3, summary.positive_observation_count)
            self.assertEqual(1.0, summary.positive_match_coverage)
            self.assertEqual(0, summary.unexpected_match_count)
            self.assertTrue(summary.acceptable)
            self.assertRegex(summary.backtest_digest, r"^sha256:[0-9a-f]{64}$")

    def test_manual_profile_digests_are_sorted_unique_and_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_feedback_policy(root, mode="reviewed")
            fixture = M1CHistoryFixture(root)
            fixture.insert_observations(
                count=3,
                dates=(
                    "2026-09-01T00:00:00.000Z",
                    "2026-09-02T00:00:00.000Z",
                ),
            )
            policy = resolve_effective_policy(
                personal=MemoryPolicyRepository(root).inspect_personal(),
                workspace=None,
            )
            store = MemoryStore.open_if_enabled(root, policy)
            assert store is not None
            with store:
                candidate = CandidateEngine(store, policy).rebuild(
                    MemoryScope.PERSONAL,
                    "2026-09-04T00:00:00.000Z",
                )[0]
                proposed = decode_routing_profile(
                    build_profile_document(candidate, None),
                    expected_scope="personal",
                )
                summary = backtest_profile_update(
                    (),
                    proposed,
                    tuple(store.list_route_observations()),
                    candidate,
                    manual_profiles=(proposed, proposed),
                )
            self.assertEqual((proposed.profile_digest,), summary.manual_profile_digests)
            self.assertEqual(
                [proposed.profile_digest],
                summary.to_dict()["manual_profile_digests"],
            )


if __name__ == "__main__":
    unittest.main()
