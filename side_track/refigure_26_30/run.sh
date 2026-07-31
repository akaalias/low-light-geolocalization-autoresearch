#!/usr/bin/env bash
# Side-track: redraw experiments 26-30's architecture figure with Fable
# explicitly as FIGURE_MODEL, isolated from the live autoresearch loop (never
# touches runs/pending_experiment.json or experiments.sqlite). Compares
# against the originals; does not write anything back into the DB/gallery.
set -uo pipefail
cd "$(dirname "$0")/../.."
PY=".venv/bin/python"
DIR="side_track/refigure_26_30"

for eid in 26 27 28 29 30; do
  rundir="$DIR/exp$eid"
  design="$rundir/design.json"
  out="$rundir/figure.json"
  prompt="$rundir/prompt_figure.md"
  echo "=== exp$eid: drawing with claude-fable-5 ==="

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
    || echo "exp$eid: agent exited non-zero (turn limit?) — using whatever it wrote"

  # Detect a capped/rate-limited model before burning the remaining budget.
  capped=$($PY -c "
import json
try:
    d = json.load(open('$rundir/agent_figure.json'))
except Exception:
    print(0); raise SystemExit
r = str(d.get('result') or '').lower()
print(1 if d.get('is_error') and any(k in r for k in ('limit', '429', 'rate')) else 0)
" 2>/dev/null)
  if [ "$capped" = "1" ]; then
    echo "exp$eid: Fable looks rate-limited/capped — stopping the side-track here."
    echo "$(date): stopped at exp$eid, capped" >> "$DIR/STATUS.txt"
    exit 1
  fi

  $PY - "$out" <<'PYFIG'
import json, sys
fig_path = sys.argv[1]
try:
    fig = json.load(open(fig_path))
    svg = (fig.get("architecture_svg") or "").strip()
    if not svg.startswith("<svg"):
        raise SystemExit(1)
except Exception:
    print("exp: figure merge skipped (no valid svg produced)")
    raise SystemExit(0)
PYFIG

  if [ -f "$out" ]; then
    $PY -m autoresearch.figcheck "$out" \
      || echo "exp$eid: WARNING figure violates the anchor contract"
  fi
  echo "=== exp$eid done ==="
done

echo "$(date): side-track finished all 5 figures" >> "$DIR/STATUS.txt"
