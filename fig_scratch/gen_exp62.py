import sys, json, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "archive"))
from terrain_frame_glyph import terrain_frame

INK, MUT, FAINT, ACC, OCH = "#111111", "#6b6a60", "#9b998c", "#8c2f1f", "#8a6a1e"
FONT = "Palatino,Georgia,serif"
IC = 138


def fmt(n):
    return f"{n:.0f}" if float(n).is_integer() else f"{n:.1f}"


def txt(x, y, s, size=10, color=MUT, w=400, anchor="middle", style="", tid=None):
    tid_attr = f"id='{tid}' " if tid else ""
    return (f"<text {tid_attr}x='{fmt(x)}' y='{fmt(y)}' font-family='{FONT}' font-size='{size}' "
            f"fill='{color}' font-weight='{w}' text-anchor='{anchor}' {style}>{s}</text>")


def cap(xc, y, name, sub=None, color=MUT, name_color=None):
    out = [txt(xc, y, name, 10.5, name_color or (INK if color == MUT else color), 600)]
    if sub:
        out.append(txt(xc, y + 12, sub, 9.5, color))
    return "".join(out)


def harrow(x1, x2, y, label=None, color=FAINT):
    out = [f"<line x1='{fmt(x1)}' y1='{fmt(y)}' x2='{fmt(x2 - 5)}' y2='{fmt(y)}' stroke='{color}' stroke-width='1'/>",
           f"<path d='M {fmt(x2)},{fmt(y)} l -6,-3 v 6 Z' fill='{color}'/>"]
    if label:
        out.append(txt((x1 + x2) / 2, y - 6, label, 9, FAINT, style="font-style='italic'"))
    return "".join(out)


def leader(x1, y1, x2, y2, color):
    return (f"<line x1='{fmt(x1)}' y1='{fmt(y1)}' x2='{fmt(x2)}' y2='{fmt(y2)}' stroke='{color}' "
            f"stroke-width='1' stroke-dasharray='2 4'/>")


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


def converge(gx, gs, tx, ty, color, n=8):
    out = []
    src = []
    y0 = ty - gs / 2
    for gyy in range(n):
        for gxx in range(n):
            if (gxx + gyy) % 2:
                continue
            src.append((gx + (gxx + 0.5) * gs / n, y0 + (gyy + 0.5) * gs / n))
    for (sx, sy) in src:
        out.append(f"<line x1='{sx:.1f}' y1='{sy:.1f}' x2='{tx}' y2='{ty}' "
                   f"stroke='{color}' stroke-width='0.55' opacity='0.4'/>")
    out.append(crosspt(tx, ty, color))
    return "".join(out)


def gauge(x, yc, color=MUT, r=14):
    a = math.radians(55)
    return (f"<path d='M {x - r},{yc} A {r} {r} 0 0 1 {x + r},{yc}' fill='none' "
            f"stroke='{color}' stroke-width='1.2'/>"
            f"<line x1='{x}' y1='{yc}' x2='{x + (r - 3) * math.cos(a):.1f}' "
            f"y2='{yc - (r - 3) * math.sin(a):.1f}' stroke='{color}' stroke-width='1.4'/>"
            f"<circle cx='{x}' cy='{yc}' r='1.6' fill='{color}'/>")


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


def frame_part():
    g = terrain_frame(IC - 38)
    out = (g + txt(53, IC - 44, "128²×3", 9, FAINT)
           + txt(53, IC + 48, "camera frame", 10.5, MUT, 600)
           + txt(53, IC + 60, "one night exposure", 9.5, FAINT)
           + txt(53, IC + 73, "frozen contract", 8.5, FAINT,
                 style="font-style='italic'"))
    return out, 26 + 76


def output_part(x, sub="position fix + confidence"):
    return (txt(x, IC - 18, "frozen contract", 8.5, FAINT, anchor="start",
                style="font-style='italic'")
            + txt(x, IC - 2, "(lat, lon, confidence)", 13, MUT, 600, "start",
                  tid="frozen-output")
            + txt(x, IC + 12, sub, 9, FAINT, anchor="start"))


def label_block(path_pts, x_lab, y_lab, lines, color, glyph=None):
    d = "M " + " L ".join(f"{fmt(px)},{fmt(py)}" for px, py in path_pts)
    out = [f"<path d='{d}' fill='none' stroke='{color}' stroke-width='1' stroke-dasharray='2 4'/>"]
    if glyph:
        out.append(glyph)
    out.append(txt(x_lab, y_lab - 12, lines[0], 10, color, 600, "start"))
    if len(lines) > 1:
        out.append(txt(x_lab, y_lab, lines[1], 9.5, color, 400, "start"))
    return "".join(out)


