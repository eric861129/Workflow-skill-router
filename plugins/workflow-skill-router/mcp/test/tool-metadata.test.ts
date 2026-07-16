import assert from "node:assert/strict";
import test from "node:test";
import { TOOL_DEFINITIONS } from "../src/tool-definitions.js";


test("all public tools expose actionable MCP metadata", () => {
  assert.equal(TOOL_DEFINITIONS.length, 10);
  for (const definition of TOOL_DEFINITIONS) {
    assert.ok(definition.title.length >= 8, definition.name);
    assert.ok(definition.description.length >= 80, definition.name);
    assert.ok(definition.outputSchema, definition.name);
    assert.equal(typeof definition.annotations.readOnlyHint, "boolean", definition.name);
    assert.equal(typeof definition.annotations.idempotentHint, "boolean", definition.name);
    assert.match(definition.runtimeRequirement, /local-r0|verified-host|configured-adapter/, definition.name);
  }
});

test("read and mutation annotations reflect real authority", () => {
  const definitions = Object.fromEntries(TOOL_DEFINITIONS.map((item) => [item.name, item]));
  assert.equal(definitions.get_next_work.annotations.readOnlyHint, true);
  assert.equal(definitions.get_router_status.annotations.readOnlyHint, true);
  assert.equal(definitions.plan_work.annotations.readOnlyHint, false);
  assert.equal(definitions.plan_work.annotations.idempotentHint, true);
});
