from __future__ import annotations

import copy
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


DRIVER_PATH = ROOT / "evaluation" / "v2" / "adapters" / "codex_cli_driver.py"
SPEC = importlib.util.spec_from_file_location("codex_cli_driver", DRIVER_PATH)
DRIVER_MODULE = importlib.util.module_from_spec(SPEC) if SPEC else None
if SPEC and SPEC.loader and DRIVER_MODULE:
    SPEC.loader.exec_module(DRIVER_MODULE)


VALID_ROUTE = {
    "envelope": "single",
    "selection_mode": "auto",
    "primary_skill": "skill:code-documenter",
    "support_skills": [],
    "consent_action": "not-required",
    "goal_relation": "none",
    "rationale": "One documentation task needs one primary skill.",
    "evaluation_evidence": {
        "classification": {
            "source": "deterministic-analyzer",
            "reason_codes": ["single-default"],
        },
        "authority": {"mode": "router-local", "native_goal_mutated": False},
        "profile_explain": {"status": "not-requested", "reason_codes": []},
        "activation_status": "unverified",
        "semantic_candidate_persisted": False,
    },
}


def completed(route=VALID_ROUTE, *, returncode=0, stderr=""):
    event = {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": json.dumps(route)},
    }
    return subprocess.CompletedProcess([], returncode, json.dumps(event) + "\n", stderr)


