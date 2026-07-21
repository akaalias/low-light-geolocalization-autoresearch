"""Canonical nadir-terrain camera-frame glyph, v2 (autoresearch/prompt.md:
"The camera frame is a fixed glyph — copy it verbatim"). 76x76 frame at
x=26 carrying id='frozen-input', wrapped in <g id='cam-terrain'> (the new
figcheck rejects figures without the marker). All elements sit strictly
INSIDE the frame border — v1's street strokes ended on the frame edge and
their caps overflowed it. `y` is the frame's top edge. Shared by
archive/arch_svg_reference.py (rows 1-6) and the row patch scripts.

terrain_frame_v1 is kept verbatim for the patch scripts, which need to
reconstruct the exact v1 strings previously written into the DB in order
to assert-and-replace them."""


def terrain_frame(y):
    return (
        f"<g id='cam-terrain'>"
        f"<rect id='frozen-input' x='26' y='{y}' width='76' height='76' "
        f"fill='#f6f4ea' stroke='#9b998c' stroke-width='1.6'/>"
        f"<path d='M31 {y + 47} L97 {y + 27}' stroke='#e6e3d4' stroke-width='5' fill='none'/>"
        f"<path d='M59 {y + 6} L49 {y + 70}' stroke='#e6e3d4' stroke-width='3.5' fill='none'/>"
        f"<rect x='34' y='{y + 9}' width='12' height='8' fill='#d9d5c3' transform='rotate(-8 40 {y + 13})'/>"
        f"<rect x='78' y='{y + 8}' width='10' height='11' fill='#cfccbd'/>"
        f"<rect x='35' y='{y + 57}' width='13' height='8' fill='#d9d5c3'/>"
        f"<rect x='75' y='{y + 50}' width='10' height='9' fill='#cfccbd' transform='rotate(6 80 {y + 54})'/>"
        f"<rect x='54' y='{y + 31}' width='9' height='8' fill='#d9d5c3' opacity='.85'/>"
        f"<ellipse cx='86' cy='{y + 63}' rx='8' ry='6' fill='#8a6a1e' opacity='.12'/>"
        f"<circle cx='40' cy='{y + 28}' r='.7' fill='#6b6a60' opacity='.5'/>"
        f"<circle cx='70' cy='{y + 14}' r='.7' fill='#6b6a60' opacity='.5'/>"
        f"<circle cx='92' cy='{y + 36}' r='.7' fill='#6b6a60' opacity='.5'/>"
        f"<circle cx='52' cy='{y + 52}' r='.7' fill='#6b6a60' opacity='.5'/>"
        f"<circle cx='82' cy='{y + 70}' r='.7' fill='#6b6a60' opacity='.5'/>"
        f"<circle cx='31' cy='{y + 42}' r='.7' fill='#6b6a60' opacity='.5'/>"
        f"</g>")


def terrain_frame_v1(y, wrap_g=True):
    """v1 geometry as deployed by the round-3/row-17 sweeps — street
    endpoints on the frame edge (26/102), no cam-terrain marker. For
    patch-script matching only; do not emit into new figures."""
    body = (
        f"<rect id='frozen-input' x='26' y='{y}' width='76' height='76' "
        f"fill='#f6f4ea' stroke='#9b998c' stroke-width='1.6'/>"
        f"<path d='M26 {y + 50} L102 {y + 24}' stroke='#e6e3d4' stroke-width='6' fill='none'/>"
        f"<path d='M62 {y + 2} L48 {y + 74}' stroke='#e6e3d4' stroke-width='4' fill='none'/>"
        f"<rect x='33' y='{y + 8}' width='13' height='9' fill='#d9d5c3' transform='rotate(-8 39 {y + 12})'/>"
        f"<rect x='79' y='{y + 7}' width='10' height='12' fill='#cfccbd'/>"
        f"<rect x='34' y='{y + 58}' width='14' height='9' fill='#d9d5c3'/>"
        f"<rect x='76' y='{y + 50}' width='11' height='10' fill='#cfccbd' transform='rotate(6 81 {y + 55})'/>"
        f"<rect x='55' y='{y + 32}' width='9' height='8' fill='#d9d5c3' opacity='.85'/>"
        f"<ellipse cx='88' cy='{y + 66}' rx='10' ry='7' fill='#8a6a1e' opacity='.12'/>"
        f"<circle cx='40' cy='{y + 28}' r='.7' fill='#6b6a60' opacity='.5'/>"
        f"<circle cx='70' cy='{y + 14}' r='.7' fill='#6b6a60' opacity='.5'/>"
        f"<circle cx='92' cy='{y + 34}' r='.7' fill='#6b6a60' opacity='.5'/>"
        f"<circle cx='52' cy='{y + 50}' r='.7' fill='#6b6a60' opacity='.5'/>"
        f"<circle cx='83' cy='{y + 70}' r='.7' fill='#6b6a60' opacity='.5'/>"
        f"<circle cx='31' cy='{y + 44}' r='.7' fill='#6b6a60' opacity='.5'/>")
    return f"<g>{body}</g>" if wrap_g else body
