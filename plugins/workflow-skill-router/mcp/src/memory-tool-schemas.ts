import { z } from "zod";
import { Validator } from "@cfworker/json-schema";
import routingProfileContract from "./routing-profile-contract.json" with { type: "json" };

export const MEMORY_TOOL_NAMES = [
  "get_memory_status", "remember_workflow", "record_route_feedback",
  "list_workflow_candidates", "preview_profile_update", "transition_profile_update",
  "rollback_profile_revision", "purge_workflow_memory",
] as const;
export type MemoryToolName = typeof MEMORY_TOOL_NAMES[number];
export const isMemoryTool = (name: string): name is MemoryToolName =>
  (MEMORY_TOOL_NAMES as readonly string[]).includes(name);

const key = z.string().regex(/^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$/);
const digest = z.string().regex(/^sha256:[0-9a-f]{64}$/);
const artifactId = (kind: string) => z.string().regex(new RegExp(`^${kind}:[0-9a-f]{32}$`));
const target = z.enum(["managed-personal", "managed-workspace-local", "user-personal", "workspace-file"]);
const mode = z.enum(["disabled", "observe", "reviewed", "automatic"]);
const candidateStatus = z.enum(["proposed", "approved", "rejected", "expired", "suppressed", "superseded", "auto-promoted"]);
const feedbackType = z.enum(["accepted", "corrected", "rejected", "support-rejected", "capability-unavailable", "gate-failed", "completed", "abandoned", "no-memory"]);
const feedbackReason = z.enum(["user-accepted", "user-rejected", "user-correction", "support-rejected", "capability-unavailable", "gate-failed", "completed", "abandoned", "no-memory"]);
const dimension = z.enum(["work-mode", "phase-order", "primary-skill", "support-skill", "exit-gate", "matcher", "target"]);
const purgeScope = z.enum(["history-only", "analytics-only", "candidates-only", "revisions-only", "managed-profiles-only", "all-memory-data"]);
const context = z.object({
  session_id: key.max(128), actor: key.max(128), runtime_policy_snapshot_id: key.max(128),
}).strict().describe("Session/actor correlation context; these identifiers do not grant Host write authority.");
const control = {
  context,
  workspace_root: z.string().min(1).max(4096).refine((value) => !value.includes("\0"))
    .nullable().describe("Optional Workspace root bound to MCP Client or operator-advertised roots before Core access; never a target filename."),
};
const mutation = {
  idempotency_key: key.describe("Stable key for replaying the identical bounded intent."),
  correlation_id: key.describe("Public-safe correlation identity. A changed identity is not the same replay."),
};
const version = z.number().int().min(1).max(2_147_483_647);
const correctionDimensions = z.array(dimension).max(7)
  .refine((values) => new Set(values).size === values.length, "Correction dimensions must be unique.");

