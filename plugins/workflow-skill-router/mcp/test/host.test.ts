import assert from "node:assert/strict";
import test from "node:test";
import { HOST_ENVIRONMENT_VARIABLE, HostConfigurationError, resolveHost } from "../src/host.js";

test("an unset or blank host keeps the Codex default", () => {
  assert.equal(resolveHost({}), "codex");
  assert.equal(resolveHost({ [HOST_ENVIRONMENT_VARIABLE]: "  " }), "codex");
});

test("Claude Code is selected only by its exact host identifier", () => {
  assert.equal(resolveHost({ [HOST_ENVIRONMENT_VARIABLE]: "claude-code" }), "claude-code");
  for (const value of ["claude", "Claude-Code", "../codex"]) {
    assert.throws(() => resolveHost({ [HOST_ENVIRONMENT_VARIABLE]: value }), HostConfigurationError);
  }
});