def rot_cluster(x0, y0, color, n=4, dx=6, dy=-2.1, s=20, dash=None):
    out = []
    opac = (0.32, 0.5, 0.68, 0.86)
    for i in range(n):
        xx = x0 + i * dx
        yy = y0 + i * dy
        dasharray = f" stroke-dasharray='{dash}'" if dash else ""
        out.append(f"<rect x='{fmt(xx)}' y='{fmt(yy)}' width='{s}' height='{s}' fill='none' "
                    f"stroke='{color}' stroke-width='1' opacity='{opac[min(i, 3)]}'{dasharray}/>")
    return "".join(out), x0 + (n - 1) * dx + s


def mirror_glyph(x, yc, color):
    out = [f"<line x1='{fmt(x)}' y1='{fmt(yc-13)}' x2='{fmt(x)}' y2='{fmt(yc+13)}' "
           f"stroke='{color}' stroke-width='1' stroke-dasharray='1 2.5'/>",
           f"<path d='M {fmt(x-4)},{fmt(yc-13)} l -5,3 l 5,3 Z' fill='{color}'/>",
           f"<path d='M {fmt(x+4)},{fmt(yc-13)} l 5,3 l -5,3 Z' fill='{color}'/>"]
    return "".join(out)


H = 560
b = []
b.append(txt(8, 26, "INFERENCE PATH — WHAT FLIES", 9, FAINT, 600, "start", "letter-spacing='1.8'"))
b.append(txt(8, 366, "TRAINING SIGNALS — NEVER FLY", 9, OCH, 600, "start", "letter-spacing='1.8'"))

g, x = frame_part(); b.append(g)
b.append(harrow(x + 6, x + 54, IC)); x += 56

# ---- D4 symmetry ensemble: rotation cluster + mirror-axis glyph + mirrored cluster ----
d4x0 = x
g1, xr = rot_cluster(d4x0, IC - 24, ACC, s=20)
b.append(g1)
mx = xr + 16
b.append(mirror_glyph(mx, IC, ACC))
g2, xr2 = rot_cluster(mx + 14, IC - 24, ACC, s=20)
b.append(g2)
d4_xc = (d4x0 + xr2) / 2
b.append(cap(d4_xc, IC + 46, "×8 exact-pixel views (D4)", "rotations + mirror, shared weights",
             name_color=ACC))
x = xr2
b.append(harrow(x + 8, x + 32, IC)); x += 34

# ---- SqueezeNet1.1 Fire trunk: stem + 4 fire blocks, growing channel depth ----
sizes = [(40, 7), (30, 10), (22, 13), (16, 16)]
trunk_x0 = x
faces = []
for (s, d) in sizes:
    gg, w = slab(x, s, d, ACC)
    b.append(gg)
    faces.append((x, s))
    x += w + 11
trunk_x1 = x - 11
b.append(kernel_proj(d4x0, 20, faces[0][0], faces[0][1], ACC))
for (x1, s1), (x2, s2) in zip(faces, faces[1:]):
    b.append(kernel_proj(x1, s1, x2, s2, ACC))
xc_trunk = (trunk_x0 + trunk_x1) / 2
b.append(cap(xc_trunk, IC + 56, "SqueezeNet1.1 Fire trunk",
             "stem + 4 fire blocks (BSD-3)", name_color=ACC))
b.append(txt(xc_trunk, IC + 82, "mobilenet_v3_small banned this round", 8.5, ACC,
             style="font-style='italic'"))
b.append(txt(trunk_x0 + 20, IC - 30, "63²×64", 9, FAINT))
b.append(txt(trunk_x1 - 14, IC - 24, "7²×384", 9, FAINT))
trunk_out_x = trunk_x1
x = trunk_x1
b.append(harrow(x + 6, x + 26, IC)); x += 28

# ---- FiLM (γ, β) modulation: brightness scalar -> tiny MLP -> per-channel scale/shift ----
film_lum_x = trunk_x0 - 4
gg, _ = bar(film_lum_x, 14, ACC, ticks=1, yc=46)
b.append(gg)
b.append(txt(film_lum_x + 4, 34, "lum", 8.5, ACC, style="font-style='italic'"))
film_gx, film_gy = trunk_out_x - 8, 46
b.append(fan(film_lum_x + 7, 14, film_gx, 16, ACC, n=3, yc=46))
gg2, _ = bar(film_gx, 16, ACC, ticks=3, yc=46)
b.append(gg2)
b.append(cap(film_gx + 4, 26, "FiLM (γ, β) MLP", None, name_color=ACC))
b.append(f"<path d='M {fmt(film_gx+3)},53 V {fmt(IC - 8)}' fill='none' stroke='{ACC}' "
         f"stroke-width='1' stroke-dasharray='2 4'/>")
b.append(f"<path d='M {fmt(film_gx+3)},{fmt(IC-8)} l -3,6 h 6 Z' fill='{ACC}'/>")
b.append(txt(film_gx + 20, IC - 44, "modulates feature map", 8.5, ACC,
             style="font-style='italic'", anchor="start"))