export const MEMORY_INPUT_SCHEMAS = {
  get_memory_status: z.object({ ...control }).strict(),
  remember_workflow: z.object({
    ...control, ...mutation, workflow_run_id: key,
    target_profile_class: target,
    risk_class: z.enum(["r0", "r1", "r2", "r3"]),
    side_effect_outcome: z.enum(["none", "known-success", "known-failure", "unknown"]),
    one_shot: z.enum(["none", "remember-once", "no-memory"]),
  }).strict(),
  record_route_feedback: z.object({
    ...control, ...mutation, workflow_run_id: key, observation_id: artifactId("observation"),
    feedback_type: feedbackType, reason_code: feedbackReason.nullable(),
    correction_dimensions: correctionDimensions,
    original_route_digest: digest.nullable(), corrected_route_digest: digest.nullable(),
  }).strict().superRefine((value, ctx) => {
    const corrected = value.feedback_type === "corrected";
    if (corrected ? (value.correction_dimensions.length === 0 || value.original_route_digest === null || value.corrected_route_digest === null || value.original_route_digest === value.corrected_route_digest)
      : (value.correction_dimensions.length !== 0 || value.original_route_digest !== null || value.corrected_route_digest !== null)) {
      ctx.addIssue({ code: "custom", message: "Correction metadata is required only for corrected feedback." });
    }
  }),
  list_workflow_candidates: z.object({
    ...control, status: candidateStatus.nullable(), limit: z.number().int().min(1).max(1000),
  }).strict(),
  preview_profile_update: z.object({ ...control, candidate_id: artifactId("candidate") }).strict(),
  transition_profile_update: z.object({
    ...control, ...mutation, proposal_id: artifactId("proposal"),
    expected_proposal_digest: digest,
    expected_profile_digest: z.union([digest, z.literal("missing")]),
    expected_state_version: version,
    action: z.enum(["approve", "reject"]),
  }).strict(),
  rollback_profile_revision: z.object({
    ...control, ...mutation, source_revision_id: artifactId("revision"), expected_profile_digest: digest,
  }).strict(),
  purge_workflow_memory: z.object({
    context, ...mutation, scope: purgeScope, expected_summary_digest: digest,
    include_managed_profiles: z.boolean(),
    confirmed: z.literal(true).describe("Explicit confirmation of the destructive scope. Never inferred from Memory mode."),
  }).strict(),
} as const;

// The full object schemas above remain the authority for strictness and
// cross-field validation; shapes only support shared metadata consumers.
export const MEMORY_INPUT_SHAPES = {
  get_memory_status: MEMORY_INPUT_SCHEMAS.get_memory_status.shape,
  remember_workflow: MEMORY_INPUT_SCHEMAS.remember_workflow.shape,
  record_route_feedback: MEMORY_INPUT_SCHEMAS.record_route_feedback.shape,
  list_workflow_candidates: MEMORY_INPUT_SCHEMAS.list_workflow_candidates.shape,
  preview_profile_update: MEMORY_INPUT_SCHEMAS.preview_profile_update.shape,
  transition_profile_update: MEMORY_INPUT_SCHEMAS.transition_profile_update.shape,
  rollback_profile_revision: MEMORY_INPUT_SCHEMAS.rollback_profile_revision.shape,
  purge_workflow_memory: MEMORY_INPUT_SCHEMAS.purge_workflow_memory.shape,
} as const;

export const MEMORY_REASON_CODES = [
  "memory-disabled",
  "personal-policy-missing",
  "workspace-policy-missing",
  "invalid-memory-policy",
  "ambiguous-memory-policy",
  "workspace-policy-exceeds-ceiling",
  "workspace-root-unverified",
  "explicit-no-memory",
  "workflow-not-terminal",
  "required-gate-not-passed",
  "unknown-side-effect-outcome",
  "sensitive-route-excluded",
  "insufficient-evidence",
  "candidate-conflict",
  "candidate-suppressed",
  "candidate-not-proposed",
  "workflow-candidate-not-found",
  "profile-preview-stale",
  "profile-policy-drift",
  "profile-drift",
  "profile-candidate-drift",
  "profile-proposal-state-conflict",
  "profile-proposal-expired",
  "profile-promotion-disabled",
  "profile-target-not-allowed",
  "profile-backtest-failed",
  "profile-backtest-drift",
  "profile-lint-failed",
  "profile-authority-mismatch",
  "profile-proposal-not-found",
  "memory-store-unavailable",
  "memory-operation-failed",
  "idempotency-conflict",
  "memory-idempotency-conflict",
  "stale-summary-digest",
  "scope-not-available",
  "managed-profile-purge-not-available",
  "rollback-source-revision-unavailable",
  "automatic-user-profile-write-forbidden",
  "explicit-route-requires-review",
  "workflow-context-mismatch",
  "workflow-run-not-found",
  "workflow-not-completed",
  "no-matchable-routing-context",
  "matcher-seed-required",
  "unresolved-skill-identity",
  "risk-class-excluded",
  "profile-versioning-required",
  "candidate-evidence-drift"
] as const;
const reasons = z.array(z.enum(MEMORY_REASON_CODES)).max(64);
const localAuthority = z.literal("router-local");
const count = z.number().int().nonnegative();
const rate = z.number().min(0).max(1);
const instant = z.string().datetime();
const jsonObject = z.string().max(1_048_576).refine((text) => {
  try { const value = JSON.parse(text); return value !== null && typeof value === "object" && !Array.isArray(value); }
  catch { return false; }
}, "Expected a canonical JSON object compiled by the Router.");

