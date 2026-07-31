"""Middle-figure primitive toolkit — the EXACT hand-drawn visual language from
archive/arch_svg_reference.py, adapted to draw ONLY the design-specific MIDDLE
of an architecture figure (the frozen chrome — camera frame, output block, lane
labels — is composited separately by code and must NOT be drawn here).

Import this from a small Python script, call the primitives to assemble the
middle, then call `emit(out_path, parts)`. Composing from these primitives is
what makes the figure match the gold-standard originals: clean orthogonal
routing, kernel-projection ties between conv layers, converge fans that start at
real cells, gauges/branches drawn correctly. DO NOT hand-author raw <line>/
<path>/<polygon> for anything a primitive already covers.

Fixed anchors (the chrome is already there — draw to these EXACTLY):
  IC  = 112   inference lane centre y — the main left→right flow lives here
  TX  = 812   output crosshair x — every decode/aggregation converges to (TX, IC)
  The camera frame occupies x=26..102 (chrome); begin the middle around x=130.
  The output block sits at x>=828 (chrome); never draw past x=820.
Region you may draw in: x in [110, 820], y in [40, 412] (figure height is 420).
Training-signal annotations live low, around y=250..405.
"""
import html
import math

INK, MUT, FAINT, ACC, OCH = "#111111", "#6b6a60", "#9b998c", "#8c2f1f", "#8a6a1e"
FONT = "Palatino,Georgia,serif"
IC = 112            # inference lane centre y  (FIXED)
TX = 812            # output crosshair x       (FIXED)
HEIGHT = 420        # composite figure height
TRAIN_Y = 300       # baseline for the training-signal annotation row


# ---------------------------------------------------------------- text
def txt(x, y, s, size=10, color=MUT, w=400, anchor="middle", style="", tid=None):
    tid_attr = f"id='{tid}' " if tid else ""
    return (f"<text {tid_attr}x='{x:.0f}' y='{y:.0f}' font-family='{FONT}' font-size='{size}' "
            f"fill='{color}' font-weight='{w}' text-anchor='{anchor}' {style}>{html.escape(str(s))}</text>")


def cap(xc, y, name, sub=None, color=MUT, name_color=None):
    """Element caption: bold name on row y, faint sub-note 12px below.
    Place STRICTLY under its element; stagger y between adjacent columns so
    captions never collide."""
    out = [txt(xc, y, name, 10.5, name_color or (INK if color == MUT else color), 600)]
    if sub:
        out.append(txt(xc, y + 12, sub, 9.5, color))
    return "".join(out)


def shape(x, y, s, color=FAINT):
    """Tiny italic tensor-shape annotation (e.g. '8²×128'). Put it ABOVE the
    flow (y ~ IC-34) or tucked at a face — never on top of a caption."""
    return txt(x, y, s, 9, color, style="font-style='italic'")


# ---------------------------------------------------------------- arrows / leaders
def harrow(x1, x2, y=IC, label=None, color=FAINT):
    """Clean horizontal flow arrow x1→x2 on row y (straight, never diagonal)."""
    out = [f"<line x1='{x1}' y1='{y}' x2='{x2 - 5}' y2='{y}' stroke='{color}' stroke-width='1'/>",
           f"<path d='M {x2},{y} l -6,-3 v 6 Z' fill='{color}'/>"]
    if label:
        out.append(txt((x1 + x2) / 2, y - 6, label, 9, FAINT, style="font-style='italic'"))
    return "".join(out)


def leader(x1, y1, x2, y2, color=FAINT):
    """Dashed annotation leader. Prefer orthogonal L-routes (use lroute) through
    EMPTY lanes; a bare slanted leader is fine only for a short hop to text."""
    return (f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='{color}' "
            f"stroke-width='1' stroke-dasharray='2 4'/>")


def lroute(x1, y1, x2, y2, color=FAINT, dashed=True, horizontal_first=False):
    """Orthogonal L-shaped route (one right-angle bend) — the clean way to route
    a connector to a stage below/aside. horizontal_first=False goes vertical then
    horizontal. Use this instead of diagonal or multi-bend paths."""
    da = "stroke-dasharray='2 4' " if dashed else ""
    if horizontal_first:
        d = f"M {x1},{y1} H {x2} V {y2}"
    else:
        d = f"M {x1},{y1} V {y2} H {x2}"
    return f"<path d='{d}' fill='none' stroke='{color}' stroke-width='1' {da}/>"


