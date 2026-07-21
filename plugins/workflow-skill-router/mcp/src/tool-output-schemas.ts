import { z } from "zod";


const nullableIdentifier = z.string().nullable();
const unknownObject = z.record(z.string(), z.unknown());
const supportConsent = z.object({
  status: z.enum(["proposal-required", "approved", "rejected"]),
  proposal_id: z.string(),
  workflow_run_id: z.string(),
  phase_id: z.string(),
  routing_envelope: z.enum(["single", "phased", "managed-goal"]),
  selection_mode: z.literal("explicit-locked"),
  primary_skill: z.string(),
  support_skills: z.array(z.string()),
  consent_action: z.enum(["proposal-required", "approved", "rejected"]),
  goal_relation: z.enum(["none", "progress"]),
  decision_ref: z.string().nullable(),
  state_version: z.number().int().positive(),
  replayed: z.boolean(),
  runtime_mode: z.string(),
}).strict();
const plannedSkillPhase = z.object({
  phase_id: z.string(),
  primary_skill_id: z.string(),
  support_skill_ids: z.array(z.string()).max(3),
  exit_gate: z.string(),
}).strict();
const sha256Digest = z.string().regex(/^sha256:[0-9a-f]{64}$/);
const classificationDecision = z.object({
  source: z.enum([
    "native-goal-binding",
    "caller-work-mode-hint",
    "deterministic-analyzer",
    "profile-route",
    "builtin-fallback",
    "legacy-replay",
  ]).describe("Authoritative source for the deterministic work-envelope decision."),
  confidence: z.enum(["high", "medium", "low"]),
  classifier_revision: z.string(),
  reason_codes: z.array(z.string()),
}).strict().describe(
  "Deterministic classification trace for the work envelope only; it neither selects runtime capabilities nor grants authority.",
);
const nextWorkFields = {
  status: z.string(),
  refresh_requirements: z.array(z.string()),
  work_item: z.unknown().nullable(),
};
const recordWorkEvent = z.object({
  event_ids: z.array(z.string()),
  resulting_state_version: z.number().int().nonnegative(),
  replayed: z.boolean(),
  authority_mode: z.literal("router-local").optional(),
  evidence_class: z.literal("user-or-agent-reported-local").optional(),
  host_transition_authorized: z.literal(false).optional(),
}).strict().superRefine((value, context) => {
  const isLocal = value.authority_mode === "router-local";
  if (isLocal && (
    value.evidence_class !== "user-or-agent-reported-local"
    || value.host_transition_authorized !== false
  )) {
    context.addIssue({
      code: "custom",
      message: "Router-local records require local evidence and deny Host transition authority.",
    });
  }
  if (!isLocal && (
    value.evidence_class !== undefined
    || value.host_transition_authorized !== undefined
  )) {
    context.addIssue({
      code: "custom",
      message: "Verified-Host records cannot carry Router-local-only fields.",
    });
  }
});
const gateEvaluation = z.object({
  status: z.string(),
  passed: z.boolean(),
  failures: z.array(z.string()).optional(),
  mandatory_failures: z.array(z.string()).optional(),
  evidence_digest: sha256Digest,
  resulting_state_version: z.number().int().nonnegative().optional(),
  replayed: z.boolean().optional(),
  gate_scope: z.literal("router-local").optional(),
  authority_mode: z.literal("router-local").optional(),
  evidence_class: z.literal("user-or-agent-reported-local").optional(),
  host_transition_authorized: z.literal(false).optional(),
}).strict().superRefine((value, context) => {
  const isLocal = value.authority_mode === "router-local";
  const localFieldsComplete = value.status === "evaluated-local"
    && value.failures !== undefined
    && value.resulting_state_version !== undefined
    && value.replayed !== undefined
    && value.gate_scope === "router-local"
    && value.evidence_class === "user-or-agent-reported-local"
    && value.host_transition_authorized === false
    && value.mandatory_failures === undefined;
  if (isLocal && !localFieldsComplete) {
    context.addIssue({
      code: "custom",
      message: "Router-local gates require the complete local evidence boundary and no Host-only fields.",
    });
  }
  const carriesLocalOnlyField = value.failures !== undefined
    || value.resulting_state_version !== undefined
    || value.replayed !== undefined
    || value.gate_scope !== undefined
    || value.evidence_class !== undefined
    || value.host_transition_authorized !== undefined;
  if (!isLocal && (value.mandatory_failures === undefined || carriesLocalOnlyField)) {
    context.addIssue({
      code: "custom",
      message: "Verified-Host gates require mandatory_failures and cannot carry Router-local-only fields.",
    });
  }
});

