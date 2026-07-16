import assert from "node:assert/strict";
import test from "node:test";
import { defaultDataDir } from "../src/state-path.js";

test("state defaults remain outside plugin cache", () => {
  assert.equal(defaultDataDir("win32", { LOCALAPPDATA: "C:/Local" }, "C:/Home"), "C:\\Local\\Codex\\workflow-skill-router");
  assert.equal(defaultDataDir("darwin", {}, "/home/u"), "/home/u/Library/Application Support/Codex/workflow-skill-router");
  assert.equal(defaultDataDir("linux", { XDG_STATE_HOME: "/state" }, "/home/u"), "/state/codex/workflow-skill-router");
});
