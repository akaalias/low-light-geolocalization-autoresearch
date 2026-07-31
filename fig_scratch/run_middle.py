#!/usr/bin/env python3
"""Improved middle-agent runner. Same split as the prototype (deterministic
chrome + agent-drawn middle) but the agent now composes the middle from the
gold-standard primitive toolkit (fig_scratch/midprims.py) and must pass the
stricter fig_scratch/midcheck.py. Renders fig_scratch/quality_v2.html:
per experiment ORIGINAL (arch_svg) vs NEW composite.

Read-only on the DB. All output in fig_scratch/.
  usage: .venv/bin/python fig_scratch/run_middle.py 4 2
"""
import html
import json
import subprocess
import sqlite3
import sys
from pathlib import Path

REPO = Path("/Users/alexisrondeau/Workshop/low-light-geolocalization-autoresearch")
SCRATCH = REPO / "fig_scratch"
SCRATCH.mkdir(exist_ok=True)
INK, MUT, FAINT, ACC, OCH = "#111111", "#6b6a60", "#9b998c", "#8c2f1f", "#8a6a1e"
FONT = "Palatino,Georgia,serif"
IC = 112
TX = 812
HEIGHT = 420


def txt(x, y, s, size=10, color=MUT, w=400, anchor="middle", style="", tid=None):
    tid_attr = f"id='{tid}' " if tid else ""
    return (f"<text {tid_attr}x='{x:.0f}' y='{y:.0f}' font-family='{FONT}' font-size='{size}' "
            f"fill='{color}' font-weight='{w}' text-anchor='{anchor}' {style}>{html.escape(str(s))}</text>")


def terrain_frame(y):
    b = (f"<rect id='frozen-input' x='26' y='{y}' width='76' height='76' fill='#f6f4ea' stroke='#9b998c' stroke-width='1.6'/>"
         f"<path d='M31 {y+47} L97 {y+27}' stroke='#e6e3d4' stroke-width='5' fill='none'/>"
         f"<path d='M59 {y+6} L49 {y+70}' stroke='#e6e3d4' stroke-width='3.5' fill='none'/>"
         f"<rect x='34' y='{y+9}' width='12' height='8' fill='#d9d5c3'/>"
         f"<rect x='78' y='{y+8}' width='10' height='11' fill='#cfccbd'/>"
         f"<rect x='35' y='{y+57}' width='13' height='8' fill='#d9d5c3'/>"
         f"<rect x='75' y='{y+50}' width='10' height='9' fill='#cfccbd'/>"
         f"<rect x='54' y='{y+31}' width='9' height='8' fill='#d9d5c3' opacity='.85'/>"
         f"<ellipse cx='86' cy='{y+63}' rx='8' ry='6' fill='#8a6a1e' opacity='.12'/>")
    for (cx, cy) in ((40, 28), (70, 14), (92, 36), (52, 52), (82, 70), (31, 44)):
        b += f"<circle cx='{cx}' cy='{y+cy}' r='.7' fill='#6b6a60' opacity='.5'/>"
    return f"<g id='cam-terrain'>{b}</g>"


def chrome(height):
    return "".join([
        txt(8, 26, "INFERENCE PATH — WHAT FLIES", 9, FAINT, 600, "start", "letter-spacing='1.8'"),
        txt(8, height - 34, "TRAINING SIGNAL — NEVER FLY", 9, OCH, 600, "start", "letter-spacing='1.8'"),
        terrain_frame(IC - 38),
        txt(64, IC - 44, "128²×3", 9, FAINT),
        txt(64, IC + 50, "camera frame", 10.5, MUT, 600),
        txt(64, IC + 62, "one night exposure", 9.5, FAINT),
        txt(64, IC + 74, "frozen contract", 8.5, FAINT, style="font-style='italic'"),
        txt(828, IC - 18, "frozen contract", 8.5, FAINT, anchor="start", style="font-style='italic'"),
        txt(828, IC - 2, "(lat, lon, confidence)", 13, MUT, 600, "start", tid="frozen-output"),
        txt(828, IC + 12, "position fix + confidence", 9, FAINT, anchor="start"),
        # input arrow: camera frame -> first middle stage (part of the template)
        f"<line x1='108' y1='{IC}' x2='127' y2='{IC}' stroke='{FAINT}' stroke-width='1'/>",
        f"<path d='M 132,{IC} l -6,-3 v 6 Z' fill='{FAINT}'/>",
    ])


def composite(middle_body, height=HEIGHT):
    return (f"<svg viewBox='0 0 980 {height}' xmlns='http://www.w3.org/2000/svg' role='img'>"
            f"{chrome(height)}{middle_body}</svg>")


