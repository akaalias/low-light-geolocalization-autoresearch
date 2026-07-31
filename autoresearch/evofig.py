"""The research-evolution figure, generated from data instead of hand-placed.

WHY THIS EXISTS
---------------
This figure used to be a 13.8 KB single-line SVG literal in gallery.py with
every coordinate baked in, plus an `evolution_fork_svg()` that did eight
find-and-replace edits on that string to lift the berlin-slim work onto its
own lane. Three lists (TRUNK, DEAD, SUPER) sat next to it looking like the
source of truth and were not: the literal had been hand-edited past them, so
SUPER held five entries while the figure drew six, and TRUNK held thirteen
while the figure drew nine.

The cost showed up the first time anything was added. Placing one small branch
took three attempts -- once outside the era band, once anchored to y=256, which
after the fork surgery is the DORMANT main line, so the new branch was drawn
descending from an abandoned trunk rather than from the champion that produced
it. Both were invisible in the markup and obvious in a screenshot. A figure
that cannot be reviewed by reading it is a figure that ships wrong.

So: the marks below are data, and this module lays them out. Adding a branch is
appending a tuple; moving it is changing its lane. The fork is part of layout
rather than surgery performed on the output.

THE TIME AXIS IS NOT LINEAR, AND THAT IS DELIBERATE
Each day gets width proportional to how much happened in it: the six silent
days of 24-29 July are 96 px each, while 22 and 31 July are ~1,000. The widths
were tuned by hand in the original figure and are preserved here verbatim
rather than re-derived, because they encode a judgement about what deserves
room -- not something to recompute. DAY_W is that judgement, written down.

Coordinates are recovered from the original figure to within 0.15 px, so this
regenerates it rather than redrawing it.
"""

# --- the time axis -------------------------------------------------------
# Left edge of each day, and how wide that day is drawn. Activity-weighted.
DAY_W = {20: 824.0, 21: 304.0, 22: 928.0, 23: 824.0, 24: 200.0, 25: 96.0,
         26: 96.0, 27: 96.0, 28: 96.0, 29: 96.0, 30: 928.0, 31: 1031.8}
DAY_X = {21: 306.5}
for _d in range(22, 32):
    DAY_X[_d] = DAY_X[_d - 1] + DAY_W[_d - 1]
DAY_X[20] = DAY_X[21] - DAY_W[20]

VIEW_W, VIEW_H = 5349, 608
TRUNK_Y = 256.0
BRANCH_Y = 216.0          # the berlin-slim fork's own lane
TRUNK_X0 = 52.0
TRUNK_X1 = 4629.7         # where the line stops
SPLIT_D = 31.38           # berlin-slim: the trunk forks here
GAP = (24.0200, 30.7700, "six days of silence")


def x(day: float) -> float:
    """Day (fractional) -> pixel. Piecewise-linear, one segment per day."""
    d = int(day)
    return DAY_X[d] + (day - d) * DAY_W[d]


# --- the marks -----------------------------------------------------------
# (day, label, 'above'|'below')  -- where the label sits relative to the line
TRUNK_NODES = [
    (20.73, "Bootstrap", "below"),
    (20.80, "1 m/px orthophotos", "above"),
    (20.86, "Relighting rebuilt", "below"),
    (21.5099, "Goes public", "above"),
    (22.85, "Pivot enforced in code", "below"),
    (23.60, "One git writer", "below"),
    (30.8699, "PNG decode fix", "below"),
    (31.38, "berlin-slim branch", "below"),
    (31.6001, "0.040 - 96.5% usable", "below"),
]

# (from_day, to_day, lane_y, label, end_label) -- tried, then abandoned
DEAD = [
    (20.73, 20.80, 128, "Sentinel-2 10 m/px", "dropped in 20 min"),
    (22.50, 22.85, 128, "Prompt-only pivot rules", "never worked"),
    (30.88, 30.91, 64, "3D shadow relighting", "parked"),
    (30.90, 30.94, 128, "Retrieval-index probe", "parked, not disproven"),
]

