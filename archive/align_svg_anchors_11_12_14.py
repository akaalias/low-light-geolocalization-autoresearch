"""One-off follow-up to align_svg_anchors.py for experiments 11, 12, 14:
bring the agent-drawn architecture figures onto the shared anchor contract
(autoresearch/figcheck.py) — camera frame flush left (x=26, id='frozen-input'),
decode crosshair at x=812, output text block at x=828 with
id='frozen-output'.

Exp 11 drew its output cluster short (crosshair 712, text 730): uniform
dx=+100 on the converge fan + crosshair, dx=+98 on the text block, decode
caption re-centered between the field grid and the new crosshair, confidence
elbow stretched to match. Exps 12 and 14 already sit at 812/828 and only
lack the frozen-input/frozen-output ids. Purely coordinate shifts and id
additions; nothing the agents drew is redrawn or removed. Safe to re-run:
every replacement asserts its expected occurrence count, so an
already-aligned figure fails loudly instead of double-shifting.

Usage: .venv/bin/python archive/align_svg_anchors_11_12_14.py
(run on the pod, against the pod's experiments.sqlite — never push a local
DB up; back the DB up first: cp experiments.sqlite experiments.sqlite.bak-figfix)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autoresearch.db import connect

# (old, new, expected occurrences) per experiment
PATCHES = {
    # exp 11: reference-style output cluster drawn at 712/730 — converge
    # fan + crosshair dx=+100, text block dx=+98, decode caption re-centered
    # at (540+76+812)/2+4 = 718, elbow stretched to tx+46 = 858.
    11: [
        ("x2='712' y2='112'", "x2='812' y2='112'", 32),          # converge fan
        ("<line x1='705' y1='112' x2='719' y2='112'", "<line x1='805' y1='112' x2='819' y2='112'", 1),
        ("<line x1='712' y1='105' x2='712' y2='119'", "<line x1='812' y1='105' x2='812' y2='119'", 1),
        ("cx='712' cy='112'", "cx='812' cy='112'", 2),
        ("<text x='668' y='58'", "<text x='718' y='58'", 1),     # soft-argmax caption
        ("<text x='668' y='70'", "<text x='718' y='70'", 1),
        ("<text x='730' y='94'", "<text x='828' y='94'", 1),     # output text block
        ("<text x='730' y='110' font-family='Palatino,Georgia,serif' font-size='13' "
         "fill='#6b6a60' font-weight='600' text-anchor='start' >(lat, lon, confidence)</text>",
         "<text id='frozen-output' x='828' y='110' font-family='Palatino,Georgia,serif' font-size='13' "
         "fill='#6b6a60' font-weight='600' text-anchor='start' >(lat, lon, confidence)</text>", 1),
        ("<text x='730' y='124'", "<text x='828' y='124'", 1),
        ("H 758 V 138", "H 858 V 138", 1),                       # confidence elbow
        ("M 758,132 l -3,6 h 6 Z", "M 858,132 l -3,6 h 6 Z", 1),
        ("<text x='594' y='224'", "<text x='644' y='224'", 1),   # may abstain
        ("<rect x='26' y='85.0' width='54' height='54'",
         "<rect id='frozen-input' x='26' y='85.0' width='54' height='54'", 1),
    ],
    # exps 12 & 14: already anchored at 812/828 — only the contract ids
    # are missing.
    12: [
        ("<rect x='26' y='85.0' width='54' height='54'",
         "<rect id='frozen-input' x='26' y='85.0' width='54' height='54'", 1),
        ("<text x='828' y='110' font-family='Palatino,Georgia,serif' font-size='13' "
         "fill='#6b6a60' font-weight='600' text-anchor='start' >(lat, lon, confidence)</text>",
         "<text id='frozen-output' x='828' y='110' font-family='Palatino,Georgia,serif' font-size='13' "
         "fill='#6b6a60' font-weight='600' text-anchor='start' >(lat, lon, confidence)</text>", 1),
    ],
    14: [
        ("<rect x='26' y='85' width='54' height='54'",
         "<rect id='frozen-input' x='26' y='85' width='54' height='54'", 1),
        ("<text x='828' y='110' font-family='Palatino,Georgia,serif' font-size='13' "
         "fill='#6b6a60' font-weight='600' text-anchor='start'>(lat, lon, confidence)</text>",
         "<text id='frozen-output' x='828' y='110' font-family='Palatino,Georgia,serif' font-size='13' "
         "fill='#6b6a60' font-weight='600' text-anchor='start'>(lat, lon, confidence)</text>", 1),
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
                f"already aligned or figure changed; aborting unmodified")
            svg = svg.replace(old, new)
        conn.execute("UPDATE experiments SET arch_svg=? WHERE id=?",
                     (svg, exp_id))
        print(f"exp {exp_id}: anchored at 26/812/828 with frozen ids")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
