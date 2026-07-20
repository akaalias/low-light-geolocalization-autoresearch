import numpy as np, torch, tempfile, os
import model.train  # syntax check
from model.model import (DenseLocNet, GRID, build_model, cell_target_grid,
                         export_onnx, loss_fn)
from pipeline.dataset import extract_crop

# 1. dummy forward / loss / backward
m = build_model()
x = torch.rand(4, 3, 128, 128)
uv, w = m.forward_dense(x)
assert uv.shape == (4, 2, GRID, GRID) and w.shape == (4, GRID, GRID), (uv.shape, w.shape)
y = torch.rand(4, 2, GRID, GRID)
loss = loss_fn(uv, w, y)
loss.backward()
print("dense forward/loss/backward OK, loss =", float(loss))

# 2. contract forward + ONNX export
out = m(x)
assert out.shape == (4, 3), out.shape
assert (out >= 0).all() and (out <= 1).all()
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, "t.onnx")
    export_onnx(m, p)
    import onnxruntime as ort
    sess = ort.InferenceSession(p, providers=["CPUExecutionProvider"])
    feed = dict(frame=np.random.rand(1, 3, 128, 128).astype(np.float32))
    r = sess.run(None, feed)[0]
    assert r.shape == (1, 3), r.shape
    print("ONNX export + [[u,v,conf]] contract OK, size =", os.path.getsize(p), "bytes")

# 3. cell_target_grid vs extract_crop geometry (coordinate-ramp image)
H = W = 400
ys_, xs_ = np.mgrid[0:H, 0:W]
img = np.zeros((H, W, 3), dtype=np.uint8)
img[..., 0] = (xs_ * 0.5).astype(np.uint8)
img[..., 1] = (ys_ * 0.5).astype(np.uint8)
meta = dict(width=W, height=H)
worst = 0.0
for angle in [0.0, 30.0, 137.0, 251.5, 359.0]:
    crop = extract_crop(img, 200, 210, angle)
    tgt = cell_target_grid(meta, 200, 210, angle)  # 2 x G x G
    for i in range(GRID):
        for j in range(GRID):
            cell = crop[i * 16:(i + 1) * 16, j * 16:(j + 1) * 16]
            x_obs = cell[..., 0].astype(np.float64).mean() * 2.0
            y_obs = cell[..., 1].astype(np.float64).mean() * 2.0
            worst = max(worst,
                        abs(tgt[0, i, j] * W - x_obs),
                        abs(tgt[1, i, j] * H - y_obs))
print(f"cell_target_grid vs extract_crop: max |err| = {worst:.2f} px (uint8 quantization floor ~1-2 px)")
assert worst < 3.0
print("all checks passed")
