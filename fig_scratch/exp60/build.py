import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "archive"))
from terrain_frame_glyph import terrain_frame

INK, MUT, FAINT, ACC, OCH = "#111111", "#6b6a60", "#9b998c", "#8c2f1f", "#8a6a1e"
FONT = "Palatino,Georgia,serif"
IC = 122          # inference lane center y


def txt(x, y, s, size=10, color=MUT, w=400, anchor="middle", style="", tid=None):
    tid_attr = f"id='{tid}' " if tid else ""
    return (f"<text {tid_attr}x='{x:.0f}' y='{y:.0f}' font-family='{FONT}' font-size='{size}' "
            f"fill='{color}' font-weight='{w}' text-anchor='{anchor}' {style}>{s}</text>")


def cap(xc, y, name, sub=None, color=MUT, name_color=None):
    out = [txt(xc, y, name, 10.5, name_color or (INK if color == MUT else color), 600)]
    if sub:
        out.append(txt(xc, y + 12, sub, 9.5, color))
    return "".join(out)


def harrow(x1, x2, y, label=None, color=FAINT):
    out = [f"<line x1='{x1}' y1='{y}' x2='{x2 - 5}' y2='{y}' stroke='{color}' stroke-width='1'/>",
           f"<path d='M {x2},{y} l -6,-3 v 6 Z' fill='{color}'/>"]
    if label:
        out.append(txt((x1 + x2) / 2, y - 6, label, 9, FAINT, style="font-style='italic'"))
    return "".join(out)


def leader(x1, y1, x2, y2, color):
    return (f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='{color}' "
            f"stroke-width='1' stroke-dasharray='2 4'/>")


def lroute(x1, y1, x2, y2, color):
    """Orthogonal L-route dashed leader (vertical then horizontal)."""
    return (f"<path d='M {x1},{y1} V {y2} H {x2}' fill='none' stroke='{color}' "
            f"stroke-width='1' stroke-dasharray='2 4'/>")


def rroute(x1, y1, x2, y2, color):
    """Orthogonal L-route dashed leader (horizontal then vertical)."""
    return (f"<path d='M {x1},{y1} H {x2} V {y2}' fill='none' stroke='{color}' "
            f"stroke-width='1' stroke-dasharray='2 4'/>")


def tw(s, fs):
    """Approximate text width, matching figcheck's own measurement formula."""
    return len(s) * fs * 0.52


def slab(x, s, d, color=INK, yc=None):
    yc = IC if yc is None else yc
    y = yc - s / 2
    dx, dy = d, d * 0.55
    out = [
        f"<polygon points='{x},{y} {x+dx},{y-dy} {x+dx+s},{y-dy} {x+s},{y}' "
        f"fill='#00000010' stroke='{color}' stroke-width='1'/>",
        f"<polygon points='{x+s},{y} {x+dx+s},{y-dy} {x+dx+s},{y-dy+s} {x+s},{y+s}' "
        f"fill='#0000001c' stroke='{color}' stroke-width='1'/>",
        f"<rect x='{x}' y='{y}' width='{s}' height='{s}' fill='#00000006' "
        f"stroke='{color}' stroke-width='1.2'/>",
    ]
    return "".join(out), s + dx


def bar(x, h, color=INK, ticks=9, yc=None):
    yc = IC if yc is None else yc
    y = yc - h / 2
    out = [f"<rect x='{x}' y='{y}' width='7' height='{h}' fill='none' "
           f"stroke='{color}' stroke-width='1.2'/>"]
    for i in range(1, ticks):
        out.append(f"<line x1='{x}' y1='{y + i * h / ticks:.1f}' x2='{x + 7}' "
                   f"y2='{y + i * h / ticks:.1f}' stroke='{color}' stroke-width='0.5' opacity='0.5'/>")
    return "".join(out), 7


def fan(x1, h1, x2, h2, color=FAINT, n=5, yc=None):
    yc = IC if yc is None else yc
    out = []
    for i in range(n):
        ya = yc - h1 / 2 + (i + 0.5) * h1 / n
        for j in range(n):
            yb = yc - h2 / 2 + (j + 0.5) * h2 / n
            out.append(f"<line x1='{x1}' y1='{ya:.1f}' x2='{x2}' y2='{yb:.1f}' "
                       f"stroke='{color}' stroke-width='0.5' opacity='0.45'/>")
    return "".join(out)


