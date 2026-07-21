"""One-off layout fixes for the agent-drawn architecture figures of
experiments 7, 8, 9 (same asserted-replacement pattern as
align_svg_anchors.py / align_svg_anchors_11_12_14.py):

  exp 7 — the 'was: 800 places/bucket' and 'now: 6,000 places/bucket'
    captions both sat centered at y=312 (centers 75 px apart, texts
    ~105-120 px wide) and covered each other. 'was' is now right-aligned
    to the olive box's right edge (x=194), 'now' left-aligned to the red
    box's left edge (x=215), 'of ~45,000 available' centered between the
    two boxes (x=204). Also brings exp 7 onto the shared anchor contract
    (autoresearch/figcheck.py): camera rect to x=26 with id='frozen-input',
    output text from x=848 to x=828 with text-anchor='start' and
    id='frozen-output'; the 20 px crosshair→text arrow is dropped because
    the contract gap (819→828) can no longer host it — every other figure
    joins crosshair and text by adjacency alone.

  exp 8 — the red encoder sub-caption was one ~420 px line centered at
    x=227 (spanning ~18-436), colliding with the camera-frame captions on
    the left and the 'FC → 1024 logits' label on the right. Wrapped into
    two centered lines (y=194, y=206) confined to the encoder's span
    (~x 112-342). Contract ids added.

  exp 9 — (a) the 'FC → 1024 logits'/'softmax' labels moved down 14 px
    (y 196/208 → 210/222) clear of the probability-field caption and the
    old leader's path; (b) the red dashed NT-Xent leader ran diagonally
    from the 128-d GAP bar (372,148) to (600,262) across the FC fan and
    labels — rerouted orthogonally through empty space: left under the
    GAP bar (y=146 to x=332, skirting the '128-d'/'GAP' captions and the
    confidence branch at x 338-402), straight down to y=252 (above the
    pair-annotation texts, below 'confidence 0-1'), right to x=597, and
    down to the NT-Xent projection bar's top corner. Contract ids added.

Nothing else is moved; every replacement asserts its expected occurrence
count, so an already-patched figure fails loudly instead of
double-shifting.

Usage: .venv/bin/python archive/align_svg_fixes_7_8_9.py
(run on the pod against the pod's experiments.sqlite — back it up first:
cp experiments.sqlite experiments.sqlite.bak-figfix2)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autoresearch.db import connect

# (old, new, expected occurrences) per experiment
PATCHES = {
    7: [
        # anchor contract: camera frame to x=26 + id (pixel texture keeps
        # its 1 px inset — invisible at gallery scale)
        ("<rect x='25' y='85' width='70' height='70' fill='none' stroke='#111111' stroke-width='1.2'/>",
         "<rect id='frozen-input' x='26' y='85' width='70' height='70' fill='none' stroke='#111111' stroke-width='1.2'/>", 1),
        # overlapping coverage captions: split left/right of the box gap
        ("<text x='167' y='312' text-anchor='middle' font-size='9.5' fill='#6b6a60'>was: 800 places/bucket</text>",
         "<text x='194' y='312' text-anchor='end' font-size='9.5' fill='#6b6a60'>was: 800 places/bucket</text>", 1),
        ("<text x='242' y='312' text-anchor='middle' font-size='9.5' font-weight='600' fill='#8c2f1f'>now: 6,000 places/bucket</text>",
         "<text x='215' y='312' text-anchor='start' font-size='9.5' font-weight='600' fill='#8c2f1f'>now: 6,000 places/bucket</text>", 1),
        ("<text x='242' y='323' text-anchor='middle' font-size='9' fill='#6b6a60'>of ~45,000 available</text>",
         "<text x='204' y='323' text-anchor='middle' font-size='9' fill='#6b6a60'>of ~45,000 available</text>", 1),
        # anchor contract: output text 848 → 828; the arrow can't fit the
        # 819→828 gap, so it goes — crosshair meets text by adjacency
        ("<line x1='822' y1='120' x2='842' y2='120' stroke='#9b998c' stroke-width='1' marker-end='url(#ah)'/>",
         "", 1),
        ("<text x='848' y='124' font-size='13' font-style='italic' fill='#111111'>(lat, lon, confidence)</text>",
         "<text id='frozen-output' x='828' y='124' font-size='13' font-style='italic' text-anchor='start' fill='#111111'>(lat, lon, confidence)</text>", 1),
    ],
    8: [
        # wide red sub-caption → two lines inside the encoder's span
        ("<text x='227' y='194' font-family='Palatino,Georgia,serif' font-size='9.5' fill='#8c2f1f' "
         "font-weight='400' text-anchor='middle' >~973k params, 4.2× the old 4-conv stack — 3.7 of "
         "the 4.0 MiB flight-memory budget (was 0.9)</text>",
         "<text x='227' y='194' font-family='Palatino,Georgia,serif' font-size='9.5' fill='#8c2f1f' "
         "font-weight='400' text-anchor='middle' >~973k params, 4.2× the old 4-conv stack</text>"
         "<text x='227' y='206' font-family='Palatino,Georgia,serif' font-size='9.5' fill='#8c2f1f' "
         "font-weight='400' text-anchor='middle' >3.7 of the 4.0 MiB flight-memory budget (was 0.9)</text>", 1),
        ("<rect x='26' y='85.0' width='54' height='54'",
         "<rect id='frozen-input' x='26' y='85.0' width='54' height='54'", 1),
        ("<text x='828' y='110' font-family='Palatino,Georgia,serif' font-size='13' "
         "fill='#6b6a60' font-weight='600' text-anchor='start' >(lat, lon, confidence)</text>",
         "<text id='frozen-output' x='828' y='110' font-family='Palatino,Georgia,serif' font-size='13' "
         "fill='#6b6a60' font-weight='600' text-anchor='start' >(lat, lon, confidence)</text>", 1),
    ],
    9: [
        # FC head labels down 14 px, clear of neighbors and the new route
        ("<text x='442' y='196' font-family='Palatino,Georgia,serif' font-size='10.5' fill='#111111' "
         "font-weight='600' text-anchor='middle' >FC → 1024 logits</text>",
         "<text x='442' y='210' font-family='Palatino,Georgia,serif' font-size='10.5' fill='#111111' "
         "font-weight='600' text-anchor='middle' >FC → 1024 logits</text>", 1),
        ("<text x='442' y='208' font-family='Palatino,Georgia,serif' font-size='9.5' fill='#6b6a60' "
         "font-weight='400' text-anchor='middle' >softmax</text>",
         "<text x='442' y='222' font-family='Palatino,Georgia,serif' font-size='9.5' fill='#6b6a60' "
         "font-weight='400' text-anchor='middle' >softmax</text>", 1),
        # NT-Xent leader: diagonal across the figure → orthogonal route
        ("<line x1='372' y1='148' x2='600' y2='262' stroke='#8c2f1f' stroke-width='1' stroke-dasharray='2 4'/>",
         "<path d='M 373,146 H 332 V 252 H 597 V 257' fill='none' stroke='#8c2f1f' stroke-width='1' "
         "stroke-dasharray='2 4'/>", 1),
        ("<rect x='26' y='85.0' width='54' height='54'",
         "<rect id='frozen-input' x='26' y='85.0' width='54' height='54'", 1),
        ("<text x='828' y='110' font-family='Palatino,Georgia,serif' font-size='13' "
         "fill='#6b6a60' font-weight='600' text-anchor='start' >(lat, lon, confidence)</text>",
         "<text id='frozen-output' x='828' y='110' font-family='Palatino,Georgia,serif' font-size='13' "
         "fill='#6b6a60' font-weight='600' text-anchor='start' >(lat, lon, confidence)</text>", 1),
    ],
}


def main():
    conn = connect()
    for exp_id, patches in PATCHES.items():
        svg = conn.execute("SELECT arch_svg FROM experiments WHERE id=?",
                           (exp_id,)).fetchone()[0]
        for old, new, expect in patches:
            n = svg.count(old)
            assert n == expect, (
                f"exp {exp_id}: expected {expect}x {old!r}, found {n} — "
                f"already patched or figure changed; aborting unmodified")
            svg = svg.replace(old, new)
        conn.execute("UPDATE experiments SET arch_svg=? WHERE id=?",
                     (svg, exp_id))
        print(f"exp {exp_id}: layout fixed, anchors/ids on contract")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
