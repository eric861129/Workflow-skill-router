from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.memory import (
    HistorySummaryQuery,
    RecordRouteFeedbackCommand,
    MemoryCommandConflict,
    PurgeMemoryCommand,
    WorkflowMemoryService,
)

from memory.m1c_fixture import M1CHistoryFixture, write_feedback_policy


class RetentionAndPurgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        write_feedback_policy(
            self.root,
            retention_days=10,
            max_observations=3,
        )
        self.fixture = M1CHistoryFixture(self.root)
        write_feedback_policy(self.root, retention_days=10, max_observations=3)
        self.fixture.service = WorkflowMemoryService(self.fixture.database, data_dir=self.root)
        self.ids = self.fixture.insert_observations(
            count=5,
            dates=(
                "2026-08-01T00:00:00.000Z",
                "2026-09-01T00:00:00.000Z",
                "2026-09-02T00:00:00.000Z",
                "2026-09-03T00:00:00.000Z",
                "2026-09-04T00:00:00.000Z",
            ),
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_retention_removes_expired_then_oldest_excess_deterministically(self) -> None:
        result = self.fixture.service.enforce_retention(
            now="2026-09-05T00:00:00.000Z"
        )
        self.assertEqual(2, result.deleted_observations)
        self.assertEqual(3, result.remaining_observations)
        store = self.fixture.service.open_store_for_current_policy()
        assert store is not None
        with store:
            remaining = tuple(item.observation_id for item in store.list_route_observations())
        self.assertEqual(self.ids[2:], remaining)

    def test_history_export_is_canonical_and_redacted(self) -> None:
        export = self.fixture.service.export_history(
            HistorySummaryQuery(context=self.fixture.memory_context),
            include_observations=True,
        )
        self.assertEqual(export, export.strip())
        for forbidden in (
            str(self.root),
            "raw_prompt",
            "reported_outcome",
            "tool_arguments",
            "free_text",
            "/private/project",
        ):
            self.assertNotIn(forbidden, export)

    def test_digest_bound_purge_is_idempotent_and_preserves_schema(self) -> None:
        summary = self.fixture.service.history_summary(
            HistorySummaryQuery(context=self.fixture.memory_context)
        )
        command = PurgeMemoryCommand(
            context=self.fixture.memory_context,
            scope="history-only",
            expected_summary_digest=summary.summary_digest,
            include_managed_profiles=False,
            idempotency_key="purge-history",
            correlation_id="correlation-purge-history",
        )
        first = self.fixture.service.purge_memory(command)
        replay = self.fixture.service.purge_memory(command)
        self.assertEqual("purged", first.status)
        self.assertTrue(replay.replayed)
        self.assertEqual(first.deleted_observations, replay.deleted_observations)

        store = self.fixture.service.open_store_for_current_policy()
        assert store is not None
        with store:
            self.assertEqual(0, store.observation_count())
            self.assertIn(3, store.applied_migration_versions())

    def test_stale_digest_and_future_scope_delete_nothing(self) -> None:
        with self.assertRaisesRegex(MemoryCommandConflict, "stale-summary-digest"):
            self.fixture.service.purge_memory(PurgeMemoryCommand(
                context=self.fixture.memory_context,
                scope="history-only",
                expected_summary_digest="sha256:" + "0" * 64,
                include_managed_profiles=False,
                idempotency_key="stale-purge",
                correlation_id="correlation-stale-purge",
            ))
        before = self.fixture.service.history_summary(
            HistorySummaryQuery(context=self.fixture.memory_context)
        )
        result = self.fixture.service.purge_memory(PurgeMemoryCommand(
            context=self.fixture.memory_context,
            scope="candidates-only",
            expected_summary_digest=before.summary_digest,
            include_managed_profiles=False,
            idempotency_key="future-scope",
            correlation_id="correlation-future-scope",
        ))
        self.assertEqual("scope-not-available", result.status)
        after = self.fixture.service.history_summary(
            HistorySummaryQuery(context=self.fixture.memory_context)
        )
        self.assertEqual(before.eligible_workflow_count, after.eligible_workflow_count)

    def test_disabled_status_does_not_implicitly_purge_existing_history(self) -> None:
        before = self.fixture.service.history_summary(
            HistorySummaryQuery(context=self.fixture.memory_context)
        )
        (self.root / "config/workflow-memory.json").unlink()
        disabled = self.fixture.service.history_summary(
            HistorySummaryQuery(context=self.fixture.memory_context)
        )
        self.assertEqual(0, disabled.eligible_workflow_count)
        write_feedback_policy(self.root, retention_days=10, max_observations=3)
        restored = self.fixture.service.history_summary(
            HistorySummaryQuery(context=self.fixture.memory_context)
        )
        self.assertEqual(before.eligible_workflow_count, restored.eligible_workflow_count)


    def test_managed_profile_purge_request_is_idempotently_rejected(self) -> None:
        summary = self.fixture.service.history_summary(
            HistorySummaryQuery(context=self.fixture.memory_context)
        )
        command = PurgeMemoryCommand(
            context=self.fixture.memory_context,
            scope="all-memory-data",
            expected_summary_digest=summary.summary_digest,
            include_managed_profiles=True,
            idempotency_key="managed-profile-purge-not-yet-available",
            correlation_id="correlation-managed-profile-purge-not-yet-available",
        )

        first = self.fixture.service.purge_memory(command)
        replay = self.fixture.service.purge_memory(command)

        self.assertEqual("scope-not-available", first.status)
        self.assertIn("managed-profile-purge-not-available", first.reason_codes)
        self.assertTrue(replay.replayed)

    def test_explicit_purge_remains_available_after_policy_is_disabled(self) -> None:
        before = self.fixture.service.history_summary(
            HistorySummaryQuery(context=self.fixture.memory_context)
        )
        (self.root / "config/workflow-memory.json").unlink()

        result = self.fixture.service.purge_memory(PurgeMemoryCommand(
            context=self.fixture.memory_context,
            scope="history-only",
            expected_summary_digest=before.summary_digest,
            include_managed_profiles=False,
            idempotency_key="disabled-explicit-purge",
            correlation_id="correlation-disabled-explicit-purge",
        ))

        self.assertEqual("purged", result.status)
        write_feedback_policy(self.root, retention_days=10, max_observations=3)
        after = self.fixture.service.history_summary(
            HistorySummaryQuery(context=self.fixture.memory_context)
        )
        self.assertEqual(0, after.eligible_workflow_count)

    def test_direct_store_purge_removes_typed_feedback_and_admin_receipts(self) -> None:
        plan, remembered = self.fixture.remember(key="direct-purge-feedback")
        self.fixture.service.record_route_feedback(RecordRouteFeedbackCommand(
            context=self.fixture.memory_context,
            workflow_run_id=plan.workflow_run_id,
            workspace_root=None,
            observation_id=remembered.observation_id,
            feedback_type="accepted",
            reason_code="route-useful",
            correction_dimensions=(),
            original_route_digest=None,
            corrected_route_digest=None,
            free_text=None,
            idempotency_key="direct-purge-feedback-command",
            correlation_id="correlation-direct-purge-feedback-command",
        ))
        summary = self.fixture.service.history_summary(
            HistorySummaryQuery(context=self.fixture.memory_context)
        )
        self.fixture.service.purge_memory(PurgeMemoryCommand(
            context=self.fixture.memory_context,
            scope="candidates-only",
            expected_summary_digest=summary.summary_digest,
            include_managed_profiles=False,
            idempotency_key="future-command-before-direct-purge",
            correlation_id="correlation-future-command-before-direct-purge",
        ))

        store = self.fixture.service.open_store_for_current_policy()
        assert store is not None
        with store:
            removed = store.purge_history()
            connection = store._require_open()
            typed_feedback = connection.execute(
                "SELECT COUNT(*) FROM route_feedback_events"
            ).fetchone()[0]
            admin_commands = connection.execute(
                "SELECT COUNT(*) FROM memory_admin_commands"
            ).fetchone()[0]

        self.assertGreaterEqual(removed["route_feedback"], 1)
        self.assertEqual(0, typed_feedback)
        self.assertEqual(0, admin_commands)


if __name__ == "__main__":
    unittest.main()
