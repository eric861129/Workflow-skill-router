from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from memory.m1c_fixture import M1CHistoryFixture


class MemoryCandidatesCliTests(unittest.TestCase):
    def test_rebuild_list_show_and_reject_are_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = M1CHistoryFixture(root)
            fixture.insert_observations(
                count=3,
                dates=("2026-09-01T10:00:00.000Z", "2026-09-02T10:00:00.000Z"),
            )
            common = [
                "--database", str(fixture.database),
                "--data-dir", str(root),
            ]

            rebuild = self.run_cli("memory", "candidates", "rebuild", *common)
            self.assertEqual(0, rebuild.returncode, rebuild.stderr)
            payload = json.loads(rebuild.stdout)
            self.assertEqual("rebuilt", payload["status"])
            self.assertEqual(1, len(payload["candidates"]))
            candidate_id = payload["candidates"][0]["candidate_id"]

            listed = self.run_cli("memory", "candidates", "list", *common, "--status", "proposed")
            self.assertEqual(0, listed.returncode, listed.stderr)
            self.assertEqual(candidate_id, json.loads(listed.stdout)["candidates"][0]["candidate_id"])

            shown = self.run_cli("memory", "candidates", "show", candidate_id, *common)
            self.assertEqual(0, shown.returncode, shown.stderr)
            self.assertEqual(candidate_id, json.loads(shown.stdout)["candidate_id"])

            rejected = self.run_cli(
                "memory", "candidates", "reject", candidate_id, *common,
                "--reason", "not-reusable",
            )
            self.assertEqual(0, rejected.returncode, rejected.stderr)
            self.assertEqual("rejected", json.loads(rejected.stdout)["status"])

    @staticmethod
    def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "workflow_skill_router.cli", *arguments],
            cwd=Path(__file__).resolve().parents[4],
            capture_output=True,
            text=True,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
