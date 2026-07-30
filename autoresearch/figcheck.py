"""Validate the pre-registered architecture figure against the shared
anchor contract (see autoresearch/prompt.md and the reference
implementation in archive/arch_svg_reference.py):

  - viewBox '0 0 980 H' with H in 240-640 (width fixed, height flexible)
  - the camera-frame element carries id='frozen-input' at x=26
  - the output text block carries id='frozen-output' at x=828,
    text-anchor='start'
  - style contract: only the five palette colors, Palatino/Georgia/serif,
    stroke-width near the spec, no gradients/images, no emoji, and red
    used iff some stage is marked changed (see check_style / check_changed)

Usage:  .venv/bin/python -m autoresearch.figcheck [svg-or-json-path]
Default input: runs/pending_experiment.json (field architecture_svg).
Prints PASS or one line per violation; exit code 1 on any violation.
The design agent iterates until PASS; the harness treats failures as a
logged warning only (figures are record-keeping, not the metric).

Deliberately NOT checked here — geometry can't judge these without risking
false positives on legitimate elements, so they stay prompt-only: the
"fills only faint tints (opacity <=.12)" rule (foreground glyphs like
tick-bars/kernel-squares are correctly drawn at full ink opacity, and
telling a tint fill from a foreground glyph fill needs to know what the
shape represents, not just its geometry) and overall visual richness/craft
(a holistic aesthetic judgment, not a geometric one).
"""
import json
import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# The five-color style contract (prompt_figure.md). Hex values normalized
# to lowercase before comparison. archive/arch_svg_reference.py's own pseudo-
# 3D slab shading uses '#000000xx' (black + inline alpha) for faint edge/face
# tints instead of a separate opacity attribute — that's the canonical
# reference implementation, not a violation, so '#000000' is allowed too.
_PALETTE = {"#111111", "#6b6a60", "#9b998c", "#8c2f1f", "#8a6a1e", "#000000"}
_RED = "#8c2f1f"
_FONT = "palatino,georgia,serif"
# Calibrated against archive/arch_svg_reference.py's own stroke-widths, which
# range 0.4 (faint hairline ticks) to 2 (accent highlight border) — this is a
# sanity floor/ceiling for broken values, not a tight match to "~1.2/1".
_STROKE_RANGE = (0.3, 2.2)
_EMOJI_RANGES = (
    (0x1F000, 0x1FFFF),  # emoji/pictograph/symbol blocks (SMP)
    (0x2600, 0x26FF),    # misc symbols (weather/dingbat-adjacent)
    (0x2700, 0x27BF),    # dingbats
)


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


