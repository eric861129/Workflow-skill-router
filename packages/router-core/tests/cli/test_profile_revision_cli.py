from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from memory.test_profile_materializer import prepare_approved


ROOT = Path(__file__).resolve().parents[4]


class ProfileRevisionCliTests(unittest.TestCase):
    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "workflow_skill_router", "profile", *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_apply_and_revision_list_are_machine_readable_without_local_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture, _, store, _, proposal = prepare_approved(root)
            store.close()

            applied = self.run_cli(
                "apply",
                proposal.proposal_id,
                "--database", str(fixture.database),
                "--data-dir", str(root),
                "--expected-state-version", str(proposal.state_version),
                "--idempotency-key", "cli-apply",
                "--correlation-id", "corr-cli-apply",
                "--actor", "developer",
                "--session-id", "session-m2c",
                "--authority", "router-local-managed",
                "--now", "2026-09-04T03:00:00.000Z",
            )
            self.assertEqual(0, applied.returncode, applied.stderr)
            payload = json.loads(applied.stdout)
            self.assertEqual("applied", payload["status"])
            self.assertNotIn(str(root), applied.stdout)

            listed = self.run_cli(
                "revisions", "list", "personal:adaptive-memory",
                "--database", str(fixture.database),
                "--data-dir", str(root),
            )
            self.assertEqual(0, listed.returncode, listed.stderr)
            listed_payload = json.loads(listed.stdout)
            self.assertEqual(1, len(listed_payload["revisions"]))
            self.assertEqual(payload["revision_id"], listed_payload["revisions"][0]["revision_id"])
            self.assertNotIn(str(root), listed.stdout)


if __name__ == "__main__":
    unittest.main()
