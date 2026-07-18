CREATE TABLE local_support_consent_proposals (
    proposal_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    workflow_run_id TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    scope_anchor_id TEXT NOT NULL,
    goal_binding_id TEXT,
    goal_revision INTEGER,
    plan_revision INTEGER NOT NULL CHECK (plan_revision >= 1),
    routing_envelope TEXT NOT NULL CHECK (routing_envelope IN ('single', 'phased', 'managed-goal')),
    selection_mode TEXT NOT NULL CHECK (selection_mode = 'explicit-locked'),
    primary_skill_id TEXT NOT NULL,
    support_skill_ids_json TEXT NOT NULL,
    context_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
    decision_ref TEXT,
    state_version INTEGER NOT NULL CHECK (state_version IN (1, 2)),
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    FOREIGN KEY (workflow_run_id) REFERENCES local_control_plans(workflow_run_id),
    UNIQUE (session_id, idempotency_key)
);

CREATE INDEX idx_local_support_consent_workflow_phase
    ON local_support_consent_proposals (workflow_run_id, phase_id, status);

CREATE TABLE local_support_consent_transitions (
    transition_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('approve', 'reject')),
    decision_ref TEXT NOT NULL,
    resulting_state_version INTEGER NOT NULL CHECK (resulting_state_version = 2),
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (proposal_id) REFERENCES local_support_consent_proposals(proposal_id),
    UNIQUE (session_id, idempotency_key)
);