# ---------------------------------------------------------------- tensors
def slab(x, s, d, color=INK):
    """Pseudo-3D feature-map slab (front s×s, depth d). Returns (svg, width)."""
    y = IC - s / 2
    dx, dy = d, d * 0.55
    out = [
        f"<polygon points='{x},{y} {x+dx},{y-dy} {x+dx+s},{y-dy} {x+s},{y}' "
        f"fill='#00000010' stroke='{color}' stroke-width='1'/>",
        f"<polygon points='{x+s},{y} {x+dx+s},{y-dy} {x+dx+s},{y-dy+s} {x+s},{y+s}' "
        f"fill='#0000001c' stroke='{color}' stroke-width='1'/>",
        f"<rect x='{x}' y='{y}' width='{s}' height='{s}' fill='#00000006' "
        f"stroke='{color}' stroke-width='1.2'/>",
    ]
    return "".join(out), s + dx


def bar(x, h, color=INK, ticks=9):
    """1-D vector as a thin vertical tick-bar. Returns (svg, width=7)."""
    y = IC - h / 2
    out = [f"<rect x='{x}' y='{y}' width='7' height='{h}' fill='none' "
           f"stroke='{color}' stroke-width='1.2'/>"]
    for i in range(1, ticks):
        out.append(f"<line x1='{x}' y1='{y + i * h / ticks:.1f}' x2='{x + 7}' "
                   f"y2='{y + i * h / ticks:.1f}' stroke='{color}' stroke-width='0.5' opacity='0.5'/>")
    return "".join(out), 7


def fan(x1, h1, x2, h2, color=FAINT, n=5):
    """Fully-connected layer as a fan of crossing connections between two bars."""
    out = []
    for i in range(n):
        ya = IC - h1 / 2 + (i + 0.5) * h1 / n
        for j in range(n):
            yb = IC - h2 / 2 + (j + 0.5) * h2 / n
            out.append(f"<line x1='{x1}' y1='{ya:.1f}' x2='{x2}' y2='{yb:.1f}' "
                       f"stroke='{color}' stroke-width='0.5' opacity='0.45'/>")
    return "".join(out)


def gridsq(x, s, n, color=INK, bumps=(), yc=None, lw=1.2):
    """A real n×n grid (probability field / coordinate field / target grid).
    bumps = iterable of (col, row, opacity) shaded cells. Returns (svg, s).
    Keep s <= 96 for a field on the inference lane: a taller grid pushes its top
    row into the y≈55-68 decode-caption band and the converge fan then crosses
    the caption. Training-row target glyphs (yc set low) can be smaller (~48)."""
    yc = IC if yc is None else yc
    y = yc - s / 2
    out = [f"<rect x='{x}' y='{y}' width='{s}' height='{s}' fill='none' "
           f"stroke='{color}' stroke-width='{lw}'/>"]
    for i in range(1, n):
        out.append(f"<line x1='{x + i * s / n:.1f}' y1='{y}' x2='{x + i * s / n:.1f}' "
                   f"y2='{y + s}' stroke='{color}' stroke-width='0.45' opacity='0.5'/>")
        out.append(f"<line x1='{x}' y1='{y + i * s / n:.1f}' x2='{x + s}' "
                   f"y2='{y + i * s / n:.1f}' stroke='{color}' stroke-width='0.45' opacity='0.5'/>")
    for (gx, gy, o) in bumps:
        out.append(f"<rect x='{x + gx * s / n:.1f}' y='{y + gy * s / n:.1f}' "
                   f"width='{s / n:.1f}' height='{s / n:.1f}' fill='{color}' fill-opacity='{o}'/>")
    return "".join(out), s


# a pleasant default clustered bump pattern for a probability field
BUMP = ((5, 2, .55), (4, 2, .28), (5, 1, .28), (6, 2, .18), (5, 3, .18), (2, 5, .12), (1, 6, .1))


