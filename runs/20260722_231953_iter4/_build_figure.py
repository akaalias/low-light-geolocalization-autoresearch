"""One-off builder for exp iter4's architecture figure. Not part of the
frozen pipeline; deleted after use."""
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "archive"))

from archive.arch_svg_reference import (  # noqa: E402
    INK, MUT, FAINT, ACC, OCH, FONT, IC, LOSS_Y,
    txt, cap, harrow, leader, slab, imgsq, bar, fan, gridsq, BUMP,
    crosspt, converge, gauge, svgwrap, kernel_proj, frame_part,
    output_part, loss_note,
)

H = 420
LOSS_Y2 = H - 28  # training lane baseline for this taller figure

b = []
b.append(txt(8, 26, "INFERENCE PATH — WHAT FLIES", 9, FAINT, 600, "start",
             "letter-spacing='1.8'"))
b.append(txt(8, LOSS_Y2 - 96, "TRAINING SIGNALS — NEVER FLY", 9, OCH, 600, "start",
             "letter-spacing='1.8'"))

# ---- camera frame -----------------------------------------------------
g, x = frame_part()
b.append(g)
raw_input_x = 26  # anchor for the residual leader later
b.append(harrow(x + 6, x + 28, IC))
x += 30

# ---- rotation fan (unchanged mechanism, now feeds translator first) ---
rot_cx = x + 32
for i, ang in enumerate((0, 90, 180, 270)):
    s = 22
    b.append(f"<rect x='{rot_cx - s/2:.1f}' y='{IC - s/2:.1f}' width='{s}' height='{s}' "
              f"fill='none' stroke='{ACC}' stroke-width='1.1' opacity='{0.35 + i*0.18:.2f}' "
              f"transform='rotate({ang} {rot_cx:.1f} {IC})'/>")
r = 18
b.append(f"<path d='M {rot_cx - r},{IC - 34} A {r} {r} 0 0 1 {rot_cx + r},{IC - 34}' "
          f"fill='none' stroke='{ACC}' stroke-width='1.1'/>")
b.append(f"<path d='M {rot_cx + r},{IC - 28} l -3,-6 h 6 Z' fill='{ACC}'/>")
b.append(cap(rot_cx, IC + 46, "rotation fan", "4× C4 views, each through translator+trunk",
             name_color=ACC))
x = rot_cx + 32
b.append(harrow(x, x + 22, IC))
x += 24

# ---- delighting translator: shrink, bottleneck, grow-to-image ---------
t0 = x
g, w = slab(x, 30, 6, ACC)
b.append(g)
enc1 = (x, 30)
x += w + 13
g, w = slab(x, 19, 8, ACC)
b.append(g)
bott = (x, 19)
b.append(kernel_proj(enc1[0], enc1[1], bott[0], bott[1], ACC))
x += w + 13
g, w = slab(x, 30, 6, ACC)
b.append(g)
dec1 = (x, 30)
b.append(kernel_proj(bott[0], bott[1], dec1[0], dec1[1], ACC))
x += w + 16
canon_x = x
g, cw = imgsq(x, 50, ACC, tid="canon-out")
b.append(g)
b.append(kernel_proj(dec1[0], dec1[1], canon_x, 50, ACC))
# residual add: raw pixels loop over the top, "+" glyph, clamp note
resid_y = IC - 70
b.append(f"<path d='M {raw_input_x + 38},{IC - 38} L {raw_input_x + 38},{resid_y} "
          f"L {canon_x + 12},{resid_y} L {canon_x + 12},{IC - 25}' fill='none' "
          f"stroke='{ACC}' stroke-width='1' stroke-dasharray='2 3'/>")
b.append(f"<path d='M {canon_x + 12},{IC - 25} l -3,-6 h 6 Z' fill='{ACC}'/>")
b.append(f"<circle cx='{canon_x - 6:.1f}' cy='{resid_y:.1f}' r='6' fill='none' stroke='{ACC}' stroke-width='1'/>")
b.append(f"<line x1='{canon_x - 10:.1f}' y1='{resid_y:.1f}' x2='{canon_x - 2:.1f}' y2='{resid_y:.1f}' stroke='{ACC}' stroke-width='1'/>")
b.append(f"<line x1='{canon_x - 6:.1f}' y1='{resid_y - 4:.1f}' x2='{canon_x - 6:.1f}' y2='{resid_y + 4:.1f}' stroke='{ACC}' stroke-width='1'/>")
b.append(txt(canon_x - 6, resid_y - 10, "+ raw pixels, clamp[0,1]", 8.5, ACC, 400, "middle",
             style="font-style='italic'"))
xc_t = (t0 + canon_x) / 2
b.append(cap(xc_t, IC + 58, "delighting translator", "NEW · 2 down + bottleneck + 2 up, from scratch",
             name_color=ACC))
b.append(txt(xc_t, IC + 70, "predicts a correction, not a full repaint", 8.5, ACC,
             style="font-style='italic'"))
b.append(txt(t0 + 15, IC - 30, "128²×3", 8.5, FAINT))
x = canon_x + cw
b.append(cap(x - 25, IC - 42, "canonicalized crop", "128²×3, flies every frame", name_color=ACC))
b.append(harrow(x + 6, x + 26, IC))
x += 28

