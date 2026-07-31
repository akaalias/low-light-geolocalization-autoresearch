#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/../.."
PY=".venv/bin/python"
rundir="side_track/refigure_26_30/exp26"
design="$rundir/design.json"
out="$rundir/figure.json"
prompt="$rundir/prompt_figure.md"

echo "=== exp26 redo: drawing with claude-fable-5 (fixed figcheck) ==="
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
  || echo "exp26 redo: agent exited non-zero (turn limit?) — using whatever it wrote"

if [ -f "$out" ]; then
  $PY -m autoresearch.figcheck "$out" \
    || echo "exp26 redo: WARNING figure violates the anchor contract"
fi
echo "=== exp26 redo done ==="
