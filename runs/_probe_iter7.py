"""One-off probe for iter 7: does train-set error keep falling with more
optimization steps (underfitting) or plateau early (capacity limit)?
Small subset, time-boxed — not the experiment itself. (No hamburg.)"""
import numpy as np, torch, time
from PIL import Image
from model.model import build_model, loss_fn
from pipeline.common import DATA_DIR, area_dir, load_meta
from pipeline.dataset import list_crops, extract_crop, crop_center_norm

area = "berlin"
meta = load_meta(area, DATA_DIR)
img = np.asarray(Image.open(area_dir(area, DATA_DIR) / "relight" / "midday.png"))
rng = np.random.default_rng(0)
crops = list_crops(area, meta["width"], meta["height"], "train")
picks = rng.choice(len(crops), size=800, replace=False)
xs, ys = [], []
for i in picks:
    c = crops[i]
    xs.append(extract_crop(img, c["cx"], c["cy"], float(rng.uniform(0, 360))))
    ys.append(crop_center_norm(meta, c["cx"], c["cy"]))
x = torch.from_numpy(np.stack(xs)).permute(0, 3, 1, 2).contiguous().float() / 255.0
y = torch.tensor(ys, dtype=torch.float32)

device = "mps" if torch.backends.mps.is_available() else "cpu"
torch.manual_seed(0)
model = build_model().to(device)
opt = torch.optim.Adam(model.parameters(), lr=1e-3)
x, y = x.to(device), y.to(device)
n = len(x)
t0 = time.time()
step = 0
for epoch in range(60):
    perm = torch.randperm(n)
    for i in range(0, n, 64):
        idx = perm[i:i + 64]
        out, logits = model(x[idx], return_logits=True)
        loss = loss_fn(out, logits, y[idx])
        opt.zero_grad(); loss.backward(); opt.step()
        step += 1
    if epoch % 5 == 4 or epoch == 0:
        model.eval()
        with torch.no_grad():
            o = model(x)
        err = ((o[:, :2] - y) ** 2).sum(1).sqrt() * meta["width"] * meta["gsd_m"]
        model.train()
        print(f"epoch {epoch+1:3d} step {step:5d} loss={loss.item():.4f} "
              f"train-median={err.median().item():7.1f} m  ({time.time()-t0:.0f}s)")
    if time.time() - t0 > 240:
        print("time box hit"); break
