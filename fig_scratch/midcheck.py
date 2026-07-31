"""Stricter validator for the AGENT-DRAWN MIDDLE only (the frozen chrome is
composited separately). Adapts autoresearch/figcheck.py's geometry (text-boxes,
segment extraction, Liang-Barsky clip) and adds the checks that close the
quality gap versus the hand-drawn originals:

  1. no text overlaps other text                        (readability)
  2. no line/leader crosses a text label                (readability)
  3. everything stays inside the middle region          (no chrome collision)
  4. the middle does NOT redraw any frozen chrome        (split contract)
  5. the flow reaches the (812,112) crosshair CLEANLY    (no zig-zag connector)
        - a converge fan (>=3 lines ending at the crosshair) OR
        - a single straight horizontal arrow ending at it
        - and NO long slanted/curved segment approaches the lane end messily

Usage: .venv/bin/python fig_scratch/midcheck.py <middle-json-or-svg-path>
Prints PASS, or one line per violation; exit 1 on any violation.
"""
import json
import re
import sys
from pathlib import Path

IC, TX = 112.0, 812.0
# region the middle may draw in (chrome owns x<110 and x>820)
X_MIN, X_MAX, Y_MIN, Y_MAX = 108.0, 820.0, 40.0, 414.0
CHROME_TOKENS = ["frozen-input", "frozen-output", "cam-terrain", "INFERENCE PATH",
                 "TRAINING SIGNAL", "lat, lon, confidence", "camera frame"]


def _num(attrs, name, default=None):
    m = re.search(rf"\b{name}=['\"]([-\d.]+)", attrs)
    return float(m.group(1)) if m else default


def _text_boxes(svg):
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
        w = len(content) * fs * 0.52
        a = re.search(r"text-anchor=['\"](\w+)", attrs)
        a = a.group(1) if a else "start"
        x0 = x - w if a == "end" else x - w / 2 if a == "middle" else x
        boxes.append((x0, y - fs, x0 + w, y + fs * 0.25, content[:36]))
    return boxes


def _segments(svg):
    """Straight segments from <line>, <polygon>, and absolute M/L/H/V paths.
    Also returns whether each path used curve commands (C/S/Q/A) for the
    connector check."""
    segs = []
    for m in re.finditer(r"<line([^>]*?)/?>", svg):
        a = m.group(1)
        p = (_num(a, "x1"), _num(a, "y1"), _num(a, "x2"), _num(a, "y2"))
        if None not in p:
            segs.append(p)
    for m in re.finditer(r"\bd=['\"]([^'\"]+)", svg):
        d = m.group(1)
        toks = re.findall(r"([MLHVmlhvZzACSQTacsqt])|(-?\d+\.?\d*)", d)
        cur = start = None
        cmd = None
        nums = []
        for c, n in toks:
            if c:
                cmd, nums = c, []
                if c in "Zz":
                    cmd = None
                elif c.islower() or c in "ACSQTacsqt":
                    cmd = None  # only absolute straight parts become segments
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


def _all_coords(svg):
    """All (x,y) vertices we can cheaply read: line/rect/circle/text/poly/path
    numeric pairs — for region-bounds checking."""
    pts = []
    for m in re.finditer(r"<line([^>]*?)/?>", svg):
        a = m.group(1)
        for xa, ya in (("x1", "y1"), ("x2", "y2")):
            x, y = _num(a, xa), _num(a, ya)
            if x is not None and y is not None:
                pts.append((x, y))
    for m in re.finditer(r"<rect([^>]*?)/?>", svg):
        a = m.group(1)
        x, y, w, h = _num(a, "x"), _num(a, "y"), _num(a, "width", 0), _num(a, "height", 0)
        if x is not None and y is not None:
            pts += [(x, y), (x + w, y + h)]
    for m in re.finditer(r"<circle([^>]*?)/?>", svg):
        a = m.group(1)
        x, y = _num(a, "cx"), _num(a, "cy")
        if x is not None and y is not None:
            pts.append((x, y))
    for m in re.finditer(r"<text([^>]*)>", svg):
        a = m.group(1)
        if "transform" in a:
            continue
        x, y = _num(a, "x"), _num(a, "y")
        if x is not None and y is not None:
            pts.append((x, y))
    for m in re.finditer(r"points=['\"]([^'\"]+)", svg):
        for pr in re.findall(r"(-?\d+\.?\d*)[ ,]+(-?\d+\.?\d*)", m.group(1)):
            pts.append((float(pr[0]), float(pr[1])))
    return pts


