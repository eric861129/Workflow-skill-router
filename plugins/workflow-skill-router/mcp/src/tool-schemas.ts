import { z } from "zod";


const context = z.object({
  session_id: z.string().min(1).describe("Stable session identifier used to isolate Router state and idempotency."),
  actor: z.string().min(1).describe("Verified user or host actor responsible for this request."),
  runtime_policy_snapshot_id: z.string().min(1).describe("Host policy snapshot governing authority and runtime behavior."),
}).strict().describe("Authority context supplied by the Codex host.");

const mutation = {
  context,
  expected_state_version: z.number().int().nonnegative().describe("Expected aggregate state version for compare-and-swap protection."),
  idempotency_key: z.string().min(1).describe("Caller-stable key that safely replays the same semantic command."),
  correlation_id: z.string().min(1).describe("Public-safe correlation identifier for tracing one command flow."),
};
const control = { context };
const agentSnapshot = z.object({
  schema_id: z.string().describe("Registered schema identifier for the agent runtime snapshot."),
  schema_version: z.string().describe("Version of the registered runtime snapshot schema."),
  artifact_kind: z.string().describe("Artifact discriminator for the runtime snapshot."),
  runtime_revision: z.string().describe("Host-observed revision of the available runtime surface."),
  capabilities: z.array(z.object({
    canonical_id: z.string().describe("Canonical capability identifier."),
    kind: z.string().describe("Capability kind such as Skill, Plugin, MCP tool, or app."),
    display_name: z.string().describe("Human-readable capability name."),
    exposure: z.string().describe("How the capability is exposed to the current agent runtime."),
    aliases: z.array(z.string()).describe("Alternative identifiers observed for this capability."),
  }).strict()).describe("Capabilities directly observable from the current agent runtime."),
}).strict();

export const TOOL_INPUT_SHAPES = {
  sync_runtime_context: z.object({
    ...mutation,
    intent: z.object({
      host_snapshot_ref: z.string().nullable().describe("Verified host snapshot reference, or null when unavailable."),
      plugin_handshake_ref: z.string().nullable().describe("Verified Plugin handshake reference, or null when unavailable."),
      agent_runtime_snapshot: agentSnapshot.describe("Runtime capabilities directly observed by the active agent."),
    }).strict().describe("Inputs to verified runtime capability discovery."),
  }).strict().shape,
  plan_work: z.object({
    ...mutation,
    objective: z.string().min(1).describe("The user-visible outcome this workflow must achieve."),
    goal_binding_id: z.string().nullable().describe("Native Goal identifier when this request progresses or steers an existing Goal."),
    requested_work_mode: z.enum(["single", "phased", "managed-goal"]).nullable().describe("Explicit envelope hint; null allows Router classification."),
    explicit_skill_ids: z.array(z.string()).describe("Skill IDs explicitly selected by the user; an empty array means automatic routing."),
    explicit_semantics: z.enum(["use", "only"]).nullable().describe("How explicit Skill IDs constrain routing; null when no explicit lock exists."),
  }).strict().shape,
  get_next_work: z.object({
    ...control,
    workflow_run_id: z.string().min(1).describe("Workflow run whose next host-scheduled work item is requested."),
  }).strict().shape,
  validate_route: z.object({
    ...mutation,
    route_proposal: z.record(z.string(), z.unknown()).describe("Complete route proposal evaluated against current policy and capability state."),
    capability_snapshot_id: z.string().min(1).describe("Verified capability snapshot used for route validation."),
    policy_revision: z.number().int().nonnegative().describe("Immutable routing policy revision expected by the caller."),
  }).strict().shape,
  record_work_event: z.object({
    ...mutation,
    workflow_run_id: z.string().min(1).describe("Workflow run receiving the semantic observation."),
    phase_id: z.string().min(1).describe("Phase receiving the semantic observation."),
    observation: z.record(z.string(), z.unknown()).describe("Versioned work observation validated by the core codec."),
    activation_receipt_ref: z.string().nullable().describe("Single-use activation receipt when the observation reports execution."),
  }).strict().shape,
  evaluate_gate: z.object({
    ...mutation,
    workflow_run_id: z.string().min(1).describe("Workflow run whose phase gate is evaluated."),
    phase_id: z.string().min(1).describe("Phase whose exit gate is evaluated."),
    expected_plan_revision: z.number().int().nonnegative().describe("Plan revision bound to this gate decision."),
    expected_evidence_digest: z.string().min(1).describe("Evidence digest expected before evaluating mandatory checks."),
    evidence_refs: z.array(z.string()).describe("Content-addressed evidence references considered by the gate."),
  }).strict().shape,
  get_router_status: z.object({
    ...control,
    goal_binding_id: z.string().nullable().describe("Native Goal binding to filter, or null for session scope."),
    workflow_run_id: z.string().nullable().describe("Workflow run to filter, or null for session scope."),
  }).strict().shape,
  run_model_evaluation: z.object({
    ...control,
    authorization_ref: z.string().min(1).describe("Trusted server-side authorization selecting a configured evaluation adapter."),
    sealed_case_ref: z.string().min(1).describe("Reference to a sealed evaluation package with isolated scoring data."),
    repeats: z.number().int().min(1).describe("Fresh attempt count requested for each selected evaluation case."),
    idempotency_key: z.string().min(1).describe("Caller-stable key for this authorized evaluation request."),
    correlation_id: z.string().min(1).describe("Public-safe evaluation correlation identifier."),
  }).strict().shape,
  compare_evaluations: z.object({
    ...control,
    authorization_ref: z.string().min(1).describe("Trusted authorization permitting comparison of the selected runs."),
    baseline_run_id: z.string().min(1).describe("Completed baseline evaluation run identifier."),
    candidate_run_id: z.string().min(1).describe("Completed candidate evaluation run identifier."),
    idempotency_key: z.string().min(1).describe("Caller-stable key for the comparison request."),
    correlation_id: z.string().min(1).describe("Public-safe comparison correlation identifier."),
  }).strict().shape,
  export_router_artifact: z.object({
    ...control,
    authorization_ref: z.string().min(1).describe("Trusted authorization permitting sanitized artifact export."),
    comparison_ref: z.string().min(1).describe("Validated evaluation comparison used to build the artifact."),
    export_kind: z.string().min(1).describe("Supported sanitized export format requested by the caller."),
    attestation_ref: z.string().nullable().describe("Human or trusted verifier attestation, or null for review-required output."),
    idempotency_key: z.string().min(1).describe("Caller-stable key for the export request."),
    correlation_id: z.string().min(1).describe("Public-safe export correlation identifier."),
  }).strict().shape,
} as const;
