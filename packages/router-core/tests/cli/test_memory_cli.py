from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[4]


def policy_document(*, scope: str = "personal", mode: str = "reviewed") -> dict[str, object]:
    return {
        "schema_id": "workflow-skill-router/memory-policy",
        "schema_version": "1.0.0",
        "artifact_kind": "memory-policy",
        "policy_id": f"{scope}:cli",
        "scope": scope,
        "mode": mode,
    }


def policy_yaml(*, scope: str = "personal", mode: str = "reviewed") -> str:
    return (
        "schema_id: workflow-skill-router/memory-policy\n"
        "schema_version: 1.0.0\n"
        "artifact_kind: memory-policy\n"
        f"policy_id: {scope}:cli\n"
        f"scope: {scope}\n"
        f"mode: {mode}\n"
    )


class MemoryCliTests(unittest.TestCase):
    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        environment = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "packages/router-core/src"),
        }
        return subprocess.run(
            [sys.executable, "-m", "workflow_skill_router", "memory", *arguments],
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=environment,
        )

    def test_status_is_default_off_and_does_not_create_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "missing-state"
            result = self.run_cli("status", "--data-dir", str(data_dir))

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("ready", payload["status"])
            self.assertEqual("disabled", payload["mode"])
            self.assertEqual("disabled", payload["personal_mode"])
            self.assertEqual(["personal-policy-missing"], payload["reason_codes"])
            self.assertFalse(payload["capture_enabled"])
            self.assertFalse(payload["memory_store_exists"])
            self.assertFalse(data_dir.exists())
            self.assertNotIn(str(data_dir), result.stdout)

    def test_status_loads_personal_policy_without_echoing_its_path_or_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "state"
            config = data_dir / "config"
            config.mkdir(parents=True)
            (config / "workflow-memory.yaml").write_text(policy_yaml(), encoding="utf-8")

            result = self.run_cli("status", "--data-dir", str(data_dir))

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("reviewed", payload["mode"])
            self.assertEqual("personal-policy", payload["policy_source"])
            self.assertTrue(payload["capture_enabled"])
            self.assertTrue(payload["candidate_generation_enabled"])
            self.assertEqual("review-required", payload["profile_promotion"])
            self.assertEqual(["managed-personal"], payload["allowed_targets"])
            self.assertNotIn(str(root), result.stdout)
            self.assertNotIn("raw_prompt", result.stdout)

    def test_workspace_policy_restricts_but_cannot_elevate_personal_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "state"
            config = data_dir / "config"
            config.mkdir(parents=True)
            (config / "workflow-memory.json").write_text(
                json.dumps(policy_document(mode="automatic")), encoding="utf-8"
            )
            workspace = root / "workspace"
            workspace_config = workspace / ".codex"
            workspace_config.mkdir(parents=True)
            (workspace_config / "workflow-memory.yaml").write_text(
                policy_yaml(scope="workspace", mode="reviewed"), encoding="utf-8"
            )

            restricted = self.run_cli(
                "status",
                "--data-dir", str(data_dir),
                "--workspace", str(workspace),
            )

            self.assertEqual(0, restricted.returncode, restricted.stderr)
            payload = json.loads(restricted.stdout)
            self.assertEqual("reviewed", payload["mode"])
            self.assertEqual("automatic", payload["personal_mode"])
            self.assertEqual("reviewed", payload["workspace_requested_mode"])
            self.assertEqual("workspace-restriction", payload["policy_source"])
            self.assertIn("workspace-policy-reduced-autonomy", payload["reason_codes"])
            self.assertNotIn(str(root), restricted.stdout)

            (config / "workflow-memory.json").write_text(
                json.dumps(policy_document(mode="observe")), encoding="utf-8"
            )
            (workspace_config / "workflow-memory.yaml").write_text(
                policy_yaml(scope="workspace", mode="automatic"), encoding="utf-8"
            )
            not_elevated = self.run_cli(
                "status",
                "--data-dir", str(data_dir),
                "--workspace", str(workspace),
            )
            self.assertEqual(0, not_elevated.returncode, not_elevated.stderr)
            payload = json.loads(not_elevated.stdout)
            self.assertEqual("observe", payload["mode"])
            self.assertIn("workspace-policy-exceeds-ceiling", payload["reason_codes"])

    def test_ambiguous_personal_policy_reports_disabled_in_machine_readable_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "state"
            config = data_dir / "config"
            config.mkdir(parents=True)
            (config / "workflow-memory.json").write_text(
                json.dumps(policy_document()), encoding="utf-8"
            )
            (config / "workflow-memory.yml").write_text(policy_yaml(), encoding="utf-8")

            result = self.run_cli("status", "--data-dir", str(data_dir))

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("disabled", payload["mode"])
            self.assertEqual("invalid-personal-policy", payload["policy_source"])
            self.assertIn("ambiguous-memory-policy", payload["reason_codes"])

    def test_policy_validate_has_stable_exit_codes_and_never_echoes_the_input_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid = root / "personal.yaml"
            valid.write_text(policy_yaml(), encoding="utf-8")
            valid_result = self.run_cli(
                "policy", "validate", str(valid), "--scope", "personal"
            )
            self.assertEqual(0, valid_result.returncode, valid_result.stderr)
            payload = json.loads(valid_result.stdout)
            self.assertEqual("valid", payload["status"])
            self.assertEqual("personal:cli", payload["policy_id"])
            self.assertEqual("reviewed", payload["mode"])
            self.assertRegex(payload["policy_digest"], r"^sha256:[0-9a-f]{64}$")
            self.assertNotIn(str(root), valid_result.stdout)

            invalid = root / "invalid.json"
            invalid.write_text("{not-json", encoding="utf-8")
            invalid_result = self.run_cli(
                "policy", "validate", str(invalid), "--scope", "personal"
            )
            self.assertEqual(2, invalid_result.returncode)
            payload = json.loads(invalid_result.stderr)
            self.assertEqual("invalid", payload["status"])
            self.assertTrue(payload["error"])
            self.assertNotIn(str(root), invalid_result.stderr)

    def test_policy_explain_shows_source_states_and_resolution_without_local_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "state"
            config = data_dir / "config"
            config.mkdir(parents=True)
            (config / "workflow-memory.json").write_text(
                json.dumps(policy_document(mode="automatic")), encoding="utf-8"
            )
            workspace = root / "workspace"
            (workspace / ".codex").mkdir(parents=True)
            (workspace / ".codex" / "workflow-memory.json").write_text(
                json.dumps(policy_document(scope="workspace", mode="reviewed")),
                encoding="utf-8",
            )

            result = self.run_cli(
                "policy", "explain",
                "--data-dir", str(data_dir),
                "--workspace", str(workspace),
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("ready", payload["status"])
            self.assertEqual("valid", payload["personal_policy"]["status"])
            self.assertEqual("valid", payload["workspace_policy"]["status"])
            self.assertEqual("reviewed", payload["effective_policy"]["mode"])
            self.assertEqual(
                [
                    "personal-policy-loaded",
                    "workspace-policy-loaded",
                    "workspace-policy-reduced-autonomy",
                    "effective-policy-canonicalized",
                ],
                payload["resolution_steps"],
            )
            serialized = json.dumps(payload, sort_keys=True)
            self.assertNotIn(str(root), serialized)
            self.assertNotIn("source_path", serialized)
            self.assertNotIn("raw_prompt", serialized)


if __name__ == "__main__":
    unittest.main()
