"""Self-test: build an exp4-style middle purely from midprims and confirm it
passes midcheck. Proves the toolkit yields a clean figure by construction."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import midprims as M

p = []
x = 132
g, x = M.encoder(x); p.append(g)
p.append(M.harrow(x + 6, x + 34)); x += 40

# dilated-context stage (the changed thing → ACC)
dil_x = x
g, w = M.slab(x, 17, 21, M.ACC); p.append(g)
p.append(M.cap(dil_x + 19, M.IC + 48, "dilated conv 3×3 d2", "~95px context/cell", color=M.ACC, name_color=M.ACC))
p.append(M.shape(dil_x + 8, M.IC - 34, "8²×128"))
x += w + 40
p.append(M.harrow(dil_x + w + 6, x - 6))

# per-patch coordinate field
gx = x
g, gs = M.gridsq(gx, 96, 8, M.ACC); p.append(g)
pts = M.cell_centers(gx, gs, 8, jitter=0.9)
for (cx, cy) in pts:
    p.append(f"<circle cx='{cx:.1f}' cy='{cy:.1f}' r='1.3' fill='{M.ACC}'/>")
p.append(M.cap(gx + gs / 2, M.IC + 72, "64 per-patch coords", "1×1 conv + σ (8×8×2)", color=M.ACC, name_color=M.ACC))

# committee decode → converge to the crosshair
p.append(M.converge_pts(pts, M.ACC, every=2))
p.append(M.cap((gx + gs + M.TX) / 2, M.IC - 54, "mean of 64 answers", "one committee answer", color=M.ACC, name_color=M.ACC))

# confidence branch, anchored in an empty column
p.append(M.conf_branch(dil_x + 19))

# training row
p.append(M.loss_note(gx + gs / 2, M.IC + 92, gx + gs / 2 - 60,
                     ["smooth-L1: each patch vs its OWN true coord",
                      "crop center + rotated offset → 64× denser supervision"], M.ACC))

M.emit(str(Path(__file__).resolve().parent / "selftest_mid.json"), p)
print("wrote selftest_mid.json")
