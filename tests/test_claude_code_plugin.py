from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "claude-code" / "workflow-skill-router"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
SKILL = PLUGIN / "skills" / "workflow-skill-router" / "SKILL.md"
RESERVED_NAME_PREFIXES = ("claude-", "anthropic-", "anthropics-", "cc-plugin-")
TOOL_PREFIX = "mcp__plugin_workflow-skill-router_workflow-skill-router__"

sys.path.insert(0, str(ROOT / "packages" / "router-core" / "src"))

from workflow_skill_router.hosts import HOST_ENVIRONMENT_VARIABLE, HOST_PROFILES


def load_sync_module():
    spec = importlib.util.spec_from_file_location(
        "sync_claude_plugin", ROOT / "scripts" / "sync-claude-plugin.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def skill_frontmatter() -> dict[str, str]:
    text = SKILL.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert match is not None
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


class ClaudeCodePluginLayoutTests(unittest.TestCase):
    def test_generated_files_match_their_canonical_sources(self) -> None:
        self.assertEqual([], load_sync_module().problems())

    def test_manifest_uses_an_allowed_name_and_tracks_commits(self) -> None:
        manifest = read_json(PLUGIN / ".claude-plugin" / "plugin.json")
        self.assertEqual(PLUGIN.name, manifest["name"])
        self.assertFalse(manifest["name"].startswith(RESERVED_NAME_PREFIXES))
        self.assertRegex(manifest["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        # 尚未進入 release 管線前不宣告版本，避免讓人以為它屬於已發布的 v2.0.2。
        self.assertNotIn("version", manifest)
        self.assertTrue(manifest["homepage"].startswith("https://"))
        self.assertEqual(
            [".claude-plugin/plugin.json"],
            [path.relative_to(PLUGIN).as_posix() for path in (PLUGIN / ".claude-plugin").iterdir()],
        )

    def test_plugin_ships_no_npm_manifest_to_install(self) -> None:
        self.assertFalse((PLUGIN / "package.json").exists())
        self.assertFalse((PLUGIN / "package-lock.json").exists())

    def test_marketplace_exposes_the_plugin_from_this_repository(self) -> None:
        marketplace = read_json(MARKETPLACE)
        self.assertEqual("workflow-skill-router", marketplace["name"])
        self.assertTrue(marketplace["owner"]["name"])
        self.assertEqual(1, len(marketplace["plugins"]))
        entry = marketplace["plugins"][0]
        self.assertEqual(read_json(PLUGIN / ".claude-plugin" / "plugin.json")["name"], entry["name"])
        self.assertEqual("./plugins/claude-code/workflow-skill-router", entry["source"])
        self.assertEqual(PLUGIN.resolve(), (ROOT / entry["source"]).resolve())
        self.assertNotIn("version", entry)

    def test_mcp_server_is_rooted_in_the_plugin_and_pins_the_claude_host(self) -> None:
        servers = read_json(PLUGIN / ".mcp.json")["mcpServers"]
        self.assertEqual(["workflow-skill-router"], list(servers))
        server = servers["workflow-skill-router"]
        self.assertEqual("node", server["command"])
        self.assertEqual(["${CLAUDE_PLUGIN_ROOT}/mcp/server.bundle.mjs"], server["args"])
        self.assertEqual({HOST_ENVIRONMENT_VARIABLE: "claude-code"}, server["env"])
        self.assertIn(server["env"][HOST_ENVIRONMENT_VARIABLE], HOST_PROFILES)

    def test_skill_frontmatter_and_links_are_valid_for_claude_code(self) -> None:
        fields = skill_frontmatter()
        self.assertEqual("workflow-skill-router", fields["name"])
        self.assertLessEqual(len(fields["description"]), 1536)
        self.assertIn("Claude Code", fields["description"])
        text = SKILL.read_text(encoding="utf-8")
        self.assertLess(len(text.splitlines()), 500)
        self.assertIn(TOOL_PREFIX, text)
        self.assertIn(".claude/workflow-skill-router.json", text)
        for link in re.findall(r"\]\((references/[^)]+)\)", text):
            self.assertTrue((SKILL.parent / link).is_file(), link)


class McpSession:
    def __init__(self, environment: dict[str, str], cwd: Path) -> None:
        self.process = subprocess.Popen(
            [shutil.which("node") or "node", str(PLUGIN / "mcp" / "server.bundle.mjs")],
            cwd=cwd,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self.lines: queue.Queue[str] = queue.Queue()
        self.diagnostics: list[str] = []
        # stdout 與 stderr 都由背景執行緒排空，避免管線塞滿或在斷言時阻塞。
        self.readers = [
            threading.Thread(target=self._read, daemon=True),
            threading.Thread(target=self._drain_stderr, daemon=True),
        ]
        for reader in self.readers:
            reader.start()
        self.sequence = 0

    def _read(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.lines.put(line)

    def _drain_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self.diagnostics.append(line)

    def request(self, method: str, params: dict) -> dict:
        self.sequence += 1
        request_id = self.sequence
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps({
            "jsonrpc": "2.0", "id": request_id, "method": method, "params": params,
        }) + "\n")
        self.process.stdin.flush()
        while True:
            try:
                message = json.loads(self.lines.get(timeout=30))
            except queue.Empty:
                self.close()
                raise AssertionError(f"MCP request timed out: {method}\n{self.stderr()}")
            if message.get("id") == request_id and "method" not in message:
                return message

    def notify(self, method: str) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.process.stdin.flush()

    def stderr(self) -> str:
        return "".join(self.diagnostics)

    def close(self) -> None:
        if self.process.stdin is not None and not self.process.stdin.closed:
            self.process.stdin.close()
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=10)
        for reader in self.readers:
            reader.join(timeout=10)
        for stream in (self.process.stdout, self.process.stderr):
            if stream is not None:
                stream.close()


def write_profile(workspace: Path, directory: str, profile_id: str) -> None:
    document = read_json(PLUGIN / "skills/workflow-skill-router/assets/workspace-routing-profile.example.json")
    document["profile_id"] = profile_id
    path = workspace / directory / "workflow-skill-router.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")


@unittest.skipIf(shutil.which("node") is None, "Node.js is required for the MCP smoke test")
class ClaudeCodePluginRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.workspace = self.root / "workspace"
        write_profile(self.workspace, ".codex", "workspace:codex-delivery")
        write_profile(self.workspace, ".claude", "workspace:claude-delivery")
        (self.root / "launch").mkdir()

    def tearDown(self) -> None:
        self.directory.cleanup()

    def environment(self, host: str | None) -> dict[str, str]:
        environment = {
            key: value for key, value in os.environ.items()
            if not key.startswith("WORKFLOW_SKILL_ROUTER_")
        }
        environment["WORKFLOW_SKILL_ROUTER_DATA_DIR"] = str(self.root / "state")
        environment["WORKFLOW_SKILL_ROUTER_WORKSPACE_ROOTS"] = str(self.workspace)
        environment["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN)
        if host is not None:
            environment[HOST_ENVIRONMENT_VARIABLE] = host
        return environment

    def plan_with_workspace_profile(self, host: str | None) -> dict:
        # 以非 Plugin 目錄作為 cwd，確認 server 不依賴 Claude Code 的啟動目錄。
        session = McpSession(self.environment(host), cwd=self.root / "launch")
        try:
            initialized = session.request("initialize", {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "claude-code-plugin-test", "version": "1.0.0"},
            })
            self.assertNotIn("error", initialized, session.stderr())
            session.notify("notifications/initialized")
            tools = session.request("tools/list", {})["result"]["tools"]
            self.assertIn("plan_work", {tool["name"] for tool in tools})
            response = session.request("tools/call", {
                "name": "plan_work",
                "arguments": {
                    "context": {
                        "session_id": "claude-code-plugin-test",
                        "actor": "test",
                        "runtime_policy_snapshot_id": "policy-test",
                    },
                    "expected_state_version": 0,
                    "idempotency_key": f"claude-code-plugin-{host}",
                    "correlation_id": "claude-code-plugin-test",
                    "objective": "Deliver the api contract, implementation, and tests.",
                    "goal_binding_id": None,
                    "requested_work_mode": None,
                    "explicit_skill_ids": [],
                    "explicit_semantics": None,
                    "routing_context": {
                        "workspace_root": str(self.workspace),
                        "domains": ["api"],
                        "tags": [],
                        "current_phase_id": None,
                    },
                },
            })
            result = response["result"]
            self.assertNotIn("isError", result, json.dumps(result, ensure_ascii=False))
            return result["structuredContent"]
        finally:
            session.close()

    def test_claude_host_plans_from_the_claude_workspace_profile(self) -> None:
        plan = self.plan_with_workspace_profile("claude-code")

        self.assertEqual("workspace-profile", plan["route_source"])
        self.assertEqual(["workspace:claude-delivery"], plan["routing_profile_ids"])
        self.assertEqual("intended-unverified", plan["activation_status"])
        self.assertEqual([], list((self.root / "launch").iterdir()))

    def test_default_host_keeps_reading_the_codex_workspace_profile(self) -> None:
        plan = self.plan_with_workspace_profile(None)

        self.assertEqual(["workspace:codex-delivery"], plan["routing_profile_ids"])

    def test_unknown_host_stops_before_serving_tools(self) -> None:
        result = subprocess.run(
            [shutil.which("node") or "node", str(PLUGIN / "mcp" / "server.bundle.mjs")],
            cwd=self.root / "launch",
            env=self.environment("claude"),
            input="",
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

        self.assertEqual(78, result.returncode)
        self.assertIn(HOST_ENVIRONMENT_VARIABLE, result.stderr)
        self.assertFalse((self.root / "state").exists())


if __name__ == "__main__":
    unittest.main()
