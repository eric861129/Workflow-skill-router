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


DRIVER_PATH = ROOT / "evaluation" / "v2" / "adapters" / "claude_code_driver.py"
SPEC = importlib.util.spec_from_file_location("claude_code_driver", DRIVER_PATH)
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
USAGE = {
    "input_tokens": 40,
    "cache_creation_input_tokens": 10,
    "cache_read_input_tokens": 50,
    "output_tokens": 30,
}


def completed(route=VALID_ROUTE, *, structured=True, returncode=0, stderr="", **extra):
    event = {"type": "result", "subtype": "success", "is_error": False, "usage": USAGE, **extra}
    if structured:
        event["structured_output"] = route
        event["result"] = ""
    else:
        event["result"] = json.dumps(route)
    return subprocess.CompletedProcess([], returncode, json.dumps(event), stderr)


@unittest.skipIf(DRIVER_MODULE is None, "driver module could not be loaded")
class ClaudeCodeDriverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.executable = (self.root / "claude.exe").resolve()
        self.schema = (ROOT / "evaluation" / "v2" / "schemas" / "codex-route-output.schema.json").resolve()
        environment = patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "test-oauth-token"})
        environment.start()
        self.addCleanup(environment.stop)
        self.driver = DRIVER_MODULE.ClaudeCodeDriver(
            self.executable,
            self.schema,
            (self.root / "attempts").resolve(),
            timeout_seconds=17,
            model="claude-sonnet-5-5",
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

    def turn(self, context, index, prompt):
        return {
            "type": "execute_turn", "context_id": context["context_id"],
            "attempt_nonce": "nonce-1", "turn_index": index,
            "prompt": prompt, "allowed_tools": [],
        }

    def test_refuses_to_start_without_explicit_claude_auth(self):
        names = {name: "" for name in DRIVER_MODULE.AUTH_ENVIRONMENT}
        with patch.dict(os.environ, names):
            with self.assertRaisesRegex(ValueError, "claude_driver_auth_missing"):
                DRIVER_MODULE.ClaudeCodeDriver(
                    self.executable, self.schema, (self.root / "other").resolve(),
                )

    def test_invokes_print_mode_without_tools_mcp_skills_or_user_state(self):
        context = self.start()
        leaked = {
            "WORKFLOW_ROUTER_TEST_SECRET": "must-not-leak",
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:9/desktop-proxy",
            "CLAUDE_CODE_SESSION_ID": "host-session",
        }
        with patch.dict(os.environ, leaked), \
             patch.object(DRIVER_MODULE.subprocess, "run", return_value=completed()) as run:
            response = self.driver.handle(self.turn(context, 0, "Route this task"))

        argv = run.call_args.args[0]
        self.assertEqual(str(self.executable), argv[0])
        for flag in ("--print", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
            self.assertIn(flag, argv)
        self.assertEqual("json", argv[argv.index("--output-format") + 1])
        self.assertEqual("", argv[argv.index("--tools") + 1])
        self.assertEqual("claude-sonnet-5-5", argv[argv.index("--model") + 1])
        self.assertEqual(
            json.loads(self.schema.read_text(encoding="utf-8")),
            json.loads(argv[argv.index("--json-schema") + 1]),
        )
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertEqual(17, run.call_args.kwargs["timeout"])
        workspace = Path(run.call_args.kwargs["cwd"])
        self.assertEqual("workspace", workspace.name)
        self.assertEqual([], list(workspace.iterdir()))
        environment = run.call_args.kwargs["env"]
        for name in leaked:
            self.assertNotIn(name, environment)
        self.assertEqual("test-oauth-token", environment["CLAUDE_CODE_OAUTH_TOKEN"])
        config = Path(environment["CLAUDE_CONFIG_DIR"])
        self.assertEqual("claude-config", config.name)
        self.assertEqual(workspace.parent, config.parent)
        for name in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
            self.assertEqual(str(workspace.parent / "runtime-home"), environment[name])
        self.assertEqual("1", environment["DISABLE_TELEMETRY"])
        self.assertEqual("1", environment["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"])
        self.assertEqual(VALID_ROUTE, response["route"])

    def test_effort_is_forwarded_and_usage_is_normalized(self):
        self.driver._reasoning_effort = "medium"
        context = self.start()
        with patch.object(DRIVER_MODULE.subprocess, "run", return_value=completed()) as run:
            self.driver.handle(self.turn(context, 0, "Route"))
        argv = run.call_args.args[0]
        self.assertEqual("medium", argv[argv.index("--effort") + 1])
        transcript = json.loads(
            (self.root / "attempts" / context["context_id"] / "transcript.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {"input_tokens": 100, "cached_input_tokens": 50, "output_tokens": 30},
            transcript["turns"][0]["execution_metrics"]["usage"],
        )

    def test_usage_rejects_missing_or_negative_fields(self):
        for invalid in ("", json.dumps({"type": "result"}), json.dumps({"type": "result", "usage": {**USAGE, "output_tokens": -1}})):
            self.assertIsNone(DRIVER_MODULE.ClaudeCodeDriver._extract_usage(invalid))

    def test_route_can_arrive_as_result_text(self):
        context = self.start()
        with patch.object(DRIVER_MODULE.subprocess, "run", return_value=completed(structured=False)):
            response = self.driver.handle(self.turn(context, 0, "Route"))
        self.assertEqual(VALID_ROUTE, response["route"])

    def test_error_results_and_cli_failures_fail_closed(self):
        cases = (
            (completed(is_error=True), "claude_route_output_missing"),
            (completed(returncode=1, stderr="test-oauth-token rejected"), "claude_cli_failed"),
            (subprocess.CompletedProcess([], 0, "not json", ""), "claude_route_output_missing"),
        )
        for result, code in cases:
            with self.subTest(code=code):
                context = self.start()
                with patch.object(DRIVER_MODULE.subprocess, "run", return_value=result):
                    with self.assertRaisesRegex(EvaluationIntegrityError, code):
                        self.driver.handle(self.turn(context, 0, "Route"))
        failures = list((self.root / "attempts").glob("*/failure.json"))
        self.assertEqual(1, len(failures))
        self.assertNotIn("test-oauth-token", failures[0].read_text(encoding="utf-8"))

    def test_shared_validation_rejects_activation_claims(self):
        claimed = copy.deepcopy(VALID_ROUTE)
        claimed["evaluation_evidence"]["activation_status"] = "claimed-activated"
        context = self.start()
        with patch.object(DRIVER_MODULE.subprocess, "run", return_value=completed(claimed)):
            with self.assertRaisesRegex(EvaluationIntegrityError, "codex_route_schema_invalid"):
                self.driver.handle(self.turn(context, 0, "Route"))

    def test_hybrid_consent_uses_the_shared_state_machine(self):
        proposed = {
            **copy.deepcopy(VALID_ROUTE),
            "envelope": "phased",
            "selection_mode": "explicit-locked",
            "primary_skill": "skill:api-designer",
            "support_skills": ["skill:qa-test-planner"],
            "consent_action": "proposal-required",
            "rationale": "Contract verification needs scoped support.",
        }
        intent = {"action": "approved", "rationale": "The user approved it."}
        context = self.start(execution_mode="hybrid-router")
        with patch.object(
            DRIVER_MODULE.subprocess, "run", side_effect=[completed(proposed), completed(intent)],
        ) as run:
            first = self.driver.handle(self.turn(context, 0, "Use api-designer and propose required support."))
            final = self.driver.handle(self.turn(context, 1, "I approve this support for the current phase."))

        self.assertEqual("proposal-required", first["route"]["consent_action"])
        self.assertEqual("approved", final["model_consent_intent"])
        self.assertEqual("approved", final["route"]["consent_action"])
        self.assertEqual(["skill:qa-test-planner"], final["route"]["support_skills"])
        consent_argv = run.call_args_list[1].args[0]
        consent_schema = json.loads(consent_argv[consent_argv.index("--json-schema") + 1])
        self.assertEqual(["action", "rationale"], consent_schema["required"])
        self.assertIn("Classify only", run.call_args_list[1].kwargs["input"])


if __name__ == "__main__":
    unittest.main()