def _clip_len(seg, box):
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


def check(svg):
    errs = []

    # 4. no chrome redrawn in the middle
    for tok in CHROME_TOKENS:
        if tok in svg:
            errs.append(f"middle redraws frozen chrome ('{tok}') — the chrome is "
                        "composited by code; draw only the middle")

    boxes = _text_boxes(svg)
    segs = _segments(svg)

    # 1. text-on-text
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            ox = min(a[2], b[2]) - max(a[0], b[0])
            oy = min(a[3], b[3]) - max(a[1], b[1])
            if ox > 3.0 and oy > 3.0:
                errs.append(f"text overlap: '{a[4]}' vs '{b[4]}'")

    # 2. line-through-label
    for seg in segs:
        for box in boxes:
            if _inside(seg[:2], box) or _inside(seg[2:], box):
                continue
            if _clip_len(seg, box) > 12.0:
                errs.append(f"line crosses label '{box[4]}' "
                            f"(seg {seg[0]:.0f},{seg[1]:.0f}→{seg[2]:.0f},{seg[3]:.0f})")

    # 3. region bounds
    oob = 0
    for (x, y) in _all_coords(svg):
        if x < X_MIN - 1 or x > X_MAX + 1 or y < Y_MIN - 1 or y > Y_MAX + 1:
            oob += 1
            if oob <= 4:
                errs.append(f"element outside middle region: ({x:.0f},{y:.0f}) "
                            f"— stay within x[{X_MIN:.0f},{X_MAX:.0f}] y[{Y_MIN:.0f},{Y_MAX:.0f}]")

    # 5. clean connector into the (TX, IC) crosshair
    def near(px, py, ex, ey, tol=8.0):
        return abs(px - ex) <= tol and abs(py - ey) <= tol
    arriving = [s for s in segs if near(s[2], s[3], TX, IC) or near(s[0], s[1], TX, IC)]
    converge_lines = [s for s in arriving
                      if near(s[2], s[3], TX, IC) and not near(s[0], s[1], TX, IC)]
    # a horizontal arrow ending at the crosshair (dy ~ 0)
    horiz = [s for s in arriving if abs(s[3] - IC) <= 6 and abs(s[1] - IC) <= 6
             and abs(s[2] - s[0]) > 15]
    clean = len(converge_lines) >= 3 or len(horiz) >= 1
    if not clean:
        errs.append("flow does not reach the (812,112) crosshair cleanly — the "
                    "decode must be a converge fan (>=3 lines ending at 812,112) "
                    "or a single straight horizontal arrow into it")
    # any long slanted segment (not near-horizontal, not near-vertical) whose
    # endpoint sits near the lane end reads as a zig-zag/U connector
    for s in segs:
        near_end = (760 < s[0] < 815 or 760 < s[2] < 815)
        touches_lane = min(abs(s[1] - IC), abs(s[3] - IC)) < 40
        length = ((s[2] - s[0]) ** 2 + (s[3] - s[1]) ** 2) ** 0.5
        slant = abs(s[2] - s[0]) > 8 and abs(s[3] - s[1]) > 8  # neither H nor V
        # allow converge fan lines (they end exactly at the crosshair)
        ends_at_cross = near(s[2], s[3], TX, IC) or near(s[0], s[1], TX, IC)
        if near_end and touches_lane and slant and length > 30 and not ends_at_cross:
            errs.append(f"messy slanted connector near the output "
                        f"(seg {s[0]:.0f},{s[1]:.0f}→{s[2]:.0f},{s[3]:.0f}) — route "
                        "confidence on a clean L-branch, converge decode to 812,112")

    return errs[:14]


def main():
    if len(sys.argv) < 2:
        print("usage: midcheck.py <middle-json-or-svg-path>")
        return 1
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"midcheck: {src} not found")
        return 1
    text = src.read_text()
    svg = json.loads(text).get("middle_svg", "") if src.suffix == ".json" else text
    if not svg.strip():
        print("midcheck: no middle_svg found")
        return 1
    errs = check(svg)
    if errs:
        for e in errs:
            print(f"midcheck FAIL: {e}")
        return 1
    print("midcheck PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
