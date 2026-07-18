from __future__ import annotations

import copy
from hashlib import sha256
import importlib.util
import json
import os
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
from workflow_skill_router.evaluation.local_evidence import LocalEvidenceProtector


V2 = ROOT / "evaluation" / "v2"
EXPECTED_CASES = {
    "small-auto",
    "small-explicit-lock",
    "phased-current-boundary",
    "phased-transition",
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
REFERENCE_SPEC = importlib.util.spec_from_file_location(
    "reference_driver", V2 / "reference_driver.py"
)
REFERENCE_DRIVER = (
    importlib.util.module_from_spec(REFERENCE_SPEC) if REFERENCE_SPEC else None
)
if REFERENCE_SPEC and REFERENCE_SPEC.loader and REFERENCE_DRIVER:
    REFERENCE_SPEC.loader.exec_module(REFERENCE_DRIVER)


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
    def test_full_suite_has_thirteen_public_safe_behavior_cases(self):
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
            "phased-current-boundary", "managed-goal", "capability-unavailable",
        }, set(smoke["case_ids"]))

    def test_behavior_cases_are_bound_to_contract_revision_2_2(self):
        smoke = json.loads((V2 / "profiles" / "beta-smoke.json").read_text(encoding="utf-8"))
        rows = [
            json.loads(line)
            for line in (V2 / "cases" / "behavior-routing.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ]

        self.assertEqual("workflow-skill-router.behavior-routing", smoke["contract_id"])
        self.assertEqual("2.2.0", smoke["contract_revision"])
        self.assertTrue(all(row["contract_revision"] == "2.2.0" for row in rows))
        self.assertTrue(all(
            RUNNER.public_case_payload(row)["contract_revision"] == "2.2.0"
            for row in rows
        ))

    def test_phase_boundary_and_transition_have_separate_oracles(self):
        cases = {row["id"]: row for row in RUNNER.load_cases("full")}
        current = cases["phased-current-boundary"]
        transition = cases["phased-transition"]

        self.assertEqual("skill:systematic-debugging", current["expected"]["primary_skill"])
        self.assertEqual([], current["expected"]["support_skills"])
        self.assertEqual([], current["interaction_script"])
        self.assertEqual(1, current["max_turns"])

        self.assertEqual(1, len(transition["interaction_script"]))
        self.assertEqual(2, transition["max_turns"])
        self.assertEqual(2, len(transition["expected_turns"]))
        self.assertEqual(
            "skill:systematic-debugging",
            transition["expected_turns"][0]["primary_skill"],
        )
        self.assertEqual("skill:playwright", transition["expected_turns"][1]["primary_skill"])
        self.assertEqual(transition["expected_turns"][-1], transition["expected"])

    def test_consent_cases_bind_support_to_current_phase_exit_evidence(self):
        cases = {row["id"]: row for row in RUNNER.load_cases("full")}

        for case_id in (
            "phased-explicit-consent-approve",
            "phased-explicit-consent-reject",
        ):
            with self.subTest(case_id=case_id):
                case = cases[case_id]
                prompt = case["prompt"]
                self.assertIn("current Phase", prompt)
                self.assertIn("exit evidence", prompt)
                self.assertIn("risk-based contract-test plan", prompt)
                self.assertNotIn("implement it", prompt)
                self.assertEqual(
                    ["skill:qa-test-planner"],
                    case["expected_turns"][0]["support_skills"],
                )

    def test_multi_turn_contract_scores_every_turn_not_only_the_final_route(self):
        self.assertTrue(
            hasattr(RUNNER, "score_attempt"),
            "runner must expose multi-turn contract scoring",
        )
        expected_first = {
            "envelope": "phased",
            "selection_mode": "auto",
            "primary_skill": "skill:systematic-debugging",
            "support_skills": [],
            "consent_action": "not-required",
            "goal_relation": "none",
        }
        expected_final = {
            **expected_first,
            "primary_skill": "skill:playwright",
        }
        case = {
            "expected": expected_final,
            "expected_turns": [expected_first, expected_final],
        }
        wrong_first = {**expected_first, "primary_skill": "skill:playwright"}

        passed, hard, turn_passes = RUNNER.score_attempt(
            case,
            [wrong_first, expected_final],
        )

        self.assertFalse(passed)
        self.assertEqual([], hard)
        self.assertEqual([False, True], turn_passes)

    def test_baseline_and_candidate_share_public_inputs_but_use_distinct_product_modes(self):
        baseline = json.loads((V2 / "baselines" / "no-router.json").read_text(encoding="utf-8"))
        candidate = json.loads((V2 / "profiles" / "router-v2.json").read_text(encoding="utf-8"))
        baseline_package = baseline.pop("instruction_package")
        candidate_package = candidate.pop("instruction_package")
        baseline_execution = baseline.pop("execution")
        candidate_execution = candidate.pop("execution")
        self.assertEqual(baseline, candidate)
        self.assertEqual("model-only", baseline_execution.pop("mode"))
        self.assertEqual("hybrid-router", candidate_execution.pop("mode"))
        self.assertEqual(baseline_execution, candidate_execution)
        self.assertIsNone(baseline_package)
        sources = [ROOT / item for item in candidate_package["files"]]
        self.assertEqual(candidate_package["digest"], canonical_package_digest(sources))
        self.assertTrue(all(path.is_file() for path in sources))
        required_descriptor_fields = {
            "canonical_id", "description", "domains", "stages", "availability",
        }
        self.assertTrue(all(
            isinstance(item, dict) and set(item) == required_descriptor_fields
            for item in baseline["skill_catalog"]
        ))
        catalog = {
            item["canonical_id"]: item
            for item in baseline["skill_catalog"]
        }
        self.assertTrue(all(item["description"] for item in catalog.values()))
        self.assertTrue(all(item["domains"] for item in catalog.values()))
        self.assertTrue(all(item["stages"] for item in catalog.values()))
        rows = [json.loads(line) for line in
                (V2 / "cases" / "behavior-routing.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()]
        for row in rows:
            self.assertIn(row["expected"]["primary_skill"], catalog)
            self.assertTrue(set(row["expected"]["support_skills"]).issubset(catalog))

    def test_runner_recomputes_instruction_digest_and_fails_closed_on_drift(self):
        candidate = json.loads(
            (V2 / "profiles" / "router-v2.json").read_text(encoding="utf-8")
        )
        RUNNER.validate_instruction_package(candidate)

        drifted = copy.deepcopy(candidate)
        drifted["instruction_package"]["digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(
            EvaluationIntegrityError,
            "instruction_package_digest_mismatch",
        ):
            RUNNER.validate_instruction_package(drifted)

    def test_router_instruction_treats_scoped_consent_reply_as_a_state_transition(self):
        instruction = (ROOT / "starter" / "v2" / "workflow-skill-router" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("consent state transition，不是新的任務", instruction)
        self.assertIn("propose_support_consent", instruction)
        self.assertIn("transition_support_consent", instruction)
        self.assertIn("skill-only-fallback", instruction)

    def test_runner_rejects_instruction_paths_outside_the_repository(self):
        candidate = json.loads(
            (V2 / "profiles" / "router-v2.json").read_text(encoding="utf-8")
        )
        candidate["instruction_package"]["files"] = ["../outside.md"]
        with self.assertRaisesRegex(
            EvaluationIntegrityError,
            "instruction_package_path_outside_root",
        ):
            RUNNER.validate_instruction_package(candidate)

    def test_model_prompt_includes_verified_case_capability_snapshot(self):
        cases = {
            row["id"]: row
            for row in RUNNER.load_cases("full")
        }
        case = cases["capability-unavailable"]
        snapshot = case["capability_snapshot"]
        self.assertEqual("verified", snapshot["status"])
        self.assertEqual(
            [{
                "canonical_id": "skill:playwright",
                "availability": "unavailable",
                "reasons": ["runtime-not-exposed"],
            }],
            snapshot["capabilities"],
        )
        profile = RUNNER.load_profiles()["baseline"]
        prompt = RUNNER.model_prompt(case, profile)
        self.assertIn("Verified capability snapshot", prompt)
        self.assertIn('"canonical_id": "skill:playwright"', prompt)
        self.assertIn('"availability": "unavailable"', prompt)
        changed = copy.deepcopy(case)
        changed["capability_snapshot"]["capabilities"][0]["availability"] = "available"
        self.assertNotEqual(
            RUNNER.digest(RUNNER.public_case_payload(case)),
            RUNNER.digest(RUNNER.public_case_payload(changed)),
        )

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
                restricted = Path(output) / "restricted"
                protector = LocalEvidenceProtector()
                self.assertTrue(protector.verify_directory(restricted))
                self.assertTrue(protector.verify_file(restricted / "checkpoint.json"))
                self.assertTrue(protector.verify_file(restricted / "raw-results.json"))
                self.assertFalse((Path(output) / "checkpoint.json").exists())
                self.assertFalse((Path(output) / "raw-results.json").exists())
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
        self.assertNotEqual(
            report["arm_manifests"]["baseline"]["execution_config_digest"],
            report["arm_manifests"]["candidate"]["execution_config_digest"],
        )
        self.assertEqual("model-only", report["arm_manifests"]["baseline"]["execution_mode"])
        self.assertEqual("hybrid-router", report["arm_manifests"]["candidate"]["execution_mode"])
        self.assertIsNone(report["arm_manifests"]["baseline"]["instruction_package_digest"])
        self.assertIsNotNone(report["arm_manifests"]["candidate"]["instruction_package_digest"])
        self.assertEqual("not-observable", report["metrics"]["real_tool_activation"]["metric_status"])
        self.assertEqual("reference-only", report["metrics"]["hybrid_consent_transition"]["metric_status"])
        self.assertIsNone(report["metrics"]["hybrid_consent_transition"]["value"])
        self.assertEqual(0, report["metrics"]["hard_violations"]["value"])
        self.assertEqual(1.0, report["comparison"]["baseline"]["route_contract_match_rate"])
        self.assertEqual(1.0, report["comparison"]["candidate"]["route_contract_match_rate"])
        self.assertIsNone(report["metrics"]["model_usage"]["value"])
        self.assertEqual("unavailable", report["metrics"]["model_usage"]["metric_status"])
        self.assertIsNone(report["provenance"]["model_identifier"])
        self.assertEqual("unavailable", report["provenance"]["model_identity_status"])
        self.assertEqual(0, report["provenance"]["execution_resumed_attempt_count"])
        self.assertEqual(
            "workflow-skill-router.behavior-routing",
            report["provenance"]["evaluation_contract_id"],
        )
        self.assertEqual("2.2.0", report["provenance"]["evaluation_contract_revision"])
        self.assertEqual("verified", report["provenance"]["evidence_protection"]["status"])
        self.assertEqual("restricted", report["provenance"]["evidence_protection"]["directory"])
        self.assertEqual(6, len(report["case_diagnostics"]))
        self.assertTrue(all(
            set(item) == {"case_id", "arms", "candidate_minus_baseline"}
            for item in report["case_diagnostics"]
        ))
        diagnostics_text = json.dumps(
            report["case_diagnostics"],
            ensure_ascii=False,
            sort_keys=True,
        )
        self.assertNotIn("skill:", diagnostics_text)
        self.assertNotIn('"route"', diagnostics_text)
        self.assertNotIn('"expected"', diagnostics_text)
        self.assertIn("turn_contract_match_rate", report["comparison"]["candidate"])
        self.assertTrue(all(
            set(("turn_count", "turn_pass_count")).issubset(item)
            for item in report["attempts"]
        ))

    def test_reference_driver_routes_only_the_user_task_section(self):
        self.assertIsNotNone(REFERENCE_DRIVER)
        prompt = (
            "Router instruction package:\n"
            "Use skill:workflow-skill-router for a managed Goal.\n\n"
            "Available SKILL catalog:\n"
            "[{\"canonical_id\":\"skill:workflow-skill-router\"}]\n\n"
            "User task:\n"
            "Add a short troubleshooting note for one documented API error. "
            "Choose the minimum useful Skill route before doing the work."
        )

        route = REFERENCE_DRIVER._route(prompt)

        self.assertEqual("single", route["envelope"])
        self.assertEqual("auto", route["selection_mode"])
        self.assertEqual("skill:code-documenter", route["primary_skill"])

    def test_reference_driver_routes_public_consent_followups(self):
        self.assertIsNotNone(REFERENCE_DRIVER)
        approved = REFERENCE_DRIVER._route(
            "I approve the proposed contract-testing support for this phase only."
        )
        rejected = REFERENCE_DRIVER._route(
            "Do not use the proposed supporting Skill. Continue with only "
            "skill:api-designer."
        )

        self.assertEqual("skill:api-designer", approved["primary_skill"])
        self.assertEqual(["skill:qa-test-planner"], approved["support_skills"])
        self.assertEqual("approved", approved["consent_action"])
        self.assertEqual("explicit-locked", approved["selection_mode"])
        self.assertEqual("skill:api-designer", rejected["primary_skill"])
        self.assertEqual([], rejected["support_skills"])
        self.assertEqual("rejected", rejected["consent_action"])
        self.assertEqual("explicit-locked", rejected["selection_mode"])

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
            protector = LocalEvidenceProtector()
            protector.protect_directory(complete)
            protector.protect_file(complete / "transcript.json")
            protector.protect_directory(failed)
            protector.protect_file(failed / "transcript.json")
            protector.protect_file(failed / "failure.json")

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
                protector = LocalEvidenceProtector()
                protector.protect_directory(path)
                protector.protect_file(path / "transcript.json")
            with self.assertRaisesRegex(EvaluationIntegrityError, "resume_nonce_ambiguous"):
                RUNNER.recover_attempt(root, "nonce-1", 1)

    def test_resume_rejects_unprotected_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory) / "legacy-context"
            context.mkdir()
            transcript = context / "transcript.json"
            transcript.write_text(json.dumps({
                "attempt_nonce": "nonce-1",
                "turns": [{"user": "task", "assistant": {"envelope": "single"}}],
            }), encoding="utf-8")
            if os.name != "nt":
                context.chmod(0o755)
                transcript.chmod(0o644)

            self.assertIsNone(RUNNER.recover_attempt(Path(directory), "nonce-1", 1))

    def test_output_preflight_rejects_legacy_public_raw_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "raw-results.json").write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(
                EvaluationIntegrityError,
                "benchmark_legacy_public_evidence_present",
            ):
                RUNNER.prepare_output_directory(output, LocalEvidenceProtector())

            self.assertFalse((output / "restricted").exists())

    def test_output_preflight_rejects_any_nonempty_output_root(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "sanitized-report.json").write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(
                EvaluationIntegrityError,
                "benchmark_output_not_fresh",
            ):
                RUNNER.prepare_output_directory(output, LocalEvidenceProtector())

            self.assertFalse((output / "restricted").exists())

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

    def test_case_diagnostics_aggregate_matches_without_exposing_route_values(self):
        expected = {
            "envelope": "single",
            "selection_mode": "auto",
            "primary_skill": "skill:secret-expected",
            "support_skills": [],
            "consent_action": "not-required",
            "goal_relation": "none",
        }
        cases = [{"id": "public-case", "expected": expected}]
        records = [
            {
                "arm": "baseline",
                "case_id": "public-case",
                "route": {**expected, "primary_skill": "skill:secret-actual"},
                "passed": False,
                "hard_violations": [],
            },
            {
                "arm": "candidate",
                "case_id": "public-case",
                "route": dict(expected),
                "passed": True,
                "hard_violations": [],
            },
        ]

        diagnostics = RUNNER.case_diagnostics(records, cases)

        self.assertEqual(1, len(diagnostics))
        item = diagnostics[0]
        self.assertEqual("public-case", item["case_id"])
        self.assertEqual(0.0, item["arms"]["baseline"]["pass_rate"])
        self.assertEqual(1.0, item["arms"]["candidate"]["pass_rate"])
        self.assertEqual(
            0.0,
            item["arms"]["baseline"]["field_match_rates"]["primary_skill"],
        )
        self.assertEqual(
            1.0,
            item["candidate_minus_baseline"]["field_match_rates"]["primary_skill"],
        )
        serialized = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("secret-expected", serialized)
        self.assertNotIn("secret-actual", serialized)
        self.assertNotIn('"route"', serialized)
        self.assertNotIn('"expected"', serialized)

    def test_attempt_nonce_is_bound_to_prompt_and_tool_inventory(self):
        first = RUNNER.make_attempt_nonce("full", "baseline", "case", 0, "prompt-a", [])
        changed_prompt = RUNNER.make_attempt_nonce("full", "baseline", "case", 0, "prompt-b", [])
        changed_tools = RUNNER.make_attempt_nonce("full", "baseline", "case", 0, "prompt-a", ["read"])
        self.assertEqual(3, len({first, changed_prompt, changed_tools}))


if __name__ == "__main__":
    unittest.main()