def cell_centers(x, s, n, cols=None, rows=None, jitter=0.0):
    """Return real cell-centre (cx, cy) points of a gridsq — feed these to
    converge_pts so decode/vote lines start at ACTUAL cells, not thin air.
    cols/rows: iterables to subset (e.g. a refinement window). jitter in cells."""
    y0 = IC - s / 2
    cols = range(n) if cols is None else cols
    rows = range(n) if rows is None else rows
    pts = []
    for gy in rows:
        for gx in cols:
            ox = (((gx * 37 + gy * 53) % 9 - 4) * jitter)
            oy = (((gx * 61 + gy * 29) % 9 - 4) * jitter)
            pts.append((x + (gx + 0.5) * s / n + ox, y0 + (gy + 0.5) * s / n + oy))
    return pts


# ---------------------------------------------------------------- decode
def crosspt(x, y, color, r=7):
    """The decode crosshair. The final aggregation MUST land here at (TX, IC)."""
    return (f"<line x1='{x - r}' y1='{y}' x2='{x + r}' y2='{y}' stroke='{color}' stroke-width='1.4'/>"
            f"<line x1='{x}' y1='{y - r}' x2='{x}' y2='{y + r}' stroke='{color}' stroke-width='1.4'/>"
            f"<circle cx='{x}' cy='{y}' r='{r * 0.55:.1f}' fill='none' stroke='{color}' stroke-width='1.4'/>"
            f"<circle cx='{x}' cy='{y}' r='1.5' fill='{color}'/>")


def converge_pts(points, color, tx=TX, ty=IC, thin=0.55, op=0.4, every=1):
    """Decode/vote as thin lines from REAL source points to the crosshair, then
    the crosshair itself. This is the ONLY correct way to reach the output — a
    clean fan converging on (tx, ty). points = list of (x, y). `every` subsamples
    (e.g. 2 = checkerboard) to keep the fan legible."""
    out = []
    for k, (sx, sy) in enumerate(points):
        if every > 1 and k % every:
            continue
        out.append(f"<line x1='{sx:.0f}' y1='{sy:.0f}' x2='{tx}' y2='{ty}' "
                   f"stroke='{color}' stroke-width='{thin}' opacity='{op}'/>")
    out.append(crosspt(tx, ty, color))
    return "".join(out)


def converge(gx, gs, tx, color, cells="all", n=8):
    """Convenience: converge from a whole grid's cells (cells='all' = checker
    subset) to the crosshair. For a subset window pass cell_centers + converge_pts."""
    if cells == "all":
        pts = cell_centers(gx, gs, n)
        return converge_pts(pts, color, tx, every=2)
    return converge_pts(cell_centers(gx, gs, n), color, tx)


# ---------------------------------------------------------------- confidence
def gauge(x, yc, color=MUT, r=14):
    """Semicircular confidence gauge with a needle. Draw it on a BRANCH below the
    lane (via conf_branch), never inline on the main flow."""
    a = math.radians(55)
    return (f"<path d='M {x - r},{yc} A {r} {r} 0 0 1 {x + r},{yc}' fill='none' "
            f"stroke='{color}' stroke-width='1.2'/>"
            f"<line x1='{x}' y1='{yc}' x2='{x + (r - 3) * math.cos(a):.1f}' "
            f"y2='{yc - (r - 3) * math.sin(a):.1f}' stroke='{color}' stroke-width='1.4'/>"
            f"<circle cx='{x}' cy='{yc}' r='1.6' fill='{color}'/>")


def conf_branch(anchor_x, out_x=None, color=FAINT, gauge_y=232):
    """The confidence branch, drawn the canonical clean way: a dashed vertical
    leader drops from the lane at anchor_x to a gauge below, then a single
    orthogonal route (H then V) carries it to the output arrow. NEVER route
    confidence as a bezier squiggle and NEVER put the gauge inline on the lane.
    anchor_x = x on the inference lane the branch descends from (pick an EMPTY
    column). out_x defaults to just right of the crosshair."""
    gx = anchor_x
    ex = (TX + 30) if out_x is None else out_x
    out = [leader(gx, IC + 64, gx, gauge_y - 16, FAINT),
           gauge(gx, gauge_y, MUT),
           txt(gx, gauge_y + 18, "confidence 0–1", 9, MUT),
           f"<path d='M {gx + 18},{gauge_y} H {ex} V {IC + 26}' fill='none' "
           f"stroke='{FAINT}' stroke-width='0.8'/>",
           f"<path d='M {ex},{IC + 20} l -3,6 h 6 Z' fill='{FAINT}'/>",
           txt((gx + ex) / 2, gauge_y - 6, "may abstain instead of guessing", 8.5, FAINT,
               style="font-style='italic'")]
    return "".join(out)