# ---- from-scratch feature extractor (replaces pretrained trunk) -------
enc_x0 = x
sizes = [(40, 6), (30, 9), (21, 12), (15, 16)]
faces = []
for i, (s, d) in enumerate(sizes):
    g, w = slab(x, s, d, ACC)
    b.append(g)
    faces.append((x, s))
    x += w + 12
x -= 12
b.append(kernel_proj(canon_x, 50, faces[0][0], faces[0][1], ACC))
for (x1, s1), (x2, s2) in zip(faces, faces[1:]):
    b.append(kernel_proj(x1, s1, x2, s2, ACC))
b.append(cap((enc_x0 + x) / 2, IC + 58, "feature extractor", "from-scratch 4-stage conv · 32→64→96→64",
             name_color=ACC))
b.append(txt(enc_x0 + 20, IC - 32, "64²×32", 8.5, FAINT))
b.append(txt(x - 16, IC - 28, "8²×64", 8.5, FAINT))
b.append(harrow(x + 8, x + 26, IC))
x += 28

# ---- layout summary vector ---------------------------------------------
bar_x = x
g, bw = bar(x, 58, ACC, ticks=10)
b.append(g)
b.append(cap(x + 3, IC + 44, "layout summary", "spatial code + texture avg", name_color=ACC))
x += bw + 10

# ---- FC fan into unified field (gate removed) --------------------------
fan_x2 = x + 58
g, fw = bar(fan_x2, 78, ACC, ticks=12)
b.append(fan(x, 58, fan_x2, 78, ACC))
b.append(g)
b.append(cap(fan_x2 + 3, IC + 54, "FC → unified logits", "single scorer, gate deleted",
             name_color=ACC))
x = fan_x2 + fw + 22
b.append(harrow(x - 14, x + 4, IC))

# ---- probability field + decode -----------------------------------------
field_x = x + 6
g, gs = gridsq(field_x, 66, 8, ACC, BUMP)
b.append(g)
b.append(cap(field_x + gs / 2, IC + 52, "probability field", "unified field, no day/night blend",
             name_color=ACC))
tx = 812
b.append(converge(field_x, 66, tx, ACC, cells="all"))
b.append(cap((field_x + gs + tx) / 2 + 4, IC - 48, "soft-argmax decode",
             "same sharpened decode, reads one field"))
b.append(output_part(828))
b.append(conf_branch := "")  # placeholder removed below

# confidence branch off the field (own mechanism, unchanged, new descriptor)
cbx = field_x + gs / 2
b.append(leader(cbx, IC + 62, cbx, IC + 96, FAINT))
b.append(gauge(cbx, IC + 112, MUT))
b.append(txt(cbx, IC + 130, "confidence 0–1", 9, MUT))
b.append(txt(cbx, IC + 142, "same mechanism, new descriptor", 8.5, FAINT, style="font-style='italic'"))
ex = tx + 30
b.append(f"<path d='M {cbx + 16},{IC + 112} H {ex} V {IC + 26}' fill='none' stroke='{FAINT}' stroke-width='0.8'/>")
b.append(f"<path d='M {ex},{IC + 20} l -3,6 h 6 Z' fill='{FAINT}'/>")

# ==== training-only lane =================================================
ty = LOSS_Y2
# reference.tif twin sampler glyph (small pictorial image tile)
samp_x = 60
g, sw = imgsq(samp_x, 40, OCH)
b.append(g)
b.append(cap(samp_x + 20, ty - 58, "reference.tif twin", "same cx, cy, angle — free from the frozen sim",
             color=OCH, name_color=OCH))
b.append(leader(canon_x - 6, resid_y - 12, samp_x + 20, ty - 78, OCH))

# translator L1 loss note, leader from the canonicalized-crop stage
b.append(leader(canon_x + 20, IC + 45, 230, ty - 34, ACC))
b.append(txt(230, ty - 26, "L1(translator output, clean reference crop) × 1.0", 10, ACC, 600, "start"))
b.append(txt(230, ty - 13, "active every step from step one — not a pretrain phase", 9.5, ACC, 400, "start"))

# unchanged CE + coord L2 + conf BCE, now grading the new descriptor
tiny, _ = gridsq(586, 20, 6, OCH, ((3, 2, .6),), yc=ty - 30, lw=1)
b.append(tiny)
b.append(txt(614, ty - 26, "CE + coord L2 + conf BCE (unchanged formula)", 10, OCH, 600, "start"))
b.append(txt(614, ty - 13, "now grades the translator+from-scratch descriptor, not pretrained features",
             9.5, OCH, 400, "start"))

# single shared LR note
b.append(leader(enc_x0 + 60, IC + 66, enc_x0 + 60, ty + 14, ACC))
b.append(txt(enc_x0 + 60, ty + 24, "single LR (1e-3), all params", 10, ACC, 600, "middle"))
b.append(txt(enc_x0 + 60, ty + 37, "no 10× trunk/head split — nothing pretrained to protect",
             9.5, ACC, 400, "middle"))

svg = svgwrap(H, "".join(x for x in b if x))
out_path = Path(__file__).resolve().parent / "figure.json"
out_path.write_text(json.dumps({"architecture_svg": svg}))
print(f"wrote {out_path} ({len(svg)} bytes), field_x={field_x}, tx={tx}, x_end={x}")
