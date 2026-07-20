-- FROZEN (see /FROZEN) — lineage schema, CLAUDE.md §7.
-- Each experiment row is a full experiment design record: the agent states a
-- hypothesis, method, and expected outcome BEFORE the run; the harness fills
-- in result and conclusion from the measured §6 metric afterward.
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,                 -- ISO UTC
    git_commit TEXT NOT NULL,         -- commit the experiment ran at
    parent_commit TEXT,               -- best-so-far commit it branched from
    kind TEXT NOT NULL DEFAULT 'development',  -- 'development' | 'holdout_check'
    title TEXT NOT NULL,              -- one-line name of the experiment
    category TEXT,                    -- architecture|loss|augmentation|relighting|training|quantization|other
    hypothesis TEXT,                  -- what the agent believes and why (pre-registered)
    method TEXT,                      -- the ONE focused change made, concretely
    expected_outcome TEXT,            -- predicted effect on the §6 metric (pre-registered)
    result TEXT,                      -- measured outcome (harness-written)
    conclusion TEXT,                  -- kept/reverted + hypothesis supported? (harness-written)
    init_strategy TEXT,               -- from-scratch | pretrained:<name> (§9)
    primary_metric REAL,              -- §6 worst-case median error (m); 1e9 = gated fail
    kept INTEGER,                     -- 1 kept, 0 reverted, NULL = holdout check
    model_bytes_max INTEGER,          -- largest per-area ONNX
    latency_ms_host_proxy REAL,       -- worst per-area host latency proxy
    metrics_json TEXT,                -- full score.py output (per-area/bucket)
    artifacts_dir TEXT,               -- runs/<id>/ path with models/heatmaps/samples
    agent_prompt TEXT,                -- exact prompt given to the headless agent
    agent_model TEXT,                 -- LLM model id that ran the headless agent
    duration_s REAL,                  -- wall time of the whole iteration (agent+train+score)
    eli5 TEXT,                        -- pre-registered plain-language explanation (no jargon)
    arch_json TEXT,                   -- pre-registered {"stages":[...]} inference-path summary
    arch_svg TEXT                     -- pre-registered technical architecture diagram (SVG)
);

CREATE TABLE IF NOT EXISTS area_results (
    experiment_id INTEGER NOT NULL REFERENCES experiments(id),
    area TEXT NOT NULL,
    bucket TEXT NOT NULL,
    median_error_m REAL,
    mean_error_m REAL,
    coverage REAL,
    n_eval INTEGER,
    cell_score REAL,
    PRIMARY KEY (experiment_id, area, bucket)
);
