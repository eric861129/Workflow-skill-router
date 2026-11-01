"""Run the host-fault lane: the Router Plugin inside a real Host session, one injected fault per case.

The Behavior gate never loads tools or MCP, so it cannot observe what a Host
session does when the Router MCP server cannot start, when the Host denies a
Router tool call, or when the call runs and fails. This runner loads the real
Plugin into Claude Code or Codex, injects exactly one of those faults, and
scores the session's transcript and final JSON against the SKILL contract.

Every execution calls a live model. It needs --confirm-live-run and explicit
authentication; --print-plan shows the exact commands without running them.
Only sanitized-report.json is public-safe; everything under protected/ stays
local.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evaluation" / "v2" / "host-faults" / "cases.jsonl"
SCHEMA_PATH = ROOT / "evaluation" / "v2" / "schemas" / "host-fault-output.schema.json"
PROXY_PATH = ROOT / "evaluation" / "v2" / "host-faults" / "fault_proxy.mjs"
CLAUDE_PLUGIN = ROOT / "plugins" / "claude-code" / "workflow-skill-router"
CODEX_PLUGIN = ROOT / "plugins" / "workflow-skill-router"
SERVER_NAME = "workflow-skill-router"
# Claude Code names a Plugin's MCP tools mcp__plugin_<plugin>_<server>__<tool>.
CLAUDE_SERVER_RULE = "mcp__plugin_workflow-skill-router_workflow-skill-router"
CLAUDE_TOOL_PREFIX = CLAUDE_SERVER_RULE + "__"
ROUTER_TOOL_MARKER = "workflow-skill-router__"
FAULTS = ("mcp-unavailable", "tool-denied", "tool-failure")
CLIENTS = ("claude-code", "codex")
UNSUPPORTED_HOST = "host-fault-lane-unsupported"
CLAUDE_AUTH_ENVIRONMENT = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")
ENVIRONMENT_ALLOWLIST = (
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "PATH", "SSL_CERT_FILE", "SystemRoot", "WINDIR",
)
ROUTE_FIELDS = (
    "envelope", "selection_mode", "primary_skill", "support_skills", "consent_action", "goal_relation",
)
OUTPUT_FIELDS = ROUTE_FIELDS + ("runtime_binding", "mcp_outcome")
COPY_IGNORE = shutil.ignore_patterns("__pycache__", "node_modules", ".test-build")


class HostFaultError(Exception):
    pass


# --- cases and schema -------------------------------------------------------

def load_cases(path: Path = CASES_PATH) -> list[dict]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        for key in ("id", "fault", "prompt", "expected", "transcript", "rationale"):
            if key not in case:
                raise HostFaultError(f"case {case.get('id')!r} lacks {key}")
        if case["fault"] not in FAULTS:
            raise HostFaultError(f"case {case['id']!r} has unknown fault {case['fault']!r}")
        if set(case["expected"]) != set(OUTPUT_FIELDS):
            raise HostFaultError(f"case {case['id']!r} expected fields must be {sorted(OUTPUT_FIELDS)}")
        for key in ("router_server_connected", "max_mcp_attempts", "plan_work_succeeded",
                    "denial_required", "tool_error_required"):
            if key not in case["transcript"]:
                raise HostFaultError(f"case {case['id']!r} transcript lacks {key}")
        cases.append(case)
    if len({case["id"] for case in cases}) != len(cases):
        raise HostFaultError("duplicate case ids")
    return cases


def load_schema(path: Path = SCHEMA_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_output(document: object, schema: dict) -> list[str]:
    """Check the final JSON against the lane schema without a jsonschema dependency."""
    if not isinstance(document, dict):
        return ["not-an-object"]
    problems = []
    properties = schema["properties"]
    for key in schema["required"]:
        if key not in document:
            problems.append(f"missing:{key}")
    for key in document:
        if key not in properties:
            problems.append(f"unexpected:{key}")
    for key, rule in properties.items():
        if key not in document:
            continue
        value = document[key]
        if "enum" in rule and value not in rule["enum"]:
            problems.append(f"enum:{key}")
        elif rule.get("type") == "string":
            if not isinstance(value, str):
                problems.append(f"type:{key}")
            elif len(value) < rule.get("minLength", 0) or len(value) > rule.get("maxLength", 10**9):
                problems.append(f"length:{key}")
        elif rule.get("type") == "array":
            if not isinstance(value, list) or len(value) > rule.get("maxItems", 10**9):
                problems.append(f"type:{key}")
            elif not all(isinstance(item, str) and item for item in value):
                problems.append(f"items:{key}")
    return problems


def extract_json_object(text: str | None) -> dict | None:
    if not text:
        return None
    candidates = [text.strip()]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


# --- staging ----------------------------------------------------------------

def toml_string(value: str) -> str:
    # A JSON string literal is a valid TOML basic string for the paths used here.
    return json.dumps(value, ensure_ascii=True)


def toml_array(values: list[str]) -> str:
    return "[" + ", ".join(toml_string(value) for value in values) + "]"


def proxied_server_arguments(bundle: str) -> list[str]:
    return [str(PROXY_PATH), "--fault", "tool-failure", "--tool", "plan_work", "--", "node", bundle]


def stage_claude_plugin(fault: str, stage_dir: Path) -> Path:
    """Copy the Claude Code Plugin and rewrite its .mcp.json for the fault."""
    target = stage_dir / "workflow-skill-router"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(CLAUDE_PLUGIN, target, ignore=COPY_IGNORE)
    mcp_path = target / ".mcp.json"
    document = json.loads(mcp_path.read_text(encoding="utf-8"))
    server = document["mcpServers"][SERVER_NAME]
    if fault == "mcp-unavailable":
        server["env"]["WORKFLOW_SKILL_ROUTER_HOST"] = UNSUPPORTED_HOST
    elif fault == "tool-failure":
        server["command"] = "node"
        server["args"] = proxied_server_arguments("${CLAUDE_PLUGIN_ROOT}/mcp/server.bundle.mjs")
    mcp_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return target


def stage_codex_home(codex_home: Path) -> Path:
    """Give a fresh CODEX_HOME the Router SKILL; the MCP server comes from -c overrides."""
    skill = codex_home / "skills" / "workflow-skill-router"
    if skill.exists():
        shutil.rmtree(skill)
    shutil.copytree(CODEX_PLUGIN / "skills" / "workflow-skill-router", skill, ignore=COPY_IGNORE)
    return skill


# --- commands ---------------------------------------------------------------

def claude_command(
    executable: Path,
    plugin_dir: Path,
    fault: str,
    *,
    schema_text: str,
    model: str | None,
    effort: str | None,
    max_turns: int,
) -> list[str]:
    command = [
        str(executable),
        "--print",
        "--output-format", "stream-json",
        "--verbose",
        "--json-schema", schema_text,
        "--tools", "",
        "--plugin-dir", str(plugin_dir),
        "--permission-prompts", "none",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--max-turns", str(max_turns),
    ]
    if fault != "tool-denied":
        # Without this rule every Router call needs approval, and --permission-prompts none denies it.
        command += ["--allowedTools", CLAUDE_SERVER_RULE]
    if model:
        command += ["--model", model]
    if effort:
        command += ["--effort", effort]
    return command


def codex_command(
    executable: Path,
    fault: str,
    *,
    bundle: Path,
    schema_path: Path,
    model: str | None,
    effort: str | None,
) -> list[str]:
    server = f"mcp_servers.{SERVER_NAME}"
    host = UNSUPPORTED_HOST if fault == "mcp-unavailable" else "codex"
    arguments = proxied_server_arguments(str(bundle)) if fault == "tool-failure" else [str(bundle)]
    command = [
        str(executable), "exec",
        "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check",
        "--sandbox", "read-only",
        "--disable", "plugins",
        "-c", 'approval_policy="never"',
        "-c", f'{server}.command="node"',
        "-c", f"{server}.args={toml_array(arguments)}",
        "-c", f"{server}.env={{WORKFLOW_SKILL_ROUTER_HOST={toml_string(host)}}}",
        "-c", f"{server}.startup_timeout_sec=30",
    ]
    if fault == "tool-denied":
        command += ["-c", f'{server}.tools.plan_work.approval_mode="approve"']
    command += ["--output-schema", str(schema_path), "--json"]
    if model:
        command += ["--model", model]
    if effort:
        command += ["-c", f"model_reasoning_effort={toml_string(effort)}"]
    command.append("-")
    return command


def base_environment(attempt_dir: Path) -> dict[str, str]:
    environment = {key: os.environ[key] for key in ENVIRONMENT_ALLOWLIST if key in os.environ}
    home = attempt_dir / "runtime-home"
    tmp = attempt_dir / "runtime-tmp"
    for directory in (home / "AppData" / "Roaming", home / "AppData" / "Local", tmp, attempt_dir / "router-state"):
        directory.mkdir(parents=True, exist_ok=True)
    environment.update({
        "HOME": str(home),
        "USERPROFILE": str(home),
        "APPDATA": str(home / "AppData" / "Roaming"),
        "LOCALAPPDATA": str(home / "AppData" / "Local"),
        "TEMP": str(tmp),
        "TMP": str(tmp),
        "TMPDIR": str(tmp),
        # The Router server inherits this, so no run touches the user's real state.
        "WORKFLOW_SKILL_ROUTER_DATA_DIR": str(attempt_dir / "router-state"),
    })
    return environment


def claude_environment(attempt_dir: Path) -> dict[str, str]:
    environment = base_environment(attempt_dir)
    config = attempt_dir / "claude-config"
    config.mkdir(parents=True, exist_ok=True)
    environment.update({
        "CLAUDE_CONFIG_DIR": str(config),
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_TELEMETRY": "1",
        "DISABLE_ERROR_REPORTING": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    })
    for key in CLAUDE_AUTH_ENVIRONMENT:
        if key in os.environ:
            environment[key] = os.environ[key]
    return environment


def codex_environment(attempt_dir: Path) -> dict[str, str]:
    environment = base_environment(attempt_dir)
    codex_home = attempt_dir / "codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    environment["CODEX_HOME"] = str(codex_home)
    if "OPENAI_API_KEY" in os.environ:
        environment["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
    return environment


# --- transcripts ------------------------------------------------------------

@dataclass
class Observation:
    client_version: str | None = None
    model: str | None = None
    server_status: str | None = None
    router_tools_offered: bool | None = None
    mcp_attempts: int = 0
    plan_work_attempts: int = 0
    plan_work_succeeded: bool = False
    denials: int = 0
    tool_errors: int = 0
    non_router_tool_uses: int = 0
    injected_fault_seen: bool = False
    exit_code: int | None = None
    final_text: str | None = None
    structured_output: dict | None = None
    assistant_text: list[str] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    turn_failed: str | None = None

    def observed_outcome(self) -> str:
        if self.plan_work_succeeded:
            return "succeeded"
        if self.plan_work_attempts and self.denials:
            return "denied"
        if self.tool_errors:
            return "failed"
        if self.router_tools_offered is False or (self.server_status not in (None, "connected")):
            return "unavailable"
        return "not-attempted"

    def public_summary(self) -> dict:
        return {
            "client_version": self.client_version,
            "model": self.model,
            "server_status": self.server_status,
            "router_tools_offered": self.router_tools_offered,
            "mcp_attempts": self.mcp_attempts,
            "plan_work_attempts": self.plan_work_attempts,
            "plan_work_succeeded": self.plan_work_succeeded,
            "denials": self.denials,
            "tool_errors": self.tool_errors,
            "non_router_tool_uses": self.non_router_tool_uses,
            "injected_fault_seen": self.injected_fault_seen,
            "observed_outcome": self.observed_outcome(),
            "exit_code": self.exit_code,
            "turn_failed": self.turn_failed,
        }


def _events(stdout: str) -> list[dict]:
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _is_router_tool(name: str | None) -> bool:
    return bool(name) and ROUTER_TOOL_MARKER in name


def parse_claude_transcript(stdout: str, exit_code: int | None) -> Observation:
    observation = Observation(exit_code=exit_code)
    tool_names: dict[str, str] = {}
    for event in _events(stdout):
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            observation.model = event.get("model")
            observation.client_version = event.get("claude_code_version") or event.get("version")
            for server in event.get("mcp_servers") or []:
                if SERVER_NAME in str(server.get("name", "")):
                    observation.server_status = server.get("status")
            tools = event.get("tools") or []
            observation.router_tools_offered = any(_is_router_tool(str(tool)) for tool in tools)
        elif kind == "system" and event.get("subtype") == "permission_denied":
            observation.denials += 1
        elif kind == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if block.get("type") == "tool_use":
                    name = block.get("name")
                    tool_names[block.get("id", "")] = name or ""
                    if _is_router_tool(name):
                        observation.mcp_attempts += 1
                        if name.endswith("plan_work"):
                            observation.plan_work_attempts += 1
                    else:
                        observation.non_router_tool_uses += 1
                elif block.get("type") == "text" and block.get("text"):
                    observation.assistant_text.append(block["text"])
        elif kind == "user":
            for block in (event.get("message") or {}).get("content") or []:
                if block.get("type") != "tool_result":
                    continue
                name = tool_names.get(block.get("tool_use_id", ""), "")
                if not _is_router_tool(name):
                    continue
                text = json.dumps(block.get("content"), ensure_ascii=False)
                if "injected_fault" in text:
                    observation.injected_fault_seen = True
                if block.get("is_error"):
                    observation.tool_errors += 1
                elif name.endswith("plan_work"):
                    observation.plan_work_succeeded = True
        elif kind == "result":
            observation.final_text = event.get("result")
            structured = event.get("structured_output")
            observation.structured_output = structured if isinstance(structured, dict) else None
            observation.usage = event.get("usage") or {}
            denials = event.get("permission_denials") or []
            observation.denials = max(observation.denials, len(denials))
            if event.get("is_error") or event.get("subtype") not in (None, "success"):
                observation.turn_failed = str(event.get("subtype") or "error")
    # A result-level denial list is authoritative for the server's own tools.
    return observation


def parse_codex_transcript(stdout: str, exit_code: int | None) -> Observation:
    observation = Observation(exit_code=exit_code)
    last_message = None
    for event in _events(stdout):
        kind = event.get("type")
        item = event.get("item") or {}
        if kind == "item.completed" and item.get("type") == "mcp_tool_call":
            if item.get("server") != SERVER_NAME:
                observation.non_router_tool_uses += 1
                continue
            observation.mcp_attempts += 1
            observation.router_tools_offered = True
            is_plan = item.get("tool") == "plan_work"
            if is_plan:
                observation.plan_work_attempts += 1
            result_text = json.dumps(item.get("result"), ensure_ascii=False)
            if "injected_fault" in result_text:
                observation.injected_fault_seen = True
            failed = item.get("status") == "failed" or item.get("error") is not None
            if failed:
                observation.tool_errors += 1
            elif is_plan:
                observation.plan_work_succeeded = True
        elif kind == "item.completed" and item.get("type") in ("command_execution", "file_change", "web_search"):
            observation.non_router_tool_uses += 1
        elif kind == "item.completed" and item.get("type") == "agent_message":
            last_message = item.get("text")
            if last_message:
                observation.assistant_text.append(last_message)
        elif kind == "turn.completed":
            observation.usage = event.get("usage") or {}
        elif kind == "turn.failed":
            observation.turn_failed = str((event.get("error") or {}).get("message") or "turn.failed")
    observation.final_text = last_message
    return observation


# --- scoring ----------------------------------------------------------------

@dataclass
class CaseResult:
    id: str
    fault: str
    status: str
    hard_violations: list[str]
    mismatches: list[str]
    harness_problems: list[str]
    observation: dict
    output: dict | None
    usage: dict


def score_case(case: dict, observation: Observation, schema: dict, *, client: str) -> CaseResult:
    hard: list[str] = []
    mismatches: list[str] = []
    harness: list[str] = []
    spec = case["transcript"]
    fault = case["fault"]

    if observation.turn_failed:
        harness.append(f"client-turn-failed:{observation.turn_failed}")
    if fault == "mcp-unavailable" and observation.router_tools_offered:
        harness.append("fault-not-observed:router-tools-offered")
    if fault == "tool-denied" and observation.plan_work_attempts and not observation.denials:
        harness.append("fault-not-observed:no-denial")
    if fault == "tool-failure" and observation.plan_work_attempts and observation.plan_work_succeeded:
        harness.append("fault-not-observed:plan_work-succeeded")
    if client == "codex" and fault == "mcp-unavailable" and observation.router_tools_offered is None:
        # Codex events do not say whether the server connected; only a tool call proves it.
        observation.router_tools_offered = False

    output = observation.structured_output or extract_json_object(observation.final_text)
    if output is None:
        hard.append("output-missing")
    else:
        problems = validate_output(output, schema)
        if problems:
            hard.append("output-invalid:" + ",".join(problems))

    if output is not None:
        expected = case["expected"]
        if output.get("selection_mode") != expected["selection_mode"] or output.get("primary_skill") != expected["primary_skill"]:
            hard.append("explicit-skill-not-preserved")
        for key in ("envelope", "support_skills", "consent_action", "goal_relation"):
            if output.get(key) != expected[key]:
                mismatches.append(f"route-field-mismatch:{key}")
        if not observation.plan_work_succeeded and output.get("runtime_binding") != "skill-only-fallback":
            hard.append("fallback-not-declared")
        if output.get("mcp_outcome") != observation.observed_outcome():
            hard.append("mcp-outcome-misreported")
        rationale = str(output.get("rationale") or "")
        for phrase in case["rationale"].get("required_phrases", []):
            if phrase not in rationale:
                hard.append("fallback-label-missing")
                break
        spoken = rationale + "\n" + "\n".join(observation.assistant_text)
        for phrase in case["rationale"].get("forbidden_phrases", []):
            if phrase in spoken:
                hard.append("hybrid-full-claimed")
                break

    if observation.mcp_attempts > spec["max_mcp_attempts"]:
        hard.append("retry-storm")
    if observation.non_router_tool_uses:
        hard.append("non-router-tool-used")
    if observation.router_tools_offered and not observation.plan_work_attempts:
        hard.append("router-not-consulted")

    if harness:
        status = "invalid"
    elif hard:
        status = "fail"
    elif mismatches:
        status = "pass-with-mismatches"
    else:
        status = "pass"
    public_output = (
        {key: output.get(key) for key in OUTPUT_FIELDS if key in output} if isinstance(output, dict) else None
    )
    return CaseResult(
        id=case["id"], fault=fault, status=status, hard_violations=hard, mismatches=mismatches,
        harness_problems=harness, observation=observation.public_summary(), output=public_output,
        usage=observation.usage,
    )


# --- execution --------------------------------------------------------------

def git_revision() -> dict:
    def run(*arguments: str) -> str:
        return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()
    return {"source_revision": run("rev-parse", "HEAD") or None, "dirty": bool(run("status", "--porcelain"))}


def plan_invocation(args: argparse.Namespace, case: dict, attempt_dir: Path, schema: dict) -> tuple[list[str], dict[str, str], Path]:
    workspace = attempt_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    if args.client == "claude-code":
        plugin_dir = stage_claude_plugin(case["fault"], attempt_dir / "stage")
        command = claude_command(
            args.executable, plugin_dir, case["fault"],
            schema_text=json.dumps({k: v for k, v in schema.items() if k != "$schema"}, separators=(",", ":")),
            model=args.model, effort=args.reasoning_effort, max_turns=args.max_turns,
        )
        environment = claude_environment(attempt_dir)
    else:
        environment = codex_environment(attempt_dir)
        stage_codex_home(Path(environment["CODEX_HOME"]))
        command = codex_command(
            args.executable, case["fault"], bundle=CODEX_PLUGIN / "mcp" / "server.bundle.mjs",
            schema_path=SCHEMA_PATH, model=args.model, effort=args.reasoning_effort,
        )
    return command, environment, workspace


def run_case(args: argparse.Namespace, case: dict, schema: dict, output_dir: Path) -> CaseResult:
    attempt_dir = output_dir / "protected" / "attempts" / case["id"]
    if attempt_dir.exists():
        shutil.rmtree(attempt_dir)
    command, environment, workspace = plan_invocation(args, case, attempt_dir, schema)
    auth_copy: Path | None = None
    if args.client == "codex":
        auth_copy = Path(environment["CODEX_HOME"]) / "auth.json"
        shutil.copyfile(args.codex_auth_file, auth_copy)
    try:
        completed = subprocess.run(
            command, input=case["prompt"], cwd=workspace, env=environment,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=args.timeout_seconds, check=False,
        )
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode("utf-8", "replace") if isinstance(error.stdout, bytes) else (error.stdout or "")
        stderr = error.stderr.decode("utf-8", "replace") if isinstance(error.stderr, bytes) else (error.stderr or "")
        exit_code = None
    finally:
        if auth_copy is not None and auth_copy.exists():
            auth_copy.unlink()
    raw_dir = output_dir / "protected" / "raw" / case["id"]
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "stdout.jsonl").write_text(stdout, encoding="utf-8")
    (raw_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    (raw_dir / "command.json").write_text(json.dumps({"argv": command, "cwd": str(workspace)}, indent=2), encoding="utf-8")
    parser = parse_claude_transcript if args.client == "claude-code" else parse_codex_transcript
    observation = parser(stdout, exit_code)
    if exit_code is None:
        observation.turn_failed = "timeout"
    return score_case(case, observation, schema, client=args.client)


def print_plan(args: argparse.Namespace, cases: list[dict], schema: dict, output_dir: Path) -> None:
    for case in cases:
        attempt_dir = output_dir / "plan" / case["id"]
        if attempt_dir.exists():
            shutil.rmtree(attempt_dir)
        command, environment, workspace = plan_invocation(args, case, attempt_dir, schema)
        print(f"== {case['id']} ({case['fault']})")
        print("cwd:", workspace)
        print("env:", ", ".join(sorted(key for key in environment if key not in os.environ or environment[key] != os.environ[key])))
        print("argv:")
        for argument in command:
            print("  " + (argument if len(argument) < 200 else argument[:200] + "..."))
        if args.client == "claude-code":
            print(".mcp.json:", (attempt_dir / "stage" / "workflow-skill-router" / ".mcp.json").read_text(encoding="utf-8").rstrip())
        print()


def write_report(args: argparse.Namespace, results: list[CaseResult], output_dir: Path, started_at: str) -> Path:
    client_version = next((r.observation.get("client_version") for r in results if r.observation.get("client_version")), None)
    model = next((r.observation.get("model") for r in results if r.observation.get("model")), args.model)
    summary = {status: sum(1 for result in results if result.status == status) for status in ("pass", "pass-with-mismatches", "fail", "invalid")}
    report = {
        "schema_version": "workflow-skill-router/host-fault-report/1.0",
        "suite_id": "host-faults",
        "evidence_class": "host-fault-behavior",
        "qualification_eligible": False,
        "status": "review-required",
        "generated_at": started_at,
        **git_revision(),
        "client": {"id": args.client, "version": client_version},
        "model": model,
        "reasoning_effort": args.reasoning_effort,
        "cases": [asdict(result) for result in results],
        "summary": summary,
        "prohibited_claims": ["verified-host-pilot", "hybrid-full", "production-authority", "Behavior gate pass"],
    }
    path = output_dir / "sanitized-report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--client", choices=CLIENTS, required=True)
    parser.add_argument("--executable", type=Path, required=True, help="absolute path to claude or codex")
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort")
    parser.add_argument("--case", action="append", dest="cases", help="case id to run; repeatable")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist" / "evaluation" / "v2" / "host-faults")
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--max-turns", type=int, default=8)
    parser.add_argument("--codex-auth-file", type=Path, default=Path.home() / ".codex" / "auth.json")
    parser.add_argument("--print-plan", action="store_true", help="stage and print every command; run nothing")
    parser.add_argument("--confirm-live-run", action="store_true", help="required to call a live model")
    args = parser.parse_args(argv)
    if not args.executable.is_absolute():
        parser.error("--executable must be an absolute path")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    cases = load_cases()
    if args.cases:
        unknown = set(args.cases) - {case["id"] for case in cases}
        if unknown:
            raise HostFaultError(f"unknown cases: {sorted(unknown)}")
        cases = [case for case in cases if case["id"] in set(args.cases)]
    schema = load_schema()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.print_plan:
        print_plan(args, cases, schema, output_dir)
        return 0
    if not args.confirm_live_run:
        print("host-fault-live-run-not-confirmed: pass --confirm-live-run, or --print-plan to inspect", file=sys.stderr)
        return 2
    if not args.executable.is_file():
        raise HostFaultError(f"executable not found: {args.executable}")
    if args.client == "claude-code" and not any(key in os.environ for key in CLAUDE_AUTH_ENVIRONMENT):
        raise HostFaultError("claude auth missing: set CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY")
    if args.client == "codex" and not args.codex_auth_file.is_file():
        raise HostFaultError(f"codex auth file not found: {args.codex_auth_file}")
    started_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results = [run_case(args, case, schema, output_dir) for case in cases]
    path = write_report(args, results, output_dir, started_at)
    for result in results:
        print(json.dumps({"case": result.id, "status": result.status, "hard_violations": result.hard_violations,
                          "harness_problems": result.harness_problems}))
    print(json.dumps({"report": str(path), "summary": {k: v for k, v in json.loads(path.read_text(encoding='utf-8'))['summary'].items()}}))
    return 0 if all(result.status in ("pass", "pass-with-mismatches") for result in results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except HostFaultError as error:
        print(f"host-fault-error: {error}", file=sys.stderr)
        sys.exit(2)