# (from_day, to_day, lane_y, label, end_label) -- ran as mainline, replaced
SUPER = [
    (20.75, 31.4701, 320, "Region-holdout evaluation", "→ held-out viewpoints"),
    (20.75, 31.5201, 384, "Median error as the score", "→ mission score"),
    (21.3299, 23.60, 448, "RunPod - rented 4090 pod", "→ Modal"),
    (23.60, 30.96, 448, "Modal A100 - serverless", "credits out → local M1"),
    (23.56, 23.85, 512, "Berlin-only scope cut", "→ 4 areas restored"),
    (31.5201, 31.5501, 512, "Geometric mean", "→ mission score"),
]

# (day, label) -- something broke
INCIDENTS = [
    (22.03, "pod disk full"),
    (22.43, "Fable hits its cap"),
    (22.65, "CI out of disk"),
    (22.80, "two writers on main"),
    (23.58, "pod won&#39;t resume"),
    (24.02, "loop dies unnoticed"),
    (30.96, "credits exhausted"),
]

# (from_day, to_day, lane_y, label) -- an insight that changed the project
MERGES = [
    (22.5741, 22.85, 192, "enforce it in the source, not the prompt"),
    (23.2626, 23.60, 192, "the problem is two writers, not the platform"),
    (30.6830, 30.8699, 192, "stop guessing, profile it"),
    (31.2006, 31.4701, 192, "it is never shown the places it is tested on"),
    (31.2967, 31.5501, 128, "the score must BE the product requirement"),
    (31.4213, 31.6001, 64, "it was starved, not refuted"),
]

# --- the second fork: Prignitz becomes the live line ---------------------
# The probe that measured the Berlin champion on rural ground (0.113) did not
# stay a side-branch: its RESULT opened an era, so the line it runs on is the
# one work continues along. Berlin's lane ends at 0.040, complete rather than
# abandoned -- there is no × on it, because nothing about it failed.
PRIGNITZ_SPLIT_D = 31.6100   # the probe leaves the berlin-slim lane here
PRIGNITZ_Y = 128.0           # and the era continues on its own lane
PRIGNITZ_END_X = 4980.0   # runs on past the last node: work continues here
BERLIN_DONE_LABEL = "berlin era · complete at 0.040"
PRIGNITZ_NODES = [
    (31.6740, "Prignitz probe · 0.113", "above"),
    (31.7800, "prignitz era opens", "below"),
]


def _f(v):
    """Match the original figure's number formatting (one decimal, no -0.0)."""
    return f"{v + 0.0:.1f}"


def _branch(kind, key, x0, y0, x1, lane, lab, endlab, end_mark):
    """One branch: elbow off a horizontal line, run flat, terminate, label.

    The elbow's control offsets shrink for short branches so a 28 px stub does
    not overshoot its own endpoint -- the original figure's behaviour, kept.
    """
    s = min(1.0, (x1 - x0) / 45.0)
    c1, ex = x0 + 15.0 * s, x0 + 24.0 * s
    out = [f"<path class='evo-{kind}' data-k='{key}' d='M{_f(x0)},{y0:.0f} "
           f"C{_f(c1)},{y0:.0f} {_f(x0)},{_f(lane)} {_f(ex)},{_f(lane)} "
           f"L{_f(x1)},{_f(lane)}'/>"]
    if end_mark == "x":
        out.append(
            f"<g class='evo-end' data-k='{key}'>"
            f"<line x1='{_f(x1 - 4.5)}' y1='{_f(lane - 4.5)}' "
            f"x2='{_f(x1 + 4.5)}' y2='{_f(lane + 4.5)}'/>"
            f"<line x1='{_f(x1 - 4.5)}' y1='{_f(lane + 4.5)}' "
            f"x2='{_f(x1 + 4.5)}' y2='{_f(lane - 4.5)}'/></g>")
    else:
        out.append(f"<circle class='evo-{end_mark}' data-k='{key}' "
                   f"cx='{_f(x1)}' cy='{_f(lane)}' r='5'/>")
    cls = {"dead": "d", "super": "s", "open": "o"}[kind]
    out.append(f"<text class='evo-lab {cls}' data-k='{key}' x='{_f(ex + 8)}' "
               f"y='{_f(lane - 10)}' text-anchor='start'>{lab}</text>")
    out.append(f"<text class='evo-endlab {cls}' data-k='{key}' "
               f"x='{_f(x1 + 11)}' y='{_f(lane + 4)}' "
               f"text-anchor='start'>{endlab}</text>")
    return "".join(out)


