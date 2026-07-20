"""FROZEN (see /FROZEN) — SQLite lineage logging, CLAUDE.md §7.

Logs one full experiment-design record per run: the agent's pre-registered
title/hypothesis/method/expected_outcome (from experiment.json) plus the
harness-measured result/conclusion and all §6 metrics.

experiment.json format (written by the agent BEFORE the run):
  {"title": "...", "category": "architecture|loss|augmentation|relighting|training|quantization|other",
   "hypothesis": "...", "method": "...", "expected_outcome": "...",
   "init_strategy": "from-scratch" | "pretrained:<name>"}

Usage (invoked by loop.sh; also usable manually):
  python -m autoresearch.db --metrics runs/X/metrics.json \
      --experiment-file runs/X/experiment.json --result "..." --conclusion "..." \
      --parent-commit <sha> --artifacts-dir runs/X [--kept 1] [--kind holdout_check]
"""

import argparse
import datetime
import json
import sqlite3
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "experiments.sqlite"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH)
    with open(REPO_ROOT / "autoresearch" / "schema.sql") as f:
        conn.executescript(f.read())
    # Migrate DBs created before a column was added to the schema.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(experiments)")]
    if "agent_prompt" not in cols:
        conn.execute("ALTER TABLE experiments ADD COLUMN agent_prompt TEXT")
    return conn


def git_rev(ref: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", ref], cwd=REPO_ROOT, text=True).strip()


def log_experiment(metrics_path: Path, design: dict, result: str,
                   conclusion: str, git_commit: str, parent_commit: str | None,
                   artifacts_dir: str, kept: int | None, kind: str,
                   agent_prompt: str | None = None,
                   db_path: Path | None = None) -> int:
    with open(metrics_path) as f:
        metrics = json.load(f)
    sizes = [a["gates"].get("model_bytes") or 0 for a in metrics["areas"]]
    lats = [a["gates"].get("latency_ms_host_proxy") or 0 for a in metrics["areas"]]
    conn = connect(db_path)
    cur = conn.execute(
        """INSERT INTO experiments
           (ts, git_commit, parent_commit, kind, title, category, hypothesis,
            method, expected_outcome, result, conclusion, init_strategy,
            primary_metric, kept, model_bytes_max, latency_ms_host_proxy,
            metrics_json, artifacts_dir, agent_prompt)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (datetime.datetime.now(datetime.timezone.utc).isoformat(),
         git_commit, parent_commit, kind,
         design.get("title", "(untitled)"), design.get("category"),
         design.get("hypothesis"), design.get("method"),
         design.get("expected_outcome"), result, conclusion,
         design.get("init_strategy"),
         metrics["primary_worst_median_error_m"], kept,
         max(sizes) if sizes else None, max(lats) if lats else None,
         json.dumps(metrics), artifacts_dir, agent_prompt))
    exp_id = cur.lastrowid
    for a in metrics["areas"]:
        for bucket, c in a.get("buckets", {}).items():
            conn.execute(
                """INSERT INTO area_results VALUES (?,?,?,?,?,?,?,?)""",
                (exp_id, a["area"], bucket, c["median_error_m"],
                 c["mean_error_m"], c["coverage"], c["n_eval"], c["score"]))
    conn.commit()
    conn.close()
    return exp_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", required=True)
    ap.add_argument("--experiment-file", required=True,
                    help="JSON with title/category/hypothesis/method/expected_outcome/init_strategy")
    ap.add_argument("--result", default="")
    ap.add_argument("--conclusion", default="")
    ap.add_argument("--git-commit", default="HEAD")
    ap.add_argument("--parent-commit", default=None)
    ap.add_argument("--artifacts-dir", required=True)
    ap.add_argument("--kept", type=int, default=None)
    ap.add_argument("--kind", default="development",
                    choices=["development", "holdout_check"])
    ap.add_argument("--prompt-file", default=None,
                    help="file holding the exact prompt given to the headless agent")
    args = ap.parse_args()

    try:
        design = json.loads(Path(args.experiment_file).read_text())
    except (OSError, json.JSONDecodeError) as e:
        design = {"title": "(missing/invalid experiment.json)", "hypothesis": str(e)}

    prompt = None
    if args.prompt_file and Path(args.prompt_file).exists():
        prompt = Path(args.prompt_file).read_text().strip()

    exp_id = log_experiment(
        Path(args.metrics), design, args.result, args.conclusion,
        git_rev(args.git_commit),
        git_rev(args.parent_commit) if args.parent_commit else None,
        args.artifacts_dir, args.kept, args.kind, prompt)
    print(exp_id)


if __name__ == "__main__":
    main()
