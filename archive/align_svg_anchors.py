"""One-off: right-anchor the frozen (u, v, conf) output in the agent-drawn
architecture figures (experiments 7-10) so every figure on the
inference-paths page shares the contract figure's endpoints — camera frame
flush left (x=26), decode crosshair at x=812, output text block at x=828.
Purely a coordinate shift of each figure's output cluster; nothing the
agents drew is redrawn or removed. Experiments 1-6 get the same anchors by
re-running arch_svg_reference.py. Safe to re-run: every replacement asserts
its expected occurrence count, so an already-aligned figure fails loudly
instead of double-shifting.

Usage: .venv/bin/python archive/align_svg_anchors.py
"""
import sys

sys.path.insert(0, "/Users/alexisrondeau/Workshop/low-light-geolocalization-autoresearch")
from autoresearch.db import connect

# (old, new, expected occurrences) per experiment
PATCHES = {
    # exp 7: nonstandard output cluster (italic ink text, arrow between
    # crosshair and text) — uniform dx=+157 keeps its internal layout.
    7: [
        ("x2='650' y2='118'", "x2='807' y2='118'", 2),   # converge lines
        ("x2='650' y2='122'", "x2='807' y2='122'", 2),
        ("<line x1='523' y1='112' x2='650' y2='120'", "<line x1='523' y1='112' x2='807' y2='120'", 1),
        ("<circle cx='655' cy='120' r='3'", "<circle cx='812' cy='120' r='3'", 1),
        ("<line x1='648' y1='120' x2='662' y2='120'", "<line x1='805' y1='120' x2='819' y2='120'", 1),
        ("<line x1='655' y1='113' x2='655' y2='127'", "<line x1='812' y1='113' x2='812' y2='127'", 1),
        ("<text x='655' y='172'", "<text x='740' y='172'", 1),   # soft-argmax caption
        ("<text x='655' y='184'", "<text x='740' y='184'", 1),   # (740 not 812: clears the output captions)
        ("<line x1='665' y1='120' x2='702' y2='120'", "<line x1='822' y1='120' x2='842' y2='120'", 1),
        ("<text x='712' y='124' font-size='13' font-style='italic' fill='#111111'>(u, v, conf)</text>",
         "<text x='848' y='124' font-size='13' font-style='italic' fill='#111111'>(lat, lon, confidence)</text>", 1),
        ("<text x='748' y='172'", "<text x='905' y='172'", 1),   # position + confidence
        ("<text x='748' y='184'", "<text x='905' y='184'", 1),
        ("L722 45 L732 112", "L879 45 L889 112", 1),             # confidence elbow
    ],
    # exps 8-10: reference-style output_part/crosspt/converge — move the
    # cluster to the shared anchor; re-center the decode caption between the
    # field grid and the new crosshair; stretch the confidence elbow.
    8: [
        ("x2='662' y2='112'", "x2='812' y2='112'", 32),          # converge + crosspt h-line
        ("x1='655' y1='112'", "x1='805' y1='112'", 1),
        ("x2='669' y2='112'", "x2='819' y2='112'", 1),
        ("<line x1='662' y1='105' x2='662' y2='119'", "<line x1='812' y1='105' x2='812' y2='119'", 1),
        ("cx='662' cy='112'", "cx='812' cy='112'", 2),
        ("<text x='618' y='58'", "<text x='693' y='58'", 1),
        ("<text x='618' y='70'", "<text x='693' y='70'", 1),
        ("<text x='680' y='94'", "<text x='828' y='94'", 1),
        ("<text x='680' y='110'", "<text x='828' y='110'", 1),
        ("<text x='680' y='124'", "<text x='828' y='124'", 1),
        ("H 708 V 138", "H 858 V 138", 1),
        ("M 708,132 l -3,6 h 6 Z", "M 858,132 l -3,6 h 6 Z", 1),
        ("<text x='544' y='224'", "<text x='628' y='224'", 1),   # may abstain
        (">(u, v, conf)</text>", ">(lat, lon, confidence)</text>", 1),
    ],
    9: [
        ("x2='652' y2='112'", "x2='812' y2='112'", 32),
        ("x1='645' y1='112'", "x1='805' y1='112'", 1),
        ("x2='659' y2='112'", "x2='819' y2='112'", 1),
        ("<line x1='652' y1='105' x2='652' y2='119'", "<line x1='812' y1='105' x2='812' y2='119'", 1),
        ("cx='652' cy='112'", "cx='812' cy='112'", 2),
        ("<text x='608' y='58'", "<text x='688' y='58'", 1),
        ("<text x='608' y='70'", "<text x='688' y='70'", 1),
        ("<text x='670' y='94'", "<text x='828' y='94'", 1),
        ("<text x='670' y='110'", "<text x='828' y='110'", 1),
        ("<text x='670' y='124'", "<text x='828' y='124'", 1),
        ("H 698 V 138", "H 858 V 138", 1),
        ("M 698,132 l -3,6 h 6 Z", "M 858,132 l -3,6 h 6 Z", 1),
        ("<text x='534' y='224'", "<text x='618' y='224'", 1),
        (">(u, v, conf)</text>", ">(lat, lon, confidence)</text>", 1),
    ],
    10: [
        ("x2='682' y2='112'", "x2='812' y2='112'", 32),
        ("x1='675' y1='112'", "x1='805' y1='112'", 1),
        ("x2='689' y2='112'", "x2='819' y2='112'", 1),
        ("<line x1='682' y1='105' x2='682' y2='119'", "<line x1='812' y1='105' x2='812' y2='119'", 1),
        ("cx='682' cy='112'", "cx='812' cy='112'", 2),
        ("<text x='638' y='58'", "<text x='703' y='58'", 1),
        ("<text x='638' y='70'", "<text x='703' y='70'", 1),
        ("<text x='700' y='94'", "<text x='828' y='94'", 1),
        ("<text x='700' y='110'", "<text x='828' y='110'", 1),
        ("<text x='700' y='124'", "<text x='828' y='124'", 1),
        ("H 728 V 138", "H 858 V 138", 1),
        ("M 728,132 l -3,6 h 6 Z", "M 858,132 l -3,6 h 6 Z", 1),
        ("<text x='564' y='234'", "<text x='637' y='234'", 1),
        (">(u, v, conf)</text>", ">(lat, lon, confidence)</text>", 1),
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
        print(f"exp {exp_id}: output cluster anchored at 812/828")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
