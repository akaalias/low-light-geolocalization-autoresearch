"""Build iteration-2 figure: adapt exp-20's stored SVG (current kept chain).
- recolor exp-20's red (now-kept per-epoch resampling) to training-ochre
- drop its 5-line red paragraph, add a compact 'kept' note
- add THIS experiment's change in red: train-only per-patch place supervision
  tapped off the trunk's 8x8 feature grid, with an orthogonal dashed leader
"""
import re, sqlite3

INK, MUT, FAINT, ACC, OCH = "#111111", "#6b6a60", "#9b998c", "#8c2f1f", "#8a6a1e"
FONT = "Palatino,Georgia,serif"

conn = sqlite3.connect("experiments.sqlite")
svg = conn.execute("SELECT arch_svg FROM experiments WHERE id=20").fetchone()[0]
conn.close()

# 1) all of exp-20's red -> ochre (kept training mechanism, unchanged now)
svg = svg.replace(ACC, OCH)

# 2) delete the old 5-line paragraph (centered x=400, y 424..486)
for y in (424, 438, 450, 462, 474, 486):
    svg = re.sub(rf"<text x='400' y='{y}'[^>]*>[^<]*</text>", "", svg)

# 3) grow height 512 -> 560
svg = svg.replace("viewBox='0 0 980 512'", "viewBox='0 0 980 560'")


def txt(x, y, s, size=10, color=MUT, w=400, anchor="middle", style=""):
    return (f"<text x='{x}' y='{y}' font-family='{FONT}' font-size='{size}' "
            f"fill='{color}' font-weight='{w}' text-anchor='{anchor}' {style}>{s}</text>")


def gridsq(x, yc, s, n, color=INK, bumps=(), lw=1.2):
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
    return "".join(out)


add = []
# compact 'kept' note under the epoch panels
add.append(txt(205, 480, "kept from exp 20 — unchanged", 9.5, OCH))

# --- red leader: trunk output slab (360..380 x 140..160) down to the aux band
add.append(f"<circle cx='370' cy='161' r='2' fill='{ACC}'/>")
add.append(f"<path d='M 370,161 H 398 V 248 H 345 V 445 H 348' fill='none' "
           f"stroke='{ACC}' stroke-width='1' stroke-dasharray='2 4' opacity='0.85'/>")

# --- feature-grid copy (identity turn), 8x8, with three tapped cells in red
FG_X, FG_YC, FG_S = 350, 460, 56
add.append(gridsq(FG_X, FG_YC, FG_S, 8, INK,
                  bumps=((1, 1, 0.0),)))  # base grid, no bump
cell = FG_S / 8
tapped = [(1, 1), (4, 3), (6, 6)]  # (col,row)
for (j, i) in tapped:
    add.append(f"<rect x='{FG_X + j * cell:.1f}' y='{FG_YC - FG_S / 2 + i * cell:.1f}' "
               f"width='{cell:.1f}' height='{cell:.1f}' fill='{ACC}' fill-opacity='0.45'/>")
add.append(txt(378, 502, "trunk feature grid 8²×48", 10.5, INK, 600))
add.append(txt(378, 514, "identity turn · read before pooling", 9.5, MUT))

# --- three per-patch field grids (of 64), diagonal stagger, red bumps
G = [(530, 430, (1, 4)), (592, 462, (4, 1)), (654, 494, (3, 3))]
for (gx, gyc, (bx, by)) in G:
    add.append(gridsq(gx, gyc, 40, 6, ACC,
                      bumps=((bx, by, 0.55), (bx - 1, by, 0.2), (bx, by - 1, 0.2))))
# red vote lines: each tapped cell -> its OWN field grid (true sources)
src = [(FG_X + (j + 0.5) * cell, FG_YC - FG_S / 2 + (i + 0.5) * cell) for (j, i) in tapped]
for (sx, sy), (gx, gyc, _) in zip(src, G):
    add.append(f"<line x1='{sx:.1f}' y1='{sy:.1f}' x2='{gx}' y2='{gyc - 2}' "
               f"stroke='{ACC}' stroke-width='0.7' opacity='0.55'/>")
add.append(txt(600, 528, "64 per-patch map fields — 3 of 64 shown", 10.5, ACC, 600))
add.append(txt(600, 540, "one shared 1×1 conv 48→1024 · training-only, deleted before export", 9.5, ACC))

# --- red text block, right side
tb = [("NEW — per-patch place supervision", 600, 10),
      ("every feature cell must place ITS OWN", 400, 9.5),
      ("16 m patch of ground on the map, graded", 400, 9.5),
      ("by a Gaussian bump at that patch's true", 400, 9.5),
      ("spot = crop centre + rotated cell offset.", 400, 9.5),
      ("64 graded answers per crop instead of 1.", 400, 9.5),
      ("The flying network is untouched — the", 400, 9.5),
      ("aux head never ships.", 400, 9.5)]
y = 430
for (s, w, fs) in tb:
    add.append(txt(758, y, s, fs, ACC, w, "start"))
    y += 13
# short leader from grid trio to the text block
add.append(f"<line x1='678' y1='494' x2='752' y2='494' stroke='{ACC}' "
           f"stroke-width='1' stroke-dasharray='2 4' opacity='0.85'/>")

svg = svg.replace("</svg>", "".join(add) + "</svg>")
open("runs/_iter2_fig.svg", "w").write(svg)
print("bytes:", len(svg))
