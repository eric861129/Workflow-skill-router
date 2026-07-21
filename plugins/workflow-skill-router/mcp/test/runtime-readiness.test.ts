import assert from "node:assert/strict";
import test from "node:test";
import { TOOL_DEFINITIONS } from "../src/tool-definitions.js";


test("tool definitions disclose always-local, conditional-local, host, and adapter boundaries", () => {
  const requirements = Object.fromEntries(
    TOOL_DEFINITIONS.map((definition) => [definition.name, definition.runtimeRequirement]),
  );
  assert.equal(requirements.plan_work, "local-r0");
  assert.equal(requirements.propose_support_consent, "local-r0");
  assert.equal(requirements.transition_support_consent, "local-r0");
  assert.equal(requirements.get_router_status, "local-r0");
  assert.equal(requirements.get_next_work, "conditional-local");
  assert.equal(requirements.record_work_event, "conditional-local");
  assert.equal(requirements.evaluate_gate, "conditional-local");
  assert.equal(requirements.validate_route, "verified-host");
  assert.equal(requirements.run_model_evaluation, "configured-adapter");
  assert.equal(requirements.compare_evaluations, "configured-adapter");
  assert.equal(requirements.export_router_artifact, "configured-adapter");
});

test("conditional-local tool descriptions disclose both authority paths", () => {
  const definitions = Object.fromEntries(
    TOOL_DEFINITIONS.map((definition) => [definition.name, definition.description]),
  );
  for (const name of ["get_next_work", "record_work_event", "evaluate_gate"]) {
    assert.match(definitions[name], /Router-owned/);
    assert.match(definitions[name], /Native Goal/);
    assert.match(definitions[name], /fail(?:s)? closed/);
  }
  assert.match(definitions.get_next_work, /host_goal_mutated=false/);
  assert.match(definitions.record_work_event, /user-or-agent-reported-local/);
  assert.match(definitions.evaluate_gate, /not Skill activation/i);
});
