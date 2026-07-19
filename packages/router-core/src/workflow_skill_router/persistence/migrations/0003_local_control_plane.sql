CREATE TABLE local_control_plans (
    plan_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    runtime_policy_snapshot_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    workflow_run_id TEXT NOT NULL UNIQUE,
    work_graph_id TEXT NOT NULL UNIQUE,
    goal_binding_id TEXT,
    objective_digest TEXT NOT NULL,
    routing_envelope TEXT NOT NULL CHECK (routing_envelope IN ('single', 'phased', 'managed-goal')),
    selection_mode TEXT NOT NULL CHECK (selection_mode IN ('auto', 'explicit-locked')),
    support_policy TEXT NOT NULL CHECK (support_policy IN ('auto', 'ask', 'forbid')),
    support_consent_required INTEGER NOT NULL CHECK (support_consent_required IN (0, 1)),
    explicit_skill_ids_json TEXT NOT NULL,
    explicit_semantics TEXT,
    created_work_items INTEGER NOT NULL CHECK (created_work_items >= 1),
    state_version INTEGER NOT NULL CHECK (state_version = 1),
    created_at TEXT NOT NULL,
    UNIQUE (session_id, idempotency_key)
);

CREATE INDEX idx_local_control_plans_goal
    ON local_control_plans (goal_binding_id, created_at);

CREATE INDEX idx_local_control_plans_session
    ON local_control_plans (session_id, created_at);
