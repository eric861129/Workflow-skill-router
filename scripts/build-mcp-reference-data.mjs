import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, rmdir, unlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";


const root = path.resolve(import.meta.dirname, "..");
const pluginRoot = path.join(root, "plugins", "workflow-skill-router");
const output = path.join(root, "site", "src", "data", "mcp-tools.generated.json");
const check = process.argv.includes("--check");

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, canonicalize(item)]),
    );
  }
  return value;
}

function readDoctor() {
  const result = spawnSync(
    process.platform === "win32" ? "python" : "python3",
    [path.join(pluginRoot, "runtime", "workflow_skill_router.pyz"), "doctor"],
    {
      cwd: pluginRoot,
      encoding: "utf8",
      env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
      shell: false,
    },
  );
  if (result.status !== 0) {
    throw new Error(`runtime doctor failed: ${result.stderr}`);
  }
  return JSON.parse(result.stdout);
}

async function listTools() {
  const stateDirectory = await mkdtemp(path.join(os.tmpdir(), "workflow-skill-router-reference-"));
  const child = spawn(process.execPath, [path.join(pluginRoot, "mcp", "server.bundle.mjs")], {
    cwd: pluginRoot,
    env: { ...process.env, WORKFLOW_SKILL_ROUTER_DATA_DIR: stateDirectory },
    shell: false,
    stdio: ["pipe", "pipe", "pipe"],
  });
  const pending = new Map();
  let buffer = "";
  let diagnostics = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => { diagnostics += chunk; });
  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk) => {
    buffer += chunk;
    for (;;) {
      const newline = buffer.indexOf("\n");
      if (newline < 0) break;
      const line = buffer.slice(0, newline);
      buffer = buffer.slice(newline + 1);
      const response = JSON.parse(line);
      if (response.id !== undefined) pending.get(response.id)?.(response);
    }
  });
  const request = (id, method, params) => new Promise((resolve, reject) => {
    const timeout = setTimeout(
      () => reject(new Error(`MCP request timed out: ${method}\n${diagnostics}`)),
      15_000,
    );
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
      clientInfo: { name: "mcp-reference-generator", version: "1.0.0" },
    });
    assert.equal(initialized.error, undefined, JSON.stringify(initialized));
    child.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized", params: {} }) + "\n");
    const listed = await request(2, "tools/list", {});
    assert.equal(listed.error, undefined, JSON.stringify(listed));
    return listed.result.tools;
  } finally {
    child.kill();
    await new Promise((resolve) => {
      if (child.exitCode !== null) return resolve();
      child.once("exit", resolve);
      setTimeout(resolve, 2_000);
    });
    for (const name of ["router-v2.sqlite3", "router-v2.sqlite3-wal", "router-v2.sqlite3-shm"]) {
      await unlink(path.join(stateDirectory, name)).catch((error) => {
        if (error.code !== "ENOENT") throw error;
      });
    }
    await rmdir(stateDirectory);
  }
}

const doctor = readDoctor();
const listedTools = await listTools();
const listedNames = listedTools.map((tool) => tool.name);
const readinessNames = Object.keys(doctor.tools);
assert.deepEqual([...listedNames].sort(), [...readinessNames].sort(), "MCP and runtime readiness tool sets differ");

const tools = listedTools.map((tool) => {
  const readiness = doctor.tools[tool.name];
  const runtimeRequirement = {
    "local-ready": "local-r0",
    "conditional-local": "conditional-local",
    "verified-host-required": "verified-host",
    "configured-adapter-required": "configured-adapter",
  }[readiness.availability];
  assert.ok(runtimeRequirement, `unknown readiness: ${readiness.availability}`);
  return {
    annotations: tool.annotations,
    availability: readiness.availability,
    description: tool.description,
    fallback_action: readiness.fallback_action,
    inputSchema: tool.inputSchema,
    local_conditions: readiness.local_conditions,
    name: tool.name,
    outputSchema: tool.outputSchema,
    required_capabilities: readiness.required_capabilities,
    risk_class: readiness.risk_class,
    runtime_requirement: runtimeRequirement,
    title: tool.title,
  };
});
const document = canonicalize({
  runtime_profile: doctor.runtime_profile,
  runtime_readiness: doctor.tools,
  schema_version: "1.0",
  tools,
});
const serialized = JSON.stringify(document) + "\n";
if (serialized.includes(root) || serialized.includes("WORKFLOW_SKILL_ROUTER_DATA_DIR")) {
  throw new Error("generated reference contains a local path or execution secret name");
}

if (check) {
  const current = await readFile(output, "utf8").catch(() => null);
  if (current !== serialized) {
    process.stderr.write("stale MCP reference data; run node scripts/build-mcp-reference-data.mjs\n");
    process.exitCode = 1;
  }
} else {
  await mkdir(path.dirname(output), { recursive: true });
  await writeFile(output, serialized, "utf8");
}