# ---- GAP descriptor (384-d) + narrow layout squeeze, concatenated ----
bar_x = x
gg, w = bar(x, 76, ACC, ticks=13); b.append(gg)
b.append(cap(x + 4, IC + 50, "384-d descriptor", "GAP, D4-pooled avg", name_color=ACC))
x += 18
lay_x = x
gg3, wlay = bar(lay_x, 34, ACC, ticks=5)
b.append(gg3)
b.append(cap(lay_x + 4, IC + 80, "1-ch layout", "1×1 squeeze, 49-d flat", name_color=ACC))
x += 46

fx = x
gg2, _ = bar(fx + 54, 20, ACC, ticks=3)
b.append(fan(fx, 76, fx + 54, 20, ACC))
b.append(fan(lay_x, 34, fx + 54, 20, ACC, n=3))
b.append(gg2)
b.append(cap(fx + 58, IC + 84, "single Linear → 1,024", "gate + dual head deleted",
             name_color=ACC))
x = fx + 66
b.append(harrow(x, x + 24, IC)); x += 26

field_x = x
gg3f, gs = gridsq(field_x, 76, 8, ACC, BUMP)
b.append(gg3f)
b.append(cap(field_x + 38, IC + 56, "probability field", "32×32 cells over the map", name_color=ACC))

tx = 812
b.append(converge(field_x, gs, tx, IC, ACC))
b.append(cap(tx - 60, IC - 30, "adaptive-β commit", None, name_color=ACC))
b.append(output_part(828))

# ---- adaptive-β gauge: reads raw field's own entropy + peak, picks a per-example β ----
# caption sits ABOVE the gauge and the leader approaches from below, so the
# leader never has to cross through the caption text on its way up.
beta_x, beta_y = field_x + 38, 60
b.append(cap(beta_x, 30, "β = f(entropy, peak)", "learned per-example sharpening",
             name_color=ACC))
b.append(leader(beta_x, IC - 40, beta_x, beta_y + 16, ACC))
b.append(gauge(beta_x, beta_y, ACC))

# ---- confidence branch: recomputed over new descriptor + adaptive β itself ----
gx_conf = bar_x + 4
ex = tx + 20
b.append(leader(gx_conf, IC + 64, gx_conf, 234, ACC))
b.append(gauge(gx_conf, 250, ACC))
b.append(cap(gx_conf, 268, "confidence 0–1", "384-d GAP + adaptive β + peak/entropy/gap",
             name_color=ACC, color=ACC))
b.append(f"<path d='M {fmt(gx_conf + 18)},250 H {fmt(ex)} V {fmt(IC + 26)}' fill='none' "
         f"stroke='{ACC}' stroke-width='0.8'/>")
b.append(f"<path d='M {fmt(ex)},{fmt(IC + 20)} l -3,6 h 6 Z' fill='{ACC}'/>")

# ---- training lane ----
row1_y = 400
safe_y = 340
tiny, _ = gridsq(0, 20, 6, OCH, ((3, 2, .6),), yc=row1_y - 10, lw=1)
b.append(label_block([(field_x + 38, IC + 76), (field_x + 38, safe_y),
                       (0, safe_y), (0, row1_y - 16)],
                      30, row1_y,
                      ("Gaussian-CE vs cell target (unchanged)", "σ = 1.5 cells over the 32×32 field"),
                      OCH, glyph=tiny))

l2_glyph = (f"<line x1='300' y1='{row1_y-4}' x2='330' y2='{row1_y-4}' stroke='{ACC}' stroke-width='1.2'/>"
            f"<circle cx='330' cy='{row1_y-4}' r='2' fill='{ACC}'/>"
            f"<line x1='330' y1='{row1_y-4}' x2='330' y2='{row1_y-18}' stroke='{ACC}' stroke-width='1' "
            f"stroke-dasharray='2 3'/>")
b.append(label_block([(tx, IC + 26), (tx, safe_y), (312, safe_y), (312, row1_y - 16)],
                      320, row1_y,
                      ("L2 on decoded (u, v)", "expected-coordinate loss — now also trains the β gauge"),
                      ACC, glyph=l2_glyph))

b.append(label_block([(gx_conf, 284), (gx_conf, safe_y), (600, safe_y), (600, row1_y - 16)],
                      608, row1_y,
                      ("confidence BCE ×0.3 (unchanged loss)", "same hit-radius target, new head inputs"),
                      OCH))

svg = (f"<svg viewBox='0 0 980 {H}' xmlns='http://www.w3.org/2000/svg' role='img'>"
       + "".join(b) + "</svg>")

out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("runs/20260730_192739_experiment62/figure.json")
out_path.write_text(json.dumps({"architecture_svg": svg}))
print("wrote", out_path, len(svg), "bytes")
print("debug:", dict(d4x0=d4x0, xr=xr, xr2=xr2, trunk_x0=trunk_x0, trunk_x1=trunk_x1,
                      xc_trunk=xc_trunk, bar_x=bar_x, lay_x=lay_x, fx=fx, field_x=field_x,
                      gs=gs, tx=tx, gx_conf=gx_conf, ex=ex, beta_x=beta_x, beta_y=beta_y))
