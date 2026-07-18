import assert from "node:assert/strict";
import test from "node:test";
import { TOOL_DEFINITIONS } from "../src/tool-definitions.js";


test("tool definitions disclose bundled, host, and adapter boundaries", () => {
  const requirements = Object.fromEntries(
    TOOL_DEFINITIONS.map((definition) => [definition.name, definition.runtimeRequirement]),
  );
  assert.equal(requirements.plan_work, "local-r0");
  assert.equal(requirements.propose_support_consent, "local-r0");
  assert.equal(requirements.transition_support_consent, "local-r0");
  assert.equal(requirements.get_router_status, "local-r0");
  assert.equal(requirements.get_next_work, "verified-host");
  assert.equal(requirements.validate_route, "verified-host");
  assert.equal(requirements.run_model_evaluation, "configured-adapter");
  assert.equal(requirements.compare_evaluations, "configured-adapter");
  assert.equal(requirements.export_router_artifact, "configured-adapter");
});
