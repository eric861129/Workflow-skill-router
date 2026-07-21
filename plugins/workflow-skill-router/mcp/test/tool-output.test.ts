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
    route_source: "builtin-default",
    routing_profile_ids: [],
    routing_profile_digest: null,
    matched_profile_rule_id: null,
    planned_skill_tree: [],
    activation_status: "not-planned",
    profile_warnings: [],
    classification: {
      source: "caller-work-mode-hint",
      confidence: "low",
      classifier_revision: "deterministic-objective-v1",
      reason_codes: ["single-default"],
    },
  }).success, true);
  assert.equal(TOOL_OUTPUT_SCHEMAS.get_router_status.safeParse({
    goal_binding_id: null,
    workflow_run_id: null,
    created_work_items: 0,
    goal_status_candidate: null,
    host_goal_mutated: false,
  }).success, true);
});

test("profile-routed plan exposes current intent without claiming activation", () => {
  assert.equal(TOOL_OUTPUT_SCHEMAS.plan_work.safeParse({
    status: "planned-local-control",
    workflow_run_id: "workflow:1",
    work_graph_id: "work-graph:1",
    created_work_items: 1,
    routing_envelope: "phased",
    selection_mode: "auto",
    support_consent_required: false,
    planned_skill_ids: ["skill:qa-test-planner", "skill:playwright"],
    runtime_mode: "mcp-local-control-plane",
    route_source: "workspace-profile",
    routing_profile_ids: ["workspace:api"],
    routing_profile_digest: `sha256:${"a".repeat(64)}`,
    matched_profile_rule_id: "api",
    planned_skill_tree: [{
      phase_id: "verification",
      primary_skill_id: "skill:qa-test-planner",
      support_skill_ids: ["skill:playwright"],
      exit_gate: "tests-passed",
    }],
    activation_status: "intended-unverified",
    profile_warnings: [],
    classification: {
      source: "profile-route",
      confidence: "low",
      classifier_revision: "deterministic-objective-v1",
      reason_codes: ["single-default"],
    },
  }).success, true);
});

test("plan classification rejects unknown properties", () => {
  const classification = {
    source: "deterministic-analyzer",
    confidence: "medium",
    classifier_revision: "deterministic-objective-v1",
    reason_codes: ["multi-stage-sequence"],
    grants_authority: true,
  };

  assert.equal(TOOL_OUTPUT_SCHEMAS.plan_work.shape.classification.safeParse(
    classification,
  ).success, false);
});

test("plan classification rejects unknown sources", () => {
  assert.equal(TOOL_OUTPUT_SCHEMAS.plan_work.shape.classification.safeParse({
    source: "semantic-guess",
    confidence: "low",
    classifier_revision: "deterministic-objective-v1",
    reason_codes: [],
  }).success, false);
});

test("support consent output preserves the route binding", () => {
  assert.equal(TOOL_OUTPUT_SCHEMAS.transition_support_consent.safeParse({
    status: "approved",
    proposal_id: "support-proposal:1",
    workflow_run_id: "workflow:1",
    phase_id: "phase-1",
    routing_envelope: "phased",
    selection_mode: "explicit-locked",
    primary_skill: "skill:api-designer",
    support_skills: ["skill:qa-test-planner"],
    consent_action: "approved",
    goal_relation: "none",
    decision_ref: "consent-grant:1",
    state_version: 2,
    replayed: false,
    runtime_mode: "mcp-local-control-plane",
  }).success, true);
});

test("success schemas reject invented wrapper fields", () => {
  assert.equal(TOOL_OUTPUT_SCHEMAS.plan_work.safeParse({
    schema_id: "invented",
    schema_version: "2.0",
    artifact_kind: "invented",
  }).success, false);
});
