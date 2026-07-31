import sys
sys.path.insert(0, "fig_scratch")
from midprims import (
    IC, TX, INK, MUT, FAINT, ACC, OCH,
    txt, cap, shape, harrow, leader, lroute, slab, bar, fan, gridsq, cell_centers,
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
bar_x = 430
parts.append(harrow(enc_end + 3, bar_x - 5))
bar_svg, bar_w = bar(bar_x, 70, INK)
parts.append(bar_svg)
parts.append(shape(bar_x + 3, IC - 46, "512-d + 48-d tex"))
parts.append(cap(bar_x + 3, 160, "Layout summary", "layout + texture code", name_color=INK))

# Multi-hypothesis head (CHANGED) — deletes the 1024-way field entirely; a
# small MLP off the layout code + texture avg + raw brightness proposes 8
# candidate (u,v) offsets (anchor-broken) plus 8 mixture weights, drawn as
# 8 stacked hypotheses rather than a scored grid.
mlp_x = 478
parts.append(fan(bar_x + bar_w, 70, mlp_x, 46, color=ACC, n=5))
mlp_svg, mlp_w = bar(mlp_x, 46, ACC, ticks=8)
parts.append(mlp_svg)
parts.append(shape(mlp_x + 3, IC - 34, "8×(u,v,w) +bright"))
parts.append(cap(mlp_x + 3, 184, "Multi-hypothesis head", "8 pts + weight (was: 1024-way field)", color=ACC))

# 8 hypothesis cell-centres along the candidate bar's right edge — the real
# source points for the vote below (4 of 8 are this pass's per-view winners)
hx = mlp_x + mlp_w
pts8 = [(hx, IC - 23 + (i + 0.5) * 46 / 8) for i in range(8)]
winners_idx = [0, 2, 5, 7]
for i, (px, py) in enumerate(pts8):
    if i in winners_idx:
        parts.append(f"<circle cx='{px:.1f}' cy='{py:.1f}' r='2.6' fill='{ACC}'/>")
    else:
        parts.append(f"<circle cx='{px:.1f}' cy='{py:.1f}' r='1.6' fill='none' "
                      f"stroke='{ACC}' stroke-width='0.8' opacity='0.5'/>")

# 4-view weighted vote (CHANGED) — each rotated view's own highest-weight
# candidate converges on the output; the other 4 (this pass's non-winners)
# stay as faint unconverged marks, matching the epsilon-trickle training role
winner_pts = [pts8[i] for i in winners_idx]
parts.append(converge_pts(winner_pts, ACC, thin=0.9, op=0.6))
parts.append(cap(700, 56, "4-view weighted vote", "4 winners → blended point", color=ACC))

# Confidence (CHANGED) — branch below an empty lane column; spread of the
# 4 winning points + their mean weight replaces the old field-peak signal
parts.append(conf_branch(650, out_x=795))
parts.append(cap(650, 268, "spread of 4 winners", "+ winner's own weight", color=ACC))

# --- training row -----------------------------------------------------

# Training data & schedule (unchanged) — confusability sampler kept, its
# 32x32 grid constant just moved out of model.py into train.py, byte-identical
rot_bottom = (148, IC + rot_s / 2)
parts.append(lroute(rot_bottom[0], rot_bottom[1], 195, 335, OCH, horizontal_first=True))
parts.append(txt(195, 351, "Training data & schedule (unchanged)", 10, OCH, 600, "start"))
parts.append(txt(195, 363, "6,000 fresh places/bucket, confusability-weighted", 9.5, OCH, 400, "start"))
parts.append(txt(195, 375, "grid constant moved to train.py, math unchanged", 9.5, OCH, 400, "start"))
parts.append(txt(195, 387, "24 fresh-draw passes · cosine glide", 9.5, OCH, 400, "start"))

# Training signal (CHANGED) — the point of this experiment: winner-take-all
# regression replaces the 1024-way Gaussian-smoothed cross-entropy
parts.append(lroute(hx + 1, IC - 23, 560, 335, ACC, horizontal_first=True))
parts.append(txt(560, 351, "Training signal — winner-take-all (NEW)", 10, ACC, 600, "start"))
parts.append(txt(560, 363, "nearest of 8 candidates: full L2 to true (u,v)", 9.5, ACC, 400, "start"))
parts.append(txt(560, 375, "other 7: ε=0.05 trickle grad, never dead", 9.5, ACC, 400, "start"))
parts.append(txt(560, 387, "+ 8-way CE: weight head ← nearest hypothesis", 9.5, ACC, 400, "start"))
parts.append(txt(560, 399, "replaces 1024-way CE + coordinate L2", 9.5, ACC, 400, "start"))

emit("fig_scratch/middle_v2_37.json", parts)
print("wrote fig_scratch/middle_v2_37.json")
