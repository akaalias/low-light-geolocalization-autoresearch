"""Validate the pre-registered architecture figure against the shared
anchor contract (see autoresearch/prompt.md and the reference
implementation in archive/arch_svg_reference.py):

  - viewBox '0 0 980 H' with H in 240-640 (width fixed, height flexible)
  - the camera-frame element carries id='frozen-input' at x=26
  - the output text block carries id='frozen-output' at x=828,
    text-anchor='start'

Usage:  .venv/bin/python -m autoresearch.figcheck [svg-or-json-path]
Default input: runs/pending_experiment.json (field architecture_svg).
Prints PASS or one line per violation; exit code 1 on any violation.
The design agent iterates until PASS; the harness treats failures as a
logged warning only (figures are record-keeping, not the metric).
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def check(svg: str) -> list[str]:
    errs = []
    m = re.search(r"viewBox=['\"]\s*0[ ,]+0[ ,]+980[ ,]+(\d+)", svg)
    if not m:
        errs.append("viewBox must be exactly '0 0 980 H' (width is fixed at 980)")
    else:
        h = int(m.group(1))
        if not 240 <= h <= 640:
            errs.append(f"viewBox height {h} outside 240-640 — grow height for "
                        "breathing room, never width")

    tag = re.search(r"<[^>]*id=['\"]frozen-input['\"][^>]*>", svg)
    if not tag:
        errs.append("missing id='frozen-input' on the camera-frame element (x=26)")
    elif not re.search(r"\bx=['\"]26['\"]", tag.group(0)):
        errs.append("frozen-input element must sit at x=26 (left-flush anchor)")

    tag = re.search(r"<[^>]*id=['\"]frozen-output['\"][^>]*>", svg)
    if not tag:
        errs.append("missing id='frozen-output' on the output text block "
                    "(x=828, text-anchor='start')")
    else:
        if not re.search(r"\bx=['\"]828['\"]", tag.group(0)):
            errs.append("frozen-output must sit at x=828 (right anchor)")
        if "text-anchor='start'" not in tag.group(0) and \
           'text-anchor="start"' not in tag.group(0):
            errs.append("frozen-output must use text-anchor='start'")
    return errs


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        REPO_ROOT / "runs" / "pending_experiment.json"
    if not src.exists():
        print(f"figcheck: {src} not found")
        return 1
    text = src.read_text()
    svg = json.loads(text).get("architecture_svg", "") \
        if src.suffix == ".json" else text
    if not svg.strip():
        print("figcheck: no architecture_svg found")
        return 1
    errs = check(svg)
    if errs:
        for e in errs:
            print(f"figcheck FAIL: {e}")
        return 1
    print("figcheck PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