def gridsq(x, s, n, color=INK, bumps=(), yc=None, lw=1.2):
    yc = IC if yc is None else yc
    y = yc - s / 2
    out = [f"<rect x='{x}' y='{y}' width='{s}' height='{s}' fill='none' "
           f"stroke='{color}' stroke-width='{lw}'/>"]
    for i in range(1, n):
        out.append(f"<line x1='{x + i * s / n:.1f}' y1='{y}' x2='{x + i * s / n:.1f}' "
                   f"y2='{y + s}' stroke='{color}' stroke-width='0.45' opacity='0.5'/>")
        out.append(f"<line x1='{x}' y1='{y + i * s / n:.1f}' x2='{x + s}' "
                   f"y2='{y + i * s / n:.1f}' stroke='{color}' stroke-width='0.45' opacity='0.5'/>")
    for (gx, gy, o) in bumps:
        out.append(f"<rect x='{x + gx * s / n:.1f}' y='{y + gy * s / n:.1f}' "
                   f"width='{s / n:.1f}' height='{s / n:.1f}' fill='{color}' fill-opacity='{o}'/>")
    return "".join(out), s


BUMP = ((5, 2, .55), (4, 2, .28), (5, 1, .28), (6, 2, .18), (5, 3, .18), (2, 5, .12), (1, 6, .1))


def crosspt(x, y, color, r=7):
    return (f"<line x1='{x - r}' y1='{y}' x2='{x + r}' y2='{y}' stroke='{color}' stroke-width='1.4'/>"
            f"<line x1='{x}' y1='{y - r}' x2='{x}' y2='{y + r}' stroke='{color}' stroke-width='1.4'/>"
            f"<circle cx='{x}' cy='{y}' r='{r * 0.55:.1f}' fill='none' stroke='{color}' stroke-width='1.4'/>"
            f"<circle cx='{x}' cy='{y}' r='1.5' fill='{color}'/>")


def converge(gx, gs, tx, color, cells="all", n=8, yc=None):
    yc = IC if yc is None else yc
    out = []
    src = []
    y0 = yc - gs / 2
    xs = ys = range(n)
    for gyy in ys:
        for gxx in xs:
            if (gxx + gyy) % 2:
                continue
            src.append((gx + (gxx + 0.5) * gs / n, y0 + (gyy + 0.5) * gs / n))
    for (sx, sy) in src:
        out.append(f"<line x1='{sx:.0f}' y1='{sy:.0f}' x2='{tx}' y2='{yc}' "
                   f"stroke='{color}' stroke-width='0.55' opacity='0.4'/>")
    out.append(crosspt(tx, yc, color))
    return "".join(out)


def gauge(x, yc, color=MUT, r=14):
    a = math.radians(55)
    return (f"<path d='M {x - r},{yc} A {r} {r} 0 0 1 {x + r},{yc}' fill='none' "
            f"stroke='{color}' stroke-width='1.2'/>"
            f"<line x1='{x}' y1='{yc}' x2='{x + (r - 3) * math.cos(a):.1f}' "
            f"y2='{yc - (r - 3) * math.sin(a):.1f}' stroke='{color}' stroke-width='1.4'/>"
            f"<circle cx='{x}' cy='{yc}' r='1.6' fill='{color}'/>")


def svgwrap(h, body):
    return (f"<svg viewBox='0 0 980 {h}' xmlns='http://www.w3.org/2000/svg' role='img'>"
            f"{body}</svg>")


