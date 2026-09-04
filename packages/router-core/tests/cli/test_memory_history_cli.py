from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from workflow_skill_router.memory import MatcherSeed, MemoryRequestContext, RememberWorkflowCommand, WorkflowMemoryService
from workflow_skill_router.service_models import RequestContext

from memory.workflow_fixture import WorkflowFixture, write_personal_memory_policy


class MemoryHistoryCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.database = self.root / "router-v2.sqlite3"
        self.context = RequestContext("session-cli-history", "developer", "runtime-policy-history")
        fixture = WorkflowFixture(self.database, self.context)
        self.plan = fixture.plan_single(key="history-cli-plan")
        fixture.complete(self.plan)
        write_personal_memory_policy(self.root, "reviewed")
        result = WorkflowMemoryService(self.database, data_dir=self.root).remember_workflow(
            RememberWorkflowCommand(
                context=MemoryRequestContext(
                    self.context.session_id,
                    self.context.actor,
                    self.context.runtime_policy_snapshot_id,
                ),
                workflow_run_id=self.plan.workflow_run_id,
                workspace_root=None,
                matcher_seed=MatcherSeed(("student api",), ("api",), (), "user-explicit"),
                target_profile_class="managed-personal",
                risk_class="r1",
                side_effect_outcome="none",
                one_shot="remember-once",
                idempotency_key="history-cli-remember",
                correlation_id="history-cli-remember-correlation",
            )
        )
        self.observation_id = result.observation_id

    def tearDown(self) -> None:
        self.directory.cleanup()

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "workflow_skill_router.cli", *arguments],
            cwd=Path(__file__).resolve().parents[4],
            capture_output=True,
            text=True,
            check=False,
        )

    def common_context(self) -> list[str]:
        return [
            "--database", str(self.database),
            "--data-dir", str(self.root),
            "--session-id", self.context.session_id,
            "--actor", self.context.actor,
            "--runtime-policy-snapshot-id", self.context.runtime_policy_snapshot_id,
        ]

    def test_feedback_summary_export_and_digest_bound_purge_are_machine_readable(self) -> None:
        feedback = self.run_cli(
            "memory", "feedback", "record",
            *self.common_context(),
            "--workflow-run", self.plan.workflow_run_id,
            "--observation-id", self.observation_id or "",
            "--type", "accepted",
            "--reason", "route-useful",
            "--idempotency-key", "history-cli-feedback",
            "--correlation-id", "history-cli-feedback-correlation",
        )
        self.assertEqual(0, feedback.returncode, feedback.stderr)
        self.assertEqual("recorded", json.loads(feedback.stdout)["status"])

        summary = self.run_cli(
            "memory", "history", "summary",
            *self.common_context(),
        )
        self.assertEqual(0, summary.returncode, summary.stderr)
        summary_payload = json.loads(summary.stdout)
        self.assertEqual(1, summary_payload["eligible_workflow_count"])

        output = self.root / "exports" / "history.json"
        export = self.run_cli(
            "memory", "history", "export",
            *self.common_context(),
            "--output", str(output),
            "--include-observations",
        )
        self.assertEqual(0, export.returncode, export.stderr)
        self.assertTrue(output.is_file())
        self.assertNotIn(str(output), export.stdout)
        self.assertNotIn(str(self.root), output.read_text(encoding="utf-8"))

        purge = self.run_cli(
            "memory", "history", "purge",
            *self.common_context(),
            "--scope", "history-only",
            "--expected-summary-digest", summary_payload["summary_digest"],
            "--idempotency-key", "history-cli-purge",
            "--correlation-id", "history-cli-purge-correlation",
        )
        self.assertEqual(0, purge.returncode, purge.stderr)
        self.assertEqual("purged", json.loads(purge.stdout)["status"])


if __name__ == "__main__":
    unittest.main()
