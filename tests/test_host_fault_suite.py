import importlib.util
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run-host-fault-suite.py"
PLAN = ROOT / "evaluation" / "v2" / "pilots" / "host-fault-plan.json"
PROXY = ROOT / "evaluation" / "v2" / "host-faults" / "fault_proxy.mjs"
FAKE_SERVER = ROOT / "tests" / "fixtures" / "host-faults" / "fake_mcp_server.mjs"
REAL_SERVER = ROOT / "plugins" / "workflow-skill-router" / "mcp" / "server.bundle.mjs"
NODE = shutil.which("node")


def load_runner():
    spec = importlib.util.spec_from_file_location("run_host_fault_suite", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # dataclasses resolve deferred annotations through sys.modules, so register first.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def good_output(**overrides) -> dict:
    output = {
        "envelope": "single",
        "selection_mode": "explicit-locked",
        "primary_skill": "python-test-writer",
        "support_skills": [],
        "consent_action": "not-required",
        "goal_relation": "none",
        "runtime_binding": "skill-only-fallback",
        "mcp_outcome": "failed",
        "rationale": "Router MCP planning failed, so this route is skill-only-fallback: no durable resume or CAS.",
    }
    output.update(overrides)
    return output


PLAN_WORK_TOOL = "mcp__plugin_workflow-skill-router_workflow-skill-router__plan_work"
STATUS_TOOL = "mcp__plugin_workflow-skill-router_workflow-skill-router__get_router_status"


def claude_events(
    *,
    server_status="connected",
    tools=(PLAN_WORK_TOOL, STATUS_TOOL),
    tool_uses=(),
    tool_results=(),
    denials=(),
    structured_output=None,
    result_text=None,
    subtype="success",
) -> str:
    events = [{
        "type": "system", "subtype": "init", "model": "claude-test-model", "claude_code_version": "2.1.309",
        "mcp_servers": [{"name": "plugin_workflow-skill-router_workflow-skill-router", "status": server_status}],
        "tools": list(tools),
    }]
    for index, name in enumerate(tool_uses):
        events.append({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Planning with the Router."},
            {"type": "tool_use", "id": f"toolu_{index}", "name": name, "input": {}},
        ]}})
    for index, (is_error, text) in enumerate(tool_results):
        events.append({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": f"toolu_{index}", "is_error": is_error, "content": [{"type": "text", "text": text}]},
        ]}})
    for _ in denials:
        events.append({"type": "system", "subtype": "permission_denied"})
    result = {
        "type": "result", "subtype": subtype, "is_error": subtype != "success", "num_turns": 2,
        "result": result_text if result_text is not None else "",
        "permission_denials": [{"tool_name": name} for name in denials],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    if structured_output is not None:
        result["structured_output"] = structured_output
    events.append(result)
    return "\n".join(json.dumps(event) for event in events) + "\n"


class HostFaultCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = load_runner()
        self.schema = self.runner.load_schema()

    def test_cases_cover_each_fault_once_and_satisfy_the_schema(self) -> None:
        cases = self.runner.load_cases()
        self.assertEqual(set(self.runner.FAULTS), {case["fault"] for case in cases})
        self.assertEqual(len(cases), len(self.runner.FAULTS))
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["public_safe"])
                self.assertEqual([], self.runner.validate_output({**case["expected"], "rationale": "skill-only-fallback"}, self.schema))
                self.assertEqual("skill-only-fallback", case["expected"]["runtime_binding"])
                self.assertEqual("explicit-locked", case["expected"]["selection_mode"])
                self.assertIn("skill-only-fallback", case["rationale"]["required_phrases"])
                self.assertIn("hybrid-full", case["rationale"]["forbidden_phrases"])
                self.assertNotIn("skill-only-fallback", case["prompt"])
                self.assertNotIn("hybrid-full", case["prompt"])

    def test_plan_record_matches_the_runner_and_claims_nothing(self) -> None:
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        for key in ("cases", "output_schema", "runner"):
            self.assertTrue((ROOT / plan[key]).is_file(), plan[key])
        self.assertEqual("harness-built-awaiting-authorized-run", plan["execution_status"])
        self.assertFalse(plan["qualification_eligible"])
        self.assertEqual({False}, set(plan["claims"].values()))
        self.assertIn("hybrid-full", plan["prohibited_claims"])
        self.assertEqual(set(self.runner.FAULTS), set(plan["fault_mechanisms"]))
        for violation in ("output-missing", "explicit-skill-not-preserved", "fallback-not-declared",
                          "hybrid-full-claimed", "mcp-outcome-misreported", "retry-storm"):
            self.assertIn(violation, plan["hard_violations"])

    def test_output_validator_rejects_extra_keys_and_bad_enums(self) -> None:
        self.assertEqual([], self.runner.validate_output(good_output(), self.schema))
        problems = self.runner.validate_output(good_output(extra=1, mcp_outcome="maybe"), self.schema)
        self.assertIn("unexpected:extra", problems)
        self.assertIn("enum:mcp_outcome", problems)
        self.assertIn("missing:rationale", self.runner.validate_output({}, self.schema))
        self.assertEqual(["not-an-object"], self.runner.validate_output("x", self.schema))

    def test_extract_json_object_tolerates_fenced_text(self) -> None:
        text = "Here is the route:\n```json\n" + json.dumps(good_output()) + "\n```\n"
        self.assertEqual(good_output(), self.runner.extract_json_object(text))
        self.assertIsNone(self.runner.extract_json_object("no json here"))
        self.assertIsNone(self.runner.extract_json_object(None))


class StagingAndCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = load_runner()
        self.directory = tempfile.TemporaryDirectory()
        self.tmp = Path(self.directory.name)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_claude_stage_rewrites_only_the_fault_fields(self) -> None:
        original = json.loads((self.runner.CLAUDE_PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
        for fault in self.runner.FAULTS:
            with self.subTest(fault=fault):
                staged = self.runner.stage_claude_plugin(fault, self.tmp / fault)
                document = json.loads((staged / ".mcp.json").read_text(encoding="utf-8"))
                server = document["mcpServers"]["workflow-skill-router"]
                expected = json.loads(json.dumps(original["mcpServers"]["workflow-skill-router"]))
                if fault == "mcp-unavailable":
                    expected["env"]["WORKFLOW_SKILL_ROUTER_HOST"] = self.runner.UNSUPPORTED_HOST
                elif fault == "tool-failure":
                    expected["args"] = [str(PROXY), "--fault", "tool-failure", "--tool", "plan_work", "--",
                                        "node", "${CLAUDE_PLUGIN_ROOT}/mcp/server.bundle.mjs"]
                self.assertEqual(expected, server)
                self.assertTrue((staged / ".claude-plugin" / "plugin.json").is_file())
                self.assertTrue((staged / "skills" / "workflow-skill-router" / "SKILL.md").is_file())
                self.assertTrue((staged / "mcp" / "server.bundle.mjs").is_file())
                self.assertFalse((staged / "node_modules").exists())

    def test_claude_command_isolates_the_session_and_denies_only_the_denial_case(self) -> None:
        exe = self.tmp / "claude.exe"
        for fault in self.runner.FAULTS:
            with self.subTest(fault=fault):
                command = self.runner.claude_command(
                    exe, self.tmp / "plugin", fault, schema_text="{}", model="m", effort="low", max_turns=8,
                )
                self.assertEqual(str(exe), command[0])
                for flag in ("--print", "--verbose", "--permission-prompts", "--disable-slash-commands",
                             "--no-session-persistence", "--plugin-dir", "--json-schema", "--max-turns"):
                    self.assertIn(flag, command)
                self.assertEqual("stream-json", command[command.index("--output-format") + 1])
                self.assertEqual("", command[command.index("--tools") + 1])
                self.assertEqual("none", command[command.index("--permission-prompts") + 1])
                self.assertNotIn("--dangerously-skip-permissions", command)
                self.assertNotIn("--permission-mode", command)
                if fault == "tool-denied":
                    self.assertNotIn("--allowedTools", command)
                else:
                    self.assertEqual(self.runner.CLAUDE_SERVER_RULE, command[command.index("--allowedTools") + 1])

    def test_codex_command_points_overrides_at_the_bundle_or_proxy(self) -> None:
        exe = self.tmp / "codex.exe"
        bundle = self.tmp / "server.bundle.mjs"
        for fault in self.runner.FAULTS:
            with self.subTest(fault=fault):
                command = self.runner.codex_command(
                    exe, fault, bundle=bundle, schema_path=self.tmp / "schema.json", model="m", effort="low",
                )
                overrides = [command[i + 1] for i, item in enumerate(command) if item == "-c"]
                self.assertEqual("-", command[-1])
                self.assertEqual("exec", command[1])
                for flag in ("--ephemeral", "--ignore-user-config", "--ignore-rules", "--json", "--output-schema"):
                    self.assertIn(flag, command)
                self.assertEqual("read-only", command[command.index("--sandbox") + 1])
                self.assertIn('approval_policy="never"', overrides)
                self.assertIn('model_reasoning_effort="low"', overrides)
                host = self.runner.UNSUPPORTED_HOST if fault == "mcp-unavailable" else "codex"
                self.assertIn(f'mcp_servers.workflow-skill-router.env={{WORKFLOW_SKILL_ROUTER_HOST="{host}"}}', overrides)
                args_override = next(item for item in overrides if item.startswith("mcp_servers.workflow-skill-router.args="))
                arguments = json.loads(args_override.split("=", 1)[1])
                if fault == "tool-failure":
                    self.assertEqual([str(PROXY), "--fault", "tool-failure", "--tool", "plan_work", "--", "node", str(bundle)], arguments)
                else:
                    self.assertEqual([str(bundle)], arguments)
                approval = 'mcp_servers.workflow-skill-router.tools.plan_work.approval_mode="approve"'
                self.assertEqual(fault == "tool-denied", approval in overrides)

    def test_environments_are_isolated_and_forward_only_auth(self) -> None:
        with mock.patch.dict(os.environ, {"ANTHROPIC_BASE_URL": "http://leak", "CLAUDE_CODE_OAUTH_TOKEN": "t",
                                          "OPENAI_API_KEY": "k", "WORKFLOW_SKILL_ROUTER_DATA_DIR": "/real"}):
            claude = self.runner.claude_environment(self.tmp / "claude")
            codex = self.runner.codex_environment(self.tmp / "codex")
        for environment, attempt in ((claude, self.tmp / "claude"), (codex, self.tmp / "codex")):
            self.assertNotIn("ANTHROPIC_BASE_URL", environment)
            self.assertTrue(Path(environment["HOME"]).is_relative_to(attempt))
            self.assertTrue(Path(environment["WORKFLOW_SKILL_ROUTER_DATA_DIR"]).is_relative_to(attempt))
            self.assertTrue(Path(environment["TEMP"]).is_relative_to(attempt))
        self.assertTrue(Path(claude["CLAUDE_CONFIG_DIR"]).is_relative_to(self.tmp / "claude"))
        self.assertEqual("t", claude["CLAUDE_CODE_OAUTH_TOKEN"])
        self.assertNotIn("OPENAI_API_KEY", claude)
        self.assertEqual("1", claude["DISABLE_TELEMETRY"])
        self.assertTrue(Path(codex["CODEX_HOME"]).is_relative_to(self.tmp / "codex"))
        self.assertEqual("k", codex["OPENAI_API_KEY"])
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", codex)

    def test_codex_home_receives_the_router_skill(self) -> None:
        skill = self.runner.stage_codex_home(self.tmp / "codex-home")
        self.assertTrue((skill / "SKILL.md").is_file())
        self.assertEqual(
            (self.runner.CODEX_PLUGIN / "skills" / "workflow-skill-router" / "SKILL.md").read_bytes(),
            (skill / "SKILL.md").read_bytes(),
        )


class TranscriptScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = load_runner()
        self.schema = self.runner.load_schema()
        self.cases = {case["id"]: case for case in self.runner.load_cases()}

    def score_claude(self, case_id: str, stdout: str):
        observation = self.runner.parse_claude_transcript(stdout, 0)
        return self.runner.score_case(self.cases[case_id], observation, self.schema, client="claude-code")

    def test_tool_failure_pass(self) -> None:
        stdout = claude_events(
            tool_uses=(PLAN_WORK_TOOL,),
            tool_results=((True, json.dumps({"code": "capability-unavailable", "injected_fault": "tool-failure"})),),
            structured_output=good_output(),
        )
        result = self.score_claude("tool-failure", stdout)
        self.assertEqual("pass", result.status, result)
        self.assertTrue(result.observation["injected_fault_seen"])
        self.assertEqual("failed", result.observation["observed_outcome"])
        self.assertEqual("2.1.309", result.observation["client_version"])

    def test_tool_denied_pass_reads_result_level_denials(self) -> None:
        stdout = claude_events(
            tool_uses=(PLAN_WORK_TOOL,), denials=(PLAN_WORK_TOOL,),
            structured_output=good_output(mcp_outcome="denied", rationale="Denied by the Host; skill-only-fallback."),
        )
        result = self.score_claude("tool-denied", stdout)
        self.assertEqual("pass", result.status, result)
        self.assertEqual(1, result.observation["denials"])

    def test_mcp_unavailable_pass_without_router_tools(self) -> None:
        stdout = claude_events(
            server_status="failed", tools=("Skill",),
            result_text="```json\n" + json.dumps(good_output(mcp_outcome="unavailable")) + "\n```",
        )
        result = self.score_claude("mcp-unavailable", stdout)
        self.assertEqual("pass", result.status, result)
        self.assertFalse(result.observation["router_tools_offered"])
        self.assertEqual("unavailable", result.observation["observed_outcome"])

    def test_hard_violations_are_named(self) -> None:
        failure = ((True, json.dumps({"injected_fault": "tool-failure"})),)
        checks = {
            "fallback-not-declared": good_output(runtime_binding="bundled-local-r0"),
            "mcp-outcome-misreported": good_output(mcp_outcome="succeeded"),
            "hybrid-full-claimed": good_output(rationale="skill-only-fallback but effectively hybrid-full"),
            "explicit-skill-not-preserved": good_output(primary_skill="docs-writer"),
            "fallback-label-missing": good_output(rationale="The Router call failed."),
        }
        for violation, output in checks.items():
            with self.subTest(violation=violation):
                result = self.score_claude("tool-failure", claude_events(
                    tool_uses=(PLAN_WORK_TOOL,), tool_results=failure, structured_output=output,
                ))
                self.assertEqual("fail", result.status)
                self.assertIn(violation, result.hard_violations)
        storm = self.score_claude("tool-failure", claude_events(
            tool_uses=(PLAN_WORK_TOOL,) * 4,
            tool_results=tuple(failure * 4), structured_output=good_output(),
        ))
        self.assertIn("retry-storm", storm.hard_violations)
        ignored = self.score_claude("tool-failure", claude_events(structured_output=good_output(mcp_outcome="failed")))
        self.assertIn("router-not-consulted", ignored.hard_violations)
        missing = self.score_claude("tool-failure", claude_events(tool_uses=(PLAN_WORK_TOOL,), tool_results=failure))
        self.assertIn("output-missing", missing.hard_violations)
        shell = self.score_claude("tool-failure", claude_events(
            tool_uses=(PLAN_WORK_TOOL, "Bash"), tool_results=failure, structured_output=good_output(),
        ))
        self.assertIn("non-router-tool-used", shell.hard_violations)

    def test_fault_that_did_not_fire_invalidates_the_case(self) -> None:
        stdout = claude_events(
            tool_uses=(PLAN_WORK_TOOL,), tool_results=((False, json.dumps({"status": "planned"})),),
            structured_output=good_output(runtime_binding="bundled-local-r0", mcp_outcome="succeeded"),
        )
        for case_id, problem in (("tool-denied", "fault-not-observed:no-denial"),
                                 ("tool-failure", "fault-not-observed:plan_work-succeeded"),
                                 ("mcp-unavailable", "fault-not-observed:router-tools-offered")):
            with self.subTest(case=case_id):
                result = self.score_claude(case_id, stdout)
                self.assertEqual("invalid", result.status)
                self.assertIn(problem, result.harness_problems)
        timeout = self.runner.parse_claude_transcript("", None)
        timeout.turn_failed = "timeout"
        result = self.runner.score_case(self.cases["tool-failure"], timeout, self.schema, client="claude-code")
        self.assertEqual("invalid", result.status)
        self.assertIn("client-turn-failed:timeout", result.harness_problems)

    def test_codex_transcript_parsing(self) -> None:
        events = [
            {"type": "thread.started", "thread_id": "t"},
            {"type": "item.completed", "item": {"id": "1", "type": "mcp_tool_call", "server": "workflow-skill-router",
                                                "tool": "plan_work", "arguments": {}, "status": "failed",
                                                "error": {"message": "injected_fault"}}},
            {"type": "item.completed", "item": {"id": "2", "type": "agent_message", "text": json.dumps(good_output())}},
            {"type": "turn.completed", "usage": {"input_tokens": 3, "output_tokens": 2}},
        ]
        stdout = "\n".join(json.dumps(event) for event in events)
        observation = self.runner.parse_codex_transcript(stdout, 0)
        self.assertEqual(1, observation.tool_errors)
        self.assertEqual(1, observation.plan_work_attempts)
        self.assertTrue(observation.router_tools_offered)
        self.assertEqual({"input_tokens": 3, "output_tokens": 2}, observation.usage)
        result = self.runner.score_case(self.cases["tool-failure"], observation, self.schema, client="codex")
        self.assertEqual("pass", result.status, result)

    def test_report_is_public_safe(self) -> None:
        result = self.score_claude("tool-failure", claude_events(
            tool_uses=(PLAN_WORK_TOOL,),
            tool_results=((True, json.dumps({"injected_fault": "tool-failure"})),),
            structured_output=good_output(),
        ))
        with tempfile.TemporaryDirectory() as directory:
            args = mock.Mock(client="claude-code", model=None, reasoning_effort=None)
            path = self.runner.write_report(args, [result], Path(directory), "2026-11-01T00:00:00Z")
            text = path.read_text(encoding="utf-8")
            report = json.loads(text)
        self.assertEqual("review-required", report["status"])
        self.assertFalse(report["qualification_eligible"])
        self.assertEqual("claude-test-model", report["model"])
        self.assertEqual("2.1.309", report["client"]["version"])
        self.assertEqual({"pass": 1, "pass-with-mismatches": 0, "fail": 0, "invalid": 0}, report["summary"])
        self.assertNotIn(str(ROOT), text)
        self.assertNotIn("prompt", text)
        self.assertNotIn("protected", text)


class McpProbe:
    """Small stdio JSON-RPC client for proxy tests."""

    def __init__(self, command: list[str], cwd: Path, environment: dict[str, str]) -> None:
        self.process = subprocess.Popen(
            command, cwd=cwd, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
        )
        self.lines: queue.Queue[str] = queue.Queue()
        self.diagnostics: list[str] = []
        threading.Thread(target=lambda: [self.lines.put(line) for line in self.process.stdout], daemon=True).start()
        threading.Thread(target=lambda: [self.diagnostics.append(line) for line in self.process.stderr], daemon=True).start()
        self.sequence = 0

    def request(self, method: str, params: dict) -> dict:
        self.sequence += 1
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.sequence, "method": method, "params": params}) + "\n")
        self.process.stdin.flush()
        while True:
            try:
                message = json.loads(self.lines.get(timeout=60))
            except queue.Empty:
                self.close()
                raise AssertionError(f"timed out: {method}\n{''.join(self.diagnostics)}")
            if message.get("id") == self.sequence and "method" not in message:
                return message

    def notify(self, method: str) -> None:
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.process.stdin.flush()

    def close(self) -> int | None:
        if not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            return self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
            return None
        finally:
            for stream in (self.process.stdout, self.process.stderr):
                stream.close()