def kernel_proj(x1, s1, x2, s2, color, yc=None):
    yc = IC if yc is None else yc
    k = max(5, s1 * 0.30)
    kx, ky = x1 + s1 * 0.60, yc - s1 / 2 + s1 * 0.18
    c = max(3, s2 * 0.14)
    cx, cy = x2 + s2 * 0.22, yc - s2 / 2 + s2 * 0.26
    out = [f"<rect x='{kx:.1f}' y='{ky:.1f}' width='{k:.1f}' height='{k:.1f}' "
           f"fill='none' stroke='{color}' stroke-width='0.9'/>",
           f"<rect x='{cx:.1f}' y='{cy:.1f}' width='{c:.1f}' height='{c:.1f}' "
           f"fill='{color}' fill-opacity='0.5' stroke='none'/>"]
    for (px, py) in ((kx, ky), (kx + k, ky), (kx, ky + k), (kx + k, ky + k)):
        out.append(f"<line x1='{px:.1f}' y1='{py:.1f}' x2='{cx + c / 2:.1f}' "
                   f"y2='{cy + c / 2:.1f}' stroke='{color}' stroke-width='0.55' "
                   f"opacity='0.45'/>")
    return "".join(out)


def conv_group(x0, colors, cap_name, cap_sub, prev=None):
    sizes = [(40, 6), (30, 9), (22, 12), (16, 17)]
    out, x, faces = [], x0, []
    for i, (s, d) in enumerate(sizes):
        g, w = slab(x, s, d, colors[i])
        out.append(g)
        faces.append((x, s))
        x += w + 13
    x -= 13
    if prev:
        out.append(kernel_proj(prev[0], prev[1], faces[0][0], faces[0][1], prev[2]))
    for (x1, s1), (x2, s2) in zip(faces, faces[1:]):
        out.append(kernel_proj(x1, s1, x2, s2, MUT))
    xc = (x0 + x) / 2
    out.append(cap(xc, IC + 56, cap_name, cap_sub, name_color=colors[0]))
    out.append(txt(x0 + 20, IC - 34, "128²×4", 9, FAINT))
    out.append(txt(x - 18, IC - 30, "8²×128", 9, FAINT))
    return "".join(out), x


def frame_part():
    g = terrain_frame(IC - 38)
    out = (g + txt(53, IC - 44, "128²×3", 9, FAINT)
           + txt(53, IC + 48, "camera frame", 10.5, MUT, 600)
           + txt(53, IC + 60, "one night exposure", 9.5, FAINT)
           + txt(53, IC + 73, "frozen contract", 8.5, FAINT,
                 style="font-style='italic'"))
    return out, 26 + 76


def retinex_glyph(xc, yc):
    """Fixed, non-learned illumination-invariant channel: a small edge-only
    sketch derived from the camera frame (log-luminance minus its own blur)."""
    s, n = 36, 6
    bumps = ((1, 4, .55), (2, 3, .48), (3, 2, .42), (4, 1, .35), (0, 5, .3), (5, 0, .28))
    g, _ = gridsq(xc - s / 2, s, n, ACC, bumps, yc=yc, lw=1.0)
    out = [g,
           cap(xc, yc + s / 2 + 18, "illumination-invariant channel",
               "log-luminance − own blur (fixed math)",
               color=ACC, name_color=ACC)]
    return "".join(out), s


def plus_glyph(x, y, color, r=8):
    return (f"<circle cx='{x}' cy='{y}' r='{r}' fill='none' stroke='{color}' stroke-width='1.2'/>"
            f"<line x1='{x-r*0.5}' y1='{y}' x2='{x+r*0.5}' y2='{y}' stroke='{color}' stroke-width='1.2'/>"
            f"<line x1='{x}' y1='{y-r*0.5}' x2='{x}' y2='{y+r*0.5}' stroke='{color}' stroke-width='1.2'/>")


def rotation_stack(x, color):
    """4 crop copies (0/90/180/270) as a shingled stack of squares, all
    fed through the shared trunk -- pooled back to one view after the FC head."""
    s = 22
    out = []
    for i, dx in enumerate((0, 6, 12, 18)):
        yy = IC - s / 2 - i * 0  # keep stack level, offset only in x for shingling
        out.append(f"<rect x='{x+dx}' y='{IC - s/2 - dx*0.35:.1f}' width='{s}' height='{s}' "
                   f"fill='none' stroke='{color}' stroke-width='1' opacity='{0.35 + i*0.18:.2f}'/>")
    w = 18 + s
    out.append(cap(x + w / 2, IC + 52, "C4 rotation ensemble",
                    color=ACC, name_color=ACC))
    return "".join(out), w


