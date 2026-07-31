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

# Training data (unchanged, brief) — fresh location draws, 3 sim realizations
rot_bottom = (148, IC + rot_s / 2)
parts.append(lroute(rot_bottom[0], rot_bottom[1], 178, 372, OCH, horizontal_first=True))
parts.append(txt(178, 388, "Training data (unchanged)", 10, OCH, 600, "start"))
parts.append(txt(178, 400, "6,000 fresh locations/bucket · 3 sim renders/crop", 9.5, OCH, 400, "start"))

# Training signal (CHANGED — the point of this experiment) — a throwaway
# reconstruction decoder hangs off the encoder's identity-turn features and
# must redraw the clean daytime crop; deleted before export.
feat_x, feat_s = 366, 17          # last conv slab face — the 8x8 feature map
src = (feat_x + feat_s + 6, IC + feat_s / 2 + 8)
parts.append(lroute(src[0], src[1], 305, 245, ACC, horizontal_first=False))

dy = 250
sq1_x, sq1_s = 300, 10   # 8x8x48   identity-turn features (read-only tap)
sq2_x, sq2_s = 328, 16   # 16x16    upsample x2 + 3x3 conv + ReLU
sq3_x, sq3_s = 356, 20   # 32x32    upsample x2 + 3x3 conv + ReLU
sq4_x, sq4_s = 392, 26   # 64x64x3  upsample x2 + 3x3 conv + ReLU, 1x1 + sigmoid
tgt_x, tgt_s = 444, 26   # 64x64    daytime reference crop, pixel-aligned

g1, _ = gridsq(sq1_x, sq1_s, 2, color=ACC, yc=dy)
g2, _ = gridsq(sq2_x, sq2_s, 2, color=ACC, yc=dy)
g3, _ = gridsq(sq3_x, sq3_s, 3, color=ACC, yc=dy)
g4, _ = gridsq(sq4_x, sq4_s, 4, color=ACC, yc=dy)
gt, _ = gridsq(tgt_x, tgt_s, 1, color=ACC, yc=dy)
parts += [g1, g2, g3, g4, gt]

parts.append(harrow(sq1_x + sq1_s + 2, sq2_x - 3, y=dy, color=ACC))
parts.append(harrow(sq2_x + sq2_s + 2, sq3_x - 3, y=dy, color=ACC))
parts.append(harrow(sq3_x + sq3_s + 2, sq4_x - 3, y=dy, color=ACC))

parts.append(shape(sq1_x + sq1_s / 2, 210, "8²×48", ACC))
parts.append(shape(sq4_x + sq4_s / 2, 226, "64²×3", ACC))
parts.append(shape(tgt_x + tgt_s / 2, 226, "64² (frozen sim)", ACC))
parts.append(txt((sq4_x + sq4_s + tgt_x) / 2, 210, "L1 · λ=0.3", 9, ACC, style="font-style='italic'"))

parts.append(cap(sq1_x + (sq4_x + sq4_s - sq1_x) / 2, 280, "ReconDecoder (NEW)",
                  "~55k params · upsample ×3 · train-only", color=ACC))
parts.append(cap(tgt_x + tgt_s / 2, 314, "daytime target",
                  "same spot/heading, held-out sim raster", color=ACC))

parts.append(txt(500, 345, "Training signal (changed)", 10, ACC, 600, "start"))
parts.append(txt(500, 357, "decoder must redraw the clean daytime crop", 9.5, ACC, 400, "start"))
parts.append(txt(500, 369, "from features alone — every lighting bucket", 9.5, ACC, 400, "start"))
parts.append(txt(500, 381, "of a place shares one daytime answer, so this", 9.5, ACC, 400, "start"))
parts.append(txt(500, 393, "pushes the encoder to cancel lighting/noise", 9.5, ACC, 400, "start"))
parts.append(txt(500, 405, "deleted before export — flying net unchanged", 9.5, ACC, 400, "start"))

emit("fig_scratch/middle_v2_23.json", parts)
print("wrote fig_scratch/middle_v2_23.json")
