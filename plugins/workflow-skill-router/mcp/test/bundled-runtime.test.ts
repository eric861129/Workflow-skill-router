import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, readFile, rmdir, unlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

type JsonRpcResponse = { id?: number; result?: Record<string, unknown>; error?: unknown };

const INITIALIZE_PARAMS = {
  protocolVersion: "2025-06-18",
  capabilities: {},
  clientInfo: { name: "runtime-version-test", version: "1.0.0" },
};
const MUTATED_MCP_SERVER_VERSION = "9.9.9";
const fakeBridge = String.raw`import sys

for _ in sys.stdin:
    pass
`;

async function initializedServerInfo(pluginRoot: string): Promise<Record<string, unknown>> {
  const stateDirectory = await mkdtemp(path.join(os.tmpdir(), "workflow-skill-router-version-"));
  const child = spawn(process.execPath, [path.join(pluginRoot, "mcp", "server.bundle.mjs")], {
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

  try {
    const initialized = await request(1, "initialize", INITIALIZE_PARAMS);
    assert.equal(initialized.error, undefined, JSON.stringify(initialized));
    const serverInfo = initialized.result?.serverInfo;
    assert.equal(typeof serverInfo, "object", JSON.stringify(initialized));
    assert.notEqual(serverInfo, null, JSON.stringify(initialized));
    return serverInfo as Record<string, unknown>;
  } finally {
    child.kill();
    await new Promise<void>((resolve) => {
      if (child.exitCode !== null) return resolve();
      child.once("exit", () => resolve());
      setTimeout(resolve, 2_000);
    });
    for (const name of ["router-v2.sqlite3", "router-v2.sqlite3-wal", "router-v2.sqlite3-shm"]) {
      await unlink(path.join(stateDirectory, name)).catch((error: NodeJS.ErrnoException) => {
        if (error.code !== "ENOENT") throw error;
      });
    }
    await rmdir(stateDirectory);
  }
}

test("bundled MCP server resolves the runtime inside the installed plugin", async () => {
  const parent = path.resolve(import.meta.dirname, "..");
  const pluginRoot = path.basename(parent) === "mcp" ? path.resolve(parent, "..") : parent;
  const stateDirectory = await mkdtemp(path.join(os.tmpdir(), "workflow-skill-router-test-"));
  const child = spawn(process.execPath, [path.join(pluginRoot, "mcp", "server.bundle.mjs")], {
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

  try {
    const initialized = await request(1, "initialize", {
      protocolVersion: "2025-06-18",
      capabilities: {},
      clientInfo: { name: "bundled-runtime-test", version: "1.0.0" },
    });
    assert.equal(initialized.error, undefined);
    child.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized", params: {} }) + "\n");
    const response = await request(2, "tools/call", {
      name: "get_router_status",
      arguments: {
        context: {
          session_id: "bundled-runtime-test",
          actor: "test",
          runtime_policy_snapshot_id: "policy-test",
        },
        goal_binding_id: null,
        workflow_run_id: null,
      },
    });
    assert.equal(response.error, undefined);
    const result = response.result as { isError?: boolean; content?: Array<{ text?: string }> };
    assert.equal(result.isError, undefined);
    assert.match(String(result.content?.[0]?.text), /created_work_items/);

    const planResponse = await request(3, "tools/call", {
      name: "plan_work",
      arguments: {
        context: {
          session_id: "bundled-runtime-test",
          actor: "test",
          runtime_policy_snapshot_id: "policy-test",
        },
        expected_state_version: 0,
        idempotency_key: "bundled-runtime-plan",
        correlation_id: "bundled-runtime-test",
        objective: "修正一個小型文件問題",
        goal_binding_id: null,
        requested_work_mode: "single",
        explicit_skill_ids: [],
        explicit_semantics: null,
      },
    });
    assert.equal(planResponse.error, undefined);
    const planResult = planResponse.result as {
      isError?: boolean;
      structuredContent?: Record<string, unknown>;
    };
    assert.equal(planResult.isError, undefined, JSON.stringify(planResponse));
    assert.equal(planResult.structuredContent?.selection_mode, "auto");
    assert.equal(planResult.structuredContent?.support_consent_required, false);

    const explicitPlanResponse = await request(4, "tools/call", {
      name: "plan_work",
      arguments: {
        context: {
          session_id: "bundled-runtime-test",
          actor: "test",
          runtime_policy_snapshot_id: "policy-test",
        },
        expected_state_version: 0,
        idempotency_key: "bundled-runtime-explicit-plan",
        correlation_id: "bundled-runtime-explicit-plan",
        objective: "使用指定 API SKILL，並在目前 Phase 提案必要支援",
        goal_binding_id: null,
        requested_work_mode: "phased",
        explicit_skill_ids: ["skill:api-designer"],
        explicit_semantics: "use",
      },
    });
    const explicitPlan = explicitPlanResponse.result as {
      structuredContent?: Record<string, unknown>;
    };
    assert.equal(explicitPlan.structuredContent?.selection_mode, "explicit-locked");

    const requiredAllPlanResponse = await request(10, "tools/call", {
      name: "plan_work",
      arguments: {
        context: {
          session_id: "bundled-runtime-test",
          actor: "test",
          runtime_policy_snapshot_id: "policy-test",
        },
        expected_state_version: 0,
        idempotency_key: "bundled-runtime-required-all-plan",
        correlation_id: "bundled-runtime-required-all-plan",
        objective: "Use both named skills before completion.",
        goal_binding_id: null,
        requested_work_mode: "single",
        explicit_skill_ids: ["skill:api-designer", "skill:qa-test-planner"],
        explicit_semantics: "all",
      },
    });
    assert.equal(requiredAllPlanResponse.error, undefined, JSON.stringify(requiredAllPlanResponse));
    const requiredAllPlan = requiredAllPlanResponse.result as {
      isError?: boolean;
      structuredContent?: Record<string, unknown>;
    };
    assert.equal(requiredAllPlan.isError, undefined, JSON.stringify(requiredAllPlanResponse));
    assert.equal(requiredAllPlan.structuredContent?.selection_mode, "explicit-locked");
    assert.deepEqual(
      requiredAllPlan.structuredContent?.planned_skill_ids,
      ["skill:api-designer", "skill:qa-test-planner"],
    );

    const proposalResponse = await request(5, "tools/call", {
      name: "propose_support_consent",
      arguments: {
        context: {
          session_id: "bundled-runtime-test",
          actor: "test",
          runtime_policy_snapshot_id: "policy-test",
        },
        expected_state_version: 1,
        idempotency_key: "bundled-runtime-proposal",
        correlation_id: "bundled-runtime-proposal",
        workflow_run_id: String(explicitPlan.structuredContent?.workflow_run_id),
        phase_id: "phase-contract-verification",
        scope_anchor_id: "scope:phase-contract-verification",
        goal_revision: null,
        plan_revision: 1,
        primary_skill_id: "skill:api-designer",
        support_skill_ids: ["skill:qa-test-planner"],
        context_fingerprint: `sha256:${"a".repeat(64)}`,
      },
    });
    assert.equal(proposalResponse.error, undefined, JSON.stringify(proposalResponse));
    const proposal = proposalResponse.result as {
      isError?: boolean;
      structuredContent?: Record<string, unknown>;
    };
    assert.equal(proposal.isError, undefined, JSON.stringify(proposalResponse));
    assert.equal(proposal.structuredContent?.consent_action, "proposal-required");

    const transitionResponse = await request(6, "tools/call", {
      name: "transition_support_consent",
      arguments: {
        context: {
          session_id: "bundled-runtime-test",
          actor: "test",
          runtime_policy_snapshot_id: "policy-test",
        },
        expected_state_version: 1,
        idempotency_key: "bundled-runtime-approval",
        correlation_id: "bundled-runtime-approval",
        proposal_id: String(proposal.structuredContent?.proposal_id),
        action: "approve",
        current_phase_id: "phase-contract-verification",
        current_scope_anchor_id: "scope:phase-contract-verification",
        current_goal_revision: null,
        current_plan_revision: 1,
        current_context_fingerprint: `sha256:${"a".repeat(64)}`,
      },
    });
    const transition = transitionResponse.result as {
      structuredContent?: Record<string, unknown>;
    };
    assert.equal(transition.structuredContent?.consent_action, "approved");
    assert.equal(transition.structuredContent?.primary_skill, "skill:api-designer");
    assert.deepEqual(
      transition.structuredContent?.support_skills,
      ["skill:qa-test-planner"],
    );

    const localNextResponse = await request(7, "tools/call", {
      name: "get_next_work",
      arguments: {
        context: {
          session_id: "bundled-runtime-test",
          actor: "test",
          runtime_policy_snapshot_id: "policy-test",
        },
        workflow_run_id: String(planResult.structuredContent?.workflow_run_id),
      },
    });
    assert.equal(localNextResponse.error, undefined);
    const localNextResult = localNextResponse.result as {
      isError?: boolean;
      structuredContent?: Record<string, unknown>;
    };
    assert.equal(localNextResult.isError, undefined, JSON.stringify(localNextResponse));
    assert.equal(localNextResult.structuredContent?.authority_mode, "router-local");
    assert.equal(localNextResult.structuredContent?.host_goal_mutated, false);

    const nativeGoalPlanResponse = await request(8, "tools/call", {
      name: "plan_work",
      arguments: {
        context: {
          session_id: "bundled-runtime-native-goal",
          actor: "test",
          runtime_policy_snapshot_id: "policy-test",
        },
        expected_state_version: 0,
        idempotency_key: "bundled-runtime-native-goal-plan",
        correlation_id: "bundled-runtime-native-goal-plan",
        objective: "Continue a Host-managed Goal without granting local Host authority.",
        goal_binding_id: "native-goal:test",
        requested_work_mode: "managed-goal",
        explicit_skill_ids: [],
        explicit_semantics: null,
      },
    });
    const nativeGoalPlan = nativeGoalPlanResponse.result as {
      isError?: boolean;
      structuredContent?: Record<string, unknown>;
    };
    assert.equal(nativeGoalPlan.isError, undefined, JSON.stringify(nativeGoalPlanResponse));

    const unavailableResponse = await request(9, "tools/call", {
      name: "get_next_work",
      arguments: {
        context: {
          session_id: "bundled-runtime-native-goal",
          actor: "test",
          runtime_policy_snapshot_id: "policy-test",
        },
        workflow_run_id: String(nativeGoalPlan.structuredContent?.workflow_run_id),
      },
    });
    assert.equal(unavailableResponse.error, undefined);
    const unavailableResult = unavailableResponse.result as {
      isError?: boolean;
      content?: Array<{ text?: string }>;
    };
    assert.equal(unavailableResult.isError, true);
    assert.match(String(unavailableResult.content?.[0]?.text), /capability-unavailable/);
    assert.match(String(unavailableResult.content?.[0]?.text), /verified-host-scheduler/);
  } finally {
    child.kill();
    await new Promise<void>((resolve) => {
      if (child.exitCode !== null) return resolve();
      child.once("exit", () => resolve());
      setTimeout(resolve, 2_000);
    });
    for (const name of ["router-v2.sqlite3", "router-v2.sqlite3-wal", "router-v2.sqlite3-shm"]) {
      await unlink(path.join(stateDirectory, name)).catch((error: NodeJS.ErrnoException) => {
        if (error.code !== "ENOENT") throw error;
      });
    }
    await rmdir(stateDirectory);
  }
});

test("shipped MCP bundle advertises release metadata through MCP_SERVER_VERSION", async () => {
  const parent = path.resolve(import.meta.dirname, "..");
  const sourcePluginRoot = path.basename(parent) === "mcp" ? path.resolve(parent, "..") : parent;
  const release = JSON.parse(await readFile(
    path.resolve(sourcePluginRoot, "..", "..", "release", "version.json"),
    "utf8",
  )) as { v2_version: string };

  const shippedServerInfo = await initializedServerInfo(sourcePluginRoot);
  assert.equal(shippedServerInfo.version, release.v2_version);

  const root = await mkdtemp(path.join(os.tmpdir(), "workflow-skill-router-version-mutation-"));
  const pluginRoot = path.join(root, "plugin");
  const mcpDirectory = path.join(pluginRoot, "mcp");
  const runtimeDirectory = path.join(pluginRoot, "runtime");
  await mkdir(mcpDirectory, { recursive: true });
  await mkdir(runtimeDirectory);

  try {
    const bundle = await readFile(path.join(sourcePluginRoot, "mcp", "server.bundle.mjs"), "utf8");
    const mutatedBundle = bundle.replace(
      /^var MCP_SERVER_VERSION = "[^"]+";$/m,
      `var MCP_SERVER_VERSION = "${MUTATED_MCP_SERVER_VERSION}";`,
    );
    assert.notEqual(mutatedBundle, bundle, "The shipped bundle must declare MCP_SERVER_VERSION");
    await writeFile(path.join(mcpDirectory, "server.bundle.mjs"), mutatedBundle, "utf8");
    await writeFile(path.join(runtimeDirectory, "workflow_skill_router.pyz"), fakeBridge, "utf8");

    const mutatedServerInfo = await initializedServerInfo(pluginRoot);
    assert.equal(mutatedServerInfo.version, MUTATED_MCP_SERVER_VERSION);
  } finally {
    await unlink(path.join(mcpDirectory, "server.bundle.mjs")).catch((error: NodeJS.ErrnoException) => {
      if (error.code !== "ENOENT") throw error;
    });
    await unlink(path.join(runtimeDirectory, "workflow_skill_router.pyz")).catch((error: NodeJS.ErrnoException) => {
      if (error.code !== "ENOENT") throw error;
    });
    await rmdir(mcpDirectory);
    await rmdir(runtimeDirectory);
    await rmdir(pluginRoot);
    await rmdir(root);
  }
});
