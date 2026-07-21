import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { copyFile, mkdir, mkdtemp, rmdir, unlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

type JsonRpcResponse = { id?: number; result?: Record<string, unknown>; error?: unknown };

const fakeBridge = String.raw`import json
import sys

for line in sys.stdin:
    request = json.loads(line)
    tool = request["tool"]
    arguments = request.get("arguments", {})
    if tool == "get_next_work":
        if arguments["workflow_run_id"].endswith("host-top"):
            result = {
                "status": "ready",
                "refresh_requirements": [],
                "work_item": {
                    "work_item_id": "work-item:local",
                    "workflow_run_id": "workflow:local",
                    "phase_id": "single-work",
                    "dependency_ids": [],
                    "primary_skill_id": None,
                    "support_skill_ids": [],
                    "status": "ready",
                    "authority_mode": "router-local",
                },
                "authority_mode": "verified-host",
                "host_goal_mutated": False,
            }
        else:
            result = {
                "status": "ready",
                "refresh_requirements": [],
                "work_item": {
                    "work_item_id": "work-item:host",
                    "routing_envelope": "single",
                    "status": "ready",
                },
                "authority_mode": "router-local",
                "host_goal_mutated": False,
            }
    else:
        if arguments["correlation_id"].endswith("host-status"):
            result = {
                "status": "evaluated-local",
                "passed": True,
                "mandatory_failures": [],
                "evidence_digest": "sha256:" + "a" * 64,
            }
        else:
            result = {
                "status": "evaluated-local",
                "passed": True,
                "failures": ["missing-local-check:tests-passed"],
                "evidence_digest": "sha256:" + "b" * 64,
                "resulting_state_version": 4,
                "replayed": False,
                "gate_scope": "router-local",
                "authority_mode": "router-local",
                "evidence_class": "user-or-agent-reported-local",
                "host_transition_authorized": False,
            }
    print(json.dumps({"request_id": request["request_id"], "ok": True, "result": result}), flush=True)
`;

test("bundled MCP server rejects forged cross-lane and contradictory runtime results", async () => {
  const sourceParent = path.resolve(import.meta.dirname, "..");
  const sourcePluginRoot = path.basename(sourceParent) === "mcp"
    ? path.resolve(sourceParent, "..")
    : sourceParent;
  const root = await mkdtemp(path.join(os.tmpdir(), "workflow-skill-router-forged-"));
  const pluginRoot = path.join(root, "plugin");
  const mcpDirectory = path.join(pluginRoot, "mcp");
  const runtimeDirectory = path.join(pluginRoot, "runtime");
  const stateDirectory = path.join(root, "state");
  await mkdir(mcpDirectory, { recursive: true });
  await mkdir(runtimeDirectory);
  await mkdir(stateDirectory);
  await copyFile(
    path.join(sourcePluginRoot, "mcp", "server.bundle.mjs"),
    path.join(mcpDirectory, "server.bundle.mjs"),
  );
  await writeFile(path.join(runtimeDirectory, "workflow_skill_router.pyz"), fakeBridge, "utf8");

  const child = spawn(process.execPath, [path.join(mcpDirectory, "server.bundle.mjs")], {
    cwd: pluginRoot,
    env: { ...process.env, WORKFLOW_SKILL_ROUTER_DATA_DIR: stateDirectory },
    shell: false,
    stdio: ["pipe", "pipe", "pipe"],
  });
  const pending = new Map<number, (response: JsonRpcResponse) => void>();
  let buffer = "";
  let diagnostics = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk: string) => { diagnostics += chunk; });
  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk: string) => {
    buffer += chunk;
    for (;;) {
      const newline = buffer.indexOf("\n");
      if (newline < 0) break;
      const line = buffer.slice(0, newline);
      buffer = buffer.slice(newline + 1);
      const response = JSON.parse(line) as JsonRpcResponse;
      if (response.id !== undefined) pending.get(response.id)?.(response);
    }
  });
  const request = (id: number, method: string, params: Record<string, unknown>) =>
    new Promise<JsonRpcResponse>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error(
        `MCP request timed out: ${method}\n${diagnostics}`,
      )), 10_000);
      pending.set(id, (response) => {
        clearTimeout(timeout);
        pending.delete(id);
        resolve(response);
      });
      child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
    });
  const context = {
    session_id: "forged-runtime-test",
    actor: "test",
    runtime_policy_snapshot_id: "policy-test",
  };

  try {
    const initialized = await request(1, "initialize", {
      protocolVersion: "2025-06-18",
      capabilities: {},
      clientInfo: { name: "forged-runtime-test", version: "1.0.0" },
    });
    assert.equal(initialized.error, undefined);
    child.stdin.write(JSON.stringify({
      jsonrpc: "2.0", method: "notifications/initialized", params: {},
    }) + "\n");

    const calls = [
      { name: "get_next_work", arguments: { context, workflow_run_id: "workflow:local-top" } },
      { name: "get_next_work", arguments: { context, workflow_run_id: "workflow:host-top" } },
      {
        name: "evaluate_gate",
        arguments: {
          context, workflow_run_id: "workflow:host", phase_id: "phase-1",
          expected_state_version: 1, expected_plan_revision: 1,
          expected_evidence_digest: `sha256:${"a".repeat(64)}`,
          evidence_refs: [], idempotency_key: "gate-host-status",
          correlation_id: "gate-host-status",
        },
      },
      {
        name: "evaluate_gate",
        arguments: {
          context, workflow_run_id: "workflow:local", phase_id: "phase-1",
          expected_state_version: 1, expected_plan_revision: 1,
          expected_evidence_digest: `sha256:${"b".repeat(64)}`,
          evidence_refs: [], idempotency_key: "gate-local-contradiction",
          correlation_id: "gate-local-contradiction",
        },
      },
    ];
    for (const [index, call] of calls.entries()) {
      const response = await request(index + 2, "tools/call", call);
      const result = response.result as { isError?: boolean } | undefined;
      assert.ok(response.error !== undefined || result?.isError === true, JSON.stringify(response));
    }
  } finally {
    child.kill();
    await new Promise<void>((resolve) => {
      if (child.exitCode !== null) return resolve();
      child.once("exit", () => resolve());
      setTimeout(resolve, 2_000);
    });
    await unlink(path.join(mcpDirectory, "server.bundle.mjs"));
    await unlink(path.join(runtimeDirectory, "workflow_skill_router.pyz"));
    await rmdir(mcpDirectory);
    await rmdir(runtimeDirectory);
    await rmdir(stateDirectory);
    await rmdir(pluginRoot);
    await rmdir(root);
  }
});
