import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[4]


class CliTests(unittest.TestCase):
    @staticmethod
    def profile_document():
        return {
            "schema_id": "workflow-skill-router/routing-profile",
            "schema_version": "1.0.0",
            "artifact_kind": "routing-profile",
            "profile_id": "personal:api",
            "scope": "personal",
            "enabled": True,
            "rules": [{
                "rule_id": "api",
                "priority": 100,
                "match": {
                    "objective_keywords": ["api"],
                    "domains": ["api"],
                    "tags": [],
                    "work_modes": ["phased"],
                },
                "route": {
                    "work_mode": "phased",
                    "skill_tree": [{
                        "phase_id": "design",
                        "primary_skill_id": "skill:api-designer",
                        "support_skill_ids": ["skill:api-guidelines-skill"],
                        "exit_gate": "contract-ready",
                    }],
                },
            }],
        }

    def test_doctor_is_honest_and_has_no_telemetry(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = {**os.environ, "PYTHONPATH": str(ROOT / "packages/router-core/src")}
            result = subprocess.run([sys.executable, "-m", "workflow_skill_router", "doctor",
                                     "--database", str(Path(directory) / "router.db")],
                                    text=True, encoding="utf-8", capture_output=True, env=environment)
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("core-ready", payload["runtime_status"])
        self.assertIsNone(payload["conformance_profile"])
        self.assertEqual("skill-only-fallback", payload["fallback_mode"])
        self.assertFalse(payload["telemetry_enabled"])

    def test_v1_scripts_are_not_wrapped(self):
        sources = "\n".join(path.read_text(encoding="utf-8") for path in
                            (ROOT / "packages/router-core/src/workflow_skill_router/cli").glob("*.py"))
        for legacy in ("scan-skills.py", "evaluate-routing.py", "validate-router.py"):
            self.assertNotIn(legacy, sources)

    def test_profile_validate_install_list_and_preview_are_machine_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "profile.json"
            profile.write_text(
                json.dumps(self.profile_document(), ensure_ascii=False),
                encoding="utf-8",
            )
            state = root / "state"
            environment = {**os.environ, "PYTHONPATH": str(ROOT / "packages/router-core/src")}

            def run(*arguments: str):
                return subprocess.run(
                    [sys.executable, "-m", "workflow_skill_router", "profile", *arguments],
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    env=environment,
                )

            validated = run("validate", str(profile))
            self.assertEqual(0, validated.returncode, validated.stderr)
            self.assertEqual("valid", json.loads(validated.stdout)["status"])

            installed = run("install", str(profile), "--data-dir", str(state))
            self.assertEqual(0, installed.returncode, installed.stderr)
            self.assertEqual("personal:api", json.loads(installed.stdout)["profile_id"])

            listed = run("list", "--data-dir", str(state))
            self.assertEqual(0, listed.returncode, listed.stderr)
            self.assertEqual(["personal:api"], json.loads(listed.stdout)["profile_ids"])

            preview = run(
                "preview",
                "--data-dir", str(state),
                "--objective", "交付 API",
                "--work-mode", "phased",
                "--domain", "api",
            )
            self.assertEqual(0, preview.returncode, preview.stderr)
            payload = json.loads(preview.stdout)
            self.assertEqual("personal-profile", payload["route_source"])
            self.assertEqual("skill:api-designer", payload["current_phase"]["primary_skill_id"])


if __name__ == "__main__": unittest.main()