def _arc_points(x1, y1, rx, ry, rot_deg, large_arc, sweep, x2, y2, n=12):
    """Flatten an absolute SVG elliptical-arc command into n+1 points via
    the standard endpoint-to-center parametrization (SVG spec F.6.5), so
    curved elements (the confidence-gauge dial glyph, etc.) can be checked
    for crossing a label the same way straight segments already are."""
    if rx == 0 or ry == 0 or (x1 == x2 and y1 == y2):
        return [(x1, y1), (x2, y2)]
    phi = math.radians(rot_deg)
    cphi, sphi = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    x1p = cphi * dx + sphi * dy
    y1p = -sphi * dx + cphi * dy
    rx, ry = abs(rx), abs(ry)
    lam = x1p ** 2 / rx ** 2 + y1p ** 2 / ry ** 2
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large_arc == sweep:
        co = -co
    cxp, cyp = co * rx * y1p / ry, co * -ry * x1p / rx
    cx = cphi * cxp - sphi * cyp + (x1 + x2) / 2.0
    cy = sphi * cxp + cphi * cyp + (y1 + y2) / 2.0

    def _ang(ux, uy, vx, vy):
        d = math.sqrt((ux ** 2 + uy ** 2) * (vx ** 2 + vy ** 2))
        a = math.acos(max(-1.0, min(1.0, (ux * vx + uy * vy) / d))) if d else 0.0
        return -a if ux * vy - uy * vx < 0 else a

    theta1 = _ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = _ang((x1p - cxp) / rx, (y1p - cyp) / ry,
                  (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dtheta > 0:
        dtheta -= 2 * math.pi
    if sweep and dtheta < 0:
        dtheta += 2 * math.pi
    pts = []
    for i in range(n + 1):
        t = theta1 + dtheta * i / n
        pts.append((cx + rx * math.cos(t) * cphi - ry * math.sin(t) * sphi,
                    cy + rx * math.cos(t) * sphi + ry * math.sin(t) * cphi))
    return pts


def _polylines(svg: str):
    """Point-chains from <line> and absolute M/L/H/V/A path commands, each
    chain kept in drawing order (not flattened into loose segments) so a
    caller can tell a chain's true start/end from points merely sampled
    along the way — e.g. from arc flattening — which matters for "a line
    may end at a label, never cross it": that exemption must apply only to
    the chain's real endpoints, not to every synthetic arc sample point,
    or a curve that fully crosses a label (entering and exiting near its
    middle) would be wrongly waved through as if it were just landing."""
    chains = []
    for m in re.finditer(r"<line([^>]*?)/?>", svg):
        a = m.group(1)
        p = (_num(a, "x1"), _num(a, "y1"), _num(a, "x2"), _num(a, "y2"))
        if None not in p:
            chains.append([(p[0], p[1]), (p[2], p[3])])
    for m in re.finditer(r"\bd=['\"]([^'\"]+)", svg):
        toks = re.findall(r"([MLHVmlhvZzACSQTacsqt])|(-?\d+\.?\d*)", m.group(1))
        cmd = None
        nums = []
        chain = []
        for c, n in toks:
            if c:
                cmd, nums = c, []
                if c in "Zz" or c.islower() or c in "CSQTcsqt":
                    cmd = None  # only absolute M/L/H/V/A parts (agents draw
                                # exclusively in absolute coords in this style)
                continue
            if cmd is None:
                continue
            nums.append(float(n))
            if cmd == "M" and len(nums) == 2:
                if len(chain) > 1:
                    chains.append(chain)
                chain, nums = [(nums[0], nums[1])], []
            elif cmd == "L" and len(nums) == 2:
                chain.append((nums[0], nums[1]))
                nums = []
            elif cmd == "H" and len(nums) == 1:
                if chain:
                    chain.append((nums[0], chain[-1][1]))
                nums = []
            elif cmd == "V" and len(nums) == 1:
                if chain:
                    chain.append((chain[-1][0], nums[0]))
                nums = []
            elif cmd == "A" and len(nums) == 7:
                if chain:
                    cx, cy = chain[-1]
                    pts = _arc_points(cx, cy, nums[0], nums[1], nums[2],
                                       nums[3], nums[4], nums[5], nums[6])
                    chain.extend(pts[1:])
                nums = []
        if len(chain) > 1:
            chains.append(chain)
    return chains


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


def _strip_cam_terrain(svg: str) -> str:
    """Remove the frozen cam-terrain glyph (copied verbatim, own fixed
    colors/strokes) so style checks below only see the agent's own drawing."""
    m = re.search(r"<g[^>]*id=['\"]cam-terrain['\"][^>]*>.*?</g>", svg, re.S)
    return svg[: m.start()] + svg[m.end():] if m else svg


def check_style(svg: str) -> list[str]:
    """Palette / font / stroke-width / gradients-icons-emoji contract."""
    errs = []
    body = _strip_cam_terrain(svg)

    bad_colors = set()
    for m in re.finditer(r"(?:fill|stroke)\s*[:=]\s*['\"]?(#[0-9a-fA-F]{3,8})",
                          body):
        c = m.group(1).lower()
        rgb = c[:7]  # ignore an 8-digit hex's trailing alpha byte
        if rgb not in _PALETTE:
            bad_colors.add(c)
    for c in sorted(bad_colors)[:5]:
        errs.append(f"color {c} is not in the palette "
                     f"({', '.join(sorted(_PALETTE))}, optionally +alpha)")

    fonts = set()
    for m in re.finditer(r"font-family\s*[:=]\s*['\"]?([^'\";]+)", svg):
        fonts.add(re.sub(r"\s*,\s*", ",", m.group(1).strip()).lower())
    if not fonts:
        errs.append("missing font-family (expected Palatino,Georgia,serif)")
    else:
        for f in sorted(fonts - {_FONT}):
            errs.append(f"font-family '{f}' must be Palatino,Georgia,serif")

    lo, hi = _STROKE_RANGE
    for m in re.finditer(r"stroke-width\s*[:=]\s*['\"]?([\d.]+)", body):
        w = float(m.group(1))
        if not lo <= w <= hi:
            errs.append(f"stroke-width {w} outside ~{lo}-{hi} "
                        "(spec: ~1.2 elements, 1 arrows)")

    if re.search(r"<(linearGradient|radialGradient)\b", svg, re.I):
        errs.append("no gradients allowed — fills only flat colors/tints")
    if re.search(r"<image\b", svg, re.I):
        errs.append("no images/icons allowed — draw everything in ink")

    for m in re.finditer(r"<text[^>]*>(.*?)</text>", svg, re.S):
        text = re.sub(r"<[^>]+>", " ", m.group(1))
        for ch in text:
            cp = ord(ch)
            if any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES):
                errs.append(f"emoji-range character {ch!r} found in text "
                            "— no emoji")
                break
    return errs[:15]


def check_changed_consistency(svg: str, stages) -> list[str]:
    """Coarse necessary condition for 'red only for what changed': red
    present iff some stage is marked changed. Cannot verify red sits on
    the RIGHT element — only that it isn't used gratuitously or omitted."""
    if not stages:
        return []
    any_changed = any(s.get("changed") for s in stages if isinstance(s, dict))
    red_present = bool(re.search(
        rf"(?:fill|stroke)\s*[:=]\s*['\"]?{re.escape(_RED)}\b", svg, re.I))
    if any_changed and not red_present:
        return [f"a stage is marked changed but {_RED} (red) never "
                "appears in the figure"]
    if not any_changed and red_present:
        return [f"no stage is marked changed but {_RED} (red) appears — "
                "red is reserved for exactly what this experiment changed"]
    return []


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
    for chain in _polylines(svg):
        for box in boxes:
            clipped = sum(_clip_len((p1[0], p1[1], p2[0], p2[1]), box)
                          for p1, p2 in zip(chain, chain[1:]))
            if clipped <= 12.0:
                continue
            # A line/curve may legitimately END at a label (a leader line
            # landing on a caption) — exempt only when the chain's TRUE
            # start or end point (not a synthetic arc-sample point) sits in
            # the box and the total clipped length is little more than just
            # that tip; anything clipping substantially more is passing
            # through the label, not landing on it.
            tip = ((_inside(chain[0], box) or _inside(chain[-1], box))
                   and clipped <= 16.0)
            if tip:
                continue
            errs.append(f"line crosses label '{box[4]}'")
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
    stages = None
    if src.suffix == ".json":
        d = json.loads(text)
        svg = d.get("architecture_svg", "")
        stages = d.get("architecture", {}).get("stages")
    else:
        svg = text
    if not svg.strip():
        print("figcheck: no architecture_svg found")
        return 1
    errs = (check(svg) + check_style(svg) + check_changed_consistency(svg, stages)
            + check_layout(svg))
    if errs:
        for e in errs:
            print(f"figcheck FAIL: {e}")
        return 1
    print("figcheck PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
