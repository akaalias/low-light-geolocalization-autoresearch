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

# Refuse to run on a dirty tree — lineage requires clean commits.
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "FATAL: working tree dirty; commit or stash first." >&2; exit 1
fi

for i in $(seq 1 "$ITERATIONS"); do
  RUN_ID="$(date -u +%Y%m%d_%H%M%S)_iter$i"
  RUN_DIR="runs/$RUN_ID"
  mkdir -p "$RUN_DIR"
  PARENT_COMMIT="$(git rev-parse HEAD)"
  echo "=== iteration $i/$ITERATIONS  run=$RUN_ID  parent=$PARENT_COMMIT ==="

  # 1. Agent designs ONE experiment: pre-registers hypothesis/method/expected
  #    outcome in runs/pending_experiment.json, then edits model/ accordingly.
  # Snapshot the exact prompt handed to the headless agent — part of the
  # experiment record (§7 lineage) even when SKIP_AGENT skips the call.
  cp autoresearch/prompt.md "$RUN_DIR/prompt.md"
  if [ "${SKIP_AGENT:-0}" != "1" ]; then
    rm -f runs/pending_experiment.json
    "$CLAUDE_BIN" -p "$(cat "$RUN_DIR/prompt.md")" \
      --permission-mode acceptEdits \
      --allowedTools "Read,Edit,Write,Grep,Glob,Bash(.venv/bin/python:*),Bash(sqlite3:*)" \
      || { echo "agent invocation failed; skipping iteration"; continue; }
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

  # 3. Train one model per development area, then score (§6).
  FAILED=0
  for area in $AREAS; do
    $PY -m model.train --area "$area" --out-dir "$RUN_DIR" --epochs "$EPOCHS" || { FAILED=1; break; }
  done
  if [ "$FAILED" = "1" ]; then
    echo '{"kind":"development","areas":[],"primary_worst_median_error_m":1e9,"target_m":20.0}' > "$RUN_DIR/metrics.json"
  else
    $PY -m pipeline.score --areas "$(echo $AREAS | tr ' ' ',')" \
      --model-dir "$RUN_DIR/models" --out "$RUN_DIR/metrics.json" \
      --heatmap-dir "$RUN_DIR/heatmaps" || \
      echo '{"kind":"development","areas":[],"primary_worst_median_error_m":1e9,"target_m":20.0}' > "$RUN_DIR/metrics.json"
  fi
  $PY -m autoresearch.samples --areas "$(echo $AREAS | tr ' ' ',')" --out "$RUN_DIR/samples" || true

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
  $PY -m autoresearch.db --metrics "$RUN_DIR/metrics.json" \
    --experiment-file "$RUN_DIR/experiment.json" \
    --result "$RESULT" --conclusion "$CONCLUSION" \
    --parent-commit "$PARENT_COMMIT" --artifacts-dir "$RUN_DIR" --kept "$KEEP" \
    --prompt-file "$RUN_DIR/prompt.md"

  # 5. Periodic read-only holdout check (§5) — logged, never drives keep/revert.
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

  $PY -m autoresearch.gallery || true
done
echo "Loop finished. Best: $(best_metric) m — see gallery/index.html"
