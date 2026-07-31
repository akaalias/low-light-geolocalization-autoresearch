import sys
sys.path.insert(0, "fig_scratch")
from midprims import (
    IC, TX, INK, MUT, FAINT, ACC, OCH,
    txt, cap, shape, harrow, lroute, bar, fan, gridsq, cell_centers,
    converge_pts, conf_branch, encoder, emit, BUMP,
)

parts = []

# Feature extractor (unchanged) — shared 4-conv encoder, GAP'd to a 128-d vector
enc_svg, enc_end = encoder(
    x0=132,
    name="Feature extractor",
    sub="4-layer CNN, stride-2 ×4 · ~230k params",
)
parts.append(enc_svg)

# global-average-pool the 8x8x128 feature map down to a 128-d vector (unchanged)
gap_x = 380
parts.append(harrow(enc_end + 3, gap_x - 5))
bar_svg, bar_w = bar(gap_x, 60, INK)
parts.append(bar_svg)
parts.append(shape(gap_x + 3, IC - 34, "128"))
parts.append(cap(gap_x + 3, IC + 86, "Global avg pool", "128-d vector", color=MUT))

# Linear(128 -> 1024) fans the pooled vector out into every map-cell logit (changed)
grid_x, grid_s, grid_n = 460, 90, 8
fan_svg = fan(gap_x + bar_w, 60, grid_x, grid_s, ACC, n=6)
parts.append(fan_svg)
grid_svg, _ = gridsq(grid_x, grid_s, grid_n, color=ACC, bumps=BUMP)
parts.append(grid_svg)
parts.append(shape(grid_x + grid_s / 2, 46, "32×32 grid, 1,024 cells"))
parts.append(cap(grid_x + grid_s / 2, IC + 72, "Probability map",
                  "softmax score per map cell", name_color=ACC))

# decode: soft-argmax — probability-weighted mean of the real cell centers
cells = cell_centers(grid_x, grid_s, grid_n)
parts.append(converge_pts(cells, ACC, every=1))
parts.append(cap(680, 55, "Decode", "soft-argmax over the grid",
                  name_color=ACC))

# confidence — unchanged, on its own branch below an empty lane column
parts.append(conf_branch(650, out_x=795))

# training-only detail: Gaussian-smoothed target grid + the CE / L2 / BCE loss
lattice_x, lattice_s, lattice_n = 440, 56, 6
lattice_bumps = ((3, 2, .5), (2, 2, .3), (3, 1, .3), (4, 2, .18), (3, 3, .18))
bottom_left = cells[(grid_n - 1) * grid_n]
parts.append(lroute(bottom_left[0], bottom_left[1], lattice_x, 320, OCH, horizontal_first=True))
lattice_svg, _ = gridsq(lattice_x, lattice_s, lattice_n, color=OCH, bumps=lattice_bumps, yc=340)
parts.append(lattice_svg)
parts.append(cap(lattice_x + lattice_s / 2, 384, "Gaussian target",
                  "soft bump, σ=1.5 cells, at true location", name_color=OCH))

bottom_right = cells[(grid_n - 1) * grid_n + (grid_n - 1)]
parts.append(lroute(bottom_right[0], bottom_right[1], 610, 280, OCH, horizontal_first=True))
parts.append(txt(620, 288, "Cross-entropy vs Gaussian target", 10, OCH, 600, "start"))
parts.append(txt(620, 300, "+ expected-coordinate L2", 9.5, OCH, 400, "start"))
parts.append(txt(620, 312, "+ 0.1 × conf BCE (unchanged)", 9.5, OCH, 400, "start"))

emit("fig_scratch/middle_v2_2.json", parts)
print("wrote fig_scratch/middle_v2_2.json")
