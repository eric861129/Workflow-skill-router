ALTER TABLE local_control_plans
ADD COLUMN local_work_graph_version INTEGER NOT NULL DEFAULT 0
CHECK (local_work_graph_version IN (0, 1));

CREATE TABLE local_work_items (
    work_item_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    work_graph_id TEXT NOT NULL,
    item_order INTEGER NOT NULL CHECK (item_order >= 0),
    phase_id TEXT NOT NULL,
    dependency_ids_json TEXT NOT NULL,
    primary_skill_id TEXT,
    support_skill_ids_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'pending', 'ready', 'active', 'verifying', 'paused', 'completed', 'failed',
        'decomposition-required', 'host-scheduler-required'
    )),
    authority_mode TEXT NOT NULL CHECK (authority_mode = 'router-local'),
    state_version INTEGER NOT NULL CHECK (state_version >= 1),
    created_at TEXT NOT NULL,
    FOREIGN KEY (workflow_run_id) REFERENCES local_control_plans(workflow_run_id),
    FOREIGN KEY (work_graph_id) REFERENCES local_control_plans(work_graph_id),
    UNIQUE (workflow_run_id, item_order),
    UNIQUE (workflow_run_id, phase_id)
);

CREATE INDEX idx_local_work_items_workflow_status
    ON local_work_items (workflow_run_id, status, item_order);

CREATE TABLE local_work_transitions (
    transition_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    workflow_run_id TEXT NOT NULL,
    work_item_id TEXT NOT NULL,
    transition_kind TEXT NOT NULL,
    from_status TEXT CHECK (from_status IS NULL OR from_status IN (
        'pending', 'ready', 'active', 'verifying', 'paused', 'completed', 'failed',
        'decomposition-required', 'host-scheduler-required'
    )),
    to_status TEXT NOT NULL CHECK (to_status IN (
        'pending', 'ready', 'active', 'verifying', 'paused', 'completed', 'failed',
        'decomposition-required', 'host-scheduler-required'
    )),
    expected_state_version INTEGER NOT NULL CHECK (expected_state_version >= 0),
    resulting_state_version INTEGER NOT NULL
        CHECK (resulting_state_version = expected_state_version + 1),
    idempotency_key TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workflow_run_id) REFERENCES local_control_plans(workflow_run_id),
    FOREIGN KEY (work_item_id) REFERENCES local_work_items(work_item_id),
    UNIQUE (session_id, idempotency_key),
    UNIQUE (work_item_id, resulting_state_version)
);

CREATE INDEX idx_local_work_transitions_item_version
    ON local_work_transitions (work_item_id, resulting_state_version);

CREATE TRIGGER local_work_transitions_no_update
BEFORE UPDATE ON local_work_transitions
BEGIN
    SELECT RAISE(ABORT, 'local_work_transitions is append-only');
END;

CREATE TRIGGER local_work_transitions_no_delete
BEFORE DELETE ON local_work_transitions
BEGIN
    SELECT RAISE(ABORT, 'local_work_transitions is append-only');
END;
