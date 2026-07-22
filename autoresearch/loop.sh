#!/usr/bin/env bash
# FROZEN (see /FROZEN) — the autoresearch loop, CLAUDE.md §7. Phase 2 entrypoint.
#
# Repeatedly: ask a headless Claude Code instance to make ONE focused change to
# the agent-editable files (model/), then train + score on the development
# areas, log to SQLite, and keep (git commit) or revert by comparing the §6
# primary metric against the best so far. Every HOLDOUT_EVERY kept
# improvements, run the read-only Hamburg holdout check (§5) — logged, never
# fed back into keep/revert.
#
# Usage:   ./autoresearch/loop.sh [iterations]
# Env:     AREAS          (default "berlin prignitz munich frankfurt")
#          PATIENCE       (default 4: consecutive non-kept experiments before
#                          the design prompt demands a pivot)
#          EPOCHS         (default 8)
#          HOLDOUT_EVERY  (default 5)
#          CLAUDE_BIN     (default "claude")
#          SKIP_AGENT=1   (run train/score/log only — no code change; smoke test)
set -euo pipefail
cd "$(dirname "$0")/.."

ITERATIONS="${1:-10}"
AREAS="${AREAS:-berlin prignitz munich frankfurt}"
EPOCHS="${EPOCHS:-8}"
HOLDOUT_EVERY="${HOLDOUT_EVERY:-5}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
PY=".venv/bin/python"
STATE="state"; mkdir -p "$STATE" runs

best_metric() { [ -f "$STATE/best.json" ] && $PY -c "import json;print(json.load(open('$STATE/best.json'))['primary'])" || echo 1e18; }

# Real-time phase reporting for the public LIVE row: a one-file commit
# force-pushed to refs/heads/status (plumbing objects only — main's history
# stays untouched). The page fetches it from raw.githubusercontent.
report_phase() {
  printf '{"iter":%s,"iterations":%s,"iter_started":%s,"phase":"%s","phase_started":%s,"best":%s}\n' \
    "${i:-0}" "$ITERATIONS" "${ITER_T0:-$(date +%s)}" "$1" "$(date +%s)" "$(best_metric)" \
    > "$STATE/phase.json" || true
  ( BLOB=$(git hash-object -w "$STATE/phase.json") &&
    TREE=$(printf '100644 blob %s\tphase.json\n' "$BLOB" | git mktree) &&
    COMMIT=$(git commit-tree "$TREE" -m "phase: $1") &&
    git push -qf origin "$COMMIT:refs/heads/status" ) 2>/dev/null || true
}

# A dirty tree would blur lineage (a kept commit must contain exactly one
# experiment's change) — but the loop itself leaves state/ modified, so
# instead of aborting, checkpoint pending TRACKED changes into their own
# commit and start every iteration from a clean, attributable tree.
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Working tree dirty — committing pending changes as a pre-loop checkpoint."
  git add -u
  git commit -q -m "Pre-loop checkpoint: pending working-tree changes" || {
    echo "FATAL: checkpoint commit failed; commit or stash manually." >&2; exit 1; }
fi

# Graceful exit: Ctrl-C / SIGTERM discards only the in-flight iteration.
# Everything durable is already on disk — kept improvements are committed,
# finished iterations are in experiments.sqlite, best is in state/best.json —
# so a restart simply continues from the current best.
cleanup_interrupt() {
  echo ""
  echo "Interrupted — discarding the in-flight iteration (all completed"
  echo "iterations are already committed/logged). Safe to restart with:"
  echo "  ./autoresearch/loop.sh"
  git checkout -- model/ 2>/dev/null || true
  rm -f runs/pending_experiment.json
  exit 130
}
trap cleanup_interrupt INT TERM

