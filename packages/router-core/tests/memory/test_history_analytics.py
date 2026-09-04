from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.memory import (
    HistorySummaryQuery,
    RouteFeedback,
    WorkflowMemoryService,
)

from memory.m1c_fixture import M1CHistoryFixture, digest


class HistoryAnalyticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.fixture = M1CHistoryFixture(self.root)
        self.ids = self.fixture.insert_observations(
            count=5,
            dates=(
                "2026-09-01T00:00:00.000Z",
                "2026-09-02T00:00:00.000Z",
                "2026-09-03T00:00:00.000Z",
            ),
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _insert_feedback(self, index: int, feedback_type: str) -> None:
        store = self.fixture.service.open_store_for_current_policy()
        assert store is not None
        with store:
            observation = store.load_route_observation(self.ids[index])
            assert observation is not None
            feedback = RouteFeedback.create(
                observation=observation,
                policy_snapshot=store.current_policy_snapshot,
                context=self.fixture.memory_context,
                feedback_type=feedback_type,
                reason_code=f"reason-{feedback_type}",
                correction_dimensions=("primary-skill",) if feedback_type == "corrected" else (),
                original_route_digest=(observation.route_signature_digest if feedback_type == "corrected" else None),
                corrected_route_digest=(digest({"corrected": index}) if feedback_type == "corrected" else None),
                free_text=None,
                recorded_at=f"2026-09-03T0{index}:00:00.000Z",
            )
            store.record_route_feedback(
                feedback_document=feedback.to_dict(),
                result_document={"status": "recorded", "feedback_id": feedback.feedback_id},
                idempotency_key=f"feedback-{index}",
                command_digest=digest({"feedback": index}),
            )

    def test_summary_uses_distinct_workflows_and_deterministic_metrics(self) -> None:
        self._insert_feedback(0, "corrected")
        self._insert_feedback(1, "support-rejected")
        self._insert_feedback(2, "capability-unavailable")
        self._insert_feedback(3, "abandoned")
        summary = self.fixture.service.history_summary(
            HistorySummaryQuery(context=self.fixture.memory_context)
        )

        self.assertEqual(5, summary.eligible_workflow_count)
        self.assertEqual(0.80, summary.completion_rate)
        self.assertEqual(1.00, summary.required_gate_pass_rate)
        self.assertEqual(0.20, summary.manual_correction_rate)
        self.assertEqual(0.20, summary.consent_rejection_rate)
        self.assertEqual(0.20, summary.capability_unavailable_rate)
        self.assertEqual(1.00, summary.reported_route_consistency)
        self.assertEqual("unavailable", summary.actual_skill_consistency)
        self.assertEqual(3, summary.distinct_active_days)
        self.assertEqual("high", summary.confidence)
        self.assertRegex(summary.summary_digest, r"^sha256:[0-9a-f]{64}$")

    def test_summary_is_empty_and_noncreating_when_memory_is_disabled(self) -> None:
        disabled_root = self.root / "disabled"
        service = WorkflowMemoryService(disabled_root / "router-v2.sqlite3", data_dir=disabled_root)
        summary = service.history_summary(HistorySummaryQuery(
            context=self.fixture.memory_context
        ))
        self.assertEqual(0, summary.eligible_workflow_count)
        self.assertEqual("insufficient-evidence", summary.confidence)
        self.assertFalse((disabled_root / "memory").exists())

    def test_summary_filters_by_workspace_digest_without_exposing_paths(self) -> None:
        summary = self.fixture.service.history_summary(
            HistorySummaryQuery(context=self.fixture.memory_context)
        )
        serialized = summary.canonical_json()
        self.assertNotIn(str(self.root), serialized)
        self.assertTrue(all(key == "none" or key.startswith("sha256:") for key in summary.workspace_distribution))


if __name__ == "__main__":
    unittest.main()
