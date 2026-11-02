import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "plugins" / "workflow-skill-router" / "mcp" / "server.bundle.mjs"
NODE = shutil.which("node")


class McpSession:
    """Minimal stdio JSON-RPC client against the bundled server."""

    def __init__(self, environment: dict[str, str], cwd: Path) -> None:
        self.process = subprocess.Popen(
            [NODE or "node", str(BUNDLE)], cwd=cwd, env=environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
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
                raise AssertionError(f"MCP request timed out: {method}\n{''.join(self.diagnostics)}")
            if message.get("id") == self.sequence and "method" not in message:
                return message

    def notify(self, method: str) -> None:
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.process.stdin.flush()

    def close(self) -> None:
        if not self.process.stdin.closed:
            self.process.stdin.close()
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=10)
        for stream in (self.process.stdout, self.process.stderr):
            stream.close()


@unittest.skipIf(NODE is None, "Node.js is required for the MCP plan_work test")
class PlanWorkExplicitSkillIdTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        environment = {key: value for key, value in os.environ.items() if not key.startswith("WORKFLOW_SKILL_ROUTER_")}
        environment["WORKFLOW_SKILL_ROUTER_DATA_DIR"] = str(self.root / "state")
        self.session = McpSession(environment, cwd=self.root)
        initialized = self.session.request("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "plan-work-skill-id-test", "version": "1.0.0"},
        })
        self.assertNotIn("error", initialized, "".join(self.session.diagnostics))
        self.session.notify("notifications/initialized")

    def tearDown(self) -> None:
        self.session.close()
        self.directory.cleanup()

    def plan_work(self, skill_ids: list[str], key: str) -> dict:
        response = self.session.request("tools/call", {"name": "plan_work", "arguments": {
            "context": {"session_id": "plan-work-skill-id-test", "actor": "test", "runtime_policy_snapshot_id": "policy-test"},
            "expected_state_version": 0,
            "idempotency_key": key,
            "correlation_id": "plan-work-skill-id-test",
            "objective": "Add a regression test for the date parser bug.",
            "goal_binding_id": None,
            "requested_work_mode": None,
            "explicit_skill_ids": skill_ids,
            "explicit_semantics": "use",
            "routing_context": {"workspace_root": None, "domains": [], "tags": [], "current_phase_id": None},
        }})
        self.assertNotIn("error", response, json.dumps(response, ensure_ascii=False))
        return response["result"]

    def test_bare_skill_name_plans_with_the_canonical_id(self) -> None:
        # A real Claude Code session sends the Skill name as the user wrote it; this used to be internal-error.
        result = self.plan_work(["python-test-writer"], "bare-1")

        self.assertNotIn("isError", result, json.dumps(result, ensure_ascii=False))
        plan = result["structuredContent"]
        self.assertEqual("explicit-locked", plan["selection_mode"])
        self.assertEqual(["skill:python-test-writer"], plan["planned_skill_ids"])
        self.assertNotIn("LocalWorkGraphCorruption", "".join(self.session.diagnostics))

    def test_other_forms_are_a_public_invalid_arguments_error(self) -> None:
        result = self.plan_work(["Bad Name"], "bad-1")

        self.assertTrue(result.get("isError"), json.dumps(result, ensure_ascii=False))
        details = json.loads(result["content"][0]["text"])
        self.assertEqual({"code": "invalid-arguments", "message": "explicit-skill-id-not-canonical"}, details)
        self.assertNotIn("Bad Name", json.dumps(result))
        self.assertNotIn("internal-error", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