// Share the Core's strict Profile contract instead of allowing arbitrary JSON
// inside a string field. The validator interprets schemas without eval/codegen.
const profileValidator = new Validator(structuredClone(routingProfileContract), "2020-12");
const fragments = ["rule", "match", "skillTreePhase"].map((name) => new Validator(structuredClone({
  $schema: routingProfileContract.$schema, $defs: routingProfileContract.$defs,
  $ref: `#/$defs/${name}`,
}), "2020-12"));
const fragment = z.unknown().refine((value) => fragments.some((validator) => validator.validate(value).valid));
const identifier = z.string().regex(/^[a-z0-9][a-z0-9._-]{0,63}$/);
const skillId = z.string().regex(/^skill:[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/);
const diffValue = z.union([z.null(), z.number().int().min(-1000).max(1000), identifier,
  skillId, z.array(z.union([identifier, skillId])).max(32), fragment]);
const diffContract = z.object({
  entries: z.array(z.object({
    change_type: z.enum(["rule-added", "rule-removed", "rule-changed", "phase-added", "phase-removed", "phase-changed", "phase-order-changed"]),
    rule_id: identifier.nullable(), phase_id: identifier.nullable(),
    field: z.enum(["priority", "match", "work_mode", "phase_order", "primary_skill_id", "support_skill_ids", "exit_gate"]).nullable(),
    before: diffValue, after: diffValue,
  }).strict()),
  json_patch: z.array(z.union([
    z.object({op: z.literal("add"), path: z.literal("/"), value: z.unknown().refine((value) => profileValidator.validate(value).valid)}).strict(),
    z.object({op: z.literal("replace"), path: z.literal("/rules"), value: z.array(z.unknown().refine((value) => fragments[0].validate(value).valid)).max(64)}).strict(),
  ])),
  semantic_diff_digest: digest, json_patch_digest: digest,
}).strict();
const profileJson = jsonObject.refine((text) => {
  try {return profileValidator.validate(JSON.parse(text)).valid;} catch {return false;}
}, "Embedded Profile violates the strict routing contract.");
const diffJson = jsonObject.refine((text) => {
  try {return diffContract.safeParse(JSON.parse(text)).success;} catch {return false;}
}, "Embedded Diff violates the strict semantic contract.");

const backtest = z.object({
  positive_observation_count: count, positive_match_count: count, positive_match_coverage: rate,
  unexpected_match_count: count, shadowed_rule_ids: z.array(key), equal_rank_conflicts: z.array(key),
  manual_precedence: z.boolean(), manual_profile_digests: z.array(digest),
  capability_gap_summary: z.literal("unavailable"), planned_route_regressions: count,
  workspace_isolation: z.boolean(), acceptable: z.boolean(), backtest_digest: digest,
}).strict();
const proposal = z.object({
  proposal_id: artifactId("proposal"), proposal_digest: digest,
  candidate_id: artifactId("candidate"), candidate_digest: digest,
  status: z.enum(["pending", "approved", "rejected", "stale", "expired", "applied", "failed"]),
  state_version: version, target_profile_class: target,
  expected_profile_digest: z.union([digest, z.literal("missing")]), proposed_profile_digest: digest,
  semantic_diff_digest: digest, backtest_digest: digest, policy_digest: digest,
  workspace_identity_digest: digest.nullable(), created_at: instant, expires_at: instant,
  proposed_profile_json: profileJson, semantic_diff_json: diffJson, backtest,
}).strict();
const profileResult = z.object({
  status: z.enum(["previewed", "pending", "applied", "rejected", "blocked", "not-found"]),
  proposal: proposal.nullable(), revision_id: artifactId("revision").nullable(),
  revision_digest: digest.nullable(), replayed: z.boolean(), reason_codes: reasons,
  authority_mode: localAuthority,
}).strict().superRefine((value, ctx) => {
  if ((value.status === "applied") !== (value.revision_id !== null && value.revision_digest !== null)) {
    ctx.addIssue({ code: "custom", message: "Only an applied result has a complete Revision identity." });
  }
  if (["previewed", "pending", "applied", "rejected"].includes(value.status) && value.proposal === null) {
    ctx.addIssue({ code: "custom", message: "Successful Profile operations require a bound Proposal." });
  }
  if (value.proposal !== null && value.proposal.backtest_digest !== value.proposal.backtest.backtest_digest) {
    ctx.addIssue({ code: "custom", message: "Backtest Digest must match the bound Proposal." });
  }
});
const metricSummary = z.object({
  distinct_runs: count, distinct_days: count, completion_rate: rate,
  required_gate_pass_rate: rate, manual_correction_rate: rate, route_consistency: rate,
  canonical_skill_ids: z.boolean(), hard_contract_violations: count,
}).strict();
const candidate = z.object({
  candidate_id: artifactId("candidate"), candidate_digest: digest, pattern_id: artifactId("pattern"),
  status: candidateStatus, recommendation_mode: z.enum(["reviewed", "automatic"]),
  confidence: z.enum(["insufficient-evidence", "low", "medium", "high"]),
  target_profile_class: target, workspace_identity_digest: digest.nullable(),
  material_evidence_digest: digest, policy_digest: digest, created_at: instant,
  scope: z.enum(["personal", "workspace"]), metrics: metricSummary, reason_codes: reasons,
}).strict();

export const MEMORY_OUTPUT_SCHEMAS = {
  get_memory_status: z.object({
    effective_mode: mode, personal_ceiling: mode, workspace_requested_mode: mode.nullable(),
    policy_digest: digest, capture_enabled: z.boolean(), candidate_generation_enabled: z.boolean(),
    profile_promotion: z.enum(["disabled", "review-required", "automatic-managed"]),
    allowed_targets: z.array(target).max(4), memory_store_exists: z.boolean(), reason_codes: reasons,
    history_summary_digest: digest, eligible_workflow_count: count,
    actual_skill_consistency: z.literal("unavailable"), authority_mode: localAuthority,
  }).strict(),
  remember_workflow: z.object({
    status: z.enum(["recorded", "not-recorded", "memory-disabled"]),
    observation_id: artifactId("observation").nullable(), observation_digest: digest.nullable(),
    route_signature_digest: digest.nullable(), policy_digest: digest.nullable(),
    target_profile_class: target, reason_codes: reasons, replayed: z.boolean(),
    candidate_id: artifactId("candidate").nullable(), authority_mode: localAuthority,
  }).strict(),
  record_route_feedback: z.object({
    status: z.enum(["recorded", "memory-disabled"]), feedback_id: artifactId("feedback").nullable(),
    feedback_digest: digest.nullable(), observation_id: artifactId("observation"),
    policy_digest: digest.nullable(), reason_codes: reasons, replayed: z.boolean(), authority_mode: localAuthority,
  }).strict(),
  list_workflow_candidates: z.object({
    candidates: z.array(candidate).max(1000), truncated: z.boolean(), authority_mode: localAuthority,
  }).strict(),
  preview_profile_update: profileResult,
  transition_profile_update: profileResult,
  rollback_profile_revision: profileResult,
  purge_workflow_memory: z.object({
    status: z.enum(["purged", "blocked", "scope-not-available"]), scope: purgeScope,
    deleted_observations: count, deleted_feedback: count, deleted_command_receipts: count,
    summary_digest_before: digest, summary_digest_after: digest, replayed: z.boolean(),
    reason_codes: reasons, authority_mode: localAuthority,
  }).strict(),
} as const;
