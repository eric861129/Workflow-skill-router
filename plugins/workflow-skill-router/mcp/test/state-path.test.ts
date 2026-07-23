import assert from "node:assert/strict";
import { mkdtemp, readFile, rmdir, unlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { defaultDataDir, resolveState } from "../src/state-path.js";

test("state defaults remain outside plugin cache", () => {
  assert.equal(defaultDataDir("win32", { LOCALAPPDATA: "C:/Local" }, "C:/Home"), "C:\\Local\\Codex\\workflow-skill-router");
  assert.equal(defaultDataDir("darwin", {}, "/home/u"), "/home/u/Library/Application Support/Codex/workflow-skill-router");
  assert.equal(defaultDataDir("linux", { XDG_STATE_HOME: "/state" }, "/home/u"), "/state/codex/workflow-skill-router");
});

test("explicit state survives local plugin root replacement rehearsal", async () => {
  const firstPluginRoot = await mkdtemp(path.join(tmpdir(), "workflow-skill-router-plugin-first-"));
  const replacementPluginRoot = await mkdtemp(path.join(tmpdir(), "workflow-skill-router-plugin-replacement-"));
  const externalStateDirectory = await mkdtemp(path.join(tmpdir(), "workflow-skill-router-state-"));

  try {
    const env = { WORKFLOW_SKILL_ROUTER_DATA_DIR: externalStateDirectory };
    const firstState = await resolveState(process.platform, firstPluginRoot, env);
    const sentinel = "local-state-continuity-sentinel";
    await writeFile(firstState.database, sentinel, "utf8");

    const replacementState = await resolveState(process.platform, replacementPluginRoot, env);

    assert.equal(replacementState.directory, firstState.directory);
    assert.equal(replacementState.database, firstState.database);
    assert.ok(isOutsidePluginRoot(firstState.directory, firstPluginRoot));
    assert.ok(isOutsidePluginRoot(firstState.directory, replacementPluginRoot));
    assert.equal(await readFile(replacementState.database, "utf8"), sentinel);
  } finally {
    try {
      await unlink(path.join(externalStateDirectory, "router-v2.sqlite3")).catch(ignoreMissingFile);
    } finally {
      try {
        await rmdir(externalStateDirectory);
      } finally {
        try {
          await rmdir(firstPluginRoot);
        } finally {
          await rmdir(replacementPluginRoot);
        }
      }
    }
  }
});

test("state path inside plugin root remains fail-closed", async () => {
  const pluginRoot = await mkdtemp(path.join(tmpdir(), "workflow-skill-router-plugin-root-"));

  try {
    await assert.rejects(
      resolveState(process.platform, pluginRoot, { WORKFLOW_SKILL_ROUTER_DATA_DIR: pluginRoot }),
      /state-path-inside-plugin/,
    );
  } finally {
    await rmdir(pluginRoot);
  }
});

function isOutsidePluginRoot(stateDirectory: string, pluginRoot: string): boolean {
  const relative = path.relative(path.resolve(pluginRoot), path.resolve(stateDirectory));
  return relative.startsWith("..") || path.isAbsolute(relative);
}

function ignoreMissingFile(error: NodeJS.ErrnoException): void {
  if (error.code !== "ENOENT") throw error;
}
