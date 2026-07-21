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

test("conditional-local outputs require explicit Router-local authority boundaries", () => {
  const nextWork = {
    status: "ready",
    refresh_requirements: [],
    work_item: { work_item_id: "work-item:1" },
    authority_mode: "router-local",
    host_goal_mutated: false,
  };
  assert.equal(TOOL_OUTPUT_SCHEMAS.get_next_work.safeParse(nextWork).success, true);
  assert.equal(TOOL_OUTPUT_SCHEMAS.get_next_work.safeParse({
    ...nextWork,
    host_goal_mutated: true,
  }).success, false);

  const recorded = {
    event_ids: ["local-transition:1"],
    resulting_state_version: 2,
    replayed: false,
    authority_mode: "router-local",
    evidence_class: "user-or-agent-reported-local",
    host_transition_authorized: false,
  };
  assert.equal(TOOL_OUTPUT_SCHEMAS.record_work_event.safeParse(recorded).success, true);
  assert.equal(TOOL_OUTPUT_SCHEMAS.record_work_event.safeParse({
    ...recorded,
    host_transition_authorized: true,
  }).success, false);
  assert.equal(TOOL_OUTPUT_SCHEMAS.record_work_event.safeParse({
    event_ids: ["host-event:1"],
    resulting_state_version: 3,
    replayed: false,
    evidence_class: "user-or-agent-reported-local",
  }).success, false);

  const gate = {
    status: "evaluated-local",
    passed: true,
    failures: [],
    evidence_digest: `sha256:${"a".repeat(64)}`,
    resulting_state_version: 4,
    replayed: false,
    gate_scope: "router-local",
    authority_mode: "router-local",
    evidence_class: "user-or-agent-reported-local",
    host_transition_authorized: false,
  };
  assert.equal(TOOL_OUTPUT_SCHEMAS.evaluate_gate.safeParse(gate).success, true);
  assert.equal(TOOL_OUTPUT_SCHEMAS.evaluate_gate.safeParse({
    ...gate,
    gate_scope: "production",
  }).success, false);
  assert.equal(TOOL_OUTPUT_SCHEMAS.evaluate_gate.safeParse({
    ...gate,
    mandatory_failures: [],
  }).success, false);
});

test("conditional-local output schemas retain strict verified-host variants", () => {
  assert.equal(TOOL_OUTPUT_SCHEMAS.record_work_event.safeParse({
    event_ids: ["event:1"],
    resulting_state_version: 2,
    replayed: false,
  }).success, true);
  assert.equal(TOOL_OUTPUT_SCHEMAS.evaluate_gate.safeParse({
    status: "passed",
    passed: true,
    mandatory_failures: [],
    evidence_digest: `sha256:${"b".repeat(64)}`,
  }).success, true);
  assert.equal(TOOL_OUTPUT_SCHEMAS.get_next_work.safeParse({
    status: "ready",
    refresh_requirements: [],
    work_item: null,
    authority_mode: "verified-host",
    host_goal_mutated: true,
  }).success, true);
  assert.equal(TOOL_OUTPUT_SCHEMAS.evaluate_gate.safeParse({
    status: "passed",
    passed: true,
    mandatory_failures: [],
    evidence_digest: `sha256:${"b".repeat(64)}`,
    gate_scope: "router-local",
  }).success, false);
  assert.equal(TOOL_OUTPUT_SCHEMAS.record_work_event.safeParse({
    event_ids: ["event:1"],
    resulting_state_version: 2,
    replayed: false,
    authority_mode: "router-local",
  }).success, false);
});

test("success schemas reject invented wrapper fields", () => {
  assert.equal(TOOL_OUTPUT_SCHEMAS.plan_work.safeParse({
    schema_id: "invented",
    schema_version: "2.0",
    artifact_kind: "invented",
  }).success, false);
});