def output_part(x, sub="position fix + confidence"):
    return (txt(x, IC - 18, "frozen contract", 8.5, FAINT, anchor="start",
                style="font-style='italic'")
            + txt(x, IC - 2, "(lat, lon, confidence)", 13, MUT, 600, "start",
                  tid="frozen-output")
            + txt(x, IC + 12, sub, 9, FAINT, anchor="start"))


def loss_note(x_from, y_from, x_lab, y_lab, text, color, glyph=None):
    out = [lroute(x_from, y_from, x_lab - 8, y_lab - 16, color)]
    if glyph:
        out.append(glyph)
    out.append(txt(x_lab, y_lab - 12, text[0], 10, color, 600, "start"))
    if len(text) > 1:
        out.append(txt(x_lab, y_lab, text[1], 9.5, color, 400, "start"))
    return "".join(out)


H = 490
LOSS_Y = 424
LOSS_Y2 = 452
CONS_Y = 330

b = []
b.append(txt(8, 26, "INFERENCE PATH — WHAT FLIES", 9, FAINT, 600, "start", "letter-spacing='1.8'"))
b.append(txt(8, 296, "TRAINING SIGNALS — NEVER FLY", 9, OCH, 600, "start", "letter-spacing='1.8'"))

# 1. camera frame (frozen)
g, x = frame_part(); b.append(g)

# retinex glyph below the frame (empty space there), feeding up into the
# concat point ahead of the lane
rx_cx = x
rx_yc = IC + 88
g, rs = retinex_glyph(rx_cx, rx_yc)
b.append(g)

b.append(harrow(x + 6, x + 26, IC)); x += 28

# 2. concat point: RGB(3ch) + retinex(1ch) -> 4-channel input
merge_x = x + 6
b.append(lroute(rx_cx, rx_yc - rs / 2, merge_x, IC + 12, ACC))
b.append(plus_glyph(merge_x, IC, ACC))
b.append(cap(merge_x, IC + 30, "concat", "128²×4 input", color=ACC, name_color=ACC))
x = merge_x + 10

b.append(harrow(x, x + 24, IC)); x += 26

# 3. C4 rotation ensemble (shared trunk, 4 turns)
g, w = rotation_stack(x, ACC); b.append(g); x += w

b.append(harrow(x + 4, x + 28, IC)); x += 32

# 4. from-scratch conv trunk (4-channel input, pretrained trunk banned)
g, x = conv_group(x, [ACC, ACC, ACC, ACC],
                  "from-scratch conv encoder", "Conv 3×3 s2 ×4 · BN+ReLU — pretrained trunk banned this round",
                  prev=(merge_x, 12, ACC))
b.append(g)

b.append(harrow(x + 8, x + 28, IC)); x += 32

# 5. pooled GAP descriptor (C4-averaged) -- this is f_primary, tapped for the
# new cross-lighting consistency loss
gap_x = x
g, _ = bar(gap_x, 60, INK, ticks=11); b.append(g)
b.append(cap(gap_x + 4, IC + 44, "128-d descriptor", "GAP, C4-pooled avg", ))
x = gap_x + 12

b.append(harrow(x + 56, x + 78, IC))
fc_x = x
g, _ = bar(fc_x + 60, 88, ACC, ticks=15); b.append(g)
b.append(fan(fc_x, 60, fc_x + 60, 88, ACC))
b.append(g)
b.append(cap(fc_x + 64, IC + 80, "unified FC → 1024 logits", "gate + dark-expert head deleted",
             color=ACC, name_color=ACC))
x = fc_x + 74

b.append(harrow(x, x + 24, IC))
gx = x + 26
g, gs = gridsq(gx, 70, 8, INK, BUMP); b.append(g)
b.append(cap(gx + 35, IC + 52, "probability field", "32×32 cells, same layout-code concat"))

tx = 812
b.append(converge(gx, gs, tx, INK, cells="all"))
b.append(cap((gx + gs + tx) / 2 + 4, IC - 50, "sharpen β=3 → soft-argmax",
             "decode mechanism unchanged"))
b.append(output_part(828))

