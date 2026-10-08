PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, session_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL, original_input_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS cases_owner ON cases(owner_id, recorded_at);
CREATE TABLE IF NOT EXISTS case_revisions (
    case_id TEXT NOT NULL REFERENCES cases(case_id), revision_seq INTEGER NOT NULL,
    revision_id TEXT NOT NULL UNIQUE, recorded_at TEXT NOT NULL, kind TEXT NOT NULL,
    reason TEXT NOT NULL, input_json TEXT NOT NULL, time_context_json TEXT NOT NULL,
    PRIMARY KEY(case_id, revision_seq)
);
CREATE TABLE IF NOT EXISTS context_events (
    event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
    event_seq INTEGER NOT NULL, event_type TEXT NOT NULL, recorded_at TEXT NOT NULL,
    session_id TEXT NOT NULL, content_json TEXT NOT NULL, UNIQUE(case_id, event_seq)
);
CREATE TABLE IF NOT EXISTS analysis_runs (
    analysis_run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
    revision_seq INTEGER NOT NULL, parent_run_id TEXT REFERENCES analysis_runs(analysis_run_id),
    analyzed_at TEXT NOT NULL, input_snapshot_id TEXT NOT NULL, input_snapshot_json TEXT NOT NULL,
    source_hash TEXT NOT NULL, rules_digest TEXT NOT NULL, prompt_digest TEXT NOT NULL,
    engine_build TEXT NOT NULL, FOREIGN KEY(case_id, revision_seq) REFERENCES case_revisions(case_id, revision_seq)
);
CREATE TABLE IF NOT EXISTS analysis_outcomes (
    analysis_run_id TEXT PRIMARY KEY REFERENCES analysis_runs(analysis_run_id),
    recorded_at TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('completed','partial','unresolved','failed')),
    result_json TEXT NOT NULL, result_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_events (
    event_id TEXT PRIMARY KEY, analysis_run_id TEXT NOT NULL REFERENCES analysis_runs(analysis_run_id),
    recorded_at TEXT NOT NULL, stage TEXT NOT NULL, attempt_id TEXT NOT NULL,
    event_json TEXT NOT NULL, UNIQUE(analysis_run_id, stage, attempt_id)
);
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
    analysis_run_id TEXT REFERENCES analysis_runs(analysis_run_id),
    occurred_at TEXT, recorded_at TEXT NOT NULL, reported_outcome TEXT NOT NULL,
    verification_status TEXT NOT NULL CHECK(verification_status IN ('self_reported','externally_supported','disputed','unknown')),
    verification_method TEXT, supersedes_feedback_id TEXT REFERENCES feedback(feedback_id)
);
CREATE TABLE IF NOT EXISTS intake_failures (
    failure_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, session_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL, related_input_json TEXT NOT NULL, errors_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency (
    owner_id TEXT NOT NULL, operation TEXT NOT NULL, idempotency_key TEXT NOT NULL,
    request_digest TEXT NOT NULL, response_json TEXT NOT NULL,
    PRIMARY KEY(owner_id, operation, idempotency_key)
);
-- A series is rooted in an existing case. Links are immutable; each child keeps
-- the parent revision and analysis that the user was viewing when branching.
CREATE TABLE IF NOT EXISTS case_series (
    case_id TEXT PRIMARY KEY REFERENCES cases(case_id),
    series_id TEXT NOT NULL REFERENCES cases(case_id),
    parent_case_id TEXT REFERENCES cases(case_id),
    parent_revision_seq INTEGER,
    parent_analysis_run_id TEXT REFERENCES analysis_runs(analysis_run_id),
    CHECK ((parent_case_id IS NULL AND parent_revision_seq IS NULL AND parent_analysis_run_id IS NULL AND series_id=case_id)
        OR (parent_case_id IS NOT NULL AND parent_revision_seq IS NOT NULL AND case_id<>parent_case_id)),
    FOREIGN KEY(parent_case_id,parent_revision_seq) REFERENCES case_revisions(case_id,revision_seq)
);
CREATE INDEX IF NOT EXISTS case_series_root ON case_series(series_id);
CREATE INDEX IF NOT EXISTS case_series_parent ON case_series(parent_case_id);
