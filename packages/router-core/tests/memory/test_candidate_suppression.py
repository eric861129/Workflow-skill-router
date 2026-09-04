from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.memory import CandidateEngine, MemoryScope, MemoryStore

from memory.m1c_fixture import M1CHistoryFixture


class CandidateSuppressionTests(unittest.TestCase):
    def test_rejected_candidate_is_suppressed_for_unchanged_material_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = M1CHistoryFixture(root)
            fixture.insert_observations(
                count=3,
                dates=("2026-09-01T10:00:00.000Z", "2026-09-02T10:00:00.000Z"),
            )
            policy = fixture.effective_policy()
            store = MemoryStore.open_if_enabled(root, policy)
            assert store is not None
            with store:
                engine = CandidateEngine(store, policy)
                candidate = engine.rebuild(MemoryScope.PERSONAL, datetime(2026, 9, 3, tzinfo=timezone.utc))[0]
                rejected = store.reject_workflow_candidate(
                    candidate.candidate_id,
                    reason_code="not-reusable",
                    rejected_at="2026-09-03T12:00:00.000Z",
                )
                self.assertEqual("rejected", rejected.status)
                self.assertEqual(
                    (),
                    engine.rebuild(MemoryScope.PERSONAL, datetime(2026, 9, 4, tzinfo=timezone.utc)),
                )



if __name__ == "__main__":
    unittest.main()