export const TOOL_OUTPUT_SCHEMAS = {
  sync_runtime_context: z.object({
    snapshot: unknownObject,
    drift: z.array(unknownObject),
    provider_failures: z.array(unknownObject),
    cache_used: z.boolean(),
    degraded: z.boolean(),
  }).strict(),
  plan_work: z.object({
    status: z.string(),
    workflow_run_id: nullableIdentifier,
    work_graph_id: nullableIdentifier,
    created_work_items: z.number().int().nonnegative(),
    routing_envelope: z.string(),
    selection_mode: z.string(),
    support_consent_required: z.boolean(),
    planned_skill_ids: z.array(z.string()).describe(
      "Planned Skill intent from an explicit lock or deterministic Profile; it does not prove runtime activation.",
    ),
    runtime_mode: z.string(),
    route_source: z.enum([
      "user-explicit", "workspace-profile", "personal-profile", "builtin-default",
    ]).describe("Source of planned Skill intent, distinct from work-envelope classification."),
    routing_profile_ids: z.array(z.string()),
    routing_profile_digest: sha256Digest.nullable(),
    matched_profile_rule_id: z.string().nullable(),
    planned_skill_tree: z.array(plannedSkillPhase),
    activation_status: z.enum(["not-planned", "intended-unverified"]).describe(
      "Planning evidence only; intended-unverified never proves actual activation.",
    ),
    profile_warnings: z.array(z.string()),
    classification: classificationDecision,
  }).strict(),
  propose_support_consent: supportConsent,
  transition_support_consent: supportConsent,
  get_next_work: z.object({
    ...nextWorkFields,
    authority_mode: z.enum(["router-local", "verified-host"]),
    host_goal_mutated: z.boolean(),
  }).strict().superRefine((value, context) => {
    if (value.authority_mode === "router-local" && value.host_goal_mutated) {
      context.addIssue({
        code: "custom",
        message: "Router-local scheduling cannot claim a Host Goal mutation.",
      });
    }
  }),
  validate_route: z.object({
    valid: z.boolean(),
    violations: z.array(unknownObject),
    requires_runtime_approval: z.boolean(),
    route: z.unknown().nullable(),
    lease: z.unknown().nullable(),
    outcome_mode: z.string(),
    exit_gate: z.string().nullable(),
  }).strict(),
  record_work_event: recordWorkEvent,
  evaluate_gate: gateEvaluation,
  get_router_status: z.object({
    goal_binding_id: nullableIdentifier,
    workflow_run_id: nullableIdentifier,
    created_work_items: z.number().int().nonnegative(),
    goal_status_candidate: z.object({
      candidate_id: z.string(),
      candidate_type: z.string(),
      evidence_digest: z.string(),
    }).strict().nullable(),
    host_goal_mutated: z.boolean(),
  }).strict(),
  run_model_evaluation: z.object({
    run_id: z.string(),
    status: z.string(),
    profile: z.string(),
    adapter_kind: z.string(),
    attempts: z.array(unknownObject),
    manifest_digest: z.string(),
    evidence_class: z.string(),
  }).strict(),
  compare_evaluations: z.object({
    baseline_run_id: z.string(),
    candidate_run_id: z.string(),
    paired_count: z.number().int().nonnegative(),
    pass_rate_difference: z.number(),
    hard_violation_difference: z.number().int(),
    candidate_release_eligible: z.boolean(),
  }).strict(),
  export_router_artifact: z.object({
    schema_version: z.string(),
    status: z.string(),
    evidence_class: z.string(),
    summary: unknownObject,
    review_subject_digest: z.string(),
    review_authority: z.string().nullable(),
    reviewed_at: z.string().nullable(),
    artifact_digest: z.string().nullable(),
  }).strict(),
} as const;