@unittest.skipIf(DRIVER_MODULE is None, "driver module could not be loaded")
class CodexCliDriverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.executable = (self.root / "codex.exe").resolve()
        self.schema = (ROOT / "evaluation" / "v2" / "schemas" / "codex-route-output.schema.json").resolve()
        self.auth = (self.root / "auth.json").resolve()
        self.auth.write_text("{}", encoding="utf-8")
        self.driver = DRIVER_MODULE.CodexCliDriver(
            self.executable,
            self.schema,
            (self.root / "attempts").resolve(),
            timeout_seconds=17,
            auth_source=self.auth,
            model="gpt-5.6-sol",
        )

    def start(self, nonce="nonce-1", execution_mode="model-only"):
        return self.driver.handle({
            "type": "start_attempt",
            "opaque_run_case_id": "opaque-case",
            "prompt": "Initial task",
            "profile": "behavior",
            "allowed_tools": [],
            "execution_mode": execution_mode,
            "attempt_nonce": nonce,
        })

    def test_invokes_resolved_codex_with_separate_safe_argv_and_minimum_environment(self):
        context = self.start()
        with patch.dict(os.environ, {"WORKFLOW_ROUTER_TEST_SECRET": "must-not-leak"}), \
             patch.object(DRIVER_MODULE.subprocess, "run", return_value=completed()) as run:
            response = self.driver.handle({
                "type": "execute_turn", "context_id": context["context_id"],
                "attempt_nonce": "nonce-1", "turn_index": 0,
                "prompt": "Route this task", "allowed_tools": [],
            })

        argv = run.call_args.args[0]
        self.assertEqual([
            str(self.executable), "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--strict-config", "--disable", "plugins", "-c", "skills.bundled.enabled=false",
            "--sandbox", "read-only", "--skip-git-repo-check", "--cd",
            str(Path(run.call_args.kwargs["cwd"])), "--model", "gpt-5.6-sol", "--output-schema",
            str(self.schema), "--json", "-",
        ], argv)
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertEqual(17, run.call_args.kwargs["timeout"])
        self.assertEqual("workspace", Path(run.call_args.kwargs["cwd"]).name)
        self.assertEqual([], list(Path(run.call_args.kwargs["cwd"]).iterdir()))
        self.assertNotIn("WORKFLOW_ROUTER_TEST_SECRET", run.call_args.kwargs["env"])
        self.assertNotEqual(str(Path.home() / ".codex"), run.call_args.kwargs["env"]["CODEX_HOME"])
        self.assertFalse((Path(run.call_args.kwargs["env"]["CODEX_HOME"]) / "auth.json").exists())
        self.assertEqual("nonce-1", response["attempt_nonce"])
        self.assertEqual(VALID_ROUTE, response["route"])

    def test_creates_fresh_restricted_attempt_directories(self):
        first = self.start("nonce-1")
        second = self.start("nonce-2")
        self.assertNotEqual(first["context_id"], second["context_id"])
        directories = [path for path in (self.root / "attempts").iterdir() if path.is_dir()]
        self.assertEqual(2, len(directories))
        self.assertTrue(all((path / "transcript.json").is_file() for path in directories))
        protector = LocalEvidenceProtector()
        self.assertTrue(protector.verify_directory(self.root / "attempts"))
        for path in directories:
            self.assertTrue(protector.verify_directory(path))
            self.assertTrue(protector.verify_directory(path / "workspace"))
            self.assertTrue(protector.verify_directory(path / "runtime-home"))
            self.assertTrue(protector.verify_directory(path / "codex-home"))
            self.assertTrue(protector.verify_file(path / "transcript.json"))

    def test_start_rejects_scoring_or_expected_oracle_material(self):
        for forbidden in (
            "expected",
            "expected_turns",
            "expected_evidence",
            "expected_evidence_turns",
            "scoring",
            "scoring_key",
        ):
            with self.subTest(forbidden=forbidden):
                request = {
                    "type": "start_attempt",
                    "opaque_run_case_id": "opaque-case",
                    "prompt": "Initial task",
                    "profile": "behavior",
                    "allowed_tools": [],
                    "execution_mode": "model-only",
                    "attempt_nonce": "nonce-oracle",
                    forbidden: {"secret": True},
                }
                with self.assertRaisesRegex(
                    EvaluationIntegrityError,
                    "codex_driver_oracle_material_forbidden",
                ):
                    self.driver.handle(request)

    def test_reconstructs_prior_turns_in_order_without_future_replies_or_scoring_data(self):
        context = self.start()
        with patch.object(DRIVER_MODULE.subprocess, "run", side_effect=[completed(), completed()]) as run:
            self.driver.handle({
                "type": "execute_turn", "context_id": context["context_id"],
                "attempt_nonce": "nonce-1", "turn_index": 0,
                "prompt": "First", "allowed_tools": [],
            })
            self.driver.handle({
                "type": "execute_turn", "context_id": context["context_id"],
                "attempt_nonce": "nonce-1", "turn_index": 1,
                "prompt": "Consent approved", "allowed_tools": [],
            })

        first_input = run.call_args_list[0].kwargs["input"]
        second_input = run.call_args_list[1].kwargs["input"]
        self.assertNotIn("Consent approved", first_input)
        self.assertLess(second_input.index("First"), second_input.index("Consent approved"))
        for forbidden in ("expected", "scoring", "scenario_label", "future_reply"):
            self.assertNotIn(forbidden, second_input.lower())

    def test_hybrid_consent_turn_classifies_intent_then_materializes_persisted_route(self):
        proposed = {
            "envelope": "phased",
            "selection_mode": "explicit-locked",
            "primary_skill": "skill:api-designer",
            "support_skills": ["skill:qa-test-planner"],
            "consent_action": "proposal-required",
            "goal_relation": "none",
            "rationale": "Contract verification needs scoped support.",
            "evaluation_evidence": copy.deepcopy(
                VALID_ROUTE["evaluation_evidence"]
            ),
        }
        intent = {"action": "approved", "rationale": "The user approved it."}
        context = self.start(execution_mode="hybrid-router")
        with patch.object(
            DRIVER_MODULE.subprocess,
            "run",
            side_effect=[completed(proposed), completed(intent)],
        ) as run:
            first = self.driver.handle({
                "type": "execute_turn", "context_id": context["context_id"],
                "attempt_nonce": "nonce-1", "turn_index": 0,
                "prompt": "Use api-designer and propose required support.",
                "allowed_tools": [],
            })
            final = self.driver.handle({
                "type": "execute_turn", "context_id": context["context_id"],
                "attempt_nonce": "nonce-1", "turn_index": 1,
                "prompt": "I approve this support for the current phase.",
                "allowed_tools": [],
            })

        self.assertEqual("proposal-required", first["route"]["consent_action"])
        self.assertEqual("approved", final["model_consent_intent"])
        self.assertEqual("approved", final["route"]["consent_action"])
        self.assertEqual("skill:api-designer", final["route"]["primary_skill"])
        self.assertEqual(["skill:qa-test-planner"], final["route"]["support_skills"])
        self.assertIn("evaluation_evidence", final["route"])
        self.assertEqual(
            proposed["evaluation_evidence"],
            final["route"]["evaluation_evidence"],
        )
        consent_schema = ROOT / "evaluation" / "v2" / "schemas" / "codex-consent-intent.schema.json"
        self.assertIn(str(consent_schema), run.call_args_list[1].args[0])
        self.assertIn("Classify only", run.call_args_list[1].kwargs["input"])

    def test_contract_2_3_rejects_missing_or_unknown_evidence(self):
        missing = copy.deepcopy(VALID_ROUTE)
        missing.pop("evaluation_evidence")
        unknown = copy.deepcopy(VALID_ROUTE)
        unknown["evaluation_evidence"]["classification"]["reason_codes"] = [
            "regex-valid-but-undeclared"
        ]

        for route in (missing, unknown):
            with self.subTest(route=route):
                context = self.start()
                request = {
                    "type": "execute_turn",
                    "context_id": context["context_id"],
                    "attempt_nonce": "nonce-1",
                    "turn_index": 0,
                    "prompt": "Route",
                    "allowed_tools": [],
                }
                with patch.object(
                    DRIVER_MODULE.subprocess,
                    "run",
                    return_value=completed(route),
                ):
                    with self.assertRaisesRegex(
                        EvaluationIntegrityError,
                        "codex_route_schema_invalid",
                    ):
                        self.driver.handle(request)

    def test_rejects_invalid_schema_timeout_and_nonzero_exit_without_leaking_stderr(self):
        context = self.start()
        request = {
            "type": "execute_turn", "context_id": context["context_id"],
            "attempt_nonce": "nonce-1", "turn_index": 0,
            "prompt": "Route", "allowed_tools": [],
        }
        with patch.object(DRIVER_MODULE.subprocess, "run", return_value=completed({"bad": True})):
            with self.assertRaisesRegex(EvaluationIntegrityError, "codex_route_schema_invalid"):
                self.driver.handle(request)
        with patch.object(DRIVER_MODULE.subprocess, "run", side_effect=subprocess.TimeoutExpired([], 17)):
            with self.assertRaisesRegex(EvaluationIntegrityError, "codex_cli_timeout"):
                self.driver.handle(request)
        with patch.object(DRIVER_MODULE.subprocess, "run", return_value=completed(returncode=2, stderr="secret-token")):
            with self.assertRaisesRegex(EvaluationIntegrityError, "^codex_cli_failed$") as raised:
                self.driver.handle(request)
            self.assertNotIn("secret-token", str(raised.exception))
        diagnostic = next((self.root / "attempts").rglob("failure.json")).read_text(encoding="utf-8")
        self.assertNotIn("secret-token", diagnostic)
        self.assertIn("[REDACTED]", diagnostic)
        self.assertTrue(LocalEvidenceProtector().verify_file(
            next((self.root / "attempts").rglob("failure.json"))
        ))

    def test_auth_copy_failure_fails_closed_without_leaving_a_partial_secret(self):
        context = self.start()
        request = {
            "type": "execute_turn", "context_id": context["context_id"],
            "attempt_nonce": "nonce-1", "turn_index": 0,
            "prompt": "Route", "allowed_tools": [],
        }
        destination = self.root / "attempts" / context["context_id"] / "codex-home" / "auth.json"
        with patch.object(DRIVER_MODULE.shutil, "copyfile", side_effect=OSError("copy failed")):
            with self.assertRaisesRegex(EvaluationIntegrityError, "codex_cli_start_failed"):
                self.driver.handle(request)
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
