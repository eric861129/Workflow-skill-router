import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import test from "node:test";
import path from "node:path";
import { pathToFileURL } from "node:url";
import {
  WorkspaceRootTrustError,
  bindPlanWorkWorkspaceRoot,
  collectTrustedWorkspaceRoots,
} from "../src/workspace-roots.js";

test("workspace profiles bind only to MCP or operator trusted roots", () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "router-roots-"));
  const demoRoot = path.join(temporary, "demo");
  const configuredRoot = path.join(temporary, "configured");
  const apiRoot = path.join(demoRoot, "apps", "api");
  fs.mkdirSync(apiRoot, { recursive: true });
  fs.mkdirSync(configuredRoot);
  const trusted = collectTrustedWorkspaceRoots(
    [{ uri: pathToFileURL(demoRoot).href }],
    [configuredRoot],
  );

  const bound = bindPlanWorkWorkspaceRoot({
    routing_context: {
      workspace_root: apiRoot,
      domains: ["api"],
      tags: [],
      current_phase_id: null,
    },
  }, trusted);

  assert.equal(
    (bound.routing_context as { workspace_root: string }).workspace_root,
    fs.realpathSync.native(apiRoot),
  );
  assert.throws(
    () => bindPlanWorkWorkspaceRoot({
      routing_context: {
        workspace_root: path.resolve("secrets"), domains: [], tags: [], current_phase_id: null,
      },
    }, trusted),
    WorkspaceRootTrustError,
  );
  fs.rmdirSync(apiRoot);
  fs.rmdirSync(path.dirname(apiRoot));
  fs.rmdirSync(demoRoot);
  fs.rmdirSync(configuredRoot);
  fs.rmdirSync(temporary);
});

test("one trusted MCP root is injected for legacy plan_work callers", () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "router-root-"));
  const demoRoot = path.join(temporary, "demo");
  fs.mkdirSync(demoRoot);
  const trusted = collectTrustedWorkspaceRoots(
    [{ uri: pathToFileURL(demoRoot).href }],
    [],
  );

  const bound = bindPlanWorkWorkspaceRoot({ objective: "Deliver API" }, trusted);

  assert.deepEqual(bound.routing_context, {
    workspace_root: fs.realpathSync.native(demoRoot),
    domains: [],
    tags: [],
    current_phase_id: null,
  });
  fs.rmdirSync(demoRoot);
  fs.rmdirSync(temporary);
});

test("non-file roots and ambiguous roots never authorize implicit reads", () => {
  const trusted = collectTrustedWorkspaceRoots(
    [
      { uri: "https://example.invalid/repo" },
      { uri: pathToFileURL(path.resolve("test-workspaces", "one")).href },
      { uri: pathToFileURL(path.resolve("test-workspaces", "two")).href },
    ],
    [],
  );

  const unchanged = bindPlanWorkWorkspaceRoot({ objective: "Deliver API" }, trusted);

  assert.equal("routing_context" in unchanged, false);
});

test("a junction or directory symlink cannot escape a trusted workspace root", () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "router-workspace-root-"));
  const trustedRoot = path.join(temporary, "trusted");
  const outsideRoot = path.join(temporary, "outside");
  const linkedRoot = path.join(trustedRoot, "linked");
  try {
    fs.mkdirSync(trustedRoot);
    fs.mkdirSync(outsideRoot);
    fs.symlinkSync(outsideRoot, linkedRoot, process.platform === "win32" ? "junction" : "dir");
    const trusted = collectTrustedWorkspaceRoots(
      [{ uri: pathToFileURL(trustedRoot).href }],
      [],
    );

    assert.throws(
      () => bindPlanWorkWorkspaceRoot({
        routing_context: {
          workspace_root: linkedRoot,
          domains: [],
          tags: [],
          current_phase_id: null,
        },
      }, trusted),
      WorkspaceRootTrustError,
    );
  } finally {
    fs.unlinkSync(linkedRoot);
    fs.rmdirSync(trustedRoot);
    fs.rmdirSync(outsideRoot);
    fs.rmdirSync(temporary);
  }
});
