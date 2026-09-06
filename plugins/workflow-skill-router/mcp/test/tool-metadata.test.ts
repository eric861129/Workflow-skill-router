import assert from "node:assert/strict";
import test from "node:test";
import { TOOL_DEFINITIONS } from "../src/tool-definitions.js";


test("all public tools expose actionable MCP metadata", () => {
  assert.equal(TOOL_DEFINITIONS.length, 20);
  for (const definition of TOOL_DEFINITIONS) {
    assert.ok(definition.title.length >= 8, definition.name);
    assert.ok(definition.description.length >= 80, definition.name);
    assert.ok(definition.outputSchema, definition.name);
    assert.equal(typeof definition.annotations.readOnlyHint, "boolean", definition.name);
    assert.equal(typeof definition.annotations.idempotentHint, "boolean", definition.name);
    assert.match(
      definition.runtimeRequirement,
      /local-r0|conditional-local|verified-host|configured-adapter/,
      definition.name,
    );
  }
});

test("read and mutation annotations reflect real authority", () => {
  const definitions = Object.fromEntries(TOOL_DEFINITIONS.map((item) => [item.name, item]));
  assert.equal(definitions.get_next_work.annotations.readOnlyHint, true);
  assert.equal(definitions.get_router_status.annotations.readOnlyHint, true);
  assert.equal(definitions.plan_work.annotations.readOnlyHint, false);
  assert.equal(definitions.plan_work.annotations.idempotentHint, true);
  assert.equal(definitions.propose_support_consent.annotations.readOnlyHint, false);
  assert.equal(definitions.transition_support_consent.annotations.readOnlyHint, false);
});

test("plan_work metadata explains user-owned profile precedence and activation boundary", () => {
  const plan = TOOL_DEFINITIONS.find((item) => item.name === "plan_work")!;
  assert.match(plan.description, /user-owned/i);
  assert.match(plan.description, /runtime discovery/i);
});

test("Memory metadata separates read-only previews from conditional writes and purge", () => {
  const byName = Object.fromEntries(TOOL_DEFINITIONS.map((item) => [item.name, item]));
  for (const name of ["get_memory_status", "list_workflow_candidates", "preview_profile_update"]) {
    assert.ok(byName[name]);
    assert.equal(byName[name].annotations.readOnlyHint, true);
  }
  for (const name of ["transition_profile_update", "rollback_profile_revision"]) {
    assert.ok(byName[name]);
    assert.equal(byName[name].runtimeRequirement, "conditional-local");
  }
  assert.equal(byName.purge_workflow_memory.annotations.destructiveHint, true);
  assert.equal(byName.remember_workflow.annotations.readOnlyHint, false);
});
