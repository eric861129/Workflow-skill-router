CREATE TABLE profile_revisions (
    revision_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    target_profile_class TEXT NOT NULL CHECK(target_profile_class IN ('managed-personal','managed-workspace-local','user-personal','workspace-file')),
    status TEXT NOT NULL CHECK(status IN ('pending','applied','roll' || 'back','failed')),
    previous_profile_digest TEXT NOT NULL,
    new_profile_digest TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    proposal_digest TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    candidate_digest TEXT NOT NULL,
    policy_digest TEXT NOT NULL,
    semantic_diff_digest TEXT NOT NULL,
    backtest_digest TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    write_authority TEXT NOT NULL CHECK(write_authority IN ('router-local-managed','reviewed-user-local','verified-host-workspace')),
    workspace_identity_digest TEXT,
    snapshot_digest TEXT NOT NULL,
    rollback_source_revision_id TEXT,
    revision_digest TEXT NOT NULL,
    revision_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX profile_revisions_profile_created_idx
    ON profile_revisions(profile_id, created_at, revision_id);

CREATE TABLE profile_materialization_receipts (
    idempotency_key TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    command_digest TEXT NOT NULL,
    revision_id TEXT NOT NULL REFERENCES profile_revisions(revision_id),
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE profile_recovery_markers (
    proposal_id TEXT PRIMARY KEY REFERENCES profile_update_proposals(proposal_id),
    revision_id TEXT NOT NULL REFERENCES profile_revisions(revision_id),
    marker_digest TEXT NOT NULL,
    marker_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE rollback_proposal_sources (
    proposal_id TEXT PRIMARY KEY REFERENCES profile_update_proposals(proposal_id),
    source_revision_id TEXT NOT NULL REFERENCES profile_revisions(revision_id),
    created_at TEXT NOT NULL
);
