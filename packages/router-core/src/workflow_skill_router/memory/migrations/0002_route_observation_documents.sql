CREATE TABLE route_observation_documents (
    observation_id TEXT PRIMARY KEY
        REFERENCES route_observations(observation_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,
    observation_digest TEXT NOT NULL UNIQUE
        CHECK(length(observation_digest) = 71)
        CHECK(substr(observation_digest, 1, 7) = 'sha256:')
        CHECK(substr(observation_digest, 8) NOT GLOB '*[^0-9a-f]*'),
    workflow_run_digest TEXT NOT NULL UNIQUE
        CHECK(length(workflow_run_digest) = 71)
        CHECK(substr(workflow_run_digest, 1, 7) = 'sha256:')
        CHECK(substr(workflow_run_digest, 8) NOT GLOB '*[^0-9a-f]*'),
    matcher_source TEXT NOT NULL
        CHECK(matcher_source IN (
            'trusted-routing-context',
            'existing-profile',
            'user-explicit'
        )),
    target_profile_class TEXT NOT NULL
        CHECK(target_profile_class IN (
            'managed-personal',
            'managed-workspace-local',
            'user-personal',
            'workspace-file'
        )),
    automatic_promotion_eligible INTEGER NOT NULL
        CHECK(automatic_promotion_eligible IN (0, 1)),
    observation_json TEXT NOT NULL
        CHECK(length(observation_json) BETWEEN 2 AND 65536)
) WITHOUT ROWID;

CREATE TABLE memory_command_results (
    idempotency_key TEXT PRIMARY KEY
        REFERENCES memory_command_receipts(idempotency_key)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,
    result_json TEXT NOT NULL
        CHECK(length(result_json) BETWEEN 2 AND 16384)
) WITHOUT ROWID;

CREATE INDEX route_observation_documents_matcher_idx
    ON route_observation_documents(matcher_source, target_profile_class);
