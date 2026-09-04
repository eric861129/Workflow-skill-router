CREATE TABLE memory_policy_snapshots (
    snapshot_id TEXT PRIMARY KEY
        CHECK(length(snapshot_id) = 71)
        CHECK(substr(snapshot_id, 1, 7) = 'sha256:')
        CHECK(substr(snapshot_id, 8) NOT GLOB '*[^0-9a-f]*'),
    policy_digest TEXT NOT NULL
        CHECK(length(policy_digest) = 71)
        CHECK(substr(policy_digest, 1, 7) = 'sha256:')
        CHECK(substr(policy_digest, 8) NOT GLOB '*[^0-9a-f]*'),
    mode TEXT NOT NULL
        CHECK(mode IN ('disabled', 'observe', 'reviewed', 'automatic')),
    personal_mode TEXT NOT NULL
        CHECK(personal_mode IN ('disabled', 'observe', 'reviewed', 'automatic')),
    workspace_requested_mode TEXT
        CHECK(
            workspace_requested_mode IS NULL
            OR workspace_requested_mode IN (
                'disabled',
                'observe',
                'reviewed',
                'automatic'
            )
        ),
    policy_source TEXT NOT NULL
        CHECK(length(policy_source) BETWEEN 1 AND 64),
    capture_enabled INTEGER NOT NULL
        CHECK(capture_enabled IN (0, 1)),
    candidate_generation_enabled INTEGER NOT NULL
        CHECK(candidate_generation_enabled IN (0, 1)),
    profile_promotion TEXT NOT NULL
        CHECK(
            profile_promotion IN (
                'disabled',
                'review-required',
                'automatic-managed'
            )
        ),
    allowed_targets_json TEXT NOT NULL
        CHECK(length(allowed_targets_json) BETWEEN 2 AND 512),
    features_json TEXT NOT NULL
        CHECK(length(features_json) BETWEEN 2 AND 4096),
    reason_codes_json TEXT NOT NULL
        CHECK(length(reason_codes_json) BETWEEN 2 AND 4096),
    recorded_at TEXT NOT NULL
        CHECK(length(recorded_at) BETWEEN 20 AND 40)
) WITHOUT ROWID;

CREATE TABLE route_observations (
    observation_id TEXT PRIMARY KEY
        CHECK(length(observation_id) BETWEEN 1 AND 128),
    workflow_fingerprint TEXT NOT NULL
        CHECK(length(workflow_fingerprint) = 71)
        CHECK(substr(workflow_fingerprint, 1, 7) = 'sha256:')
        CHECK(substr(workflow_fingerprint, 8) NOT GLOB '*[^0-9a-f]*'),
    workspace_identity_digest TEXT
        CHECK(
            workspace_identity_digest IS NULL
            OR (
                length(workspace_identity_digest) = 71
                AND substr(workspace_identity_digest, 1, 7) = 'sha256:'
                AND substr(workspace_identity_digest, 8)
                    NOT GLOB '*[^0-9a-f]*'
            )
        ),
    work_mode TEXT NOT NULL
        CHECK(work_mode IN ('single', 'phased', 'managed-goal')),
    route_digest TEXT NOT NULL
        CHECK(length(route_digest) = 71)
        CHECK(substr(route_digest, 1, 7) = 'sha256:')
        CHECK(substr(route_digest, 8) NOT GLOB '*[^0-9a-f]*'),
    terminal_status TEXT NOT NULL
        CHECK(
            terminal_status IN (
                'completed',
                'failed',
                'blocked',
                'cancelled'
            )
        ),
    required_gates_passed INTEGER NOT NULL
        CHECK(required_gates_passed IN (0, 1)),
    side_effect_status TEXT NOT NULL
        CHECK(side_effect_status IN ('none', 'known', 'unknown')),
    risk_level TEXT NOT NULL
        CHECK(risk_level IN ('r0', 'r1', 'r2', 'r3')),
    policy_snapshot_id TEXT NOT NULL
        REFERENCES memory_policy_snapshots(snapshot_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    source_event_ref TEXT NOT NULL
        CHECK(length(source_event_ref) BETWEEN 1 AND 160),
    observed_at TEXT NOT NULL
        CHECK(length(observed_at) BETWEEN 20 AND 40)
) WITHOUT ROWID;

CREATE TABLE route_feedback (
    feedback_id TEXT PRIMARY KEY
        CHECK(length(feedback_id) BETWEEN 1 AND 128),
    observation_id TEXT NOT NULL
        REFERENCES route_observations(observation_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,
    feedback_kind TEXT NOT NULL
        CHECK(feedback_kind IN ('accepted', 'corrected', 'rejected')),
    reason_code TEXT
        CHECK(reason_code IS NULL OR length(reason_code) BETWEEN 1 AND 64),
    source_event_ref TEXT NOT NULL
        CHECK(length(source_event_ref) BETWEEN 1 AND 160),
    recorded_at TEXT NOT NULL
        CHECK(length(recorded_at) BETWEEN 20 AND 40)
) WITHOUT ROWID;

CREATE TABLE memory_command_receipts (
    idempotency_key TEXT PRIMARY KEY
        CHECK(length(idempotency_key) BETWEEN 1 AND 160),
    command_kind TEXT NOT NULL
        CHECK(length(command_kind) BETWEEN 1 AND 64),
    command_digest TEXT NOT NULL
        CHECK(length(command_digest) = 71)
        CHECK(substr(command_digest, 1, 7) = 'sha256:')
        CHECK(substr(command_digest, 8) NOT GLOB '*[^0-9a-f]*'),
    result_digest TEXT NOT NULL
        CHECK(length(result_digest) = 71)
        CHECK(substr(result_digest, 1, 7) = 'sha256:')
        CHECK(substr(result_digest, 8) NOT GLOB '*[^0-9a-f]*'),
    created_at TEXT NOT NULL
        CHECK(length(created_at) BETWEEN 20 AND 40)
) WITHOUT ROWID;

CREATE INDEX route_observations_workflow_time_idx
    ON route_observations(workflow_fingerprint, observed_at);

CREATE INDEX route_observations_policy_idx
    ON route_observations(policy_snapshot_id);

CREATE INDEX route_feedback_observation_time_idx
    ON route_feedback(observation_id, recorded_at);