# Graceful stop request: type "exit" (or quit/stop) + Enter while the loop is
# running to finish the CURRENT iteration completely (train, score, log,
# keep/revert) and then stop. Also triggered by: touch state/stop
# (useful from another terminal or when running under nohup).
STOP_FLAG="$STATE/stop"
rm -f "$STOP_FLAG"
WATCHER_PID=""
if [ -t 0 ]; then
  ( while IFS= read -r line; do
      case "$line" in
        exit|quit|stop|q)
          touch "$STOP_FLAG"
          echo ">>> stop requested — will exit gracefully after the current iteration" ;;
      esac
    done ) &
  WATCHER_PID=$!
  echo "Type 'exit' + Enter to stop gracefully after the current iteration"
  echo "(Ctrl-C aborts the in-flight iteration immediately)."
fi
cleanup_watcher() { [ -n "$WATCHER_PID" ] && kill "$WATCHER_PID" 2>/dev/null || true; }
trap cleanup_watcher EXIT

for i in $(seq 1 "$ITERATIONS"); do
  if [ -f "$STOP_FLAG" ]; then
    rm -f "$STOP_FLAG"
    echo "Graceful stop: $((i-1))/$ITERATIONS iterations completed and logged."
    break
  fi
  RUN_ID="$(date -u +%Y%m%d_%H%M%S)_iter$i"
  RUN_DIR="runs/$RUN_ID"
  mkdir -p "$RUN_DIR"
  PARENT_COMMIT="$(git rev-parse HEAD)"
  ITER_T0="$(date +%s)"
  echo "=== iteration $i/$ITERATIONS  run=$RUN_ID  parent=$PARENT_COMMIT ==="

  # 1. Two-stage agent (models chosen per task — design is the creative/
  #    strategic work, implementation is focused code editing):
  #      stage 1 DESIGN_MODEL (default Fable): pre-registers the experiment +
  #        an implementation_brief in runs/pending_experiment.json; no code edits.
  #      stage 2 IMPL_MODEL (default Sonnet): applies the brief to model/.
  # Snapshot the exact prompts handed to the agents — part of the experiment
  # record (§7 lineage) even when SKIP_AGENT skips the calls.
  cp autoresearch/prompt.md "$RUN_DIR/prompt.md"
  cp autoresearch/prompt_impl.md "$RUN_DIR/prompt_impl.md"
  # Patience / auto-pivot (workshop pattern): after PATIENCE consecutive
  # non-kept experiments, the design prompt gets a mandatory-pivot preamble —
  # the guard against refining a dead line forever. The preamble is written
  # into the run's prompt snapshot so the record shows the prompt actually
  # used.
  PLATEAU=$(sqlite3 experiments.sqlite "SELECT COUNT(*) FROM experiments \
    WHERE kind='development' AND id > \
    (SELECT COALESCE(MAX(id),0) FROM experiments \
     WHERE kept=1 AND kind='development');" 2>/dev/null || echo 0)
  if [ "${PLATEAU:-0}" -ge "${PATIENCE:-4}" ]; then
    echo "PIVOT: $PLATEAU consecutive experiments without a new best — pivot directive injected"
    cat - "$RUN_DIR/prompt.md" > "$RUN_DIR/prompt.md.tmp" <<PIVOTNOTE
## PATIENCE SPENT — THIS ITERATION MUST PIVOT

$PLATEAU consecutive experiments have failed to beat the current best.
Do NOT refine the champion's current mechanism again this round. Step back
and propose from a design family ABSENT from the last $PLATEAU experiments
— the spec (§3) explicitly invites, among others: dispatcher + lighting-
condition-specialist models, learned relighting, a different coordinate
parameterization, quantization-aware capacity changes, or training-data
strategy overhauls. Genuine novelty over incremental tuning.

