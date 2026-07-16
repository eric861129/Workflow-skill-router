from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCE = ROOT / "packages" / "router-core" / "src"
if str(CORE_SOURCE) not in sys.path:
    sys.path.insert(0, str(CORE_SOURCE))

from workflow_skill_router.evaluation.contracts import EvaluationIntegrityError


V2 = ROOT / "evaluation" / "v2"
EXPECTED_CASES = {
    "small-auto",
    "small-explicit-lock",
    "phased-auto",
    "phased-explicit-consent-approve",
    "phased-explicit-consent-reject",
    "managed-goal",
    "goal-status",
    "goal-steer",
    "side-question",
    "capability-unavailable",
    "runtime-drift",
    "evaluation-manual-required",
}
RUNNER_SPEC = importlib.util.spec_from_file_location("run_v2_benchmark", ROOT / "scripts" / "run-v2-benchmark.py")
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC) if RUNNER_SPEC else None
if RUNNER_SPEC and RUNNER_SPEC.loader and RUNNER:
    RUNNER_SPEC.loader.exec_module(RUNNER)


def canonical_package_digest(paths: list[Path]) -> str:
    records = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix().casefold())
    ]
    canonical = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(canonical.encode("utf-8")).hexdigest()


class V2BenchmarkTests(unittest.TestCase):
    def test_full_suite_has_twelve_public_safe_behavior_cases(self):
        rows = [json.loads(line) for line in
                (V2 / "cases" / "behavior-routing.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()]
        self.assertEqual(EXPECTED_CASES, {row["id"] for row in rows})
        self.assertTrue(all(row["public_safe"] is True for row in rows))
        self.assertTrue(all(row["allowed_tools"] == [] for row in rows))
        self.assertTrue(all(row["max_turns"] >= len(row["interaction_script"]) + 1 for row in rows))

    def test_beta_smoke_selects_six_representative_cases(self):
        smoke = json.loads((V2 / "profiles" / "beta-smoke.json").read_text(encoding="utf-8"))
        self.assertEqual(6, smoke["case_count"])
        self.assertEqual(6, len(set(smoke["case_ids"])))
        self.assertEqual({
            "small-auto", "small-explicit-lock", "phased-explicit-consent-approve",
            "phased-auto", "managed-goal", "capability-unavailable",
        }, set(smoke["case_ids"]))

    def test_baseline_and_candidate_differ_only_by_router_instruction_package(self):
        baseline = json.loads((V2 / "baselines" / "no-router.json").read_text(encoding="utf-8"))
        candidate = json.loads((V2 / "profiles" / "router-v2.json").read_text(encoding="utf-8"))
        baseline_package = baseline.pop("instruction_package")
        candidate_package = candidate.pop("instruction_package")
        self.assertEqual(baseline, candidate)
        self.assertIsNone(baseline_package)
        sources = [ROOT / item for item in candidate_package["files"]]
        self.assertEqual(candidate_package["digest"], canonical_package_digest(sources))
        self.assertTrue(all(path.is_file() for path in sources))
        catalog = set(baseline["skill_catalog"])
        rows = [json.loads(line) for line in
                (V2 / "cases" / "behavior-routing.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()]
        for row in rows:
            self.assertIn(row["expected"]["primary_skill"], catalog)
            self.assertTrue(set(row["expected"]["support_skills"]).issubset(catalog))

    def test_reference_runner_is_deterministic_and_cannot_claim_behavior_evidence(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            reports = []
            for output in (first, second):
                result = subprocess.run([
                    sys.executable,
                    str(ROOT / "scripts" / "run-v2-benchmark.py"),
                    "--suite", "beta-smoke",
                    "--evidence-class", "reference-driver",
                    "--adapter-executable", sys.executable,
                    "--adapter-arg", str(V2 / "reference_driver.py"),
                    "--repeats", "3",
                    "--output-dir", output,
                ], cwd=ROOT, text=True, encoding="utf-8", capture_output=True)
                self.assertEqual(0, result.returncode, result.stderr)
                reports.append((Path(output) / "sanitized-report.json").read_bytes())

            self.assertEqual(reports[0], reports[1])
            report = json.loads(reports[0])

        self.assertEqual("reference-driver", report["evidence_class"])
        self.assertTrue(report["evidence_class_locked"])
        self.assertEqual("review-required", report["status"])
        self.assertNotIn("public_composite_score", report)
        self.assertEqual(36, report["attempt_count"])
        self.assertEqual(36, len(set(report["attempt_nonces"])))
        self.assertEqual(36, len(set(report["fresh_context_ids"])))
        self.assertEqual(6, len(report["paired_case_ids"]))
        self.assertEqual(18, report["comparison"]["paired_attempt_count"])
        self.assertIn("candidate_minus_baseline", report["comparison"])
        self.assertEqual(
            report["arm_manifests"]["baseline"]["execution_config_digest"],
            report["arm_manifests"]["candidate"]["execution_config_digest"],
        )
        self.assertIsNone(report["arm_manifests"]["baseline"]["instruction_package_digest"])
        self.assertIsNotNone(report["arm_manifests"]["candidate"]["instruction_package_digest"])
        self.assertEqual("not-observable", report["metrics"]["real_tool_activation"]["metric_status"])
        self.assertIsNone(report["metrics"]["model_usage"]["value"])
        self.assertEqual("unavailable", report["metrics"]["model_usage"]["metric_status"])
        self.assertIsNone(report["provenance"]["model_identifier"])
        self.assertEqual("unavailable", report["provenance"]["model_identity_status"])
        self.assertEqual(0, report["provenance"]["execution_resumed_attempt_count"])

    def test_reference_driver_uses_utf8_for_protocol_input_and_output(self):
        request = {
            "type": "start_attempt",
            "opaque_run_case_id": "case-繁體中文",
            "prompt": "請路由—不要執行",
            "profile": "behavior",
            "allowed_tools": [],
            "attempt_nonce": "nonce-繁體中文",
        }
        result = subprocess.run(
            [sys.executable, str(V2 / "reference_driver.py")],
            input=json.dumps(request, ensure_ascii=False).encode("utf-8"),
            capture_output=True,
        )
        self.assertEqual(0, result.returncode, result.stderr.decode("utf-8", errors="replace"))
        self.assertEqual("nonce-繁體中文", json.loads(result.stdout.decode("utf-8"))["attempt_nonce"])

    def test_resume_accepts_only_complete_failure_free_nonce_bound_transcript(self):
        self.assertIsNotNone(RUNNER)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            complete = root / "fresh-context"
            complete.mkdir()
            (complete / "transcript.json").write_text(json.dumps({
                "attempt_nonce": "nonce-1",
                "turns": [{"user": "task", "assistant": {"envelope": "single"}}],
            }), encoding="utf-8")
            failed = root / "failed-context"
            failed.mkdir()
            (failed / "transcript.json").write_text(json.dumps({
                "attempt_nonce": "nonce-1",
                "turns": [{"user": "task", "assistant": {"envelope": "phased"}}],
            }), encoding="utf-8")
            (failed / "failure.json").write_text("{}", encoding="utf-8")

            recovered = RUNNER.recover_attempt(root, "nonce-1", 1)

        self.assertIsNotNone(recovered)
        self.assertEqual("fresh-context", recovered[0])
        self.assertEqual("single", recovered[1][0]["route"]["envelope"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("one", "two"):
                path = root / name
                path.mkdir()
                (path / "transcript.json").write_text(json.dumps({
                    "attempt_nonce": "nonce-1",
                    "turns": [{"user": "task", "assistant": {"envelope": "single"}}],
                }), encoding="utf-8")
            with self.assertRaisesRegex(EvaluationIntegrityError, "resume_nonce_ambiguous"):
                RUNNER.recover_attempt(root, "nonce-1", 1)

    def test_skill_prefix_is_normalized_for_explicit_lock_scoring(self):
        case = {
            "expected": {
                "envelope": "single",
                "selection_mode": "explicit-locked",
                "primary_skill": "skill:api-designer",
                "support_skills": [],
                "consent_action": "not-required",
                "goal_relation": "none",
            },
        }
        route = {
            "envelope": "single",
            "selection_mode": "explicit-locked",
            "primary_skill": "api-designer",
            "support_skills": [],
            "consent_action": "not-required",
            "goal_relation": "none",
        }
        passed, hard = RUNNER.score_route(case, route)
        self.assertTrue(passed)
        self.assertEqual([], hard)

    def test_attempt_nonce_is_bound_to_prompt_and_tool_inventory(self):
        first = RUNNER.make_attempt_nonce("full", "baseline", "case", 0, "prompt-a", [])
        changed_prompt = RUNNER.make_attempt_nonce("full", "baseline", "case", 0, "prompt-b", [])
        changed_tools = RUNNER.make_attempt_nonce("full", "baseline", "case", 0, "prompt-a", ["read"])
        self.assertEqual(3, len({first, changed_prompt, changed_tools}))


if __name__ == "__main__":
    unittest.main()
