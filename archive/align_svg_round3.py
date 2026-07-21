"""Round-3 figure fixes for experiments 7-16 (rows with arch_svg; 13 has
none). Two workstreams, same asserted-replacement discipline as
align_svg_anchors.py / align_svg_fixes_7_8_9.py — every replacement
asserts its expected occurrence count so an already-patched figure fails
loudly instead of double-shifting.

Workstream B (all rows here): the abstract gray pixel-texture camera
frame is replaced by the canonical 76x76 nadir-terrain glyph
(autoresearch/prompt.md, archive/terrain_frame_glyph.py), frame top
chosen per figure so it stays centered on that figure's inference lane
(y=74 for lane 112; y=82 for row 7's lane 120; y=110 for row 16's lane
148). The old 54x54 frames end at x=80, the glyph at x=102, so each
figure's frame→encoder arrow shaft (86→10x) is dropped — its arrowhead
(104-110) exactly fills the remaining gap — and the 128²x3 shape caption
moves up clear of the taller frame. Receptive-field squares and
kernel-projection lines stay drawn on top, as the spec requires. Rows 10
and 15 also gain the frozen-output id they were missing (frozen-input
rides on the glyph rect).

Workstream A (author feedback):
  10 — 'FC 640 → 1024 logits'/'softmax' collided head-on with
       '128-d GAP'/'texture average — as before'; moved right (474→500)
       into the empty space between the logits bar and the field.
  11 — red ImageNet leader ran diagonally from (178.5,180) across the
       caption area; now a short vertical tick at x=88 (the trunk
       sub-caption's left edge) dropping to the training-lane text that
       sits nearly below.
  12 — full cleanup: trunk captions 170/182→200/212 (clear of the camera
       captions), layout-code captions 158/170→188/200 (clear of
       48-d GAP), Σ/n brightness box relocated from (58,208) to (140,32)
       so frame→Σ/n→gate reads as two short orthogonal hops instead of a
       dashed diagonal through the whole trunk, 'g ∈ [0,1]' moved off the
       gate wires to (545,52), and both training leaders rerouted as
       orthogonal paths through empty lanes.
  14 — same family: trunk 170/182→200/212, layout →(330,188/200), Σ/n
       relocated as in 12, field captions pulled apart (626→617,
       724→733), Gaussian-CE and L2-on-sharpened leaders rerouted
       orthogonally.
  15 — same, plus: sharpened-field sub-caption split onto two lines,
       viewBox 340→420, training lane dropped to y=338 with the three
       bottom caption blocks spread at x 58/350/760 y 360/372, the whole
       confidence-head cluster (feature labels, MLP bars, fan, threshold
       bar + 0.3 marker, notes) shifted down 44 px into the new room, its
       three input leaders rerouted (two orthogonal drops through the
       caption gap at x 672/680; the 48-d GAP one as H-then-slant-then-V
       that clears every label), and the three block leaders re-aimed
       (olive re-targeted, BCE re-sourced off the MLP bar, per-bucket as
       an orthogonal path around the threshold note).
  16 — glyph only, plus rotation-fan origins moved from the old frame
       edge (82) to the new one (104) and the camera captions nudged
       +6 px below the taller frame.

Usage: .venv/bin/python archive/align_svg_round3.py
(run on the pod against the pod's experiments.sqlite — back it up first:
cp experiments.sqlite experiments.sqlite.bak-figfix3)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from autoresearch.db import connect
from terrain_frame_glyph import terrain_frame

F = "Palatino,Georgia,serif"


def _texture_v1(y0, with_id, y_fmt="{:.1f}"):
    """54x54 imgsq-style block, float-y variant (rows 8-12: y='85.0';
    row 16: y='121.0'); interleaved grid lines, long float opacities."""
    tid = "id='frozen-input' " if with_id else ""
    ys = y_fmt.format(y0)
    ye = y_fmt.format(y0 + 54)
    out = [f"<rect {tid}x='26' y='{ys}' width='54' height='54' fill='#00000008' "
           f"stroke='#9b998c' stroke-width='1.4'/>"]
    for i in range(1, 6):
        out.append(f"<line x1='{26 + i * 9}' y1='{ys}' x2='{26 + i * 9}' y2='{ye}' "
                   f"stroke='#9b998c' stroke-width='0.4' opacity='0.3'/>")
        out.append(f"<line x1='26' y1='{y0 + i * 9}' x2='80' y2='{y0 + i * 9}' "
                   f"stroke='#9b998c' stroke-width='0.4' opacity='0.3'/>")
    for (a, b, o) in ((1, 2, .35), (3, 1, .5), (2, 4, .4), (4, 3, .3), (0, 4, .25), (4, 0, .3)):
        out.append(f"<rect x='{26 + a * 9}' y='{y0 + b * 9}' width='9' height='9' "
                   f"fill='#9b998c' opacity='{o * 0.35}'/>")
    return "".join(out)


def _texture_v2(with_id):
    """Integer-coordinate agent redraw of the same block (rows 14, 15):
    all verticals, then all horizontals, short opacities."""
    tid = "id='frozen-input' " if with_id else ""
    out = [f"<rect {tid}x='26' y='85' width='54' height='54' fill='#00000008' "
           f"stroke='#9b998c' stroke-width='1.4'/>"]
    for i in range(1, 6):
        out.append(f"<line x1='{26 + i * 9}' y1='85' x2='{26 + i * 9}' y2='139' "
                   f"stroke='#9b998c' stroke-width='0.4' opacity='0.3'/>")
    for i in range(1, 6):
        out.append(f"<line x1='26' y1='{85 + i * 9}' x2='80' y2='{85 + i * 9}' "
                   f"stroke='#9b998c' stroke-width='0.4' opacity='0.3'/>")
    for (a, b, o) in ((1, 2, '0.12'), (3, 1, '0.18'), (2, 4, '0.14'),
                      (4, 3, '0.1'), (0, 4, '0.09'), (4, 0, '0.1')):
        out.append(f"<rect x='{26 + a * 9}' y='{85 + b * 9}' width='9' height='9' "
                   f"fill='#9b998c' opacity='{o}'/>")
    return "".join(out)


def _texture_row7():
    out = ["<rect id='frozen-input' x='26' y='85' width='70' height='70' "
           "fill='none' stroke='#111111' stroke-width='1.2'/>"]
    for (x, y, o) in ((25, 85, '.09'), (45, 85, '.05'), (75, 85, '.11'),
                      (35, 95, '.04'), (65, 95, '.08'), (25, 105, '.10'),
                      (55, 105, '.06'), (85, 105, '.09'), (45, 115, '.12'),
                      (75, 115, '.05'), (25, 125, '.07'), (55, 125, '.10'),
                      (35, 135, '.08'), (65, 135, '.04'), (85, 145, '.07')):
        out.append(f"<rect x='{x}' y='{y}' width='10' height='10' "
                   f"fill='#111111' opacity='{o}'/>")
    return "".join(out)


ARROW_SHAFT_105 = "<line x1='86' y1='112' x2='105' y2='112' stroke='#9b998c' stroke-width='1'/>"
ARROW_SHAFT_103 = "<line x1='86' y1='112' x2='103' y2='112' stroke='#9b998c' stroke-width='1'/>"
SHAPE_CAP_W = ("<text x='53' y='72' font-family='" + F + "' font-size='9' fill='#9b998c' "
               "font-weight='400' text-anchor='middle' >128²×3</text>")   # generator style
SHAPE_CAP_N = ("<text x='53' y='72' font-family='" + F + "' font-size='9' fill='#9b998c' "
               "text-anchor='middle'>128²×3</text>")                      # rows 14/15 style
OUT_ID_SP = ("<text x='828' y='110' font-family='" + F + "' font-size='13' fill='#6b6a60' "
             "font-weight='600' text-anchor='start' >(lat, lon, confidence)</text>")


def glyph_patches(row):
    """Workstream-B patch list per row: frame block → terrain glyph,
    arrow shaft dropped, shape caption raised."""
    p = []
    if row == 7:
        p += [(_texture_row7(), terrain_frame(82, wrap_g=False), 1),
              ("<line x1='98' y1='120' x2='124' y2='120' stroke='#9b998c' stroke-width='1' marker-end='url(#ah)'/>",
               "<line x1='106' y1='120' x2='124' y2='120' stroke='#9b998c' stroke-width='1' marker-end='url(#ah)'/>", 1),
              ("<text x='110' y='110' text-anchor='middle' font-size='9' font-style='italic' fill='#9b998c'>128×128×3</text>",
               "<text x='60' y='76' text-anchor='middle' font-size='9' font-style='italic' fill='#9b998c'>128×128×3</text>", 1)]
    elif row in (8, 9, 11, 12):
        shaft = ARROW_SHAFT_103 if row == 11 else ARROW_SHAFT_105
        p += [(_texture_v1(85, with_id=True), terrain_frame(74), 1),
              (shaft, "", 1),
              (SHAPE_CAP_W, SHAPE_CAP_W.replace("y='72'", "y='68'"), 1)]
    elif row == 10:
        p += [(_texture_v1(85, with_id=False), terrain_frame(74), 1),
              (ARROW_SHAFT_105, "", 1),
              (SHAPE_CAP_W, SHAPE_CAP_W.replace("y='72'", "y='68'"), 1),
              (OUT_ID_SP, OUT_ID_SP.replace("<text ", "<text id='frozen-output' ", 1), 1)]
    elif row in (14, 15):
        p += [(_texture_v2(with_id=(row == 14)), terrain_frame(74), 1),
              (ARROW_SHAFT_105, "", 1),
              (SHAPE_CAP_N, SHAPE_CAP_N.replace("y='72'", "y='68'"), 1)]
        if row == 15:
            out15 = ("<text x='828' y='110' font-family='" + F + "' font-size='13' fill='#6b6a60' "
                     "font-weight='600' text-anchor='start'>(lat, lon, confidence)</text>")
            p += [(out15, out15.replace("<text ", "<text id='frozen-output' ", 1), 1)]
    elif row == 16:
        p += [(_texture_v1(121, with_id=True), terrain_frame(110), 1),
              ("x1='82' y1='148'", "x1='104' y1='148'", 4),
              ("<text x='53' y='108' font-family='" + F + "' font-size='9' fill='#9b998c' "
               "font-weight='400' text-anchor='middle' >128²×3</text>",
               "<text x='53' y='104' font-family='" + F + "' font-size='9' fill='#9b998c' "
               "font-weight='400' text-anchor='middle' >128²×3</text>", 1),
              ("<text x='53' y='196'", "<text x='53' y='202'", 1),
              ("<text x='53' y='208'", "<text x='53' y='214'", 1),
              ("<text x='53' y='221'", "<text x='53' y='227'", 1)]
    return p


def sigma_relocation(box_stroke, leader_stroke):
    """Σ/n brightness box from (58,208) up to (140,32): the frame→Σ/n→gate
    chain becomes two short orthogonal dashes along the top instead of
    diagonals through the trunk (rows 12, 14, 15)."""
    return [
        (f"<line x1='53' y1='139' x2='63' y2='208' stroke='{leader_stroke}' stroke-width='1' stroke-dasharray='2 4'/>",
         f"<path d='M 80,74 V 40 H 138' fill='none' stroke='{leader_stroke}' stroke-width='1' stroke-dasharray='2 4'/>", 1),
        (f"<rect x='58' y='208' width='22' height='15' fill='none' stroke='{box_stroke}' stroke-width='1'/>",
         f"<rect x='140' y='32' width='22' height='15' fill='none' stroke='{box_stroke}' stroke-width='1'/>", 1),
        (f"<line x1='73' y1='208' x2='401' y2='54' stroke='{leader_stroke}' stroke-width='0.8' stroke-dasharray='2 3'/>",
         f"<path d='M 164,40 H 399' fill='none' stroke='{leader_stroke}' stroke-width='0.8' stroke-dasharray='2 3'/>", 1),
    ]


def _txt12(x, y, size, fill, w, extra, s):
    weight = f"font-weight='{w}' " if w else ""
    return (f"<text x='{x}' y='{y}' font-family='{F}' font-size='{size}' fill='{fill}' "
            f"{weight}text-anchor='middle' {extra}>{s}</text>")


PATCHES = {}
for r in (7, 8, 9, 10, 11, 12, 14, 15, 16):
    PATCHES[r] = glyph_patches(r)

# --- workstream A ---------------------------------------------------------
PATCHES[10] += [
    ("<text x='474' y='196' font-family='" + F + "' font-size='10.5' fill='#8c2f1f' "
     "font-weight='600' text-anchor='middle' >FC 640 → 1024 logits</text>",
     "<text x='500' y='196' font-family='" + F + "' font-size='10.5' fill='#8c2f1f' "
     "font-weight='600' text-anchor='middle' >FC 640 → 1024 logits</text>", 1),
    ("<text x='474' y='208' font-family='" + F + "' font-size='9.5' fill='#6b6a60' "
     "font-weight='400' text-anchor='middle' >softmax</text>",
     "<text x='500' y='208' font-family='" + F + "' font-size='9.5' fill='#6b6a60' "
     "font-weight='400' text-anchor='middle' >softmax</text>", 1),
]

PATCHES[11] += [
    ("<line x1='178.5' y1='180' x2='60' y2='272' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>",
     "<line x1='88' y1='188' x2='88' y2='274' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>", 1),
]

PATCHES[12] += sigma_relocation("#8c2f1f", "#8c2f1f") + [
    ("<text x='69' y='218' font-family='" + F + "' font-size='8.5' fill='#8c2f1f' font-weight='600' text-anchor='middle' >∑/n</text>",
     "<text x='151' y='42' font-family='" + F + "' font-size='8.5' fill='#8c2f1f' font-weight='600' text-anchor='middle' >∑/n</text>", 1),
    ("<text x='69' y='235' font-family='" + F + "' font-size='8.5' fill='#8c2f1f' font-weight='400' text-anchor='middle' font-style='italic'>raw-pixel mean brightness</text>",
     "<text x='151' y='58' font-family='" + F + "' font-size='8.5' fill='#8c2f1f' font-weight='400' text-anchor='middle' font-style='italic'>raw-pixel mean brightness</text>", 1),
    ("<text x='201' y='170'", "<text x='201' y='200'", 1),   # trunk title
    ("<text x='201' y='182'", "<text x='201' y='212'", 1),   # trunk sub
    ("<text x='338' y='158'", "<text x='338' y='188'", 1),   # layout code
    ("<text x='338' y='170'", "<text x='338' y='200'", 1),   # 1x1 conv
    ("<text x='397' y='68' font-family='" + F + "' font-size='9' fill='#8c2f1f' font-weight='600' text-anchor='end' >g ∈ [0,1]</text>",
     "<text x='545' y='52' font-family='" + F + "' font-size='9' fill='#8c2f1f' font-weight='600' text-anchor='end' >g ∈ [0,1]</text>", 1),
    ("<line x1='630' y1='152' x2='532' y2='276' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>",
     "<path d='M 630,152 V 166 H 540 V 272' fill='none' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>", 1),
    ("<line x1='725.0' y1='174' x2='262' y2='276' stroke='#8a6a1e' stroke-width='1' stroke-dasharray='2 4'/>",
     "<path d='M 725,174 V 254 H 278 V 272' fill='none' stroke='#8a6a1e' stroke-width='1' stroke-dasharray='2 4'/>", 1),
]

PATCHES[14] += sigma_relocation("#6b6a60", "#9b998c") + [
    ("<text x='69' y='218' font-family='" + F + "' font-size='8.5' fill='#6b6a60' font-weight='600' text-anchor='middle'>∑/n</text>",
     "<text x='151' y='42' font-family='" + F + "' font-size='8.5' fill='#6b6a60' font-weight='600' text-anchor='middle'>∑/n</text>", 1),
    ("<text x='69' y='235' font-family='" + F + "' font-size='8.5' fill='#6b6a60' text-anchor='middle' font-style='italic'>raw-pixel mean brightness</text>",
     "<text x='151' y='58' font-family='" + F + "' font-size='8.5' fill='#6b6a60' text-anchor='middle' font-style='italic'>raw-pixel mean brightness</text>", 1),
    ("<text x='201' y='170'", "<text x='201' y='200'", 1),
    ("<text x='201' y='182'", "<text x='201' y='212'", 1),
    ("<text x='338' y='158'", "<text x='330' y='188'", 1),
    ("<text x='338' y='170'", "<text x='330' y='200'", 1),
    ("<text x='626' y='160'", "<text x='617' y='160'", 1),   # probability field
    ("<text x='626' y='172'", "<text x='617' y='172'", 1),   # 32x32 cells
    ("<text x='724' y='160'", "<text x='733' y='160'", 1),   # sharpened field
    ("<text x='724' y='172'", "<text x='733' y='172'", 1),
    ("<text x='724' y='184'", "<text x='733' y='184'", 1),
    ("<line x1='610' y1='176' x2='250' y2='272' stroke='#8a6a1e' stroke-width='1' stroke-dasharray='2 4'/>",
     "<path d='M 610,176 H 545 V 254 H 268 V 272' fill='none' stroke='#8a6a1e' stroke-width='1' stroke-dasharray='2 4'/>", 1),
    ("<line x1='812' y1='122' x2='590' y2='272' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>",
     "<path d='M 812,124 V 250 H 608 V 272' fill='none' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>", 1),
]

# row 15: viewBox growth, lane drop, cluster shift +44, leader reroutes
_p15 = sigma_relocation("#6b6a60", "#9b998c") + [
    ("<text x='69' y='218' font-family='" + F + "' font-size='8.5' fill='#6b6a60' font-weight='600' text-anchor='middle'>∑/n</text>",
     "<text x='151' y='42' font-family='" + F + "' font-size='8.5' fill='#6b6a60' font-weight='600' text-anchor='middle'>∑/n</text>", 1),
    ("<text x='69' y='235' font-family='" + F + "' font-size='8.5' fill='#6b6a60' text-anchor='middle' font-style='italic'>raw-pixel mean brightness</text>",
     "<text x='151' y='58' font-family='" + F + "' font-size='8.5' fill='#6b6a60' text-anchor='middle' font-style='italic'>raw-pixel mean brightness</text>", 1),
    ("viewBox='0 0 980 340'", "viewBox='0 0 980 420'", 1),
    ("<text x='8' y='258'", "<text x='8' y='338'", 1),
    # separate the two field captions: split the wide sharpened sub-line
    ("<text x='724' y='172' font-family='" + F + "' font-size='9.5' fill='#6b6a60' text-anchor='middle'>softmax(β·logits), β = 3 — unchanged</text>",
     "<text x='724' y='172' font-family='" + F + "' font-size='9.5' fill='#6b6a60' text-anchor='middle'>softmax(β·logits)</text>"
     "<text x='724' y='184' font-family='" + F + "' font-size='9.5' fill='#6b6a60' text-anchor='middle'>β = 3 — unchanged</text>", 1),
    # cluster input leaders → routed clear of every label
    ("<line x1='594' y1='144' x2='588' y2='194' stroke='#8c2f1f' stroke-width='0.9' stroke-dasharray='2 4'/>",
     "<path d='M 656,146 H 672 V 220 H 590 V 236' fill='none' stroke='#8c2f1f' stroke-width='0.9' stroke-dasharray='2 4'/>", 1),
    ("<line x1='700' y1='144' x2='596' y2='196' stroke='#8c2f1f' stroke-width='0.9' stroke-dasharray='2 4'/>",
     "<path d='M 694,146 H 680 V 236' fill='none' stroke='#8c2f1f' stroke-width='0.9' stroke-dasharray='2 4'/>", 1),
    ("<line x1='391' y1='143' x2='580' y2='206' stroke='#8c2f1f' stroke-width='0.9' stroke-dasharray='2 4'/>",
     "<path d='M 395,124 H 448 L 548,200 V 240' fill='none' stroke='#8c2f1f' stroke-width='0.9' stroke-dasharray='2 4'/>", 1),
    # threshold-bar elbow into the output starts from the shifted bar
    ("<path d='M 772,213 H 854 V 144' fill='none' stroke='#8c2f1f' stroke-width='0.9'/>",
     "<path d='M 772,257 H 854 V 144' fill='none' stroke='#8c2f1f' stroke-width='0.9'/>", 1),
    ("<text x='816' y='232'", "<text x='816' y='282'", 1),   # below-the-bar note
    ("<text x='668' y='252'", "<text x='668' y='296'", 1),   # cluster title
    ("<text x='668' y='264'", "<text x='668' y='308'", 1),   # cluster sub
    # bottom caption blocks: spread across the new lane
    ("<line x1='610' y1='176' x2='160' y2='272' stroke='#8a6a1e' stroke-width='1' stroke-dasharray='2 4'/>",
     "<line x1='610' y1='176' x2='230' y2='352' stroke='#8a6a1e' stroke-width='1' stroke-dasharray='2 4'/>", 1),
    ("<text x='58' y='280'", "<text x='58' y='360'", 1),
    ("<text x='58' y='292'", "<text x='58' y='372'", 1),
    ("<line x1='643' y1='228' x2='430' y2='272' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>",
     "<line x1='590' y1='276' x2='440' y2='352' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>", 1),
    ("<text x='340' y='280'", "<text x='350' y='360'", 1),
    ("<text x='340' y='292'", "<text x='350' y='372'", 1),
    ("<line x1='737' y1='224' x2='730' y2='272' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>",
     "<path d='M 770,262 V 268 H 924 V 348' fill='none' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>", 1),
    ("<text x='660' y='280'", "<text x='760' y='360'", 1),
    ("<text x='660' y='292'", "<text x='760' y='372'", 1),
]
# confidence-head cluster: uniform dy=+44 into the grown canvas
for old_y, tick_y, label in ((205, 202, "peak mass"), (216, 213, "entropy"),
                             (227, 224, "mode−mean gap")):
    _p15 += [
        (f"<text x='574' y='{old_y}' font-family='{F}' font-size='8.5' fill='#8c2f1f' "
         f"text-anchor='end' font-style='italic'>{label}</text>",
         f"<text x='574' y='{old_y + 44}' font-family='{F}' font-size='8.5' fill='#8c2f1f' "
         f"text-anchor='end' font-style='italic'>{label}</text>", 1),
        (f"<line x1='577' y1='{tick_y}' x2='585' y2='{tick_y}' stroke='#8c2f1f' stroke-width='0.7' opacity='0.7'/>",
         f"<line x1='577' y1='{tick_y + 44}' x2='585' y2='{tick_y + 44}' stroke='#8c2f1f' stroke-width='0.7' opacity='0.7'/>", 1),
    ]
_p15 += [
    ("<rect x='586' y='198' width='7' height='30' fill='none' stroke='#8c2f1f' stroke-width='1.2'/>",
     "<rect x='586' y='242' width='7' height='30' fill='none' stroke='#8c2f1f' stroke-width='1.2'/>", 1),
    ("<rect x='640' y='202' width='7' height='22' fill='none' stroke='#8c2f1f' stroke-width='1.2'/>",
     "<rect x='640' y='246' width='7' height='22' fill='none' stroke='#8c2f1f' stroke-width='1.2'/>", 1),
]
for y in (204, 210, 216, 222):
    _p15.append((f"<line x1='586' y1='{y}' x2='593' y2='{y}' stroke='#8c2f1f' stroke-width='0.5' opacity='0.5'/>",
                 f"<line x1='586' y1='{y + 44}' x2='593' y2='{y + 44}' stroke='#8c2f1f' stroke-width='0.5' opacity='0.5'/>", 1))
for y in ('207.5', '213', '218.5'):
    _p15.append((f"<line x1='640' y1='{y}' x2='647' y2='{y}' stroke='#8c2f1f' stroke-width='0.5' opacity='0.5'/>",
                 f"<line x1='640' y1='{float(y) + 44:g}' x2='647' y2='{float(y) + 44:g}' stroke='#8c2f1f' stroke-width='0.5' opacity='0.5'/>", 1))
for y1 in ('201.8', '209.2', '216.8', '224.2'):
    for y2 in ('204.8', '210.2', '215.8', '221.2'):
        _p15.append((f"<line x1='593' y1='{y1}' x2='640' y2='{y2}' stroke='#8c2f1f' stroke-width='0.5' opacity='0.45'/>",
                     f"<line x1='593' y1='{float(y1) + 44:g}' x2='640' y2='{float(y2) + 44:g}' stroke='#8c2f1f' stroke-width='0.5' opacity='0.45'/>", 1))
_p15 += [
    ("<line x1='649' y1='213' x2='671' y2='213' stroke='#8c2f1f' stroke-width='1'/>",
     "<line x1='649' y1='257' x2='671' y2='257' stroke='#8c2f1f' stroke-width='1'/>", 1),
    ("<path d='M 676,213 l -6,-3 v 6 Z' fill='#8c2f1f'/>",
     "<path d='M 676,257 l -6,-3 v 6 Z' fill='#8c2f1f'/>", 1),
    ("<line x1='680' y1='213' x2='768' y2='213' stroke='#8c2f1f' stroke-width='1.2'/>",
     "<line x1='680' y1='257' x2='768' y2='257' stroke='#8c2f1f' stroke-width='1.2'/>", 1),
    ("<line x1='680' y1='210' x2='680' y2='216' stroke='#8c2f1f' stroke-width='1'/>",
     "<line x1='680' y1='254' x2='680' y2='260' stroke='#8c2f1f' stroke-width='1'/>", 1),
    ("<line x1='768' y1='210' x2='768' y2='216' stroke='#8c2f1f' stroke-width='1'/>",
     "<line x1='768' y1='254' x2='768' y2='260' stroke='#8c2f1f' stroke-width='1'/>", 1),
    ("<rect x='706' y='206' width='62' height='14' fill='#8c2f1f' fill-opacity='0.08' stroke='none'/>",
     "<rect x='706' y='250' width='62' height='14' fill='#8c2f1f' fill-opacity='0.08' stroke='none'/>", 1),
    ("<line x1='706' y1='204' x2='706' y2='222' stroke='#8c2f1f' stroke-width='1.4'/>",
     "<line x1='706' y1='248' x2='706' y2='266' stroke='#8c2f1f' stroke-width='1.4'/>", 1),
    ("<text x='706' y='199'", "<text x='706' y='243'", 1),
]
PATCHES[15] += _p15


def main():
    conn = connect()
    for exp_id in sorted(PATCHES):
        patches = PATCHES[exp_id]
        svg = conn.execute("SELECT arch_svg FROM experiments WHERE id=?",
                           (exp_id,)).fetchone()[0]
        for old, new, expect in patches:
            n = svg.count(old)
            assert n == expect, (
                f"exp {exp_id}: expected {expect}x {old[:70]!r}, found {n} — "
                f"already patched or figure changed; aborting unmodified")
            svg = svg.replace(old, new)
        conn.execute("UPDATE experiments SET arch_svg=? WHERE id=?",
                     (svg, exp_id))
        print(f"exp {exp_id}: terrain frame + round-3 layout fixes applied "
              f"({len(patches)} patches)")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