PIVOTNOTE
    mv "$RUN_DIR/prompt.md.tmp" "$RUN_DIR/prompt.md"
  fi
  report_phase design
  AGENT_MODEL_DESIGN=""; AGENT_MODEL_IMPL=""
  T_DESIGN=0; T_IMPL=0
  if [ "${SKIP_AGENT:-0}" != "1" ]; then
    rm -f runs/pending_experiment.json
    T0=$(date +%s)
    "$CLAUDE_BIN" -p "$(cat "$RUN_DIR/prompt.md")" \
      --model "${DESIGN_MODEL:-claude-fable-5}" \
      --permission-mode acceptEdits \
      --allowedTools "Read,Write,Grep,Glob,Bash(.venv/bin/python:*),Bash(sqlite3:*)" \
      --output-format json </dev/null >"$RUN_DIR/agent_design.json" \
      || { echo "design agent failed (rate limit/usage cap?) — sleeping \
${AGENT_RETRY_SLEEP:-1800}s before next iteration"
           report_phase waiting
           sleep "${AGENT_RETRY_SLEEP:-1800}"; continue; }
    T_DESIGN=$(( $(date +%s) - T0 ))
    if [ ! -f runs/pending_experiment.json ]; then
      echo "design agent produced no runs/pending_experiment.json; skipping iteration"
      continue
    fi
    report_phase implement
    T0=$(date +%s)
    "$CLAUDE_BIN" -p "$(cat "$RUN_DIR/prompt_impl.md")" \
      --model "${IMPL_MODEL:-claude-sonnet-5}" \
      --permission-mode acceptEdits \
      --allowedTools "Read,Edit,Write,Grep,Glob,Bash(.venv/bin/python:*),Bash(sqlite3:*)" \
      --output-format json </dev/null >"$RUN_DIR/agent_impl.json" \
      || { echo "impl agent failed; skipping iteration"
           git checkout -- model/ 2>/dev/null || true; continue; }
    T_IMPL=$(( $(date +%s) - T0 ))
    $PY -m autoresearch.figcheck runs/pending_experiment.json || \
      echo "WARNING: figure violates the anchor contract (cosmetic — continuing)"
    AGENT_MODEL_DESIGN="$($PY -m autoresearch.agentmeta "$RUN_DIR/agent_design.json" 2>/dev/null || echo "${DESIGN_MODEL:-claude-fable-5}")"
    AGENT_MODEL_IMPL="$($PY -m autoresearch.agentmeta "$RUN_DIR/agent_impl.json" 2>/dev/null || echo "${IMPL_MODEL:-claude-sonnet-5}")"
    echo "agents finished (design: $AGENT_MODEL_DESIGN ${T_DESIGN}s, impl: $AGENT_MODEL_IMPL ${T_IMPL}s)"
  fi
  [ -f runs/pending_experiment.json ] && mv runs/pending_experiment.json "$RUN_DIR/experiment.json"
  [ -f "$RUN_DIR/experiment.json" ] || echo '{"title":"(no experiment design provided)"}' > "$RUN_DIR/experiment.json"

  # 2. Enforce frozen files — hard-revert any agent edits to them.
  FROZEN_TOUCHED="$(git diff --name-only | grep -xF -f FROZEN || true)"
  if [ -n "$FROZEN_TOUCHED" ]; then
    echo "WARNING: agent touched frozen files, reverting:"; echo "$FROZEN_TOUCHED"
    echo "$FROZEN_TOUCHED" | xargs git checkout --
  fi
  # Enforce holdout blindness: agent must never read/copy holdout data or score it.
  # (score.py refuses hamburg without --holdout; loop only passes dev areas.)

  # 3. Train one model per development area — IN PARALLEL (areas are fully
  #    independent; per-area out-dirs avoid a write race on train_info.json,
  #    merged below) — then score (§6).
  report_phase train
  T0=$(date +%s); FAILED=0; PIDS=""
  for area in $AREAS; do
    # Cap math-library threads per process: torch defaults each process to a
    # thread pool sized to ALL host cores, so 4 concurrent trainings spawn
    # ~4x96 threads on a small cgroup quota and thrash (observed: GPU 10%,
    # 45+ min wall). TRAIN_THREADS overrides the default cap.
    OMP_NUM_THREADS="${TRAIN_THREADS:-8}" MKL_NUM_THREADS="${TRAIN_THREADS:-8}" \
    $PY -m model.train --area "$area" --out-dir "$RUN_DIR/train_$area" \
      --epochs "$EPOCHS" >"$RUN_DIR/train_$area.log" 2>&1 &
    PIDS="$PIDS $!"
  done
  for pid in $PIDS; do wait "$pid" || FAILED=1; done
  for area in $AREAS; do echo "--- train $area:"; tail -2 "$RUN_DIR/train_$area.log"; done
  T_TRAIN=$(( $(date +%s) - T0 ))
  if [ "$FAILED" = "0" ]; then
    mkdir -p "$RUN_DIR/models"
    for area in $AREAS; do
      cp "$RUN_DIR/train_$area/models/"*.onnx "$RUN_DIR/models/" 2>/dev/null || FAILED=1
    done
    $PY - "$RUN_DIR" $AREAS <<'PYMERGE' || FAILED=1
