CREATE TABLE route_feedback_events (
    feedback_id TEXT PRIMARY KEY
        CHECK(length(feedback_id) BETWEEN 10 AND 128)
        CHECK(substr(feedback_id, 1, 9) = 'feedback:'),
    feedback_digest TEXT NOT NULL UNIQUE
        CHECK(length(feedback_digest) = 71)
        CHECK(substr(feedback_digest, 1, 7) = 'sha256:')
        CHECK(substr(feedback_digest, 8) NOT GLOB '*[^0-9a-f]*'),
    observation_id TEXT NOT NULL
        REFERENCES route_observations(observation_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,
    observation_digest TEXT NOT NULL
        CHECK(length(observation_digest) = 71)
        CHECK(substr(observation_digest, 1, 7) = 'sha256:'),
    workflow_run_digest TEXT NOT NULL
        CHECK(length(workflow_run_digest) = 71)
        CHECK(substr(workflow_run_digest, 1, 7) = 'sha256:'),
    policy_snapshot_id TEXT NOT NULL
        REFERENCES memory_policy_snapshots(snapshot_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    policy_digest TEXT NOT NULL
        CHECK(length(policy_digest) = 71)
        CHECK(substr(policy_digest, 1, 7) = 'sha256:'),
    feedback_type TEXT NOT NULL
        CHECK(feedback_type IN (
            'accepted', 'corrected', 'rejected', 'support-rejected',
            'capability-unavailable', 'gate-failed', 'completed',
            'abandoned', 'no-memory'
        )),
    reason_code TEXT
        CHECK(reason_code IS NULL OR length(reason_code) BETWEEN 1 AND 64),
    recorded_at TEXT NOT NULL
        CHECK(length(recorded_at) BETWEEN 20 AND 40),
    feedback_json TEXT NOT NULL
        CHECK(length(feedback_json) BETWEEN 2 AND 16384)
) WITHOUT ROWID;

CREATE INDEX route_feedback_events_observation_time_idx
    ON route_feedback_events(observation_id, recorded_at, feedback_id);

CREATE INDEX route_feedback_events_type_time_idx
    ON route_feedback_events(feedback_type, recorded_at, feedback_id);

CREATE TABLE memory_admin_commands (
    idempotency_key TEXT PRIMARY KEY
        CHECK(length(idempotency_key) BETWEEN 1 AND 160),
    command_kind TEXT NOT NULL
        CHECK(length(command_kind) BETWEEN 1 AND 64),
    command_digest TEXT NOT NULL
        CHECK(length(command_digest) = 71)
        CHECK(substr(command_digest, 1, 7) = 'sha256:'),
    result_digest TEXT NOT NULL
        CHECK(length(result_digest) = 71)
        CHECK(substr(result_digest, 1, 7) = 'sha256:'),
    result_json TEXT NOT NULL
        CHECK(length(result_json) BETWEEN 2 AND 16384),
    created_at TEXT NOT NULL
        CHECK(length(created_at) BETWEEN 20 AND 40)
) WITHOUT ROWID;