# ---------------------------------------------------------------- conv encoder
def kernel_proj(x1, s1, x2, s2, color):
    """Conv connection: small kernel square on layer i's face, faint lines
    converging to a cell on layer i+1 — reads as 'computed from', not 'next to'."""
    k = max(5, s1 * 0.30)
    kx, ky = x1 + s1 * 0.60, IC - s1 / 2 + s1 * 0.18
    c = max(3, s2 * 0.14)
    cx, cy = x2 + s2 * 0.22, IC - s2 / 2 + s2 * 0.26
    out = [f"<rect x='{kx:.1f}' y='{ky:.1f}' width='{k:.1f}' height='{k:.1f}' "
           f"fill='none' stroke='{color}' stroke-width='0.9'/>",
           f"<rect x='{cx:.1f}' y='{cy:.1f}' width='{c:.1f}' height='{c:.1f}' "
           f"fill='{color}' fill-opacity='0.5' stroke='none'/>"]
    for (px, py) in ((kx, ky), (kx + k, ky), (kx, ky + k), (kx + k, ky + k)):
        out.append(f"<line x1='{px:.1f}' y1='{py:.1f}' x2='{cx + c / 2:.1f}' "
                   f"y2='{cy + c / 2:.1f}' stroke='{color}' stroke-width='0.55' "
                   f"opacity='0.45'/>")
    return "".join(out)


def encoder(x0=132, colors=None, name="convolutional encoder",
            sub="Conv 3×3, stride 2 ×4 · BN + ReLU",
            shape_in="64²×16", shape_out="8²×128"):
    """The shared 4-conv encoder as OUTPUT slabs (64²×16 → 8²×128), tied by
    kernel projections (the first from the camera frame's face). Returns
    (svg, x_end). Consecutive convs MUST be tied like this — never bare boxes."""
    sizes = [(46, 7), (34, 11), (24, 15), (17, 21)]
    out, x, faces = [], x0, []
    for i, (s, d) in enumerate(sizes):
        g, w = slab(x, s, d, (colors or [INK] * 4)[i])
        out.append(g)
        faces.append((x, s))
        x += w + 15
    x -= 15
    # first projection originates just inside the region (frame handoff)
    out.append(kernel_proj(x0 - 20, 60, faces[0][0], faces[0][1], FAINT))
    for (x1, s1), (x2, s2) in zip(faces, faces[1:]):
        out.append(kernel_proj(x1, s1, x2, s2, MUT))
    xc = (x0 + x) / 2
    out.append(cap(xc, IC + 58, name, sub))
    out.append(shape(x0 + 20, IC - 36, shape_in))
    out.append(shape(x - 18, IC - 32, shape_out))
    return "".join(out), x


# ---------------------------------------------------------------- training row
def loss_note(x_from, y_from, x_lab, lines, color, glyph=None, y=TRAIN_Y):
    """A training-signal annotation: a dashed leader from a real source up in the
    figure down to a short text block low on the page (left-anchored), optionally
    with a small pictorial glyph. Put ALL of the design's training-side detail
    here. Route the leader as an L (use lroute) if a straight one would cross a
    label."""
    out = [leader(x_from, y_from, x_lab - 8, y - 16, color)]
    if glyph:
        out.append(glyph)
    out.append(txt(x_lab, y - 12, lines[0], 10, color, 600, "start"))
    for i, extra in enumerate(lines[1:], 1):
        out.append(txt(x_lab, y - 12 + i * 12, extra, 9.5, color, 400, "start"))
    return "".join(out)


# ---------------------------------------------------------------- emit
def group(parts):
    body = "".join(p for p in parts if p)
    return f"<g font-family='{FONT}'>{body}</g>"


def emit(out_path, parts):
    """Write the middle as the required JSON object. `parts` = list of SVG
    fragment strings (from the primitives above)."""
    import json
    with open(out_path, "w") as f:
        json.dump({"middle_svg": group(parts)}, f)
    return group(parts)