import json, sys
from pathlib import Path
run = Path(sys.argv[1]); merged = []
for a in sys.argv[2:]:
    p = run / f"train_{a}" / "train_info.json"
    if p.exists():
        merged += json.loads(p.read_text())
(run / "train_info.json").write_text(json.dumps(merged, indent=2))
PYMERGE
    # Per-area training dirs are SCRATCH (agent code may cache gigabytes of
    # renders there — exp 17 wrote ~5.7 GB/iteration). Models and
    # train_info are merged out above; everything else must never reach
    # the record or LFS.
    for area in $AREAS; do rm -rf "$RUN_DIR/train_$area"; done
  fi
  report_phase score
  T0=$(date +%s)
  if [ "$FAILED" = "1" ]; then
    echo '{"kind":"development","areas":[],"primary_worst_median_error_m":1e9,"target_m":20.0}' > "$RUN_DIR/metrics.json"
  else
    $PY -m pipeline.score --areas "$(echo $AREAS | tr ' ' ',')" \
      --model-dir "$RUN_DIR/models" --out "$RUN_DIR/metrics.json" \
      --heatmap-dir "$RUN_DIR/heatmaps" || \
      echo '{"kind":"development","areas":[],"primary_worst_median_error_m":1e9,"target_m":20.0}' > "$RUN_DIR/metrics.json"
  fi
  T_SCORE=$(( $(date +%s) - T0 ))
  T0=$(date +%s)
  $PY -m autoresearch.samples --areas "$(echo $AREAS | tr ' ' ',')" --out "$RUN_DIR/samples" || true
  T_SAMPLES=$(( $(date +%s) - T0 ))

  METRIC="$($PY -c "import json;print(json.load(open('$RUN_DIR/metrics.json'))['primary_worst_median_error_m'])")"
  BEST="$(best_metric)"
  KEEP="$($PY -c "print(1 if $METRIC < $BEST else 0)")"

  # 4. Keep or revert (Karpathy-style), then log the completed experiment
  #    record (pre-registered design + measured result + conclusion).
  RESULT="primary worst-case median error = $METRIC m (previous best $BEST m); full per-area/bucket breakdown in metrics.json"
  if [ "$KEEP" = "1" ]; then
    git add -A model/ && git commit -q -m "autoresearch iter $i: $METRIC m (was $BEST)

