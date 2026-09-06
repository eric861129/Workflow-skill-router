import { MEMORY_TOOL_NAMES } from "./memory-tool-schemas.js";
import { TOOL_INPUT_SHAPES } from "./tool-schemas.js";
import { TOOL_OUTPUT_SCHEMAS } from "./tool-output-schemas.js";


export const PUBLIC_TOOL_NAMES = [
  "sync_runtime_context", "plan_work", "propose_support_consent",
  "transition_support_consent", "get_next_work", "validate_route",
  "record_work_event", "evaluate_gate", "get_router_status",
  "run_model_evaluation", "compare_evaluations", "export_router_artifact",
  ...MEMORY_TOOL_NAMES,
] as const;

type PublicToolName = typeof PUBLIC_TOOL_NAMES[number];
type RuntimeRequirement =
  | "local-r0"
  | "conditional-local"
  | "verified-host"
  | "configured-adapter";

const TITLES: Record<PublicToolName, string> = {
  get_memory_status: "Get Workflow Memory Status",
  remember_workflow: "Remember Completed Workflow",
  record_route_feedback: "Record Typed Route Feedback",
  list_workflow_candidates: "List Workflow Memory Candidates",
  preview_profile_update: "Preview Bound Profile Update",
  transition_profile_update: "Apply Reviewed Profile Decision",
  rollback_profile_revision: "Propose Profile Revision Rollback",
  purge_workflow_memory: "Purge Explicit Workflow Memory Scope",

  sync_runtime_context: "Sync Runtime Capabilities",
  plan_work: "Plan Routed Work",
  propose_support_consent: "Propose Scoped Support",
  transition_support_consent: "Apply Support Consent",
  get_next_work: "Get Next Work Item",
  validate_route: "Validate Proposed Route",
  record_work_event: "Record Work Observation",
  evaluate_gate: "Evaluate Phase Gate",
  get_router_status: "Get Router Status",
  run_model_evaluation: "Run Sealed Model Evaluation",
  compare_evaluations: "Compare Evaluation Runs",
  export_router_artifact: "Export Reviewed Router Artifact",
};

