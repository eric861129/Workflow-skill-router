import { TOOL_INPUT_SHAPES } from "./tool-schemas.js";
import { TOOL_OUTPUT_SCHEMAS } from "./tool-output-schemas.js";


export const PUBLIC_TOOL_NAMES = [
  "sync_runtime_context", "plan_work", "propose_support_consent",
  "transition_support_consent", "get_next_work", "validate_route",
  "record_work_event", "evaluate_gate", "get_router_status",
  "run_model_evaluation", "compare_evaluations", "export_router_artifact",
] as const;

type PublicToolName = typeof PUBLIC_TOOL_NAMES[number];
type RuntimeRequirement = "local-r0" | "verified-host" | "configured-adapter";

const TITLES: Record<PublicToolName, string> = {
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
  sync_runtime_context: "Synchronize a verified host capability snapshot before routing or resuming work. This mutation requires verified-host authority and fails closed in the bundled local R0 runtime.",
  plan_work: "Create or replay a durable Single, Phased, or Managed Goal plan. The bundled local R0 runtime can apply strict user-owned personal and trusted-root workspace routing profiles while preserving explicit Skill locks. Profile choices remain intended routes until Runtime Discovery validates activation, and no speculative support-consent prompt is created.",
  propose_support_consent: "Persist one concrete Phase-scoped support SKILL set for an explicit-locked plan before asking the user. The bundled local R0 runtime binds the route, scope, revisions, and material context.",
  transition_support_consent: "Apply an approve or reject intent to a persisted support proposal. The bundled local R0 runtime preserves the bound route, rejects stale scope or revisions, and fails closed on conflicting replays.",
  get_next_work: "Read the next schedulable work item after refreshing Goal, workspace, capability, and evidence state. This read requires the verified-host scheduler and is unavailable in bundled local R0.",
  validate_route: "Validate a concrete route and any proposed support capability against current policy, consent, risk, and runtime evidence. This mutation requires verified-host snapshots and activation authority.",
  record_work_event: "Append a semantic work observation after validating activation receipts and reporting authority. This idempotent mutation requires the verified-host event store and fails closed locally.",
  evaluate_gate: "Evaluate and persist a phase gate against current state, plan revision, and evidence digest. This idempotent mutation requires verified-host evidence and gate authority.",
  get_router_status: "Read durable Router plan counts and native Goal status candidates without mutating the host Goal. This read is available from the bundled local R0 control plane.",
  run_model_evaluation: "Run fresh attempts from a sealed case through a server-configured evaluation adapter. This quota-consuming operation requires configured-adapter authority and never accepts executable paths from model input.",
  compare_evaluations: "Compare authorized baseline and candidate evaluation runs without fabricating unavailable metrics. This read requires configured evaluation evidence and remains review-required until attested.",
  export_router_artifact: "Export a sanitized evaluation artifact from a validated comparison and optional trusted attestation. This operation requires configured-adapter evidence and cannot self-approve publication.",
};

const RUNTIME_REQUIREMENTS: Record<PublicToolName, RuntimeRequirement> = {
  sync_runtime_context: "verified-host",
  plan_work: "local-r0",
  propose_support_consent: "local-r0",
  transition_support_consent: "local-r0",
  get_next_work: "verified-host",
  validate_route: "verified-host",
  record_work_event: "verified-host",
  evaluate_gate: "verified-host",
  get_router_status: "local-r0",
  run_model_evaluation: "configured-adapter",
  compare_evaluations: "configured-adapter",
  export_router_artifact: "configured-adapter",
};

const READ_ONLY = new Set<PublicToolName>([
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
    destructiveHint: false,
    idempotentHint: true,
    openWorldHint: name === "run_model_evaluation",
  },
  runtimeRequirement: RUNTIME_REQUIREMENTS[name],
}));
