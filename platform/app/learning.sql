-- Additive schema: existing CTF accounts and chat history remain intact.
CREATE TABLE IF NOT EXISTS learning_progress (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    current_run TEXT,
    hint_level INTEGER NOT NULL DEFAULT 0,
    example_seen INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    completed_run TEXT,
    completed_with_example INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS learning_runs (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    canary TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS learning_runs_user ON learning_runs(user_id);

CREATE TABLE IF NOT EXISTS learning_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES learning_runs(id),
    request_id TEXT NOT NULL,
    user_content TEXT NOT NULL,
    assistant_content TEXT,
    status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed')),
    feedback TEXT,
    started_at INTEGER NOT NULL,
    UNIQUE(run_id, request_id)
);

-- Each workflow trial stores its input snapshot and observed tool events.
-- Kept separate from first-lesson tables to preserve existing attempts verbatim.
CREATE TABLE IF NOT EXISTS workflow_progress (
    user_id INTEGER NOT NULL REFERENCES users(id),
    lesson TEXT NOT NULL,
    current_run TEXT,
    hint_level INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    compared_at TEXT,
    PRIMARY KEY(user_id, lesson)
);
CREATE TABLE IF NOT EXISTS workflow_runs (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    lesson TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS workflow_runs_user ON workflow_runs(user_id, lesson);
CREATE TABLE IF NOT EXISTS workflow_trials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES workflow_runs(id),
    request_id TEXT NOT NULL,
    input TEXT NOT NULL,
    response TEXT,
    events TEXT NOT NULL DEFAULT '[]',
    comparison TEXT,
    success INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('running','completed','failed')),
    feedback TEXT,
    started_at INTEGER NOT NULL,
    UNIQUE(run_id, request_id)
);

-- Joe's email lab keeps immutable messages and actual model/tool activity.
CREATE TABLE IF NOT EXISTS email_progress (
    user_id INTEGER NOT NULL REFERENCES users(id),
    goal TEXT NOT NULL,
    current_run TEXT,
    hint_level INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    completed_with_example INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(user_id, goal)
);
CREATE TABLE IF NOT EXISTS email_runs (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    goal TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS email_runs_user ON email_runs(user_id, goal);
CREATE TABLE IF NOT EXISTS email_trials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES email_runs(id),
    request_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    protected INTEGER NOT NULL DEFAULT 0,
    canary TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('running','completed','failed')),
    events TEXT NOT NULL DEFAULT '[]',
    result TEXT,
    workspace TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 0,
    feedback TEXT,
    started_at INTEGER NOT NULL,
    UNIQUE(run_id, request_id)
);