def build_svg() -> str:
    """The whole figure, forked, in the original's element order (z-order)."""
    split_x = x(SPLIT_D)
    p = [f"<svg id='evo-svg' viewBox='0 0 {VIEW_W} {VIEW_H}' width='{VIEW_W}' "
         f"height='{VIEW_H}' role='img' "
         f"aria-label='research process as a branching graph'>"]

    for d in range(21, 32):                       # day rules
        gx = x(d)
        p.append(f"<line class='evo-grid' x1='{_f(gx)}' y1='30' "
                 f"x2='{_f(gx)}' y2='574'/>")
        p.append(f"<text class='evo-day' x='{_f(gx + 6)}' y='22'>{d} Jul</text>")

    g0, g1, glab = x(GAP[0]), x(GAP[1]), GAP[2]   # the silence
    p.append(f"<rect class='evo-gap' x='{_f(g0)}' y='242' "
             f"width='{_f(g1 - g0)}' height='28'/>")
    p.append(f"<text class='evo-gaplab' x='{_f((g0 + g1) / 2)}' y='235'>"
             f"{glab}</text>")

    # The trunk stops at the fork; what continues is main, dormant since.
    p.append(f"<line class='evo-trunk' x1='{_f(TRUNK_X0)}' y1='{TRUNK_Y:.0f}' "
             f"x2='{_f(split_x)}' y2='{TRUNK_Y:.0f}'/>")
    p.append(f"<line class='evo-dormant' x1='{_f(split_x)}' y1='{TRUNK_Y:.0f}' "
             f"x2='{_f(TRUNK_X1)}' y2='{TRUNK_Y:.0f}'/>")
    p.append(f"<text class='evo-dormantlab' x='{_f((split_x + TRUNK_X1) / 2)}' "
             f"y='{TRUNK_Y + 15:.0f}' text-anchor='middle'>"
             f"main — unchanged since</text>")
    p.append(f"<path class='evo-branch' d='M{_f(split_x)},{TRUNK_Y:.0f} "
             f"C{_f(split_x + 15)},{TRUNK_Y:.0f} {_f(split_x + 22)},"
             f"{BRANCH_Y:.0f} {_f(split_x + 40)},{BRANCH_Y:.0f} "
             f"L{_f(TRUNK_X1)},{BRANCH_Y:.0f}'/>")

    def base_y(day):
        """Which line is live at this instant.

        Two forks now, so a mark can no longer assume the trunk. Asking this
        instead of hard-coding a y is the whole point of the module: the
        Prignitz probe was hand-placed on TRUNK_Y twice, which after the first
        fork is the DORMANT main line, drawing it as a descendant of an
        abandoned branch rather than of the champion that produced it.
        """
        if day > PRIGNITZ_SPLIT_D:
            return PRIGNITZ_Y
        if day > SPLIT_D:
            return BRANCH_Y
        return TRUNK_Y

    for i, (d0, d1, lane, lab, end) in enumerate(DEAD):
        p.append(_branch("dead", f"d{i}", x(d0), base_y(d0), x(d1), lane,
                         lab, end, "x"))
    for i, (d0, d1, lane, lab, end) in enumerate(SUPER):
        p.append(_branch("super", f"s{i}", x(d0), base_y(d0), x(d1), lane,
                         lab, end, "endr"))

    for i, (d, lab) in enumerate(INCIDENTS):      # pins below the red lanes
        px = x(d)
        p.append(f"<path class='evo-pindot' data-k='i{i}' d='M{_f(px)},442.5 "
                 f"l5.5,5.5 l-5.5,5.5 l-5.5,-5.5 z'/>")
        p.append(f"<line class='evo-pin' data-k='i{i}' x1='{_f(px)}' "
                 f"y1='455.0' x2='{_f(px)}' y2='468.0'/>")
        p.append(f"<text class='evo-pinlab' data-k='i{i}' x='{_f(px)}' "
                 f"y='479.0' text-anchor='middle'>{lab}</text>")

    for i, (d0, d1, lane, lab) in enumerate(MERGES):
        x0, x1 = x(d0), x(d1)
        ty = base_y(d1) - 9          # where the arrow's point lands
        # The elbow's second control point sits 16 px below the lane, but
        # must stay clear of the target: on a short drop (a merge landing
        # on the fork lane rather than the trunk) 16 px would sit PAST the
        # endpoint and bow the corner backwards.
        c2 = min(lane + 16, ty - 7)
        p.append(f"<path class='evo-merge' data-k='m{i}' d='M{_f(x0)},"
                 f"{_f(lane)} L{_f(x1 - 22)},{_f(lane)} C{_f(x1 - 7)},"
                 f"{_f(lane)} {_f(x1)},{_f(c2)} {_f(x1)},{_f(ty)}'/>")
        p.append(f"<path class='evo-arrow' data-k='m{i}' d='M{_f(x1 - 4.5)},"
                 f"{_f(ty - 2)} L{_f(x1)},{_f(ty + 7)} L{_f(x1 + 4.5)},"
                 f"{_f(ty - 2)} z'/>")
        p.append(f"<circle class='evo-mstart' data-k='m{i}' cx='{_f(x0)}' "
                 f"cy='{_f(lane)}' r='3.5'/>")
        p.append(f"<text class='evo-mlab' data-k='m{i}' x='{_f(x1 - 26)}' "
                 f"y='{_f(lane - 9)}' text-anchor='end'>{lab}</text>")

    for i, (d, lab, side) in enumerate(TRUNK_NODES):
        px, y0 = x(d), base_y(d)
        tick = y0 + 15 if side == "below" else y0 - 12
        p.append(f"<line class='evo-tick' x1='{_f(px)}' y1='{y0:.0f}' "
                 f"x2='{_f(px)}' y2='{_f(tick)}'/>")
        p.append(f"<circle class='evo-node' data-k='t{i}' cx='{_f(px)}' "
                 f"cy='{y0:.0f}' r='6'/>")
        ly = y0 + 24 if side == "below" else y0 - 24
        p.append(f"<text class='evo-tlab' data-k='t{i}' x='{_f(px)}' "
                 f"y='{ly:.0f}'>{lab}</text>")

    # The second fork. Drawn in the trunk's own weight, not a branch's: the
    # Prignitz line is where work continues, so it has to read as the live
    # line rather than as another thing hanging off Berlin's.
    px0 = x(PRIGNITZ_SPLIT_D)
    p.append(f"<path class='evo-branch' data-k='p-fork' d='M{_f(px0)},"
             f"{BRANCH_Y:.0f} C{_f(px0 + 15)},{BRANCH_Y:.0f} {_f(px0 + 22)},"
             f"{PRIGNITZ_Y:.0f} {_f(px0 + 40)},{PRIGNITZ_Y:.0f} "
             f"L{_f(x(PRIGNITZ_NODES[0][0]))},{PRIGNITZ_Y:.0f}'/>")
    p.append(f"<line class='evo-trunk' x1='{_f(x(PRIGNITZ_NODES[0][0]))}' "
             f"y1='{PRIGNITZ_Y:.0f}' x2='{_f(PRIGNITZ_END_X)}' "
             f"y2='{PRIGNITZ_Y:.0f}'/>")
    # Berlin's lane is finished, not abandoned -- no × terminator, which in
    # this figure's vocabulary would say it failed. It reached its number.
    p.append(f"<text class='evo-dormantlab' x='{_f(TRUNK_X1 + 12)}' "
             f"y='{BRANCH_Y + 4:.0f}' text-anchor='start'>"
             f"{BERLIN_DONE_LABEL}</text>")
    for i, (d, lab, side) in enumerate(PRIGNITZ_NODES):
        nx = x(d)
        tick = PRIGNITZ_Y + 15 if side == "below" else PRIGNITZ_Y - 12
        p.append(f"<line class='evo-tick' x1='{_f(nx)}' y1='{PRIGNITZ_Y:.0f}' "
                 f"x2='{_f(nx)}' y2='{_f(tick)}'/>")
        p.append(f"<circle class='evo-node' data-k='p{i}' cx='{_f(nx)}' "
                 f"cy='{PRIGNITZ_Y:.0f}' r='6'/>")
        ly = PRIGNITZ_Y + 24 if side == "below" else PRIGNITZ_Y - 24
        p.append(f"<text class='evo-tlab' data-k='p{i}' x='{_f(nx)}' "
                 f"y='{ly:.0f}'>{lab}</text>")

    return "".join(p) + "</svg>"
