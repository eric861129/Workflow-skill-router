import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, rmdir, unlink } from "node:fs/promises";
import { readFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const sourceRoot = path.resolve(import.meta.dirname, "..");
const root = process.argv[2] ? path.resolve(process.argv[2]) : sourceRoot;
const stateDirectory = await mkdtemp(path.join(os.tmpdir(), "workflow-skill-router-smoke-"));

const manifest = JSON.parse(readFileSync(path.join(root, ".codex-plugin", "plugin.json"), "utf8"));
assert.equal(manifest.name, "workflow-skill-router");
assert.equal(manifest.skills, "./skills/");
assert.equal(manifest.mcpServers, "./.mcp.json");
assert.ok(readFileSync(path.join(root, "skills", "workflow-skill-router", "SKILL.md"), "utf8").includes("Workflow Skill Router V2"));

const packageMetadata = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8"));
assert.equal(packageMetadata.dependencies["@modelcontextprotocol/sdk"], "1.29.0");
assert.equal(packageMetadata.dependencies.zod, "4.1.12");
const mcp = JSON.parse(readFileSync(path.join(root, ".mcp.json"), "utf8"));
assert.deepEqual(mcp.mcpServers["workflow-skill-router"].args, ["./mcp/server.bundle.mjs"]);

const relativeState = path.relative(root, stateDirectory);
assert.ok(relativeState.startsWith("..") || path.isAbsolute(relativeState), "state directory must remain outside Plugin root");

const child = spawn(process.execPath, [path.join(root, "mcp", "server.bundle.mjs")], {
  cwd: root,
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
  const timeout = setTimeout(() => reject(new Error(`MCP request timed out: ${method}\n${diagnostics}`)), 15_000);
  pending.set(id, (response) => {
    clearTimeout(timeout);
    pending.delete(id);
    resolve(response);
  });
  child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
});

let toolCount = 0;
try {
  const initialized = await request(1, "initialize", {
    protocolVersion: "2025-06-18",
    capabilities: {},
    clientInfo: { name: "workflow-skill-router-smoke", version: "1.0.0" },
  });
  assert.equal(initialized.error, undefined, JSON.stringify(initialized));
  child.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized", params: {} }) + "\n");
  const listed = await request(2, "tools/list", {});
  assert.equal(listed.error, undefined, JSON.stringify(listed));
  const names = listed.result.tools.map((tool) => tool.name);
  assert.equal(new Set(names).size, 10);
  assert.equal(names.length, 10);
  toolCount = names.length;
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

console.log(JSON.stringify({
  plugin: manifest.name,
  state_boundary: "outside-plugin",
  tool_count: toolCount,
}));