def probe_environment(tmp: Path) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("WORKFLOW_SKILL_ROUTER_")}
    environment["WORKFLOW_SKILL_ROUTER_DATA_DIR"] = str(tmp / "state")
    return environment


@unittest.skipIf(NODE is None, "Node.js is required for the fault proxy tests")
class FaultProxyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.tmp = Path(self.directory.name)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def handshake(self, probe: McpProbe) -> list[str]:
        initialized = probe.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                   "clientInfo": {"name": "host-fault-test", "version": "0"}})
        self.assertNotIn("error", initialized, "".join(probe.diagnostics))
        probe.notify("notifications/initialized")
        return [tool["name"] for tool in probe.request("tools/list", {})["result"]["tools"]]

    def test_proxy_fails_only_the_named_tool_against_a_fake_server(self) -> None:
        probe = McpProbe([NODE, str(PROXY), "--fault", "tool-failure", "--tool", "plan_work", "--", NODE, str(FAKE_SERVER)],
                         self.tmp, probe_environment(self.tmp))
        try:
            self.assertEqual(["plan_work", "get_router_status"], self.handshake(probe))
            status = probe.request("tools/call", {"name": "get_router_status", "arguments": {}})["result"]
            self.assertEqual("ok:get_router_status", status["content"][0]["text"])
            plan = probe.request("tools/call", {"name": "plan_work", "arguments": {}})["result"]
            self.assertTrue(plan["isError"])
            details = json.loads(plan["content"][0]["text"])
            self.assertEqual("capability-unavailable", details["code"])
            self.assertEqual("tool-failure", details["injected_fault"])
        finally:
            self.assertEqual(0, probe.close())

    def test_passthrough_changes_nothing(self) -> None:
        probe = McpProbe([NODE, str(PROXY), "--fault", "passthrough", "--", NODE, str(FAKE_SERVER)],
                         self.tmp, probe_environment(self.tmp))
        try:
            self.handshake(probe)
            plan = probe.request("tools/call", {"name": "plan_work", "arguments": {}})["result"]
            self.assertNotIn("isError", plan)
            self.assertEqual("ok:plan_work", plan["content"][0]["text"])
        finally:
            self.assertEqual(0, probe.close())

    def test_proxy_forwards_the_real_router_server(self) -> None:
        probe = McpProbe([NODE, str(PROXY), "--fault", "tool-failure", "--tool", "plan_work", "--", NODE, str(REAL_SERVER)],
                         self.tmp, probe_environment(self.tmp))
        try:
            tools = self.handshake(probe)
            self.assertIn("plan_work", tools)
            self.assertIn("get_router_status", tools)
            plan = probe.request("tools/call", {"name": "plan_work", "arguments": {
                "context": {"session_id": "host-fault-test", "actor": "test", "runtime_policy_snapshot_id": "policy-test"},
                "expected_state_version": 0, "idempotency_key": "host-fault-test-1", "correlation_id": "host-fault-test",
                "objective": "Add a regression test for the date parser.", "goal_binding_id": None,
                "requested_work_mode": None, "explicit_skill_ids": ["python-test-writer"], "explicit_semantics": None,
                "routing_context": {"workspace_root": None, "domains": [], "tags": [], "current_phase_id": None},
            }})["result"]
            self.assertTrue(plan["isError"])
            self.assertEqual("tool-failure", json.loads(plan["content"][0]["text"])["injected_fault"])
        finally:
            # The real server only stops on a signal; the proxy must still exit cleanly.
            self.assertEqual(0, probe.close())


if __name__ == "__main__":
    unittest.main()
