CREATE TABLE profile_update_proposals (
    proposal_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','stale','expired','applied','failed')),
    state_version INTEGER NOT NULL CHECK(state_version >= 1),
    expected_profile_digest TEXT NOT NULL,
    proposed_profile_digest TEXT NOT NULL,
    proposal_digest TEXT NOT NULL,
    proposal_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX profile_update_proposals_candidate_status_idx
    ON profile_update_proposals(candidate_id, status, created_at);

CREATE TABLE profile_update_proposal_receipts (
    idempotency_key TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL REFERENCES profile_update_proposals(proposal_id),
    action TEXT NOT NULL CHECK(action IN ('approved','rejected','stale','expired','applied','failed')),
    command_digest TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