PROMPT = r"""# Draw the design-specific MIDDLE of one architecture figure — to gallery quality

You draw ONLY the middle of a technical ML architecture diagram. The FROZEN
CHROME (camera-frame glyph at left, the "(lat, lon, confidence)" output block at
right, and the two lane labels) is composited in for you — you must NOT draw any
of it. Draw only what's BETWEEN the fixed input and output.

## Non-negotiable: build with the primitive toolkit, do not hand-author SVG
`fig_scratch/midprims.py` is the EXACT hand-drawn visual language of the
gold-standard figures (slab, encoder, gridsq, bar, fan, cell_centers,
converge_pts, crosspt, gauge, conf_branch, kernel_proj, harrow, leader, lroute,
cap, shape, loss_note). Your job is to write a short Python script that imports
it, calls these primitives with positions/colours/captions chosen FROM THE
DESIGN, assembles the list of fragments, and calls `midprims.emit(out_path,
parts)`. Read `fig_scratch/midprims.py` first — the module docstring and each
function's docstring give the anchors and the routing rules. Do NOT hand-write
raw <line>/<path>/<polygon>/<rect> for anything a primitive already draws; you
may only add tiny design-specific marks (a `<circle>` dot at a real cell centre,
a short tick) in the SAME colours, and even then prefer a primitive.

## Fixed anchors (already drawn — converge to these EXACTLY)
- Inference lane centre is y=112. Keep the main left→right flow on this line.
- Begin the middle near x=132 (the camera frame ends at x=102; `encoder()`
  defaults to x0=132).
- The output crosshair is at x=812, y=112. Your decode/aggregation MUST land
  there — use `converge_pts(points, colour)` (a fan from REAL source cells) or a
  single straight `harrow(...,812)`. Never draw past x=820. Never route the flow
  to the output as a zig-zag, a U-turn, or a bezier curve.

## Routing rules that separate polished from sloppy (follow all)
- Lay stages on a left-to-right x-cursor with GENEROUS column spacing; tie
  consecutive conv layers with `kernel_proj` (or just call `encoder()`), never
  bare boxes in a row.
- Decode/vote lines must ORIGINATE at real cell centres — get them from
  `cell_centers(...)` and feed `converge_pts`. Never draw vote lines from thin air.
- Keep feature grids/fields ≤ ~96 px tall (`gridsq(x, s<=96, n)`). An oversized
  grid pushes its top cells up into the y≈55-68 caption band, and the converge
  fan then crosses the decode caption. Put the decode caption ABOVE the fan
  (y≈IC-56) and to the RIGHT (x past the grid), where fan lines have already
  dropped near the lane — never directly over the widest part of the fan.
- Confidence is a BRANCH BELOW the lane: call `conf_branch(anchor_x)` where
  anchor_x is an EMPTY column. Never put the gauge inline on the main flow and
  never route it with a curved path.
- Captions sit STRICTLY under their element via `cap(xc, y, name, sub)`. Stagger
  the caption row-y between adjacent columns (e.g. IC+48 vs IC+72) so they never
  collide. Tensor-shape annotations use `shape(x, y, "8²×128")` placed ABOVE the
  flow (y≈IC-34), never on top of a caption or another shape.
- ALL training-side detail (losses, targets, samplers) goes in the low training
  row via `loss_note(...)` around y≈300, with dashed leaders (use `lroute` for an
  L-shaped route through empty space if a straight leader would cross a label).
- Colour discipline: ink #111111 for structure, captions #6b6a60, arrows/leaders
  #9b998c, training-only #8a6a1e, and **#8c2f1f (red) ONLY on what THIS
  experiment changed** (architecture.stages[].changed == true). An unchanged
  stage is never red.

## Readability (hard — midcheck enforces geometrically)
No text may overlap other text. No line/leader may cross a text label (it may
END at one, never pass through). Everything stays within x[110,820], y[40,412].
Draw the real mechanism RICHLY and design-specific — do not reduce it to a
generic skeleton.

## Workflow
1. Read the design from: {design_path}
2. Read `fig_scratch/midprims.py`.
3. Write a builder script `fig_scratch/build_{eid}.py` that imports midprims and
   emits to {out_path}. Run it: `.venv/bin/python fig_scratch/build_{eid}.py`.
4. Validate: `.venv/bin/python fig_scratch/midcheck.py {out_path}`. If it prints
   anything but PASS, fix your builder (move captions, pick emptier branch
   columns, converge cleanly) and re-run until it prints `midcheck PASS`.
5. The output file {out_path} must contain exactly:
   {{"middle_svg": "<g>…all your elements…</g>"}}  (emit() writes this for you).
Do not stop until midcheck prints PASS.
"""


