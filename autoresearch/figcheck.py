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


def _num(attrs: str, name: str, default=None):
    m = re.search(rf"\b{name}=['\"]([-\d.]+)", attrs)
    return float(m.group(1)) if m else default


def _text_boxes(svg: str):
    """Approximate bounding boxes for unrotated <text> elements."""
    boxes = []
    for m in re.finditer(r"<text([^>]*)>(.*?)</text>", svg, re.S):
        attrs, raw = m.group(1), m.group(2)
        if "transform" in attrs:
            continue
        content = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()
        x, y = _num(attrs, "x"), _num(attrs, "y")
        if x is None or y is None or not content:
            continue
        fs = _num(attrs, "font-size", 11.0)
        w = len(content) * fs * 0.52          # serif average advance
        a = re.search(r"text-anchor=['\"](\w+)", attrs)
        a = a.group(1) if a else "start"
        x0 = x - w if a == "end" else x - w / 2 if a == "middle" else x
        boxes.append((x0, y - fs, x0 + w, y + fs * 0.25, content[:36]))
    return boxes


def _segments(svg: str):
    """Straight segments from <line> and absolute M/L/H/V path commands."""
    segs = []
    for m in re.finditer(r"<line([^>]*?)/?>", svg):
        a = m.group(1)
        p = (_num(a, "x1"), _num(a, "y1"), _num(a, "x2"), _num(a, "y2"))
        if None not in p:
            segs.append(p)
    for m in re.finditer(r"\bd=['\"]([^'\"]+)", svg):
        toks = re.findall(r"([MLHVmlhvZzACSQTacsqt])|(-?\d+\.?\d*)", m.group(1))
        cur = None
        cmd = None
        nums = []
        for c, n in toks:
            if c:
                cmd, nums = c, []
                if c in "Zz" or c.islower() or c in "ACSQTacsqt":
                    cmd = None  # only absolute M/L/H/V straight parts
                continue
            if cmd is None:
                continue
            nums.append(float(n))
            if cmd in "ML" and len(nums) == 2:
                if cmd == "L" and cur:
                    segs.append((cur[0], cur[1], nums[0], nums[1]))
                cur, nums = (nums[0], nums[1]), []
                cmd = "L" if cmd == "M" else cmd
            elif cmd == "H" and len(nums) == 1:
                if cur:
                    segs.append((cur[0], cur[1], nums[0], cur[1]))
                    cur = (nums[0], cur[1])
                nums = []
            elif cmd == "V" and len(nums) == 1:
                if cur:
                    segs.append((cur[0], cur[1], cur[0], nums[0]))
                    cur = (cur[0], nums[0])
                nums = []
    return segs


def _clip_len(seg, box):
    """Length of seg inside box (Liang-Barsky)."""
    x1, y1, x2, y2 = seg
    bx0, by0, bx1, by1 = box[:4]
    dx, dy = x2 - x1, y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x1 - bx0), (dx, bx1 - x1), (-dy, y1 - by0), (dy, by1 - y1)):
        if p == 0:
            if q < 0:
                return 0.0
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return 0.0
    return ((dx * (t1 - t0)) ** 2 + (dy * (t1 - t0)) ** 2) ** 0.5


def _inside(pt, box, pad=2.0):
    return (box[0] - pad <= pt[0] <= box[2] + pad
            and box[1] - pad <= pt[1] <= box[3] + pad)


def check_layout(svg: str) -> list[str]:
    """Geometric readability checks: text-on-text and line-through-label."""
    errs = []
    boxes = _text_boxes(svg)
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            ox = min(a[2], b[2]) - max(a[0], b[0])
            oy = min(a[3], b[3]) - max(a[1], b[1])
            if ox > 3.0 and oy > 3.0:
                errs.append(f"text overlap: '{a[4]}' vs '{b[4]}'")
    for seg in _segments(svg):
        for box in boxes:
            if _inside(seg[:2], box) or _inside(seg[2:], box):
                continue  # a line may END at a label, never cross it
            if _clip_len(seg, box) > 12.0:
                errs.append(f"line crosses label '{box[4]}' "
                            f"(seg {seg[0]:.0f},{seg[1]:.0f}→{seg[2]:.0f},{seg[3]:.0f})")
    return errs[:10]


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

    if not re.search(r"id=['\"]cam-terrain['\"]", svg):
        errs.append("camera frame must be the canonical terrain glyph from the "
                    "prompt (missing <g id='cam-terrain'>) — copy it verbatim")
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
    errs = check(svg) + check_layout(svg)
    if errs:
        for e in errs:
            print(f"figcheck FAIL: {e}")
        return 1
    print("figcheck PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
