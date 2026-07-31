import sys
sys.path.insert(0, "fig_scratch")
from midprims import (
    txt, cap, shape, harrow, leader, lroute, slab, bar, fan, gridsq, BUMP,
    cell_centers, crosspt, converge_pts, gauge, conf_branch, kernel_proj,
    encoder, loss_note, emit, INK, MUT, FAINT, ACC, OCH, IC, TX,
)

parts = []

# ---------------------------------------------------------------- rotation fan note (input side)
parts.append(txt(168, 50, "C4 rotation ×4 (0/90/180/270)", 9, MUT))
parts.append(txt(168, 62, "→ coarse stage only", 8.5, ACC, style="font-style='italic'"))

# ---------------------------------------------------------------- feature extractor (from-scratch, two taps)
sizes = [(46, 7), (34, 11), (24, 15), (17, 21)]
x0 = 132
x = x0
faces = []
for (s, d) in sizes:
    g, w = slab(x, s, d, ACC)
    parts.append(g)
    faces.append((x, s))
    x += w + 15
x -= 15  # x now = start x of last face + its width already added; recompute end
x_end = faces[-1][0] + sizes[-1][0] + sizes[-1][1]

parts.append(kernel_proj(x0 - 20, 60, faces[0][0], faces[0][1], FAINT))
for (x1, s1), (x2, s2) in zip(faces, faces[1:]):
    parts.append(kernel_proj(x1, s1, x2, s2, ACC))

xc_enc = (x0 + x_end) / 2
parts.append(cap(xc_enc, IC + 48, "feature extractor", "from-scratch stem · two taps", ACC))
parts.append(shape(x0 + 18, IC - 34, "128²×3"))
parts.append(shape(x_end - 20, IC - 34, "8²×112"))

# intermediate 16x16x80 tap: taken off the 3rd slab face
tap_x, tap_s = faces[2]
tap_face_x = tap_x + tap_s  # right edge of the 3rd slab's front face
parts.append(shape(240, 92, "16²×80 (fine tap)", ACC))

# ---------------------------------------------------------------- layout summary (coarse-path only, mostly unchanged recipe)
ls_x = x_end + 20
parts.append(harrow(x_end, ls_x, IC, color=FAINT))
lsb, lsw = bar(ls_x, 60, INK)
parts.append(lsb)
xc_ls = ls_x + lsw / 2
parts.append(cap(xc_ls, IC + 72, "layout summary", "1×1 squeeze + GAP", MUT))

# ---------------------------------------------------------------- lighting gate: REMOVED
gate_x = ls_x + lsw + 34
parts.append(f"<line x1='{gate_x-6}' y1='{IC+78}' x2='{gate_x+6}' y2='{IC+90}' stroke='{ACC}' stroke-width='1.4'/>")
parts.append(f"<line x1='{gate_x-6}' y1='{IC+90}' x2='{gate_x+6}' y2='{IC+78}' stroke='{ACC}' stroke-width='1.4'/>")
parts.append(cap(gate_x, IC + 96, "lighting gate", "REMOVED — rerank replaces it", ACC))

# ---------------------------------------------------------------- coarse field (proposer)
grid_x = gate_x + 40
grid_s = 88
grid_n = 8
gsvg, gs = gridsq(grid_x, grid_s, grid_n, INK, bumps=BUMP)
parts.append(harrow(ls_x + lsw, grid_x, IC, color=FAINT))
parts.append(gsvg)
xc_grid = grid_x + grid_s / 2
parts.append(cap(xc_grid, IC + 48, "coarse field (proposer)", "Gaussian-CE over 1024 cells", MUT))

# top-8 shortlist: real cell centres pulled off this same grid
SHORTLIST = [(5, 2), (4, 2), (5, 1), (6, 2), (5, 3), (2, 5), (1, 6), (4, 3)]
y0 = IC - grid_s / 2
shortlist_pts = [(grid_x + (gx + 0.5) * grid_s / grid_n, y0 + (gy + 0.5) * grid_s / grid_n)
                 for (gx, gy) in SHORTLIST]
for (cx, cy) in shortlist_pts:
    parts.append(f"<circle cx='{cx:.1f}' cy='{cy:.1f}' r='2.6' fill='none' stroke='{ACC}' stroke-width='1.3'/>")
parts.append(txt(grid_x + grid_s + 34, 50, "top-8 shortlist", 8.5, ACC, style="font-style='italic'"))

# ---------------------------------------------------------------- fine tap: branch UP and across (clear of every caption band) to the comparator
comp_x = grid_x + grid_s + 19
parts.append(lroute(tap_face_x + 2, IC - tap_s / 2 - 12, comp_x, 44, ACC, dashed=False))
parts.append(lroute(comp_x, 44, comp_x, IC, ACC, dashed=False))

# shortlist selection feeds the comparator too (arriving on the lane)
parts.append(harrow(grid_x + grid_s + 4, comp_x - 2, IC, color=ACC))

# ---------------------------------------------------------------- candidate re-rank comparator
db, dw = bar(comp_x, 50, ACC)
parts.append(db)
eb_x = comp_x + dw + 45
eb, ew = bar(eb_x, 50, ACC)
parts.append(eb)
parts.append(fan(comp_x + dw, 50, eb_x, 50, ACC, n=4))
sc_x = eb_x + ew + 45
scb, scw = bar(sc_x, 30, ACC)
parts.append(scb)
parts.append(harrow(eb_x + ew, sc_x, IC, color=ACC))

xc_comp = (comp_x + sc_x + scw) / 2
parts.append(cap(xc_comp, IC + 72, "candidate re-rank", "MLP scores Δ & ⊗ vs cell embed", ACC))
parts.append(txt(comp_x + dw / 2, IC - 34, "detail", 8.5, ACC, style="font-style='italic'"))
parts.append(txt(eb_x + ew / 2, IC - 46, "cell-id", 8.5, ACC, style="font-style='italic'"))
parts.append(txt(sc_x + scw / 2, IC - 34, "score", 8.5, ACC, style="font-style='italic'"))

parts.append(harrow(sc_x + scw, sc_x + scw + 30, IC, color=ACC))

# ---------------------------------------------------------------- decode: soft-argmax over the same 8 candidate cells
parts.append(cap(740, IC - 56, "decode", "soft-argmax over top-8 → (lat, lon)", ACC))
parts.append(converge_pts(shortlist_pts, ACC))

# ---------------------------------------------------------------- confidence: top1-vs-top2 margin of the K-way score
parts.append(conf_branch(700, out_x=798))
parts.append(txt(700, IC + 156, "top1 vs top2 margin (K=8)", 8.5, MUT))

# ---------------------------------------------------------------- training row
parts.append(loss_note(
    150, IC + 90, 170, ["training schedule: single Adam", "group @1e-3 (nothing pretrained)"],
    OCH))
parts.append(loss_note(
    xc_grid, IC + 92, 400, ["coarse loss: Gaussian-smoothed CE", "over all 1024 cells (proposer only)"],
    OCH))
parts.append(loss_note(
    xc_comp, IC + 98, 620, ["re-rank loss: CE over top-8", "true cell forced into candidate set"],
    OCH))

svg = emit("fig_scratch/middle_v2_45.json", parts)
print("wrote", len(svg), "bytes")
