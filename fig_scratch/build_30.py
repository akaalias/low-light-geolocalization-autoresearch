import sys
sys.path.insert(0, "fig_scratch")
from midprims import (
    IC, TX, INK, MUT, FAINT, ACC, OCH,
    txt, cap, shape, harrow, leader, lroute, slab, bar, gridsq, cell_centers,
    converge_pts, gauge, conf_branch, encoder, emit, BUMP,
)

parts = []

# Rotation fan (unchanged) — 4 fixed 90deg copies, shared network
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

# Layout summary (unchanged) — 512-d layout code + 48-d texture average kept
bar_x = 428
parts.append(harrow(enc_end + 3, bar_x - 5))
bar_svg, bar_w = bar(bar_x, 70, INK)
parts.append(bar_svg)
parts.append(shape(bar_x + 3, IC - 46, "512-d + 48-d tex"))
parts.append(cap(bar_x + 3, 170, "Layout summary", "layout + texture code", name_color=INK))

# Lighting dispatcher (CHANGED) — replaces the single night-likeness gate with
# a tiny supervised 3-way router: how day-, dusk-, night-like is this crop.
disp_cx = 470
disp_grid, _ = gridsq(456, 30, 3, color=ACC, yc=58,
                       bumps=((0, 0, .25), (1, 0, .35), (2, 0, .85)))
parts.append(leader(bar_x + bar_w + 3, 90, disp_cx - 12, 70, ACC))
parts.append(disp_grid)
parts.append(cap(disp_cx, 88, "Lighting dispatcher", "supervised day/dusk/night weights", color=ACC))

# Probability map (CHANGED) — 3 FULL specialist template tables (day/dusk/
# night), each with the complete layout-aware readout, int8-packed; mixed
# per-cell by the dispatcher's 3 weights. 4 turned copies still averaged in.
spec_x, spec_s, spec_n = 520, 34, 4
parts.append(harrow(bar_x + bar_w + 3, spec_x - 5))
day_grid, _ = gridsq(spec_x, spec_s, spec_n, color=ACC, yc=IC - 40,
                      bumps=((1, 1, .30), (2, 1, .25), (1, 2, .20)))
dusk_grid, _ = gridsq(spec_x, spec_s, spec_n, color=ACC, yc=IC,
                       bumps=((2, 2, .40), (3, 2, .30), (2, 3, .20)))
night_grid, _ = gridsq(spec_x, spec_s, spec_n, color=ACC, yc=IC + 40,
                        bumps=((0, 3, .60), (3, 0, .55), (1, 0, .50)))
parts += [day_grid, dusk_grid, night_grid]
parts.append(shape(spec_x + spec_s / 2, IC - 40 - 26, "560→1024 · int8", ACC))
parts.append(cap(spec_x + spec_s / 2, IC + 40 + 30, "Probability map",
                  "3 specialists, mixed", color=ACC))

# Decode (unchanged) — contrast-sharpen then balance point, converging from
# the REAL cells of all three specialist tables onto the output crosshair.
base = cell_centers(spec_x, spec_s, spec_n)
day_pts = [(x, y - 40) for x, y in base]
dusk_pts = base
night_pts = [(x, y + 40) for x, y in base]
parts.append(converge_pts(day_pts + dusk_pts + night_pts, INK, every=3))
parts.append(cap(730, 55, "Decode", "sharpen peaks, balance point", name_color=INK))

# Confidence (unchanged) — its own branch below an empty lane column
parts.append(conf_branch(650, out_x=795))

# --- training row -----------------------------------------------------

# Training data & schedule (unchanged, brief, merged) — jog right out of the
# Rotation caption's column while still above it, then straight down.
rot_bottom = (148, IC + rot_s / 2)
parts.append(lroute(rot_bottom[0], rot_bottom[1], 195, 335, OCH, horizontal_first=True))
parts.append(txt(195, 351, "Training data & schedule (unchanged)", 10, OCH, 600, "start"))
parts.append(txt(195, 363, "6,000 fresh places/bucket · fresh heading", 9.5, OCH, 400, "start"))
parts.append(txt(195, 375, "+ 1 of 3 relight re-renders", 9.5, OCH, 400, "start"))
parts.append(txt(195, 387, "24 fresh-draw passes · cosine glide", 9.5, OCH, 400, "start"))

# Training signal (CHANGED) — the point of this experiment: the dispatcher's
# routing is now graded against the crop's true lighting regime. Escape the
# dispatcher grid above its own caption (y=52, between the shape label and
# the day-specialist grid top) before dropping into the training row.
parts.append(lroute(456 + 30, 52, 605, 335, ACC, horizontal_first=True))
parts.append(txt(605, 351, "Training signal — dispatcher routing (NEW)", 10, ACC, 600, "start"))
parts.append(txt(605, 363, "0.3 × cross-entropy vs true regime", 9.5, ACC, 400, "start"))
parts.append(txt(605, 375, "day = morning/midday/afternoon", 9.5, ACC, 400, "start"))
parts.append(txt(605, 387, "dusk = early_evening/evening · night = night", 9.5, ACC, 400, "start"))
parts.append(txt(605, 399, "position + confidence grading: unchanged", 9.5, ACC, 400, "start"))

emit("fig_scratch/middle_v2_30.json", parts)
print("wrote fig_scratch/middle_v2_30.json")
