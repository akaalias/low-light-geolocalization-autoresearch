import sys
sys.path.insert(0, "fig_scratch")
from midprims import (
    IC, TX, INK, MUT, FAINT, ACC, OCH,
    txt, cap, shape, harrow, lroute, slab, gridsq, cell_centers,
    converge_pts, conf_branch, encoder, emit,
)

parts = []

# Feature extractor (unchanged) — shared 4-conv encoder
enc_svg, enc_end = encoder(
    x0=132,
    name="Feature extractor",
    sub="4-layer CNN, stride-2 ×4 · ~230k params",
)
parts.append(enc_svg)

# hop to the new dilated-context conv (part of the changed per-patch head)
dilated_x = 376
parts.append(harrow(enc_end + 3, dilated_x - 5))
dslab_svg, dslab_w = slab(dilated_x, 17, 10, ACC)
parts.append(dslab_svg)
parts.append(shape(dilated_x + 13, IC - 44, "3×3 dil-2, RF≈95px"))

# hop to the dense per-cell (u,v) coordinate field
grid_x = 437
grid_s = 90
grid_n = 8
parts.append(harrow(dilated_x + dslab_w + 3, grid_x - 5))
grid_svg, _ = gridsq(grid_x, grid_s, grid_n, color=ACC)
parts.append(grid_svg)
parts.append(shape(grid_x + grid_s / 2, 58, "8²×2 (u,v)"))
parts.append(cap(grid_x + grid_s / 2, IC + 72, "Per-patch coordinates",
                  "64 cells, each names its own map coordinate", name_color=ACC))

# decode: the fan of 64 per-cell answers converging to a plain mean
cells = cell_centers(grid_x, grid_s, grid_n)
parts.append(converge_pts(cells, ACC, every=1))
parts.append(cap(680, 55, "Decode", "unweighted mean of 64 per-patch answers", name_color=ACC))

# confidence — unchanged, on its own branch below an empty lane column
parts.append(conf_branch(650, out_x=795))

# training-only detail: rotated per-cell target lattice + the per-cell loss
lattice_x, lattice_s, lattice_n = 372, 48, 4
bottom_left = cells[(grid_n - 1) * grid_n]
parts.append(lroute(bottom_left[0], bottom_left[1], lattice_x, 320, OCH, horizontal_first=True))
lattice_svg, _ = gridsq(lattice_x, lattice_s, lattice_n, color=OCH, yc=340)
parts.append(lattice_svg)
parts.append(f"<circle cx='{lattice_x + lattice_s / 2:.0f}' cy='340' r='2' fill='{OCH}'/>")
parts.append(cap(lattice_x + lattice_s / 2, 384, "Per-cell target grid",
                  "rotate offset lattice by θ, + crop-center coords", name_color=OCH))

bottom_right = cells[(grid_n - 1) * grid_n + (grid_n - 1)]
parts.append(lroute(bottom_right[0], bottom_right[1], 600, 280, OCH, horizontal_first=True))
parts.append(txt(610, 288, "Per-cell smooth-L1 loss", 10, OCH, 600, "start"))
parts.append(txt(610, 300, "64× denser supervision per photo", 9.5, OCH, 400, "start"))
parts.append(txt(610, 312, "+ 0.1 × conf BCE (unchanged)", 9.5, OCH, 400, "start"))

emit("fig_scratch/middle_v2_4.json", parts)
print("wrote fig_scratch/middle_v2_4.json")
