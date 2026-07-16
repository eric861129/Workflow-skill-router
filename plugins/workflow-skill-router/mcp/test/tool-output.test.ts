import assert from "node:assert/strict";
import test from "node:test";
import { TOOL_OUTPUT_SCHEMAS } from "../src/tool-output-schemas.js";


test("plan_work and get_router_status outputs match bundled runtime fields", () => {
  assert.equal(TOOL_OUTPUT_SCHEMAS.plan_work.safeParse({
    status: "planned-local-control",
    workflow_run_id: "workflow:1",
    work_graph_id: "work-graph:1",
    created_work_items: 1,
    routing_envelope: "single",
    selection_mode: "auto",
    support_consent_required: false,
    planned_skill_ids: [],
    runtime_mode: "mcp-local-control-plane",
  }).success, true);
  assert.equal(TOOL_OUTPUT_SCHEMAS.get_router_status.safeParse({
    goal_binding_id: null,
    workflow_run_id: null,
    created_work_items: 0,
    goal_status_candidate: null,
    host_goal_mutated: false,
  }).success, true);
});

test("success schemas reject invented wrapper fields", () => {
  assert.equal(TOOL_OUTPUT_SCHEMAS.plan_work.safeParse({
    schema_id: "invented",
    schema_version: "2.0",
    artifact_kind: "invented",
  }).success, false);
});
