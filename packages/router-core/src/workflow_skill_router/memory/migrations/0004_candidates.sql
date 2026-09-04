CREATE TABLE workflow_patterns (
    pattern_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL CHECK(scope IN ('personal','workspace')),
    material_evidence_digest TEXT NOT NULL,
    pattern_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE workflow_candidates (
    candidate_id TEXT PRIMARY KEY,
    pattern_id TEXT NOT NULL REFERENCES workflow_patterns(pattern_id),
    status TEXT NOT NULL CHECK(status IN ('proposed','approved','rejected','expired','suppressed','superseded','auto-promoted')),
    material_evidence_digest TEXT NOT NULL,
    candidate_digest TEXT NOT NULL,
    candidate_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX workflow_candidates_pattern_status_idx
    ON workflow_candidates(pattern_id, status, created_at);

CREATE TABLE candidate_suppressions (
    pattern_id TEXT NOT NULL REFERENCES workflow_patterns(pattern_id),
    material_evidence_digest TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    rejected_at TEXT NOT NULL,
    suppressed_until TEXT NOT NULL,
    PRIMARY KEY(pattern_id, material_evidence_digest)
);
