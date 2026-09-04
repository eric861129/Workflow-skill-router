from __future__ import annotations

from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from workflow_skill_router.memory import (
    CompletedWorkflowReader,
    MemoryRequestContext,
    WorkflowReadError,
)
from workflow_skill_router.service_models import RequestContext, RoutingContextInput

from memory.workflow_fixture import WorkflowFixture


class CompletedWorkflowReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.database = self.root / "router-v2.sqlite3"
        self.context = RequestContext("session-memory", "developer", "runtime-policy-1")
        self.fixture = WorkflowFixture(self.database, self.context)
        self.reader = CompletedWorkflowReader(self.database)
        self.memory_context = MemoryRequestContext(
            self.context.session_id,
            self.context.actor,
            self.context.runtime_policy_snapshot_id,
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_reads_completed_single_without_raw_objective_or_reported_outcome(self) -> None:
        plan = self.fixture.plan_single()
        self.fixture.complete(plan)

        snapshot = self.reader.read(self.memory_context, plan.workflow_run_id)

        self.assertEqual("completed", snapshot.terminal_status)
        self.assertEqual("single", snapshot.work_mode)
        self.assertEqual("user-explicit", snapshot.route_source)
        self.assertEqual("intended-unverified", snapshot.activation_status)
        self.assertEqual(1, len(snapshot.phases))
        self.assertEqual("skill:api-designer", snapshot.phases[0].primary_skill_id)
        self.assertEqual(("router-local-single-completed",), snapshot.phases[0].exit_gate_ids)
        serialized = repr(snapshot)
        self.assertNotIn("confidential student", serialized)
        self.assertNotIn("/private/project", serialized)
        self.assertNotIn("sensitive reported outcome", serialized)

    def test_reads_persisted_trusted_routing_context_and_profile_matcher(self) -> None:
        plan = self.fixture.plan_phased()
        self.fixture.complete(plan)

        snapshot = self.reader.read(self.memory_context, plan.workflow_run_id)

        self.assertEqual(("api",), snapshot.routing_domains)
        self.assertEqual(("backend",), snapshot.routing_tags)
        self.assertEqual(("api",), snapshot.profile_objective_keywords)
        self.assertEqual(("api",), snapshot.profile_domains)
        self.assertEqual(("backend",), snapshot.profile_tags)
        self.assertEqual("personal-profile", snapshot.route_source)
        self.assertEqual("personal:delivery", snapshot.routing_profile_ids[0])

    def test_workspace_is_stored_only_as_digest(self) -> None:
        workspace = self.root / "private-workspace"
        workspace.mkdir()
        plan = self.fixture.plan_single(
            key="workspace-digest",
            routing_context=RoutingContextInput(
                workspace_root=str(workspace),
                domains=("api",),
                tags=(),
            ),
        )
        self.fixture.complete(plan)

        snapshot = self.reader.read(self.memory_context, plan.workflow_run_id)

        expected = "sha256:" + hashlib.sha256(
            str(workspace.resolve()).encode("utf-8")
        ).hexdigest()
        self.assertEqual(expected, snapshot.workspace_identity_digest)
        with closing(sqlite3.connect(self.database)) as connection:
            values = "\n".join(
                "" if value is None else str(value)
                for row in connection.execute("SELECT * FROM local_control_plans")
                for value in row
            )
        self.assertNotIn(str(workspace), values)

    def test_rejects_incomplete_cross_context_and_native_goal(self) -> None:
        incomplete = self.fixture.plan_single(key="incomplete")
        with self.assertRaisesRegex(WorkflowReadError, "workflow-not-completed"):
            self.reader.read(self.memory_context, incomplete.workflow_run_id)

        self.fixture.complete(incomplete)
        with self.assertRaisesRegex(WorkflowReadError, "workflow-context-mismatch"):
            self.reader.read(
                MemoryRequestContext("other", "developer", "runtime-policy-1"),
                incomplete.workflow_run_id,
            )
        with self.assertRaisesRegex(WorkflowReadError, "workflow-context-mismatch"):
            self.reader.read(
                MemoryRequestContext("session-memory", "other", "runtime-policy-1"),
                incomplete.workflow_run_id,
            )
        with self.assertRaisesRegex(WorkflowReadError, "workflow-context-mismatch"):
            self.reader.read(
                MemoryRequestContext("session-memory", "developer", "other-policy"),
                incomplete.workflow_run_id,
            )

        native = self.fixture.plan_native_goal()
        with self.assertRaisesRegex(WorkflowReadError, "native-goal-not-observable"):
            self.reader.read(self.memory_context, native.workflow_run_id)

    def test_rejects_corrupt_transition_chain(self) -> None:
        plan = self.fixture.plan_single(key="corrupt")
        self.fixture.complete(plan)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("DROP TRIGGER local_work_transitions_no_update")
            connection.execute(
                "UPDATE local_work_transitions SET request_digest=? "
                "WHERE workflow_run_id=? AND transition_kind LIKE 'gate%'",
                ("sha256:" + "0" * 64, plan.workflow_run_id),
            )
            connection.commit()

        with self.assertRaisesRegex(WorkflowReadError, "workflow-graph-corrupt"):
            self.reader.read(self.memory_context, plan.workflow_run_id)


if __name__ == "__main__":
    unittest.main()
