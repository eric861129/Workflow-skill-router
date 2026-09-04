from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.memory import CandidateEngine, MemoryMode, MemoryScope, MemoryStore

from memory.m1c_fixture import M1CHistoryFixture


class CandidateEngineTests(unittest.TestCase):
    def test_reviewed_policy_creates_candidate_after_three_runs_on_two_days(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = M1CHistoryFixture(Path(temp))
            fixture.insert_observations(
                count=3,
                dates=("2026-09-01T10:00:00.000Z", "2026-09-02T10:00:00.000Z"),
            )
            policy = fixture.effective_policy()
            self.assertEqual(MemoryMode.REVIEWED, policy.mode)
            store = MemoryStore.open_if_enabled(Path(temp), policy)
            assert store is not None
            with store:
                candidates = CandidateEngine(store, policy).rebuild(
                    MemoryScope.PERSONAL,
                    datetime(2026, 9, 3, tzinfo=timezone.utc),
                )
                self.assertEqual(1, len(candidates))
                candidate = candidates[0]
                self.assertEqual("proposed", candidate.status)
                self.assertEqual("reviewed", candidate.recommendation_mode)
                self.assertEqual("medium", candidate.confidence)
                self.assertEqual(3, candidate.metrics.distinct_runs)
                self.assertEqual(2, candidate.metrics.distinct_days)
                self.assertEqual("managed-personal", candidate.target_profile_class)

    def test_reviewed_policy_returns_no_candidate_below_evidence_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = M1CHistoryFixture(Path(temp))
            fixture.insert_observations(count=2, dates=("2026-09-01T10:00:00.000Z",))
            policy = fixture.effective_policy()
            store = MemoryStore.open_if_enabled(Path(temp), policy)
            assert store is not None
            with store:
                candidates = CandidateEngine(store, policy).rebuild(
                    MemoryScope.PERSONAL,
                    datetime(2026, 9, 2, tzinfo=timezone.utc),
                )
                self.assertEqual((), candidates)

    def test_observe_mode_never_creates_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = M1CHistoryFixture(root)
            fixture.insert_observations(
                count=5,
                dates=(
                    "2026-09-01T10:00:00.000Z",
                    "2026-09-02T10:00:00.000Z",
                    "2026-09-03T10:00:00.000Z",
                ),
            )
            # Replace the policy after observations were captured; rebuilding is
            # controlled by the current effective policy, not historical mode.
            (root / "config" / "workflow-memory.json").write_text(
                '{"schema_id":"workflow-skill-router/memory-policy","schema_version":"1.0.0","artifact_kind":"memory-policy","policy_id":"personal:observe","scope":"personal","mode":"observe"}',
                encoding="utf-8",
            )
            observe = fixture.effective_policy()
            self.assertEqual(MemoryMode.OBSERVE, observe.mode)
            store = MemoryStore.open_existing(root)
            assert store is not None
            with store:
                self.assertEqual(
                    (),
                    CandidateEngine(store, observe).rebuild(
                        MemoryScope.PERSONAL,
                        datetime(2026, 9, 4, tzinfo=timezone.utc),
                    ),
                )


if __name__ == "__main__":
    unittest.main()
