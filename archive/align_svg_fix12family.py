"""Geometry repairs for the gated-head figure family (rows 12, 14, 15) —
same asserted-replacement discipline as the other archive/align_svg_*
scripts: every replacement asserts its occurrence count, so an already-
patched figure fails loudly instead of double-shifting.

Three defect classes (author screenshots):

1. Floating dashed ends — the Σ/n relocation leaders stopped 2 px short
   of the boxes they connect (H 138 vs box left edge 140; M 164 / H 399
   vs box right edge 162 and gate left edge 401), which dash phase turns
   into visibly hanging runs. Endpoints now touch the element edges.
   Same rule applied family-wide: row 14's L2 leader now starts at the
   crosshair's bottom (M 812,120 — was 124, 5 px below nothing); row
   15's two field→confidence leaders now reach the MLP bar top (V 242)
   and the threshold bar's left tick (V 254), and its per-bucket leader
   descends to the calibration block's sub-caption top (V 363 — was 348,
   touching nothing).

2. Disconnected converge fans — every fan line ended at x=455 but at
   y 103-121: the empty gap BETWEEN the bright head bar (y 66-90) and
   the dark head bar (y 134-158). Retargeted onto the bars' left faces:
   GAP→bright 16 lines to y 69/75/81/87, layout-code→bright 9 lines to
   y 70/78/86 (both feeds of the 512⊕48 concat), and in row 12 the red
   GAP→dark 9 lines to y 138/146/154 (rows 14/15 already landed their
   dark fan on the bar at y 140-152 — untouched).

3. Blend-node joins — majority figure style is: input lines end ON the
   ⊕ circle rim with no arrowhead, gate line carries the single
   arrowhead. Row 12 (blend 630,112 r9): bright line 622,109 → 621,110
   and dark line 622,115 → 621,114 (both were 0.5 px inside the rim);
   gate line ends at the arrowhead base (615,107) and its arrowhead —
   previously detached at (618,101) and pointing against the line — is
   redrawn tip-on-rim at (621,109), oriented along the line direction.
   Rows 14/15 (blend 560,112 r9): bright/dark lines already touch the
   rim (dist 9.49) and stay; the gate line ends at (547,106) with the
   redrawn arrowhead tip at (552,108).

Usage: .venv/bin/python archive/align_svg_fix12family.py
(run on the pod against the pod's experiments.sqlite — back it up first:
cp experiments.sqlite experiments.sqlite.bak-figfix6)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autoresearch.db import connect


def _sigma_endpoint_fixes(stroke):
    return [
        (f"<path d='M 80,74 V 40 H 138' fill='none' stroke='{stroke}' stroke-width='1' stroke-dasharray='2 4'/>",
         f"<path d='M 80,74 V 40 H 140' fill='none' stroke='{stroke}' stroke-width='1' stroke-dasharray='2 4'/>", 1),
        (f"<path d='M 164,40 H 399' fill='none' stroke='{stroke}' stroke-width='0.8' stroke-dasharray='2 3'/>",
         f"<path d='M 162,40 H 401' fill='none' stroke='{stroke}' stroke-width='0.8' stroke-dasharray='2 3'/>", 1),
    ]


def _fan_fixes(float_fmt):
    """Retarget bright-head fans onto the bar face. float_fmt=True for
    row 12's '103.0' style, False for rows 14/15's '103' style."""
    f = (lambda v: f"{v:.1f}") if float_fmt else (lambda v: f"{v:g}")
    p = []
    # GAP bar → bright head: 4 sources x 4 targets
    for y1 in ("88.8", "104.2", "119.8", "135.2"):
        for old, new in ((103, 69), (109, 75), (115, 81), (121, 87)):
            p.append((f"<line x1='388' y1='{y1}' x2='455' y2='{f(old)}' stroke='#9b998c' stroke-width='0.5' opacity='0.45'/>",
                      f"<line x1='388' y1='{y1}' x2='455' y2='{f(new)}' stroke='#9b998c' stroke-width='0.5' opacity='0.45'/>", 1))
    # layout code → bright head: 3 x 3
    y1s = ("101.3", "112.0", "122.7") if float_fmt else ("101.3", "112", "122.7")
    for y1 in y1s:
        for old, new in ((104, 70), (112, 78), (120, 86)):
            p.append((f"<line x1='322' y1='{y1}' x2='455' y2='{f(old)}' stroke='#9b998c' stroke-width='0.5' opacity='0.45'/>",
                      f"<line x1='322' y1='{y1}' x2='455' y2='{f(new)}' stroke='#9b998c' stroke-width='0.5' opacity='0.45'/>", 1))
    return p


PATCHES = {
    12: _sigma_endpoint_fixes("#8c2f1f") + _fan_fixes(True) + [
        # red GAP → dark head fan: was also ending between the bars
        *[(f"<line x1='388' y1='{y1}' x2='455' y2='{o}.0' stroke='#8c2f1f' stroke-width='0.55' opacity='0.45'/>",
           f"<line x1='388' y1='{y1}' x2='455' y2='{n}.0' stroke='#8c2f1f' stroke-width='0.55' opacity='0.45'/>", 1)
          for y1 in ("91.3", "112.0", "132.7")
          for o, n in ((104, 138), (112, 146), (120, 154))],
        # blend joins (circle 630,112 r9)
        ("<line x1='462' y1='78' x2='622' y2='109' stroke='#111111' stroke-width='1'/>",
         "<line x1='462' y1='78' x2='621' y2='110' stroke='#111111' stroke-width='1'/>", 1),
        ("<line x1='462' y1='146' x2='622' y2='115' stroke='#8c2f1f' stroke-width='1'/>",
         "<line x1='462' y1='146' x2='621' y2='114' stroke='#8c2f1f' stroke-width='1'/>", 1),
        ("<line x1='417' y1='44.0' x2='622' y2='104' stroke='#8c2f1f' stroke-width='0.9'/>",
         "<line x1='417' y1='44.0' x2='615' y2='107' stroke='#8c2f1f' stroke-width='0.9'/>", 1),
        ("<path d='M 618,101 l -5,-1 1,5 Z' fill='#8c2f1f'/>",
         "<path d='M 621,109 l -6.4,0.3 1.4,-4.2 Z' fill='#8c2f1f'/>", 1),
    ],
    14: _sigma_endpoint_fixes("#9b998c") + _fan_fixes(False) + [
        # gate → blend (circle 560,112 r9): line to arrowhead base,
        # arrowhead redrawn tip-on-rim, oriented along the line
        ("<line x1='417' y1='44' x2='553' y2='105' stroke='#111111' stroke-width='0.9'/>",
         "<line x1='417' y1='44' x2='547' y2='106' stroke='#111111' stroke-width='0.9'/>", 1),
        ("<path d='M 549,102 l -5,-1 1,5 Z' fill='#111111'/>",
         "<path d='M 552,108 l -6.4,-0.5 1.9,-4.0 Z' fill='#111111'/>", 1),
        # L2 leader: start at the crosshair's bottom, not 5 px below it
        ("<path d='M 812,124 V 250 H 608 V 272' fill='none' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>",
         "<path d='M 812,120 V 250 H 608 V 272' fill='none' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>", 1),
    ],
    15: _sigma_endpoint_fixes("#9b998c") + _fan_fixes(False) + [
        ("<line x1='417' y1='44' x2='553' y2='105' stroke='#111111' stroke-width='0.9'/>",
         "<line x1='417' y1='44' x2='547' y2='106' stroke='#111111' stroke-width='0.9'/>", 1),
        ("<path d='M 549,102 l -5,-1 1,5 Z' fill='#111111'/>",
         "<path d='M 552,108 l -6.4,-0.5 1.9,-4.0 Z' fill='#111111'/>", 1),
        # field → confidence-cluster leaders: end ON their targets
        ("<path d='M 656,146 H 672 V 220 H 590 V 236' fill='none' stroke='#8c2f1f' stroke-width='0.9' stroke-dasharray='2 4'/>",
         "<path d='M 656,146 H 672 V 220 H 590 V 242' fill='none' stroke='#8c2f1f' stroke-width='0.9' stroke-dasharray='2 4'/>", 1),
        ("<path d='M 694,146 H 680 V 236' fill='none' stroke='#8c2f1f' stroke-width='0.9' stroke-dasharray='2 4'/>",
         "<path d='M 694,146 H 680 V 254' fill='none' stroke='#8c2f1f' stroke-width='0.9' stroke-dasharray='2 4'/>", 1),
        # per-bucket leader: descend to the calibration sub-caption top
        ("<path d='M 770,262 V 268 H 924 V 348' fill='none' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>",
         "<path d='M 770,262 V 268 H 924 V 363' fill='none' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>", 1),
    ],
}


def main():
    conn = connect()
    for exp_id in sorted(PATCHES):
        svg = conn.execute("SELECT arch_svg FROM experiments WHERE id=?",
                           (exp_id,)).fetchone()[0]
        for old, new, expect in PATCHES[exp_id]:
            n = svg.count(old)
            assert n == expect, (
                f"exp {exp_id}: expected {expect}x {old[:70]!r}, found {n} — "
                f"already patched or figure changed; aborting unmodified")
            svg = svg.replace(old, new)
        conn.execute("UPDATE experiments SET arch_svg=? WHERE id=?",
                     (svg, exp_id))
        print(f"exp {exp_id}: fan/leader/blend geometry repaired "
              f"({len(PATCHES[exp_id])} patches)")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
