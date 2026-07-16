import { z } from "zod";

const context = z.object({ session_id: z.string().min(1), actor: z.string().min(1), runtime_policy_snapshot_id: z.string().min(1) }).strict();
const mutation = { context, expected_state_version: z.number().int().nonnegative(), idempotency_key: z.string().min(1), correlation_id: z.string().min(1) };
const control = { context };
const agentSnapshot = z.object({ schema_id: z.string(), schema_version: z.string(), artifact_kind: z.string(), runtime_revision: z.string(), capabilities: z.array(z.object({ canonical_id: z.string(), kind: z.string(), display_name: z.string(), exposure: z.string(), aliases: z.array(z.string()) }).strict()) }).strict();

export const TOOL_INPUT_SHAPES = {
  sync_runtime_context: z.object({ ...mutation, intent: z.object({ host_snapshot_ref: z.string().nullable(), plugin_handshake_ref: z.string().nullable(), agent_runtime_snapshot: agentSnapshot }).strict() }).strict().shape,
  plan_work: z.object({ ...mutation, objective: z.string(), goal_binding_id: z.string().nullable(), requested_work_mode: z.string().nullable(), explicit_skill_ids: z.array(z.string()), explicit_semantics: z.string().nullable() }).strict().shape,
  get_next_work: z.object({ ...control, workflow_run_id: z.string() }).strict().shape,
  validate_route: z.object({ ...mutation, route_proposal: z.record(z.string(), z.unknown()), capability_snapshot_id: z.string(), policy_revision: z.number().int() }).strict().shape,
  record_work_event: z.object({ ...mutation, workflow_run_id: z.string(), phase_id: z.string(), observation: z.record(z.string(), z.unknown()), activation_receipt_ref: z.string().nullable() }).strict().shape,
  evaluate_gate: z.object({ ...mutation, workflow_run_id: z.string(), phase_id: z.string(), expected_plan_revision: z.number().int(), expected_evidence_digest: z.string(), evidence_refs: z.array(z.string()) }).strict().shape,
  get_router_status: z.object({ ...control, goal_binding_id: z.string().nullable(), workflow_run_id: z.string().nullable() }).strict().shape,
  run_model_evaluation: z.object({ ...control, authorization_ref: z.string(), sealed_case_ref: z.string(), repeats: z.number().int().min(1), idempotency_key: z.string(), correlation_id: z.string() }).strict().shape,
  compare_evaluations: z.object({ ...control, authorization_ref: z.string(), baseline_run_id: z.string(), candidate_run_id: z.string(), idempotency_key: z.string(), correlation_id: z.string() }).strict().shape,
  export_router_artifact: z.object({ ...control, authorization_ref: z.string(), comparison_ref: z.string(), export_kind: z.string(), attestation_ref: z.string().nullable(), idempotency_key: z.string(), correlation_id: z.string() }).strict().shape,
} as const;
