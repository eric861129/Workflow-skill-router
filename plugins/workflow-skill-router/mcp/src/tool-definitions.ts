import { TOOL_INPUT_SHAPES } from "./tool-schemas.js";

export const PUBLIC_TOOL_NAMES = [
  "sync_runtime_context", "plan_work", "get_next_work", "validate_route",
  "record_work_event", "evaluate_gate", "get_router_status",
  "run_model_evaluation", "compare_evaluations", "export_router_artifact",
] as const;

export const TOOL_DEFINITIONS = PUBLIC_TOOL_NAMES.map((name) => ({
  name, description: `Workflow Skill Router V2：${name}`, inputSchema: TOOL_INPUT_SHAPES[name],
}));