# confidence branch (recomputed from the new unified field's shape stats)
conf_x = gap_x + 4
ex = tx + 24
b.append(lroute(conf_x, IC + 56, conf_x, 214, ACC))
b.append(gauge(conf_x, 230, ACC))
b.append(txt(conf_x, 250, "confidence 0–1", 9, ACC))
b.append(txt(conf_x, 262, "peak/entropy/gap of new field", 8.5, ACC))
b.append(f"<path d='M {conf_x + 16},230 H {ex} V {IC + 22}' fill='none' "
         f"stroke='{ACC}' stroke-width='0.8'/>")
b.append(f"<path d='M {ex},{IC + 16} l -3,6 h 6 Z' fill='{ACC}'/>")
b.append(txt((conf_x + ex) / 2, 224, "same recipe, no gate-derived inputs left", 8.5, ACC,
             style="font-style='italic'"))

# ---- training-only lane ----

# new: lighting-partner crop, shared-trunk second pass, consistency loss
pc_x = 90
pc_s = 30
b.append(f"<rect x='{pc_x - pc_s/2:.0f}' y='{CONS_Y - pc_s/2:.0f}' width='{pc_s}' height='{pc_s}' "
         f"fill='#8c2f1f0a' stroke='{ACC}' stroke-width='1.2'/>")
b.append(f"<path d='M {pc_x - 9},{CONS_Y + 5} L {pc_x + 11},{CONS_Y - 7}' stroke='{ACC}' "
         f"stroke-width='1.4' fill='none' opacity='0.5'/>")
b.append(cap(pc_x, CONS_Y + pc_s / 2 + 16, "lighting-partner crop",
             "same spot & heading, other bucket", color=ACC, name_color=ACC))
b.append(txt(pc_x, CONS_Y + pc_s / 2 + 40, "train-only", 8.5, ACC, style="font-style='italic'"))

b.append(harrow(pc_x + pc_s / 2 + 6, pc_x + pc_s / 2 + 40, CONS_Y, "shared trunk"))
fpart_x = pc_x + pc_s / 2 + 46
g, _ = bar(fpart_x, 40, ACC, ticks=8, yc=CONS_Y); b.append(g)
b.append(cap(fpart_x + 4, CONS_Y + pc_s / 2 + 16, "f partner", "2nd forward pass",
             color=ACC, name_color=ACC))

cons_x = fpart_x + 130
b.append(lroute(gap_x + 3, IC + 32, cons_x, CONS_Y - 26, ACC))
b.append(lroute(fpart_x + 3, CONS_Y - 20, cons_x, CONS_Y - 26, ACC))
b.append(crosspt(cons_x, CONS_Y - 26, ACC, r=6))
b.append(txt(cons_x + 14, CONS_Y - 30, "L2 consistency loss ×0.1 (new)", 10, ACC, 600, "start"))
b.append(txt(cons_x + 14, CONS_Y - 18, "same spot, 2 lighting buckets → match descriptors", 9.5, ACC, 400, "start"))
b.append(txt(cons_x + 14, CONS_Y - 6, "watch: across-location variance must stay healthy", 8.5, ACC, 400, "start",
             style="font-style='italic'"))

# existing losses, unchanged -- staggered across two rows so none collide
tiny, _ = gridsq(460, 20, 6, OCH, ((3, 2, .6), (2, 2, .25)), yc=LOSS_Y - 12, lw=1)
b.append(loss_note(gx + 35, IC + 68, 488, LOSS_Y,
                   ("Gaussian-CE vs cell target (unchanged)",
                    "σ = 1.5 cells, same GRID_K=32 field"), OCH, glyph=tiny))
b.append(loss_note(tx, IC + 26, 700, LOSS_Y2,
                   ("L2 on decoded (u, v) (unchanged)",), OCH))
b.append(loss_note(conf_x + 8, 262, 488, LOSS_Y2,
                   ("confidence BCE ×0.3 (unchanged loss)",
                    "same hit-radius target, new field inputs"), OCH))

svg = svgwrap(H, "".join(b))
out_path = Path(__file__).resolve().parents[2] / "runs/20260730_171527_experiment60/figure.json"
out_path.write_text(json.dumps({"architecture_svg": svg}))
print(len(svg), "bytes ->", out_path)
