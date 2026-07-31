#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/../.."
PY=".venv/bin/python"

# Don't stack too many concurrent Fable calls: wait for the exp26 redo and
# the main run.sh queue (exp29/exp30) to finish before starting.
while pgrep -f "side_track/refigure_26_30/redo26.sh" >/dev/null \
   || pgrep -f "side_track/refigure_26_30/run.sh" >/dev/null; do
  sleep 10
done

for eid in 27 28; do
  rundir="side_track/refigure_26_30/exp$eid"
  design="$rundir/design.json"
  out="$rundir/figure.json"
  prompt="$rundir/prompt_figure.md"

  cp "$out" "$rundir/figure_attempt1_buggy.json" 2>/dev/null
  cp "$rundir/agent_figure.json" "$rundir/agent_figure_attempt1.json" 2>/dev/null

  echo "=== exp$eid redo: drawing with claude-fable-5 (fixed figcheck) ==="
  cat autoresearch/prompt_figure.md > "$prompt"
  {
    echo
    echo "## Paths for this run (resolve the placeholders referenced above)"
    echo "- Read the experiment record from: \`$design\`"
    echo "- Write ONLY this output file: \`$out\` — a single JSON object of the"
    echo "  form {\"architecture_svg\": \"<svg …>\"} and nothing else."
  } >> "$prompt"

  rm -f "$out"
  claude -p "$(cat "$prompt")" \
    --model claude-fable-5 \
    --permission-mode acceptEdits \
    --max-turns 45 \
    --allowedTools "Read,Write,Grep,Glob,Bash(.venv/bin/python:*)" \
    --output-format json </dev/null >"$rundir/agent_figure.json" \
    || echo "exp$eid redo: agent exited non-zero (turn limit?) — using whatever it wrote"

  if [ -f "$out" ]; then
    $PY -m autoresearch.figcheck "$out" \
      || echo "exp$eid redo: WARNING figure violates the anchor contract"
  fi
  echo "=== exp$eid redo done ==="
done
