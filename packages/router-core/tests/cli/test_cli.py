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

            explained = run(
                "preview",
                "--data-dir", str(state),
                "--objective", r"交付 C:\Users\developer\private API instructions",
                "--work-mode", "phased",
                "--domain", "api",
                "--explain",
            )
            self.assertEqual(0, explained.returncode, explained.stderr)
            explained_payload = json.loads(explained.stdout)
            self.assertEqual(
                [{
                    "rule_id": "api",
                    "matched": True,
                    "matched_dimensions": [
                        "objective_keywords",
                        "domains",
                        "work_modes",
                    ],
                    "unmatched_dimensions": [],
                    "reason_codes": [],
                }],
                explained_payload["rule_traces"],
            )
            self.assertNotIn(str(root), explained.stdout)
            self.assertNotIn("private API instructions", explained.stdout)

    def test_profile_preview_explain_preserves_traces_when_current_phase_is_invalid(self):
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

            installed = run("install", str(profile), "--data-dir", str(state))
            self.assertEqual(0, installed.returncode, installed.stderr)

            invalid_explained = run(
                "preview",
                "--data-dir", str(state),
                "--objective", f"交付 {root} private API instructions",
                "--work-mode", "phased",
                "--domain", "api",
                "--current-phase", str(root / "missing-phase"),
                "--explain",
            )

        self.assertEqual(2, invalid_explained.returncode)
        invalid_payload = json.loads(invalid_explained.stderr)
        self.assertEqual("invalid", invalid_payload["status"])
        self.assertEqual(
            "current-phase-absent-from-matched-profile",
            invalid_payload["error"],
        )
        self.assertEqual(
            [{
                "rule_id": "api",
                "matched": True,
                "matched_dimensions": [
                    "objective_keywords",
                    "domains",
                    "work_modes",
                ],
                "unmatched_dimensions": [],
                "reason_codes": [],
            }],
            invalid_payload["rule_traces"],
        )
        self.assertNotIn(str(root), invalid_explained.stderr)
        self.assertNotIn("private API instructions", invalid_explained.stderr)

    def test_profile_lint_uses_error_code_two_and_keeps_advisories_non_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = {**os.environ, "PYTHONPATH": str(ROOT / "packages/router-core/src")}

            def run_lint(document, *arguments: str):
                profile = root / "profile.json"
                profile.write_text(
                    json.dumps(document, ensure_ascii=False),
                    encoding="utf-8",
                )
                return subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "workflow_skill_router",
                        "profile",
                        "lint",
                        str(profile),
                        *arguments,
                    ],
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    env=environment,
                )

            advisory = run_lint(self.profile_document())
            self.assertEqual(0, advisory.returncode, advisory.stderr)
            advisory_payload = json.loads(advisory.stdout)
            self.assertEqual("valid", advisory_payload["status"])
            self.assertEqual(0, advisory_payload["error_count"])
            self.assertIn(
                "lexical-alias-omission",
                [issue["code"] for issue in advisory_payload["issues"]],
            )

            conflict = self.profile_document()
            second = json.loads(json.dumps(conflict["rules"][0]))
            second["rule_id"] = "service"
            second["match"]["objective_keywords"] = ["service"]
            second["route"]["skill_tree"][0]["primary_skill_id"] = (
                "skill:architecture-designer"
            )
            conflict["rules"].append(second)
            failed = run_lint(conflict)
            self.assertEqual(2, failed.returncode)
            failed_payload = json.loads(failed.stdout)
            self.assertEqual("invalid", failed_payload["status"])
            self.assertIn(
                "equal-rank-conflict",
                [issue["code"] for issue in failed_payload["issues"]],
            )

            missing_phase = run_lint(
                self.profile_document(),
                "--current-phase",
                "verification",
            )
            self.assertEqual(2, missing_phase.returncode)
            self.assertIn(
                "missing-current-phase",
                [issue["code"] for issue in json.loads(missing_phase.stdout)["issues"]],
            )

            same_skill = self.profile_document()
            same_skill["rules"][0]["route"]["skill_tree"][0]["support_skill_ids"] = [
                "skill:api-designer"
            ]
            invalid_contract = run_lint(same_skill)
            self.assertEqual(2, invalid_contract.returncode)
            self.assertIn(
                "same-primary-support-skill",
                [
                    issue["code"]
                    for issue in json.loads(invalid_contract.stdout)["issues"]
                ],
            )


if __name__ == "__main__": unittest.main()