def run_agent(eid, design_path, out_path):
    prompt = PROMPT.replace("{design_path}", str(design_path)) \
                   .replace("{out_path}", str(out_path)) \
                   .replace("{eid}", str(eid))
    p = subprocess.run(
        ["claude", "-p", prompt,
         "--model", "claude-sonnet-5", "--permission-mode", "acceptEdits",
         "--max-turns", "50", "--allowedTools", "Read,Write,Grep,Glob,Bash(.venv/bin/python:*)",
         "--output-format", "json"],
        cwd=str(REPO), capture_output=True, text=True)
    (SCRATCH / f"agentlog_{eid}.json").write_text(
        (p.stdout or "") + ("\n--STDERR--\n" + p.stderr if p.stderr else ""))
    try:
        d = json.loads(p.stdout)
        print(f"    agent: is_error={d.get('is_error')} turns={d.get('num_turns')} "
              f"cost=${(d.get('total_cost_usd') or 0):.2f} result={str(d.get('result'))[:160]!r}", flush=True)
    except Exception:
        print(f"    agent: (unparseable rc={p.returncode}) {(p.stdout or p.stderr or '')[:200]!r}", flush=True)
    return p.returncode


def main(ids):
    con = sqlite3.connect("file:experiments.sqlite?mode=ro", uri=True)
    results = []
    for eid in ids:
        r = con.execute("SELECT id,title,hypothesis,method,arch_json,arch_svg FROM experiments WHERE id=?", (eid,)).fetchone()
        if not r:
            print(f"[{eid}] not found")
            continue
        design = {"title": r[1], "hypothesis": r[2], "method": r[3],
                  "architecture": json.loads(r[4] or "{}")}
        dpath = SCRATCH / f"design_{eid}.json"
        opath = SCRATCH / f"middle_v2_{eid}.json"
        dpath.write_text(json.dumps(design, indent=2))
        opath.unlink(missing_ok=True)
        print(f"[{eid}] drawing middle: {r[1][:56]}", flush=True)
        run_agent(eid, dpath, opath)
        mid = None
        if opath.exists():
            try:
                mid = (json.loads(opath.read_text()).get("middle_svg") or "").strip()
            except Exception:
                mid = None
        # run midcheck for the record
        chk = "n/a"
        if mid:
            cp = subprocess.run([".venv/bin/python", "fig_scratch/midcheck.py", str(opath)],
                                cwd=str(REPO), capture_output=True, text=True)
            chk = "PASS" if cp.returncode == 0 else cp.stdout.strip()
        new_svg = composite(mid) if mid and mid.startswith("<g") else None
        print(f"[{eid}] {'OK ' + str(len(mid)) + ' bytes, midcheck=' + chk.splitlines()[0] if mid else 'NO MIDDLE PRODUCED'}", flush=True)
        results.append((r[0], r[1], r[5], new_svg, chk))
    con.close()

    cards = []
    for (eid, title, orig, new, chk) in results:
        orig_html = (f"<div style='border:1px solid #eee;background:#fff'>{orig}</div>"
                     if (orig or '').lstrip().startswith('<svg') else "<i>(no original)</i>")
        new_html = (f"<div style='border:1px solid #d8e8d8;background:#fff'>{new}</div>"
                    if new else "<i style='color:#a00'>(agent produced no middle)</i>")
        badge = ("PASS" if chk == "PASS" else "midcheck issues")
        cards.append(
            f"<figure style='margin:0 0 34px'>"
            f"<figcaption style='font:600 13px {FONT};color:#222;padding:16px 0 6px'>Fig. {eid} — {html.escape(title or '')}</figcaption>"
            f"<div style='font:600 10px {FONT};color:#8c2f1f;padding:6px 0 2px;letter-spacing:.08em'>ORIGINAL · HAND-DRAWN (gold standard)</div>{orig_html}"
            f"<div style='font:600 10px {FONT};color:#2a6;padding:12px 0 2px;letter-spacing:.08em'>NEW · CHROME + AGENT MIDDLE (via primitives) · {badge}</div>{new_html}"
            f"</figure>")
    out = (f"<!doctype html><meta charset='utf-8'><title>middle quality v2</title>"
           f"<body style='max-width:1060px;margin:0 auto;padding:24px;background:#faf8f0;font-family:{FONT}'>"
           f"<h1 style='font-weight:500'>Quality v2 — primitive-driven agent middle vs hand-drawn original</h1>"
           f"<p style='color:#666'>Chrome is composited by code. The middle is built by the agent from the "
           f"gold-standard primitive toolkit (midprims.py) and validated by midcheck.py.</p>"
           + "".join(cards) + "</body>")
    (SCRATCH / "quality_v2.html").write_text(out)
    print("wrote fig_scratch/quality_v2.html")


if __name__ == "__main__":
    main([int(x) for x in sys.argv[1:]] or [4, 2])
