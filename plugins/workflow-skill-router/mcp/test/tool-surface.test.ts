import assert from "node:assert/strict";
import test from "node:test";
import { z } from "zod";
import { PUBLIC_TOOL_NAMES } from "../src/tool-definitions.js";
import { TOOL_INPUT_SHAPES } from "../src/tool-schemas.js";

test("只公開核准的十二個工具", () => {
  assert.equal(PUBLIC_TOOL_NAMES.length, 12); assert.equal(new Set(PUBLIC_TOOL_NAMES).size, 12);
  assert.ok(PUBLIC_TOOL_NAMES.includes("propose_support_consent"));
  assert.ok(PUBLIC_TOOL_NAMES.includes("transition_support_consent"));
});

test("十二個工具都拒絕空值與未知欄位", () => {
  for (const name of PUBLIC_TOOL_NAMES) {
    assert.equal(z.object(TOOL_INPUT_SHAPES[name]).strict().safeParse({ unknown: true }).success, false, name);
  }
});

test("support consent context fingerprint 必須是完整 SHA-256 digest", () => {
  const schema = z.object(TOOL_INPUT_SHAPES.propose_support_consent).strict();
  const base = {
    context: {
      session_id: "session-1",
      actor: "developer",
      runtime_policy_snapshot_id: "policy-1",
    },
    expected_state_version: 1,
    idempotency_key: "proposal-1",
    correlation_id: "correlation-1",
    workflow_run_id: "workflow-1",
    phase_id: "phase-1",
    scope_anchor_id: "scope:phase-1",
    goal_revision: null,
    plan_revision: 1,
    primary_skill_id: "skill:api-designer",
    support_skill_ids: ["skill:qa-test-planner"],
  };

  assert.equal(schema.safeParse({ ...base, context_fingerprint: `sha256:${"a".repeat(64)}` }).success, true);
  assert.equal(schema.safeParse({ ...base, context_fingerprint: "sha256:" }).success, false);
  assert.equal(schema.safeParse({ ...base, context_fingerprint: "sha256:xyz" }).success, false);
});
