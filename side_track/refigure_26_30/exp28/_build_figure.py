"""Build exp28's architecture figure.

Exp 28 is a verbatim re-registration of exp 27's pre-registered design
(design.json architecture.stages are byte-identical); iter 7 died on a
full disk before training. So the figure is exp 27's accepted,
figcheck-PASSing figure plus a faint margin note marking the rerun.
"""
import json
from pathlib import Path

here = Path(__file__).resolve().parent
svg = json.loads((here.parent / "exp27" / "figure.json").read_text())["architecture_svg"]

note = (
    "<text x='968' y='24' font-family='Palatino,Georgia,serif' font-size='9.5' "
    "fill='#9b998c' font-weight='400' text-anchor='end' font-style='italic'>"
    "verbatim rerun of exp 27&#8217;s pre-registered design</text>"
    "<text x='968' y='36' font-family='Palatino,Georgia,serif' font-size='9' "
    "fill='#9b998c' font-weight='400' text-anchor='end' font-style='italic'>"
    "iter 7 died on a full disk before training — no design delta</text>"
)
assert svg.endswith("</svg>")
svg = svg[: -len("</svg>")] + note + "</svg>"
(here / "figure.json").write_text(json.dumps({"architecture_svg": svg}))
print("written", len(svg), "bytes")
