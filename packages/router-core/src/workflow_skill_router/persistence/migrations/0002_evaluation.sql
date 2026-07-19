CREATE TABLE evaluation_suites (
    suite_digest TEXT PRIMARY KEY,
    tier TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE evaluation_runs (
    run_id TEXT PRIMARY KEY,
    authorization_ref TEXT NOT NULL,
    profile TEXT NOT NULL,
    adapter_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    manifest_digest TEXT NOT NULL,
    raw_trace_ref TEXT,
    raw_trace_digest TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE evaluation_attempts (
    attempt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES evaluation_runs(run_id),
    fresh_context_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    raw_trace_digest TEXT NOT NULL,
    failure TEXT
);

CREATE TABLE evaluation_scores (
    run_id TEXT PRIMARY KEY REFERENCES evaluation_runs(run_id),
    score_digest TEXT NOT NULL,
    hard_violation_count INTEGER NOT NULL,
    metrics_json TEXT NOT NULL,
    release_eligible INTEGER NOT NULL CHECK (release_eligible IN (0, 1))
);
