from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from workflow_skill_router.memory import (
    MatcherSeed,
    MemoryRequestContext,
    RememberWorkflowCommand,
    WorkflowMemoryService,
    MemoryCommandConflict,
)
from workflow_skill_router.service_models import RequestContext

from memory.workflow_fixture import WorkflowFixture, write_personal_memory_policy


class RememberWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.database = self.root / "router-v2.sqlite3"
        self.context = RequestContext("session-remember", "developer", "runtime-policy-1")
        self.fixture = WorkflowFixture(self.database, self.context)
        self.plan = self.fixture.plan_single(key="remember-plan")
        self.fixture.complete(self.plan)
        self.seed = MatcherSeed(("student api",), ("api",), (), "user-explicit")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def command(
        self,
        *,
        one_shot: str = "remember-once",
        side_effect: str = "none",
        risk: str = "r1",
        key: str = "remember-command",
        matcher_seed: MatcherSeed | None = None,
        workflow_run_id: str | None = None,
    ) -> RememberWorkflowCommand:
        return RememberWorkflowCommand(
            context=MemoryRequestContext(
                self.context.session_id,
                self.context.actor,
                self.context.runtime_policy_snapshot_id,
            ),
            workflow_run_id=workflow_run_id or self.plan.workflow_run_id,
            workspace_root=None,
            matcher_seed=self.seed if matcher_seed is None else matcher_seed,
            target_profile_class="managed-personal",
            risk_class=risk,
            side_effect_outcome=side_effect,
            one_shot=one_shot,
            idempotency_key=key,
            correlation_id=f"correlation-{key}",
        )

    def memory_database(self) -> Path:
        return self.root / "memory" / "workflow-memory.sqlite3"

    def count(self, table: str) -> int:
        with closing(sqlite3.connect(self.memory_database())) as connection:
            row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return 0 if row is None else int(row[0])

    def test_disabled_and_explicit_no_memory_stop_before_store_open(self) -> None:
        service = WorkflowMemoryService(self.database, data_dir=self.root)
        disabled = service.remember_workflow(self.command())
        self.assertEqual("memory-disabled", disabled.status)
        self.assertFalse(self.memory_database().exists())

        write_personal_memory_policy(self.root, "reviewed")
        suppressed = service.remember_workflow(
            self.command(one_shot="no-memory", key="suppressed")
        )
        self.assertEqual("not-recorded", suppressed.status)
        self.assertIn("explicit-no-memory", suppressed.reason_codes)
        self.assertFalse(self.memory_database().exists())

    def test_observe_requires_one_shot_for_explicit_route_and_records_once(self) -> None:
        write_personal_memory_policy(self.root, "observe")
        service = WorkflowMemoryService(self.database, data_dir=self.root)

        not_requested = service.remember_workflow(
            self.command(one_shot="none", key="not-requested")
        )
        self.assertEqual("not-recorded", not_requested.status)
        self.assertIn("explicit-route-requires-remember-once", not_requested.reason_codes)
        self.assertFalse(self.memory_database().exists())

        first = service.remember_workflow(self.command())
        replay = service.remember_workflow(self.command())

        self.assertEqual("recorded", first.status)
        self.assertFalse(first.replayed)
        self.assertEqual(first.observation_id, replay.observation_id)
        self.assertTrue(replay.replayed)
        self.assertEqual(1, self.count("route_observations"))
        self.assertEqual(1, self.count("route_observation_documents"))
        self.assertEqual(1, self.count("memory_command_receipts"))

    def test_same_idempotency_key_with_different_command_fails_closed(self) -> None:
        write_personal_memory_policy(self.root, "reviewed")
        service = WorkflowMemoryService(self.database, data_dir=self.root)
        service.remember_workflow(self.command(one_shot="none"))

        with self.assertRaisesRegex(MemoryCommandConflict, "memory-idempotency-conflict"):
            service.remember_workflow(
                self.command(one_shot="none", side_effect="known-success")
            )
        self.assertEqual(1, self.count("route_observations"))

    def test_idempotency_key_binds_effective_policy_digest(self) -> None:
        write_personal_memory_policy(self.root, "reviewed")
        service = WorkflowMemoryService(self.database, data_dir=self.root)
        service.remember_workflow(self.command(one_shot="none"))
        write_personal_memory_policy(self.root, "automatic")

        with self.assertRaisesRegex(MemoryCommandConflict, "memory-idempotency-conflict"):
            service.remember_workflow(self.command(one_shot="none"))
        self.assertEqual(1, self.count("route_observations"))

    def test_ineligible_workflow_creates_no_partial_memory_state(self) -> None:
        write_personal_memory_policy(self.root, "reviewed")
        service = WorkflowMemoryService(self.database, data_dir=self.root)
        incomplete = self.fixture.plan_single(key="incomplete-plan")

        result = service.remember_workflow(
            self.command(
                one_shot="none",
                key="incomplete-command",
                workflow_run_id=incomplete.workflow_run_id,
            )
        )

        self.assertEqual("not-recorded", result.status)
        self.assertIn("workflow-not-completed", result.reason_codes)
        self.assertFalse(self.memory_database().exists())

    def test_recorded_document_and_result_are_public_safe(self) -> None:
        write_personal_memory_policy(self.root, "reviewed")
        service = WorkflowMemoryService(self.database, data_dir=self.root)
        result = service.remember_workflow(self.command(one_shot="none"))

        with closing(sqlite3.connect(self.memory_database())) as connection:
            observation_json = connection.execute(
                "SELECT observation_json FROM route_observation_documents"
            ).fetchone()[0]
            receipt_json = connection.execute(
                "SELECT result_json FROM memory_command_results"
            ).fetchone()[0]
        combined = observation_json + receipt_json + json.dumps(result.to_dict())
        for forbidden in (
            "confidential student",
            "/private/project",
            "sensitive reported outcome",
            "raw_prompt",
            "tool_arguments",
            "file_content",
            "secrets",
        ):
            self.assertNotIn(forbidden, combined)
        self.assertIsNone(result.candidate_id)
        self.assertEqual("router-local", result.authority_mode)


if __name__ == "__main__":
    unittest.main()
