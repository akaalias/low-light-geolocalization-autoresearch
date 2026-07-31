import sys
sys.path.insert(0, "fig_scratch")
from midprims import (
    IC, TX, INK, MUT, FAINT, ACC, OCH,
    txt, cap, shape, harrow, leader, lroute, slab, bar, gridsq, cell_centers,
    converge_pts, gauge, conf_branch, encoder, emit, BUMP,
)

parts = []

# Rotation fan (unchanged) — the crop's 4 fixed 90 deg copies, drawn as a 2x2
# tile (real cells) so the shared-weight fan-out reads as a grid, not a box.
rot_svg, rot_s = gridsq(132, 32, 2, color=INK)
parts.append(rot_svg)
parts.append(cap(148, 170, "Rotation", "×4 shared", name_color=INK))

parts.append(harrow(132 + rot_s + 3, 184 - 5))

# Feature extractor (unchanged) — pretrained MobileNetV3-Small, 9 blocks
enc_svg, enc_end = encoder(
    x0=184,
    name="Feature extractor",
    sub="MobileNetV3-S, 190k, pretrained",
    shape_in="128²×3",
    shape_out="8²×128",
)
parts.append(enc_svg)

# Layout summary (unchanged) — 8x8x128 condensed to a 512-d layout code,
# with the 48-d texture average kept alongside for the lighting gate
bar_x = 430
parts.append(harrow(enc_end + 3, bar_x - 5))
bar_svg, bar_w = bar(bar_x, 70, INK)
parts.append(bar_svg)
parts.append(shape(bar_x + 3, IC - 46, "512-d"))
parts.append(cap(bar_x + 3, 170, "Layout summary", "512-d + 48-d texture", name_color=INK))

# Lighting gate (unchanged) — a small branch ABOVE the lane (empty column)
# reading brightness + the 48-d texture avg, gating the two scorers below
gate_x = 465
parts.append(leader(bar_x + bar_w + 3, IC - 35, gate_x, 78, MUT))
parts.append(gauge(gate_x, 64, MUT))
parts.append(cap(gate_x, 90, "Lighting gate", "night-likeness gates the vote", name_color=INK))
parts.append(leader(gate_x, 78, 515, 68, MUT))

# Probability map (unchanged) — 2 scorers x 4 rotations, gated + averaged
# into one voted map (drawn as a single representative voted grid)
grid_x, grid_s, grid_n = 515, 90, 8
parts.append(harrow(bar_x + bar_w + 3, grid_x - 5))
grid_svg, _ = gridsq(grid_x, grid_s, grid_n, color=INK, bumps=BUMP)
parts.append(grid_svg)
parts.append(shape(grid_x + grid_s / 2, 48, "8 votes → 1 map"))
parts.append(cap(grid_x + grid_s / 2, 170, "Probability map", "2 scorers ×4 turns, voted", name_color=INK))

# Decode (unchanged) — contrast-sharpen the voted map, then the balance
# point of the sharpened map (soft-argmax), converging on real cell centres
cells = cell_centers(grid_x, grid_s, grid_n)
parts.append(converge_pts(cells, INK, every=2))
parts.append(cap(730, 55, "Decode", "sharpen peaks, balance point", name_color=INK))

# Confidence (unchanged) — its own branch below an empty lane column
parts.append(conf_branch(650, out_x=795))

# --- training row -----------------------------------------------------
# Training signal (unchanged, train_only) — brief, ochre
ts_src = cell_centers(grid_x, grid_s, grid_n)[grid_n * (grid_n - 1)]  # bottom-left cell
parts.append(lroute(ts_src[0], ts_src[1], 490, 265, OCH, horizontal_first=True))
parts.append(txt(490, 282, "Training signal (unchanged)", 10, OCH, 600, "start"))
parts.append(txt(490, 294, "position + confidence grading, same as before", 9.5, OCH, 400, "start"))

# Training data (CHANGED — the point of this experiment) — red, richest
rot_bottom = (148, 112 + rot_s / 2)
parts.append(lroute(rot_bottom[0], rot_bottom[1], 178, 250, ACC, horizontal_first=True))
tile_y = 245
for i, tx0 in enumerate((150, 168, 186)):
    t_svg, _ = gridsq(tx0, 14, 1, color=ACC, yc=tile_y)
    parts.append(t_svg)
parts.append(txt(140, 284, "Training data — 3 sim realizations", 10, ACC, 600, "start"))
parts.append(txt(140, 296, "same crop, 3 seeded relight renders", 9.5, ACC, 400, "start"))
parts.append(txt(140, 308, "(stored + 2 fresh) — noise & lamps vary", 9.5, ACC, 400, "start"))
parts.append(txt(140, 320, "→ locks templates onto stable structure", 9.5, ACC, 400, "start"))

emit("fig_scratch/middle_v2_17.json", parts)
print("wrote fig_scratch/middle_v2_17.json")