const DESCRIPTIONS: Record<PublicToolName, string> = {
  get_memory_status: "Read the effective default-off Memory policy and a path-free global history summary without creating or migrating optional Memory state. A policy is not Skill activation, Host write permission, or background learning.",
  remember_workflow: "Record one eligible completed local Workflow under the current opt-in Memory policy using only retained routing context. This explicit local operation may rebuild Candidates but does not promote Profiles, infer raw matchers, activate Skills, or grant Side-effect authority.",
  record_route_feedback: "Record bounded typed feedback against an existing Observation and matching Workflow session. The operation rejects unbound corrections and accepts no free-text feedback, raw objective, or caller-provided Profile content.",
  list_workflow_candidates: "Read sanitized Candidate evidence summaries with a bounded result limit, Workspace isolation, and an explicit truncation marker. This read-only operation never rebuilds Candidates, creates a Memory store, or grants runtime authority.",
  preview_profile_update: "Build a read-only, deterministic Profile preview with semantic Diff, canonical Profile JSON, Backtest, and full Proposal Digest. No Proposal or Profile is persisted; approval must reproduce and bind the same preview before a local write.",
  transition_profile_update: "Apply an explicit approve or reject decision to the exact bound Profile preview under the current Memory policy. This conditional-local operation uses CAS, Backtest, Revision and atomic writes; workspace-file targets require verified Host write authority and fail closed in the bundled runtime.",
  rollback_profile_revision: "Create a new reviewable rollback Proposal from a validated Revision and current Profile Digest. This conditional-local mutation does not silently write a Profile; the new Proposal requires transition approval. Workspace file writes still require verified Host authority.",
  purge_workflow_memory: "Purge an explicitly confirmed local Memory scope bound to the current global summary Digest, including after capture is disabled. This destructive R1 operation never deletes User-owned Profiles; unsupported scopes return scope-not-available without claiming deletion.",

  sync_runtime_context: "Synchronize a verified host capability snapshot before routing or resuming work. This mutation requires verified-host authority and fails closed in the bundled local R0 runtime.",
  plan_work: "Create or replay a durable Single, Phased, or Managed Goal plan using deterministic automatic classification plus an optional deterministic Profile from user-owned configuration. The result exposes both sources and planned Skill intent; activation remains unverified until Runtime Discovery supplies evidence. Explicit Skill Lock and scoped consent still apply. This local planner is not a semantic model, does not activate Skills or mutate a native Codex Goal, and grants no deployment or production authority.",
  propose_support_consent: "Persist one concrete Phase-scoped support SKILL set for an explicit-locked plan before asking the user. The bundled local R0 runtime binds the route, scope, revisions, and material context.",
  transition_support_consent: "Apply an approve or reject intent to a persisted support proposal. The bundled local R0 runtime preserves the bound route, rejects stale scope or revisions, and fails closed on conflicting replays.",
  get_next_work: "For a validated Router-owned work graph with no Native Goal authority, return the next local item with authority_mode=router-local and host_goal_mutated=false. Native Goal scheduling requires verified-host-scheduler. A missing graph requests Router-owned graph creation or replay; a corrupt graph returns only a sanitized internal-error correlation. All unavailable or unsafe branches fail closed.",
  validate_route: "Validate a concrete route and any proposed support capability against current policy, consent, risk, and runtime evidence. This mutation requires verified-host snapshots and activation authority.",
  record_work_event: "For a validated Router-owned work graph with no Native Goal authority, append only user-or-agent-reported-local progress and return host_transition_authorized=false. Native Goal work requires verified-event-store and activation-receipt-verifier. A missing graph requests local graph creation or replay; a corrupt graph returns a sanitized internal-error. All unavailable or unsafe branches fail closed.",
  evaluate_gate: "For a validated Router-owned work graph with no Native Goal authority, evaluate only persisted local check IDs as a router-local advisory gate with host_transition_authorized=false. A local pass is not Skill activation, Native Goal completion, deployment, or production approval. Native Goal gates require verified-evidence-store and gate-authority; missing graphs request local creation or replay, while corrupt graphs return a sanitized internal-error. All unavailable or unsafe branches fail closed.",
  get_router_status: "Read durable Router plan counts and native Goal status candidates without mutating the host Goal. This read is available from the bundled local R0 control plane.",
  run_model_evaluation: "Run fresh attempts from a sealed case through a server-configured evaluation adapter. This quota-consuming operation requires configured-adapter authority and never accepts executable paths from model input.",
  compare_evaluations: "Compare authorized baseline and candidate evaluation runs without fabricating unavailable metrics. This read requires configured evaluation evidence and remains review-required until attested.",
  export_router_artifact: "Export a sanitized evaluation artifact from a validated comparison and optional trusted attestation. This operation requires configured-adapter evidence and cannot self-approve publication.",
};

const RUNTIME_REQUIREMENTS: Record<PublicToolName, RuntimeRequirement> = {
  get_memory_status: "local-r0",
  remember_workflow: "local-r0",
  record_route_feedback: "local-r0",
  list_workflow_candidates: "local-r0",
  preview_profile_update: "local-r0",
  transition_profile_update: "conditional-local",
  rollback_profile_revision: "conditional-local",
  purge_workflow_memory: "local-r0",

  sync_runtime_context: "verified-host",
  plan_work: "local-r0",
  propose_support_consent: "local-r0",
  transition_support_consent: "local-r0",
  get_next_work: "conditional-local",
  validate_route: "verified-host",
  record_work_event: "conditional-local",
  evaluate_gate: "conditional-local",
  get_router_status: "local-r0",
  run_model_evaluation: "configured-adapter",
  compare_evaluations: "configured-adapter",
  export_router_artifact: "configured-adapter",
};

const READ_ONLY = new Set<PublicToolName>([
  "get_memory_status", "list_workflow_candidates", "preview_profile_update",
  "get_next_work",
  "get_router_status",
  "compare_evaluations",
]);

export const TOOL_DEFINITIONS = PUBLIC_TOOL_NAMES.map((name) => ({
  name,
  title: TITLES[name],
  description: DESCRIPTIONS[name],
  inputSchema: TOOL_INPUT_SHAPES[name],
  outputSchema: TOOL_OUTPUT_SCHEMAS[name].shape,
  annotations: {
    readOnlyHint: READ_ONLY.has(name),
    destructiveHint: name === "purge_workflow_memory",
    idempotentHint: true,
    openWorldHint: name === "run_model_evaluation",
  },
  runtimeRequirement: RUNTIME_REQUIREMENTS[name],
}));
