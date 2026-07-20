"""Extract the LLM model id from a headless `claude -p --output-format json`
result file. Prints an empty string (exit 0) on anything unexpected — the
loop treats the model as unknown rather than failing the iteration.

Usage: python -m autoresearch.agentmeta runs/<id>/agent_result.json
"""

import json
import sys


def model_of(path: str) -> str:
    try:
        with open(path) as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError):
        return ""
    if isinstance(d, list):  # stream-json: take the final result object
        d = next((x for x in reversed(d)
                  if isinstance(x, dict) and x.get("type") == "result"), {})
    if not isinstance(d, dict):
        return ""
    usage = d.get("modelUsage")
    if isinstance(usage, dict) and usage:
        return ", ".join(sorted(usage.keys()))
    m = d.get("model")
    return m if isinstance(m, str) else ""


if __name__ == "__main__":
    print(model_of(sys.argv[1]) if len(sys.argv) > 1 else "")