$(cat "$RUN_DIR/experiment.json")" || true
    echo "{\"primary\": $METRIC, \"run\": \"$RUN_ID\", \"commit\": \"$(git rev-parse HEAD)\"}" > "$STATE/best.json"
    KEPT_COUNT=$(( $(cat "$STATE/kept_count" 2>/dev/null || echo 0) + 1 )); echo "$KEPT_COUNT" > "$STATE/kept_count"
    CONCLUSION="KEPT — metric improved ($BEST -> $METRIC m); change committed as $(git rev-parse --short HEAD)"
    echo "KEPT: $METRIC m (improved from $BEST)"
  else
    git checkout -- model/ 2>/dev/null || true
    CONCLUSION="REVERTED — metric did not improve ($METRIC m vs best $BEST m); change discarded"
    echo "REVERTED: $METRIC m (best remains $BEST)"
  fi
  DURATION_S=$(( $(date +%s) - ITER_T0 ))
  $PY -m autoresearch.db --metrics "$RUN_DIR/metrics.json" \
    --experiment-file "$RUN_DIR/experiment.json" \
    --result "$RESULT" --conclusion "$CONCLUSION" \
    --parent-commit "$PARENT_COMMIT" --artifacts-dir "$RUN_DIR" --kept "$KEEP" \
    --prompt-file "$RUN_DIR/prompt.md" \
    --agent-model-design "$AGENT_MODEL_DESIGN" \
    --agent-model-impl "$AGENT_MODEL_IMPL" \
    --duration-s "$DURATION_S"

  # 5. Periodic read-only holdout check (§5) — logged, never drives keep/revert.
  T_HOLDOUT=0; T0=$(date +%s)
  KEPT_COUNT="$(cat "$STATE/kept_count" 2>/dev/null || echo 0)"
  if [ "$KEEP" = "1" ] && [ $(( KEPT_COUNT % HOLDOUT_EVERY )) -eq 0 ]; then
    echo "--- holdout check (hamburg) ---"
    HODIR="$RUN_DIR/holdout"
    $PY -m model.train --area hamburg --out-dir "$HODIR" --epochs "$EPOCHS" && \
    $PY -m pipeline.score --areas hamburg --holdout \
      --model-dir "$HODIR/models" --out "$HODIR/holdout.json" \
      --heatmap-dir "$HODIR/heatmaps" && \
    echo '{"title":"Periodic blind holdout check (hamburg)","category":"other","hypothesis":"If the pipeline is genuinely generic, holdout error should track the development worst-case.","method":"Train current best model code on hamburg, score read-only (§5)."}' > "$HODIR/experiment.json" && \
    $PY -m autoresearch.db --metrics "$HODIR/holdout.json" \
      --experiment-file "$HODIR/experiment.json" \
      --result "informational only — never drives keep/revert" \
      --parent-commit "$PARENT_COMMIT" --artifacts-dir "$HODIR" \
      --kind holdout_check || echo "holdout check failed (non-fatal)"
  fi

  T_HOLDOUT=$(( $(date +%s) - T0 ))
  report_phase publish
  T0=$(date +%s)
  $PY -m autoresearch.gallery || true
  T_GALLERY=$(( $(date +%s) - T0 ))

  # Per-phase timing breakdown — committed with the record so the gallery's
  # experiment-detail view can render where the iteration's time went.
  $PY - <<PYTIMES || true
import json
json.dump({
    "agent_design_s": $T_DESIGN, "agent_impl_s": $T_IMPL,
    "train_wall_s": $T_TRAIN, "score_s": $T_SCORE,
    "samples_s": $T_SAMPLES, "holdout_s": $T_HOLDOUT,
    "gallery_s": $T_GALLERY,
    "total_s": $(( $(date +%s) - ITER_T0 )),
}, open("$RUN_DIR/timings.json", "w"), indent=2)
PYTIMES

  # 6. Persist the complete iteration record — artifacts (incl. any holdout
  #    check), lineage DB, state — for kept AND reverted experiments, and
  #    push off-site. A reverted experiment's record lives only here and in
  #    SQLite, so this commit is what makes the full research trail survive
  #    the pod. Push failures are non-fatal: everything is committed locally
  #    and pushes retry implicitly next iteration.
  git add -A "$RUN_DIR" experiments.sqlite state/ 2>/dev/null || true
  git commit -q -m "iter $i record: $RUN_ID ($METRIC m, kept=$KEEP)" || true
  # Rebase onto origin first: harness/docs commits pushed from the laptop
  # while the loop runs would otherwise permanently diverge us from origin
  # (tree is clean here — everything above is committed).
  git pull --rebase -q origin main 2>/dev/null || \
    { git rebase --abort 2>/dev/null || true; }
  git push -q origin main 2>/dev/null || \
    echo "WARNING: git push failed (no remote/offline?) — record is committed locally"
done
report_phase idle
echo "Loop finished. Best: $(best_metric) m — see gallery/index.html"
