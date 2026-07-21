"""Canonical nadir-terrain camera-frame glyph (autoresearch/prompt.md:
"The camera frame is a fixed glyph — copy it verbatim"). 76x76 frame at
x=26 carrying id='frozen-input'; streets, building footprints, park
ellipse, noise dots. `y` is the frame's top edge. Shared by
archive/arch_svg_reference.py (rows 1-6) and archive/align_svg_round3.py
(rows 7-16)."""


def terrain_frame(y, wrap_g=True):
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
