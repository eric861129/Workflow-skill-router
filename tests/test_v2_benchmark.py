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
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCE = ROOT / "packages" / "router-core" / "src"
if str(CORE_SOURCE) not in sys.path:
    sys.path.insert(0, str(CORE_SOURCE))

from workflow_skill_router.evaluation.contracts import EvaluationIntegrityError
from workflow_skill_router.evaluation.local_evidence import LocalEvidenceProtector


V2 = ROOT / "evaluation" / "v2"
CANONICAL_BEHAVIOR_ADAPTER = V2 / "adapters" / "codex_cli_driver.py"
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
    "profile-explain-miss",
}
SAFE_EVIDENCE = {
    "classification": {
        "source": "builtin-fallback",
        "reason_codes": ["single-default"],
    },
    "authority": {"mode": "router-local", "native_goal_mutated": False},
    "profile_explain": {"status": "not-requested", "reason_codes": []},
    "activation_status": "unverified",
    "semantic_candidate_persisted": False,
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
    def test_behavior_cli_requires_authorized_source_and_adapter_revisions(self):
        destinations = {
            action.dest for action in RUNNER.build_parser()._actions
        }

        self.assertIn("authorized_source_revision", destinations)
        self.assertIn("authorized_adapter_revision", destinations)

    def test_behavior_runbook_supplies_frozen_source_and_adapter_revisions(self):
        runbook = (ROOT / "evaluation" / "README.md").read_text(encoding="utf-8")

        self.assertIn("--print-canonical-adapter-revision", runbook)
        self.assertIn("--authorized-source-revision $SourceRevision", runbook)
        self.assertIn("--authorized-adapter-revision $AdapterRevision", runbook)
        self.assertIn("git status --porcelain=v1", runbook)
        self.assertIn("before and after every adapter invocation", runbook)

    def test_runner_prints_canonical_adapter_closure_revision(self):
        expected = RUNNER.adapter_source_revision(
            sys.executable,
            [str(CANONICAL_BEHAVIOR_ADAPTER.resolve())],
        )

        with patch("builtins.print") as printer:
            result = RUNNER.main(["--print-canonical-adapter-revision"])

        self.assertEqual(0, result)
        printer.assert_called_once_with(expected)

    def test_behavior_cli_emits_only_public_safe_integrity_code(self):
        result = subprocess.run([
            sys.executable,
            str(ROOT / "scripts" / "run-v2-benchmark.py"),
            "--suite", "beta-smoke",
            "--evidence-class", "behavior",
            "--adapter-executable", sys.executable,
            "--adapter-arg", str(V2 / "adapters" / "codex_cli_driver.py"),
            "--adapter-arg=--model",
            "--adapter-arg", "gpt-test",
            "--repeats", "3",
            "--output-dir", "unused-output",
            "--confirm-live-run",
            "--authorized-source-revision", "main",
            "--authorized-adapter-revision", "sha256:" + "0" * 64,
        ], cwd=ROOT, text=True, encoding="utf-8", capture_output=True)

        self.assertNotEqual(0, result.returncode)
        self.assertEqual(
            "behavior_source_revision_invalid",
            result.stderr.strip(),
        )

    def test_behavior_source_revision_validation_is_fail_closed_and_public_safe(self):
        if not hasattr(RUNNER, "verify_behavior_source_revision"):
            self.fail("behavior source revision verifier is missing")

        full_revision = "a" * 40

        with self.assertRaisesRegex(
            EvaluationIntegrityError,
            "behavior_source_revision_required",
        ):
            RUNNER.verify_behavior_source_revision(None)
        with self.assertRaisesRegex(
            EvaluationIntegrityError,
            "behavior_source_revision_invalid",
        ):
            RUNNER.verify_behavior_source_revision("main")

        with patch.object(
            RUNNER.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 1, "", "private diagnostic"),
        ):
            with self.assertRaisesRegex(
                EvaluationIntegrityError,
                "behavior_source_revision_unreachable",
            ) as caught:
                RUNNER.verify_behavior_source_revision(full_revision)
        self.assertNotIn("private diagnostic", str(caught.exception))

        def git_result(command, **_kwargs):
            operation = tuple(command[1:3])
            if operation == ("cat-file", "-e"):
                return subprocess.CompletedProcess(command, 0, "", "")
            if operation == ("rev-parse", "HEAD"):
                return subprocess.CompletedProcess(command, 0, "b" * 40 + "\n", "")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch.object(RUNNER.subprocess, "run", side_effect=git_result):
            with self.assertRaisesRegex(
                EvaluationIntegrityError,
                "behavior_source_revision_mismatch",
            ):
                RUNNER.verify_behavior_source_revision(full_revision)

        def dirty_git_result(command, **_kwargs):
            operation = tuple(command[1:3])
            if operation == ("cat-file", "-e"):
                return subprocess.CompletedProcess(command, 0, "", "")
            if operation == ("rev-parse", "HEAD"):
                return subprocess.CompletedProcess(command, 0, full_revision + "\n", "")
            if operation == ("status", "--porcelain=v1"):
                return subprocess.CompletedProcess(command, 0, " M private-file\n", "")
            return subprocess.CompletedProcess(command, 1, "", "private diagnostic")

        with patch.object(RUNNER.subprocess, "run", side_effect=dirty_git_result):
            with self.assertRaisesRegex(
                EvaluationIntegrityError,
                "behavior_source_checkout_dirty",
            ) as caught:
                RUNNER.verify_behavior_source_revision(full_revision)
        self.assertNotIn("private-file", str(caught.exception))
        self.assertNotIn("private diagnostic", str(caught.exception))

    def test_behavior_adapter_revision_is_required_and_matches_canonical_execution_closure(self):
        if not hasattr(RUNNER, "verify_behavior_adapter_revision"):
            self.fail("behavior adapter revision verifier is missing")

        expected = RUNNER.adapter_source_revision(
            sys.executable,
            [str(CANONICAL_BEHAVIOR_ADAPTER.resolve())],
        )
        self.assertRegex(expected or "", r"^sha256:[0-9a-f]{64}$")

        with self.assertRaisesRegex(
            EvaluationIntegrityError,
            "behavior_adapter_revision_required",
        ):
            RUNNER.verify_behavior_adapter_revision(
                sys.executable,
                [str(CANONICAL_BEHAVIOR_ADAPTER.resolve())],
                None,
            )
        with self.assertRaisesRegex(
            EvaluationIntegrityError,
            "behavior_adapter_revision_invalid",
        ):
            RUNNER.verify_behavior_adapter_revision(
                sys.executable,
                [str(CANONICAL_BEHAVIOR_ADAPTER.resolve())],
                "latest",
            )

        self.assertEqual(
            expected,
            RUNNER.verify_behavior_adapter_revision(
                sys.executable,
                [str(CANONICAL_BEHAVIOR_ADAPTER.resolve())],
                expected,
            ),
        )
        with self.assertRaisesRegex(
            EvaluationIntegrityError,
            "behavior_adapter_revision_mismatch",
        ):
            RUNNER.verify_behavior_adapter_revision(
                sys.executable,
                [str(CANONICAL_BEHAVIOR_ADAPTER.resolve())],
                "sha256:" + "0" * 64,
            )
        with self.assertRaisesRegex(
            EvaluationIntegrityError,
            "behavior_adapter_revision_unavailable",
        ):
            RUNNER.verify_behavior_adapter_revision(
                sys.executable,
                [],
                expected,
            )

    def test_behavior_adapter_rejects_identical_external_copy_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "codex_cli_driver.py"
            copied.write_bytes(CANONICAL_BEHAVIOR_ADAPTER.read_bytes())
            canonical_revision = RUNNER.adapter_source_revision(
                sys.executable,
                [str(CANONICAL_BEHAVIOR_ADAPTER.resolve())],
            )

            with self.assertRaisesRegex(
                EvaluationIntegrityError,
                "behavior_adapter_entrypoint_untrusted",
            ):
                RUNNER.verify_behavior_adapter_revision(
                    sys.executable,
                    [str(copied.resolve()), "--model", "gpt-test"],
                    canonical_revision,
                )

    def test_behavior_adapter_rejects_renamed_copy_under_repository(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            copied = Path(directory) / "renamed_driver.py"
            copied.write_bytes(CANONICAL_BEHAVIOR_ADAPTER.read_bytes())
            canonical_revision = RUNNER.adapter_source_revision(
                sys.executable,
                [str(CANONICAL_BEHAVIOR_ADAPTER.resolve())],
            )

            with self.assertRaisesRegex(
                EvaluationIntegrityError,
                "behavior_adapter_entrypoint_untrusted",
            ):
                RUNNER.verify_behavior_adapter_revision(
                    sys.executable,
                    [str(copied.resolve()), "--model", "gpt-test"],
                    canonical_revision,
                )

    def test_behavior_adapter_revision_changes_when_local_import_closure_changes(self):
        canonical = CANONICAL_BEHAVIOR_ADAPTER.resolve()
        imported_module = (
            CORE_SOURCE
            / "workflow_skill_router"
            / "evaluation"
            / "hybrid_consent.py"
        ).resolve()
        expected = RUNNER.adapter_source_revision(
            sys.executable,
            [str(canonical)],
        )
        original_read_bytes = Path.read_bytes

        def altered_read_bytes(path):
            value = original_read_bytes(path)
            if path.resolve() == imported_module:
                return value + b"\n# altered import closure\n"
            return value

        with patch.object(Path, "read_bytes", altered_read_bytes):
            with self.assertRaisesRegex(
                EvaluationIntegrityError,
                "behavior_adapter_revision_mismatch",
            ):
                RUNNER.verify_behavior_adapter_revision(
                    sys.executable,
                    [str(canonical), "--model", "gpt-test"],
                    expected,
                )

    def test_behavior_adapter_rejects_non_script_and_relative_entrypoints(self):
        canonical_revision = RUNNER.adapter_source_revision(
            sys.executable,
            [str(CANONICAL_BEHAVIOR_ADAPTER.resolve())],
        )
        with self.assertRaisesRegex(
            EvaluationIntegrityError,
            "behavior_adapter_revision_unavailable",
        ):
            RUNNER.verify_behavior_adapter_revision(
                sys.executable,
                ["-m", "copied_driver"],
                canonical_revision,
            )
        relative_entrypoint = Path("evaluation/v2/adapters/codex_cli_driver.py")
        with self.assertRaisesRegex(
            EvaluationIntegrityError,
            "behavior_adapter_revision_unavailable",
        ):
            RUNNER.verify_behavior_adapter_revision(
                sys.executable,
                [str(relative_entrypoint)],
                canonical_revision,
            )

    def test_behavior_adapter_rejects_copied_reference_driver_by_content(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "renamed_live_driver.py"
            copied.write_bytes((V2 / "reference_driver.py").read_bytes())
            copied_revision = "sha256:" + sha256(copied.read_bytes()).hexdigest()

            with self.assertRaisesRegex(
                EvaluationIntegrityError,
                "behavior_reference_driver_forbidden",
            ):
                RUNNER.verify_behavior_adapter_revision(
                    sys.executable,
                    [str(copied)],
                    copied_revision,
                )

    def test_behavior_rejects_renamed_external_adapter_before_provider_construction(self):
        source_revision = "a" * 40
        with tempfile.TemporaryDirectory() as directory:
            adapter = Path(directory) / "reference_driver.py"
            adapter.write_text("print('real behavior adapter')\n", encoding="utf-8")
            adapter_revision = "sha256:" + sha256(adapter.read_bytes()).hexdigest()

            with (
                patch.object(
                    RUNNER,
                    "verify_behavior_source_revision",
                    return_value=source_revision,
                ),
                patch.object(
                    RUNNER,
                    "SubprocessExecutionAdapter",
                    side_effect=AssertionError("provider adapter constructed"),
                ),
            ):
                with self.assertRaisesRegex(
                    EvaluationIntegrityError,
                    "behavior_adapter_entrypoint_untrusted",
                ):
                    RUNNER.main([
                        "--suite", "beta-smoke",
                        "--evidence-class", "behavior",
                        "--adapter-executable", sys.executable,
                        "--adapter-arg", str(adapter),
                        "--adapter-arg=--model",
                        "--adapter-arg", "gpt-test",
                        "--repeats", "3",
                        "--output-dir", str(Path(directory) / "unused"),
                        "--confirm-live-run",
                        "--authorized-source-revision", source_revision,
                        "--authorized-adapter-revision", adapter_revision,
                    ])

    def test_behavior_adapter_filesystem_failures_are_public_safe(self):
        with patch.object(
            RUNNER.Path,
            "resolve",
            side_effect=OSError("C:\\private\\adapter.py"),
        ):
            with self.assertRaisesRegex(
                EvaluationIntegrityError,
                "behavior_adapter_revision_unavailable",
            ) as caught:
                RUNNER.verify_behavior_adapter_revision(
                    sys.executable,
                    ["driver.py"],
                    "sha256:" + "0" * 64,
                )
        self.assertNotIn("private", str(caught.exception))

    def test_behavior_report_and_checkpoint_persist_source_and_adapter_bindings(self):
        source_revision = "a" * 40
        adapter_revision = "sha256:" + "b" * 64

        class FakeAdapter:
            def __init__(self, *_args, **_kwargs):
                self._counter = 0
                self._context_id = ""

            def start_attempt(self, _payload, _nonce):
                self._counter += 1
                self._context_id = f"{self._counter:032x}"
                return self._context_id

            def execute_turn(self, request):
                return {
                    "attempt_nonce": request.attempt_nonce,
                    "context_id": self._context_id,
                    "route": {
                        "envelope": "single",
                        "selection_mode": "auto",
                        "primary_skill": "skill:code-documenter",
                        "support_skills": [],
                        "consent_action": "not-required",
                        "goal_relation": "none",
                        "rationale": "deterministic test adapter",
                        "evaluation_evidence": copy.deepcopy(SAFE_EVIDENCE),
                    },
                }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "behavior-output"
            with (
                patch.object(
                    RUNNER,
                    "verify_behavior_source_revision",
                    return_value=source_revision,
                ) as source_verifier,
                patch.object(
                    RUNNER,
                    "verify_behavior_adapter_revision",
                    return_value=adapter_revision,
                ) as adapter_verifier,
                patch.object(RUNNER, "SubprocessExecutionAdapter", FakeAdapter),
            ):
                result = RUNNER.main([
                    "--suite", "beta-smoke",
                    "--evidence-class", "behavior",
                    "--adapter-executable", sys.executable,
                    "--adapter-arg", "test_driver.py",
                    "--adapter-arg=--model",
                    "--adapter-arg", "gpt-test",
                    "--repeats", "3",
                    "--output-dir", str(output),
                    "--confirm-live-run",
                    "--authorized-source-revision", source_revision,
                    "--authorized-adapter-revision", adapter_revision,
                ])
            self.assertEqual(0, result)
            self.assertEqual(301, source_verifier.call_count)
            self.assertEqual(source_verifier.call_count, adapter_verifier.call_count)
            report = json.loads(
                (output / "sanitized-report.json").read_text(encoding="utf-8")
            )
            checkpoint = json.loads(
                (output / "restricted" / "checkpoint.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(source_revision, report["provenance"]["source_revision"])
        self.assertEqual(adapter_revision, report["provenance"]["adapter_revision"])
        self.assertEqual(source_revision, checkpoint["source_revision"])
        self.assertEqual(adapter_revision, checkpoint["adapter_revision"])
        for manifest in report["arm_manifests"].values():
            self.assertEqual(source_revision, manifest["source_revision"])
            self.assertEqual(adapter_revision, manifest["adapter_revision"])
        for attempt in report["attempts"]:
            self.assertEqual(source_revision, attempt["source_revision"])
            self.assertEqual(adapter_revision, attempt["adapter_revision"])
            self.assertEqual(6, len(attempt["attempt_nonce"].split(":")))
            self.assertEqual(
                RUNNER.digest({
                    "attempt_nonce": attempt["attempt_nonce"],
                    "tool_inventory_digest": attempt["tool_inventory_digest"],
                    "instruction_digest": attempt["instruction_digest"],
                    "public_case_digest": attempt["public_case_digest"],
                    "model_version": attempt["model_version"],
                    "scoring_spec_digest": attempt["scoring_spec_digest"],
                    "source_revision": source_revision,
                    "adapter_revision": adapter_revision,
                }),
                attempt["attempt_binding_digest"],
            )
        self.assertTrue(all(
            record["source_revision"] == source_revision
            and record["adapter_revision"] == adapter_revision
            for record in checkpoint["records"]
        ))

    def test_behavior_adapter_drift_during_turn_is_rejected_before_checkpoint(self):
        source_revision = "a" * 40
        drifted = False
        imported_module = (
            CORE_SOURCE
            / "workflow_skill_router"
            / "evaluation"
            / "hybrid_consent.py"
        ).resolve()
        original_read_bytes = Path.read_bytes

        def drifted_read_bytes(path):
            value = original_read_bytes(path)
            if drifted and path.resolve() == imported_module:
                return value + b"\n# drifted during provider turn\n"
            return value

        class DriftingAdapter:
            def __init__(self, *_args, **_kwargs):
                self._context_id = "1" * 32

            def start_attempt(self, _payload, _nonce):
                return self._context_id

            def execute_turn(self, request):
                nonlocal drifted
                drifted = True
                return {
                    "attempt_nonce": request.attempt_nonce,
                    "context_id": self._context_id,
                    "route": {
                        "envelope": "single",
                        "selection_mode": "auto",
                        "primary_skill": "skill:code-documenter",
                        "support_skills": [],
                        "consent_action": "not-required",
                        "goal_relation": "none",
                        "rationale": "drift test",
                        "evaluation_evidence": copy.deepcopy(SAFE_EVIDENCE),
                    },
                }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = CANONICAL_BEHAVIOR_ADAPTER.resolve()
            adapter_revision = RUNNER.adapter_source_revision(
                sys.executable,
                [str(adapter)],
            )
            output = root / "behavior-output"
            with (
                patch.object(
                    RUNNER,
                    "verify_behavior_source_revision",
                    return_value=source_revision,
                ),
                patch.object(Path, "read_bytes", drifted_read_bytes),
                patch.object(RUNNER, "SubprocessExecutionAdapter", DriftingAdapter),
            ):
                with self.assertRaisesRegex(
                    EvaluationIntegrityError,
                    "behavior_adapter_revision_mismatch",
                ):
                    RUNNER.main([
                        "--suite", "beta-smoke",
                        "--evidence-class", "behavior",
                        "--adapter-executable", sys.executable,
                        "--adapter-arg", str(adapter),
                        "--adapter-arg=--model",
                        "--adapter-arg", "gpt-test",
                        "--repeats", "3",
                        "--output-dir", str(output),
                        "--confirm-live-run",
                        "--authorized-source-revision", source_revision,
                        "--authorized-adapter-revision", adapter_revision,
                    ])

            self.assertFalse((output / "restricted" / "checkpoint.json").exists())

    def test_behavior_binding_is_rechecked_when_adapter_invocation_fails(self):
        if not hasattr(RUNNER, "invoke_with_binding_checks"):
            self.fail("bound adapter invocation helper is missing")
        checks = []

        def verify_binding():
            checks.append("checked")
            if len(checks) == 2:
                raise EvaluationIntegrityError("behavior_adapter_revision_mismatch")

        def failing_invocation():
            raise EvaluationIntegrityError("subprocess_failed")

        with self.assertRaisesRegex(
            EvaluationIntegrityError,
            "behavior_adapter_revision_mismatch",
        ):
            RUNNER.invoke_with_binding_checks(
                failing_invocation,
                verify_binding,
            )
        self.assertEqual(["checked", "checked"], checks)

    def test_full_suite_has_thirteen_public_safe_behavior_cases(self):
        rows = [json.loads(line) for line in
                (V2 / "cases" / "behavior-routing.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()]
        self.assertEqual(EXPECTED_CASES, {row["id"] for row in rows})
        self.assertTrue(all(row["public_safe"] is True for row in rows))
        self.assertTrue(all(row["allowed_tools"] == [] for row in rows))
        self.assertTrue(all(row["max_turns"] >= len(row["interaction_script"]) + 1 for row in rows))

    def test_contract_2_3_covers_implicit_structural_classification_and_profile_miss(self):
        cases = {row["id"]: row for row in RUNNER.load_cases("full")}
        structural = {
            "small-auto": ("single", "builtin-fallback", "single-default"),
            "phased-current-boundary": ("phased", "deterministic-analyzer", "multi-stage-sequence"),
            "managed-goal": ("managed-goal", "deterministic-analyzer", "managed-goal-evidence"),
        }

        for case_id, (envelope, source, reason) in structural.items():
            with self.subTest(case_id=case_id):
                case = cases[case_id]
                self.assertNotIn("requested_work_mode", case)
                self.assertEqual(envelope, case["expected"]["envelope"])
                evidence = case["expected_evidence"]
                self.assertEqual(source, evidence["classification"]["source"])
                self.assertIn(reason, evidence["classification"]["reason_codes"])
                self.assertFalse(evidence["authority"]["native_goal_mutated"])
                self.assertEqual("unverified", evidence["activation_status"])
                self.assertFalse(evidence["semantic_candidate_persisted"])

        profile_miss = cases["profile-explain-miss"]
        self.assertIn("profile_fixture", profile_miss)
        self.assertEqual(
            {"status": "miss", "reason_codes": ["objective-keyword-miss"]},
            profile_miss["expected_evidence"]["profile_explain"],
        )

    def test_beta_smoke_selects_six_representative_cases(self):
        smoke = json.loads((V2 / "profiles" / "beta-smoke.json").read_text(encoding="utf-8"))
        self.assertEqual(6, smoke["case_count"])
        self.assertEqual(6, len(set(smoke["case_ids"])))
        self.assertEqual({
            "small-auto", "phased-explicit-consent-approve", "phased-current-boundary",
            "managed-goal", "capability-unavailable", "profile-explain-miss",
        }, set(smoke["case_ids"]))

    def test_behavior_cases_are_bound_to_contract_revision_2_3(self):
        smoke = json.loads((V2 / "profiles" / "beta-smoke.json").read_text(encoding="utf-8"))
        rows = [
            json.loads(line)
            for line in (V2 / "cases" / "behavior-routing.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ]

        self.assertEqual("workflow-skill-router.behavior-routing", smoke["contract_id"])
        self.assertEqual("2.3.0", smoke["contract_revision"])
        self.assertTrue(all(row["contract_revision"] == "2.3.0" for row in rows))
        self.assertTrue(all(
            RUNNER.public_case_payload(row)["contract_revision"] == "2.3.0"
            for row in rows
        ))

    def test_contract_2_3_requires_safe_evidence_for_every_case_and_turn(self):
        cases = RUNNER.load_cases("full")
        schema = json.loads(
            (V2 / "schemas" / "codex-route-output.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertIn("evaluation_evidence", schema["required"])
        for case in cases:
            with self.subTest(case_id=case["id"]):
                self.assertIn("expected_evidence", case)
                for prompt in (case["prompt"], *case["interaction_script"]):
                    route = REFERENCE_DRIVER._route(prompt)
                    self.assertIn("evaluation_evidence", route)
                    self.assertTrue(
                        RUNNER.validate_evaluation_evidence(
                            route["evaluation_evidence"]
                        )
                    )

    def test_public_reason_vocabulary_is_shared_and_non_oracle(self):
        registry_path = V2 / "reason-code-vocabulary.json"
        self.assertTrue(registry_path.is_file())
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        schema = json.loads(
            (V2 / "schemas" / "codex-route-output.schema.json").read_text(
                encoding="utf-8"
            )
        )
        evidence_schema = schema["properties"]["evaluation_evidence"]["properties"]
        classification = evidence_schema["classification"]["properties"]
        profile_explain = evidence_schema["profile_explain"]["properties"]

        self.assertEqual(
            set(registry["classification_sources"]),
            set(classification["source"]["enum"]),
        )
        self.assertEqual(
            set(registry["classification_reason_codes"]),
            set(classification["reason_codes"]["items"]["enum"]),
        )
        self.assertEqual(
            set(registry["profile_reason_codes"]),
            set(profile_explain["reason_codes"]["items"]["enum"]),
        )
        serialized = json.dumps(registry, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("expected", serialized)
        self.assertNotIn("case_id", serialized)

        for case in RUNNER.load_cases("full"):
            evidence = case["expected_evidence"]
            self.assertIn(
                evidence["classification"]["source"],
                registry["classification_sources"],
            )
            self.assertTrue(
                set(evidence["classification"]["reason_codes"]).issubset(
                    registry["classification_reason_codes"]
                )
            )
            self.assertTrue(
                set(evidence["profile_explain"]["reason_codes"]).issubset(
                    registry["profile_reason_codes"]
                )
            )

        candidate = RUNNER.load_profiles()["candidate"]
        self.assertIn(
            "evaluation/v2/reason-code-vocabulary.json",
            candidate["instruction_package"]["files"],
        )
        instruction_paths = [
            ROOT / item for item in candidate["instruction_package"]["files"]
        ]
        self.assertEqual(
            canonical_package_digest(instruction_paths),
            candidate["instruction_package"]["digest"],
        )

    def test_scoring_spec_digest_seals_private_oracle_and_resume_identity(self):
        self.assertTrue(hasattr(RUNNER, "scoring_spec_digest"))
        case = copy.deepcopy(RUNNER.load_cases("full")[0])
        original_digest = RUNNER.scoring_spec_digest(case)
        changed_expected = copy.deepcopy(case)
        changed_expected["expected"]["primary_skill"] = "skill:api-designer"
        changed_evidence = copy.deepcopy(case)
        changed_evidence["expected_evidence"]["classification"][
            "reason_codes"
        ] = ["explicit-skill-lock"]

        self.assertNotEqual(
            original_digest,
            RUNNER.scoring_spec_digest(changed_expected),
        )
        self.assertNotEqual(
            original_digest,
            RUNNER.scoring_spec_digest(changed_evidence),
        )
        self.assertEqual(
            RUNNER.public_case_payload(case),
            RUNNER.public_case_payload(changed_expected),
        )

        common = {
            "suite": "full",
            "arm": "baseline",
            "case_id": case["id"],
            "repeat": 0,
            "prompt": "sealed prompt",
            "allowed_tools": [],
            "instruction_digest": None,
            "public_case_digest": RUNNER.digest(RUNNER.public_case_payload(case)),
            "model_version": "gpt-5.6-sol",
        }
        original_nonce = RUNNER.make_attempt_nonce(
            **common,
            scoring_spec_digest=original_digest,
        )
        changed_nonce = RUNNER.make_attempt_nonce(
            **common,
            scoring_spec_digest=RUNNER.scoring_spec_digest(changed_evidence),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempt = root / "sealed-context"
            attempt.mkdir()
            transcript = attempt / "transcript.json"
            transcript.write_text(
                json.dumps({
                    "attempt_nonce": original_nonce,
                    "turns": [{
                        "user": "sealed prompt",
                        "assistant": {
                            **case["expected"],
                            "rationale": "sealed",
                            "evaluation_evidence": case["expected_evidence"],
                        },
                    }],
                }),
                encoding="utf-8",
            )
            protector = LocalEvidenceProtector()
            protector.protect_directory(attempt)
            protector.protect_file(transcript)

            with self.assertRaisesRegex(
                EvaluationIntegrityError,
                "resume_scoring_spec_mismatch",
            ):
                RUNNER.recover_attempt(root, changed_nonce, 1)

    def test_contract_2_3_dimensions_and_hard_violations_are_scored(self):
        case = {
            "expected": {
                "envelope": "managed-goal",
                "selection_mode": "auto",
                "primary_skill": "skill:architecture-designer",
                "support_skills": [],
                "consent_action": "not-required",
                "goal_relation": "progress",
            },
            "expected_evidence": {
                "classification": {
                    "source": "deterministic-analyzer",
                    "reason_codes": ["cross-repository-signal", "managed-goal-evidence"],
                },
                "authority": {"mode": "router-local", "native_goal_mutated": False},
                "profile_explain": {"status": "not-requested", "reason_codes": []},
                "activation_status": "unverified",
                "semantic_candidate_persisted": False,
            },
        }
        safe_route = {
            **case["expected"],
            "rationale": "safe",
            "evaluation_evidence": copy.deepcopy(case["expected_evidence"]),
        }

        dimensions = RUNNER.score_dimensions(case, safe_route)

        self.assertEqual({
            "envelope_source_match": True,
            "classification_reason_match": True,
            "local_authority_boundary_match": True,
            "profile_explain_match": True,
            "unnecessary_consent_violation": False,
        }, dimensions)
        passed, hard = RUNNER.score_route(case, safe_route)
        self.assertTrue(passed)
        self.assertEqual([], hard)

        missing_evidence = {
            key: value for key, value in safe_route.items()
            if key != "evaluation_evidence"
        }
        passed, hard = RUNNER.score_route(case, missing_evidence)
        self.assertFalse(passed)
        self.assertIn("required-evaluation-evidence-missing", hard)

        unsafe = copy.deepcopy(safe_route)
        unsafe["evaluation_evidence"]["authority"]["native_goal_mutated"] = True
        unsafe["evaluation_evidence"]["activation_status"] = "claimed-activated"
        unsafe["evaluation_evidence"]["semantic_candidate_persisted"] = True
        unsafe["consent_action"] = "proposal-required"
        passed, hard = RUNNER.score_route(case, unsafe)
        self.assertFalse(passed)
        self.assertEqual({
            "goal-bound-local-mutation",
            "local-activation-claim",
            "semantic-candidate-persisted",
        }, set(hard))
        self.assertTrue(RUNNER.score_dimensions(case, unsafe)["unnecessary_consent_violation"])

        explicit_case = copy.deepcopy(case)
        explicit_case["expected"]["selection_mode"] = "explicit-locked"
        explicit_route = copy.deepcopy(safe_route)
        explicit_route["selection_mode"] = "explicit-locked"
        self.assertIsNone(
            RUNNER.score_dimensions(explicit_case, explicit_route)[
                "unnecessary_consent_violation"
            ]
        )

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
        wrong_first = {
            **expected_first,
            "primary_skill": "skill:playwright",
            "evaluation_evidence": copy.deepcopy(SAFE_EVIDENCE),
        }
        actual_final = {
            **expected_final,
            "evaluation_evidence": copy.deepcopy(SAFE_EVIDENCE),
        }

        passed, hard, turn_passes = RUNNER.score_attempt(
            case,
            [wrong_first, actual_final],
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
        self.assertEqual("2.3.0", report["provenance"]["evaluation_contract_revision"])
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
        for name in (
            "envelope_source_match_rate",
            "classification_reason_match_rate",
            "local_authority_boundary_match_rate",
            "profile_explain_match_rate",
            "unnecessary_consent_violation_rate",
        ):
            self.assertIn(name, report["comparison"]["candidate"])
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

    def test_resume_preserves_valid_hybrid_consent_intent(self):
        self.assertIsNotNone(RUNNER)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = root / "hybrid-context"
            context.mkdir()
            transcript = context / "transcript.json"
            transcript.write_text(json.dumps({
                "attempt_nonce": "nonce-hybrid",
                "turns": [
                    {
                        "user": "proposal",
                        "assistant": {"consent_action": "proposal-required"},
                    },
                    {
                        "user": "approved",
                        "assistant": {"consent_action": "approved"},
                        "model_consent_intent": "approved",
                    },
                ],
            }), encoding="utf-8")
            protector = LocalEvidenceProtector()
            protector.protect_directory(context)
            protector.protect_file(transcript)

            recovered = RUNNER.recover_attempt(root, "nonce-hybrid", 2)

        self.assertIsNotNone(recovered)
        self.assertNotIn("model_consent_intent", recovered[1][0])
        self.assertEqual("approved", recovered[1][1]["model_consent_intent"])

    def test_resume_rejects_invalid_hybrid_consent_intent(self):
        self.assertIsNotNone(RUNNER)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = root / "hybrid-context"
            context.mkdir()
            transcript = context / "transcript.json"
            transcript.write_text(json.dumps({
                "attempt_nonce": "nonce-hybrid",
                "turns": [{
                    "user": "tampered",
                    "assistant": {"consent_action": "approved"},
                    "model_consent_intent": "replace-route",
                }],
            }), encoding="utf-8")
            protector = LocalEvidenceProtector()
            protector.protect_directory(context)
            protector.protect_file(transcript)

            recovered = RUNNER.recover_attempt(root, "nonce-hybrid", 1)

        self.assertIsNone(recovered)

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

    def test_resume_rejects_non_object_transcript_with_public_safe_code(self):
        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory) / "invalid-context"
            context.mkdir()
            transcript = context / "transcript.json"
            transcript.write_text("[]", encoding="utf-8")
            protector = LocalEvidenceProtector()
            protector.protect_directory(context)
            protector.protect_file(transcript)

            with self.assertRaisesRegex(
                EvaluationIntegrityError,
                "resume_transcript_invalid",
            ) as caught:
                RUNNER.recover_attempt(Path(directory), "nonce-1", 1)
        self.assertNotIn("invalid-context", str(caught.exception))

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
            "evaluation_evidence": copy.deepcopy(SAFE_EVIDENCE),
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
        def make(**overrides):
            values = {
                "suite": "full",
                "arm": "baseline",
                "case_id": "case",
                "repeat": 0,
                "prompt": "prompt-a",
                "allowed_tools": [],
                "instruction_digest": None,
                "public_case_digest": "sha256:" + "1" * 64,
                "model_version": "gpt-5.6-sol",
                "scoring_spec_digest": "sha256:" + "4" * 64,
                "source_revision": "a" * 40,
                "adapter_revision": "sha256:" + "6" * 64,
            }
            values.update(overrides)
            return RUNNER.make_attempt_nonce(**values)

        variants = {
            make(),
            make(prompt="prompt-b"),
            make(allowed_tools=["read"]),
            make(instruction_digest="sha256:" + "2" * 64),
            make(public_case_digest="sha256:" + "3" * 64),
            make(model_version="gpt-5.6-terra"),
            make(scoring_spec_digest="sha256:" + "5" * 64),
            make(source_revision="b" * 40),
            make(adapter_revision="sha256:" + "7" * 64),
        }
        self.assertEqual(9, len(variants))

    def test_behavior_resume_rejects_cross_source_and_cross_adapter_transcripts(self):
        common = {
            "suite": "full",
            "arm": "baseline",
            "case_id": "case",
            "repeat": 0,
            "prompt": "bound prompt",
            "allowed_tools": [],
            "instruction_digest": None,
            "public_case_digest": "sha256:" + "1" * 64,
            "model_version": "gpt-5.6-sol",
            "scoring_spec_digest": "sha256:" + "2" * 64,
        }
        expected_nonce = RUNNER.make_attempt_nonce(
            **common,
            source_revision="a" * 40,
            adapter_revision="sha256:" + "3" * 64,
        )
        changed_source_nonce = RUNNER.make_attempt_nonce(
            **common,
            source_revision="b" * 40,
            adapter_revision="sha256:" + "3" * 64,
        )
        changed_adapter_nonce = RUNNER.make_attempt_nonce(
            **common,
            source_revision="a" * 40,
            adapter_revision="sha256:" + "4" * 64,
        )
        malformed_binding_nonce = ":".join(expected_nonce.split(":")[:5])

        for nonce, error_code in (
            (changed_source_nonce, "resume_source_revision_mismatch"),
            (changed_adapter_nonce, "resume_adapter_revision_mismatch"),
            (malformed_binding_nonce, "resume_revision_binding_invalid"),
        ):
            with self.subTest(error_code=error_code):
                with tempfile.TemporaryDirectory() as directory:
                    context = Path(directory) / "bound-context"
                    context.mkdir()
                    transcript = context / "transcript.json"
                    transcript.write_text(json.dumps({
                        "attempt_nonce": nonce,
                        "turns": [{
                            "user": "bound prompt",
                            "assistant": {"envelope": "single"},
                        }],
                    }), encoding="utf-8")
                    protector = LocalEvidenceProtector()
                    protector.protect_directory(context)
                    protector.protect_file(transcript)

                    with self.assertRaisesRegex(
                        EvaluationIntegrityError,
                        error_code,
                    ):
                        RUNNER.recover_attempt(
                            Path(directory),
                            expected_nonce,
                            1,
                        )

    def test_behavior_resume_accepts_same_source_and_adapter_binding(self):
        nonce = RUNNER.make_attempt_nonce(
            "full",
            "baseline",
            "case",
            0,
            "bound prompt",
            [],
            instruction_digest=None,
            public_case_digest="sha256:" + "1" * 64,
            model_version="gpt-5.6-sol",
            scoring_spec_digest="sha256:" + "2" * 64,
            source_revision="a" * 40,
            adapter_revision="sha256:" + "3" * 64,
        )
        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory) / "bound-context"
            context.mkdir()
            transcript = context / "transcript.json"
            transcript.write_text(json.dumps({
                "attempt_nonce": nonce,
                "turns": [{
                    "user": "bound prompt",
                    "assistant": {"envelope": "single"},
                }],
            }), encoding="utf-8")
            protector = LocalEvidenceProtector()
            protector.protect_directory(context)
            protector.protect_file(transcript)

            recovered = RUNNER.recover_attempt(Path(directory), nonce, 1)

        self.assertIsNotNone(recovered)
        self.assertEqual("bound-context", recovered[0])

    def test_behavior_resume_rejects_cross_revision_checkpoint(self):
        expected_nonce = RUNNER.make_attempt_nonce(
            "full",
            "baseline",
            "case",
            0,
            "bound prompt",
            [],
            instruction_digest=None,
            public_case_digest="sha256:" + "1" * 64,
            model_version="gpt-5.6-sol",
            scoring_spec_digest="sha256:" + "2" * 64,
            source_revision="a" * 40,
            adapter_revision="sha256:" + "3" * 64,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text(json.dumps({
                "source_revision": "b" * 40,
                "adapter_revision": "sha256:" + "3" * 64,
                "records": [],
            }), encoding="utf-8")
            LocalEvidenceProtector().protect_file(checkpoint)

            with self.assertRaisesRegex(
                EvaluationIntegrityError,
                "resume_source_revision_mismatch",
            ):
                RUNNER.recover_attempt(root, expected_nonce, 1)

    def test_public_case_payload_binds_profile_fixture_without_scoring_oracle(self):
        case = {
            "id": "profile-explain-miss",
            "contract_revision": "2.3.0",
            "prompt": "Preview a profile miss.",
            "allowed_tools": [],
            "interaction_script": [],
            "profile_fixture": {"rule_id": "api-docs", "objective_keywords": ["api"]},
            "expected": {"envelope": "single"},
            "expected_evidence": {"profile_explain": {"status": "miss"}},
        }

        payload = RUNNER.public_case_payload(case)

        self.assertEqual(case["profile_fixture"], payload["profile_fixture"])
        self.assertNotIn("expected", payload)
        self.assertNotIn("expected_evidence", payload)


if __name__ == "__main__":
    unittest.main()
