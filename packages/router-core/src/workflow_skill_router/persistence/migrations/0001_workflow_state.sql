PRAGMA foreign_keys = ON;

CREATE TABLE schema_migrations (
    version TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE TABLE aggregate_versions (
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version >= 0),
    PRIMARY KEY (aggregate_type, aggregate_id)
);
CREATE TABLE command_receipts (
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    event_ids_json TEXT NOT NULL,
    resulting_state_version INTEGER NOT NULL,
    PRIMARY KEY (aggregate_type, aggregate_id, idempotency_key)
);
CREATE TABLE workflow_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    schema_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    artifact_kind TEXT NOT NULL CHECK (artifact_kind = 'workflow-event'),
    event_id TEXT NOT NULL UNIQUE,
    workflow_run_id TEXT,
    aggregate_id TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    state_version_before INTEGER NOT NULL,
    state_version_after INTEGER NOT NULL,
    plan_revision INTEGER NOT NULL,
    payload_digest TEXT NOT NULL,
    payload_ref TEXT,
    inline_payload TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    causation_id TEXT,
    CHECK (state_version_after = state_version_before + 1),
    CHECK (
      (aggregate_type = 'workflow' AND workflow_run_id IS NOT NULL AND workflow_run_id = aggregate_id)
      OR (aggregate_type <> 'workflow' AND workflow_run_id IS NULL)
    )
);
CREATE INDEX idx_workflow_events_stream
    ON workflow_events (aggregate_type, aggregate_id, state_version_after);
CREATE INDEX idx_workflow_events_workflow
    ON workflow_events (workflow_run_id, sequence);
CREATE TRIGGER workflow_events_no_update
BEFORE UPDATE ON workflow_events BEGIN
    SELECT RAISE(ABORT, 'workflow_events is append-only');
END;
CREATE TRIGGER workflow_events_no_delete
BEFORE DELETE ON workflow_events BEGIN
    SELECT RAISE(ABORT, 'workflow_events is append-only');
END;

CREATE TABLE projection_checkpoints (
    projection_name TEXT PRIMARY KEY,
    last_sequence INTEGER NOT NULL
);
CREATE TABLE capability_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    runtime_fingerprint TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE capabilities (
    snapshot_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    availability_r0 TEXT NOT NULL,
    availability_r1 TEXT NOT NULL,
    availability_r2 TEXT NOT NULL,
    availability_r3 TEXT NOT NULL,
    availability_reasons_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, capability_id),
    FOREIGN KEY (snapshot_id) REFERENCES capability_snapshots(snapshot_id)
);
CREATE TABLE capability_drifts (
    drift_id TEXT PRIMARY KEY,
    previous_snapshot_id TEXT NOT NULL,
    current_snapshot_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    drift_kind TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE workflow_runs (
    workflow_run_id TEXT PRIMARY KEY,
    objective_digest TEXT NOT NULL,
    envelope TEXT NOT NULL,
    status TEXT NOT NULL,
    plan_revision INTEGER NOT NULL,
    capability_snapshot_id TEXT NOT NULL,
    current_phase_id TEXT,
    paused_from_status TEXT,
    awaiting_from_status TEXT,
    pause_reason TEXT,
    state_version INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE phase_runs (
    phase_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    work_item_id TEXT NOT NULL,
    status TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    supersedes_phase_id TEXT,
    state_version INTEGER NOT NULL,
    evidence_digest TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_phase_one_active_per_workflow
    ON phase_runs(workflow_run_id) WHERE status = 'active';
CREATE TABLE goal_bindings (
    goal_binding_id TEXT PRIMARY KEY,
    host_goal_id TEXT,
    goal_revision INTEGER NOT NULL,
    host_goal_revision TEXT,
    source TEXT NOT NULL CHECK (source IN ('native', 'managed')),
    objective_digest TEXT NOT NULL,
    status_snapshot TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE goal_revisions (
    goal_binding_id TEXT NOT NULL,
    goal_revision INTEGER NOT NULL,
    objective_digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (goal_binding_id, goal_revision)
);
CREATE TABLE goal_acceptance_coverage (
    goal_binding_id TEXT NOT NULL,
    goal_revision INTEGER NOT NULL,
    criterion_id TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (goal_binding_id, goal_revision, criterion_id)
);
CREATE TABLE work_graphs (
    work_graph_id TEXT PRIMARY KEY,
    goal_binding_id TEXT NOT NULL,
    plan_revision INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE work_items (
    work_item_id TEXT PRIMARY KEY,
    work_graph_id TEXT NOT NULL,
    status TEXT NOT NULL,
    required INTEGER NOT NULL CHECK (required IN (0, 1)),
    envelope TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE workflow_completion_candidates (
    candidate_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    state_version INTEGER NOT NULL,
    evidence_digest TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE artifact_metadata (
    digest TEXT PRIMARY KEY,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    media_type TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    producer TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    protection_kind TEXT NOT NULL,
    protection_ref TEXT,
    created_at TEXT NOT NULL,
    tombstoned_at TEXT,
    erased_at TEXT,
    payload_json TEXT NOT NULL
);
CREATE TABLE goal_status_candidates (
    candidate_id TEXT PRIMARY KEY,
    goal_binding_id TEXT NOT NULL,
    candidate_type TEXT NOT NULL CHECK (candidate_type IN ('complete', 'blocked')),
    goal_revision INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE evidence_metadata (
    evidence_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    content_digest TEXT NOT NULL,
    produced_at TEXT NOT NULL,
    workspace_revision TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE consent_grants (
    grant_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    scope_anchor_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    context_fingerprint TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE consent_rejections (
    rejection_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    scope_anchor_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    context_fingerprint TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE lease_content_bindings (
    lease_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    binding_kind TEXT NOT NULL CHECK (binding_kind IN ('instruction-content','tool-schema','runtime-contract')),
    trusted_binding_digest TEXT NOT NULL,
    observed_binding_digest TEXT NOT NULL,
    binding_receipt_digest TEXT NOT NULL,
    bound_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (lease_id, capability_id)
);
CREATE TABLE lease_activation_consumptions (
    lease_id TEXT PRIMARY KEY,
    capability_id TEXT NOT NULL,
    scope_anchor_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    invocation_context_digest TEXT NOT NULL,
    invocation_digest TEXT NOT NULL,
    action_digest TEXT NOT NULL,
    runtime_approval_ref TEXT,
    runtime_approval_scope_digest TEXT,
    binding_kind TEXT NOT NULL CHECK (binding_kind IN ('instruction-content','tool-schema','runtime-contract')),
    observed_binding_digest TEXT NOT NULL,
    binding_receipt_digest TEXT NOT NULL,
    state_version INTEGER NOT NULL,
    consumption_version INTEGER NOT NULL CHECK (consumption_version = 1),
    consumed_at TEXT NOT NULL,
    reservation_digest TEXT NOT NULL,
    activation_status TEXT NOT NULL CHECK (activation_status IN ('reserved','activated','failed','unknown')),
    activation_receipt_digest TEXT,
    activated_at TEXT
);
CREATE TABLE resource_locks (
    resource_lock_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    resource_digest TEXT NOT NULL,
    mode TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE side_effect_attempts (
    attempt_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    action_digest TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed-success', 'confirmed-failure', 'unknown')),
    payload_json TEXT NOT NULL
);
