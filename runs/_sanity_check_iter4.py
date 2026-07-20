"""One-off sanity check for the dense scene-coordinate experiment (iter 4)."""
import numpy as np
import torch
import tempfile
import os

import model.train  # noqa: F401 — syntax/import check
import model.model as M
from pipeline.dataset import extract_crop

# 1) mean of per-cell targets == crop center, any angle
meta = {"width": 7000, "height": 6800}
for ang in [0, 37.3, 90, 211.9]:
    t = M.cell_target_grid(meta, 3210, 1234, ang)
    c = t.mean(axis=(1, 2))
    assert abs(c[0] - 3210 / 7000) < 1e-4 and abs(c[1] - 1234 / 6800) < 1e-4, (ang, c)
print("mean-decode unbiasedness OK")

# 2) rotation convention vs frozen extract_crop: encode map x/y in pixel values
# (coords < 250 to avoid uint8 clipping), compare patch-mean coords with q = R p.
H = W = 1200
yy, xx = np.mgrid[0:H, 0:W]
gx = np.repeat(xx[:, :, None], 3, 2).astype(np.float64)
gy = np.repeat(yy[:, :, None], 3, 2).astype(np.float64)
cx, cy, ang = 130, 120, 63.0
cgx = extract_crop(np.clip(gx, 0, 250).astype(np.uint8), cx, cy, ang).astype(float)
cgy = extract_crop(np.clip(gy, 0, 250).astype(np.uint8), cx, cy, ang).astype(float)
p = M.cell_offsets_px()
th = np.radians(ang)
qx = np.cos(th) * p[0] - np.sin(th) * p[1]
qy = np.sin(th) * p[0] + np.cos(th) * p[1]
maxerr = 0.0
for i in range(8):
    for j in range(8):
        mx = cgx[i * 16:(i + 1) * 16, j * 16:(j + 1) * 16, 0].mean() - cx
        my = cgy[i * 16:(i + 1) * 16, j * 16:(j + 1) * 16, 0].mean() - cy
        maxerr = max(maxerr, abs(mx - qx[i, j]), abs(my - qy[i, j]))
print(f"rotation-convention max abs error: {maxerr:.2f} px")
assert maxerr < 3.0, maxerr

# 3) model forward/loss/backward/export
m = M.build_model()
x = torch.rand(4, 3, 128, 128)
out, cells = m(x, return_cells=True)
assert out.shape == (4, 3) and cells.shape == (4, 2, 8, 8)
loss = M.loss_fn(out, cells, torch.rand(4, 2, 8, 8))
loss.backward()
print("forward/loss OK, params:", sum(pp.numel() for pp in m.parameters()))
f = tempfile.mktemp(suffix=".onnx")
M.export_onnx(M.build_model(), f)
import onnxruntime as ort
s = ort.InferenceSession(f, providers=["CPUExecutionProvider"])
r = s.run(None, {"frame": np.random.rand(1, 3, 128, 128).astype(np.float32)})[0]
assert r.shape == (1, 3) and 0 <= r[0, 2] <= 1
print("ONNX export OK:", os.path.getsize(f), "bytes")
os.unlink(f)
