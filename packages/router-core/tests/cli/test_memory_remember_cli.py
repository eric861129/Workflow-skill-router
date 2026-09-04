from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from workflow_skill_router.service_models import RequestContext

from memory.workflow_fixture import WorkflowFixture, write_personal_memory_policy


class MemoryRememberCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.database = self.root / "router-v2.sqlite3"
        self.context = RequestContext("session-cli-memory", "developer", "runtime-policy-1")
        fixture = WorkflowFixture(self.database, self.context)
        self.plan = fixture.plan_single(key="cli-plan")
        fixture.complete(self.plan)
        write_personal_memory_policy(self.root, "observe")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_memory_remember_accepts_structured_matchers_without_target_path(self) -> None:
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "workflow_skill_router.cli",
                "memory",
                "remember",
                "--database",
                str(self.database),
                "--data-dir",
                str(self.root),
                "--workflow-run",
                self.plan.workflow_run_id,
                "--session-id",
                self.context.session_id,
                "--actor",
                self.context.actor,
                "--runtime-policy-snapshot-id",
                self.context.runtime_policy_snapshot_id,
                "--keyword",
                "student api",
                "--domain",
                "api",
                "--matcher-source",
                "user-explicit",
                "--target",
                "managed-personal",
                "--risk",
                "r1",
                "--side-effect",
                "none",
                "--one-shot",
                "remember-once",
                "--idempotency-key",
                "cli-remember",
                "--correlation-id",
                "cli-correlation",
            ],
            cwd=Path(__file__).resolve().parents[4],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, process.returncode, process.stderr)
        payload = json.loads(process.stdout)
        self.assertEqual("recorded", payload["status"])
        self.assertNotIn(str(self.root), process.stdout)
        self.assertNotIn("target-path", process.stdout)


if __name__ == "__main__":
    unittest.main()
