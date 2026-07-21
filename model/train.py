"""AGENT-EDITABLE — training procedure. One model per area (CLAUDE.md §1).

Baseline: sample train-split crops from all six relight buckets with random
rotation augmentation, train TinyLocNet briefly, export ONNX.

Training scale (exp 7): 6,000 of the ~45k enumerable train locations per
bucket (was 800 / ~1.8%, which left a quarter of the 32x32 field cells with
zero training example in any given lighting bucket). The training tensor is
held as uint8 and converted to float per minibatch — 36k float32 crops would
be ~7 GB; uint8 is ~1.8 GB.

Exp 11: the encoder is now an ImageNet-pretrained trunk (model.py), fine-tuned
gently rather than trained from scratch — trunk params use a 10x lower LR
than the freshly-initialized head params, so early large head gradients
don't wash out the transferred features before they adapt.

Exp 12: model.py adds a gated dark-expert field head; its new params (dark
head + gate MLP) are fresh-initialized and fall into the existing "head"
param group here unchanged, so they train at the same 1e-3 LR as the rest
of the head — no changes needed to this file's training loop.

Exp 15: after the epoch loop, the new conf head (model.py) is calibrated on
fresh-rotation TRAIN-split crops per lighting bucket so that the frozen
scorer's fixed conf >= 0.3 abstention threshold keeps >= 40% of crops in
every bucket (double the scorer's 0.2 coverage floor) before ONNX export;
the resulting conf_shift buffer is exported with the model.

Exp 17: night is the binding constraint everywhere, and a stored night
render freezes one seeded roll of the relight sim's stochastic nuisances
(sensor noise, lamp thinning) that differs roll-to-roll by ~half the image's
content -- so the 1024-way head was memorizing roll-specific texture that
can't transfer to held-out locations. Each bucket's training crops are now
drawn from three seeded realizations of the frozen pipeline.relight.relight
function (the stored eval-matched render plus two fresh re-renders), so only
seed-stable structure stays discriminative between locations. Eval renders,
model, losses, decode, and calibration are unchanged.

Usage: python -m model.train --area berlin --out-dir runs/<id> [--epochs 2]
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import rasterio
import torch
from PIL import Image

from model.model import build_model, export_onnx, loss_fn
from pipeline.common import DATA_DIR, LIGHTING_BUCKETS, area_dir, load_meta, stable_hash
from pipeline.dataset import crop_center_norm, extract_crop, list_crops
from pipeline.relight import relight

CAL_CROPS_PER_BUCKET = 400
MIN_KEEP_RATE = 0.40          # per-bucket keep floor at calibration (2x the scorer's 0.2 coverage floor)
SCORER_CONF_THRESHOLD = 0.3   # mirrors pipeline/score.py's frozen CONF_THRESHOLD; restated here, not imported
TRAIN_REALIZATIONS = 3        # exp 17: seeded relight re-renders per bucket, incl. the stored eval-matched one


def load_training_tensors(area: str, data_dir: Path, max_crops_per_bucket: int, rng):
    meta = load_meta(area, data_dir)
    crops = list_crops(area, meta["width"], meta["height"], "train")
    xs, ys = [], []
    with rasterio.open(area_dir(area, data_dir) / "reference.tif") as src:
        ref = src.read().transpose(1, 2, 0)  # HxWx3 uint8
    for bucket in LIGHTING_BUCKETS:
        picks = rng.choice(len(crops), size=min(max_crops_per_bucket, len(crops)),
                           replace=False)
        for r in range(TRAIN_REALIZATIONS):
            part = picks[r::TRAIN_REALIZATIONS]
            if r == 0:
                img = np.asarray(Image.open(area_dir(area, data_dir) / "relight" / f"{bucket}.png"))
            else:
                img = relight(ref, LIGHTING_BUCKETS[bucket], meta["gsd_m"],
                             stable_hash(f"{area}:{bucket}:trainreal:{r}"))
            for i in part:
                c = crops[i]
                angle = float(rng.uniform(0, 360))  # heading augmentation
                xs.append(extract_crop(img, c["cx"], c["cy"], angle))
                ys.append(crop_center_norm(meta, c["cx"], c["cy"]))
            del img
    del ref
    x = torch.from_numpy(np.stack(xs))  # uint8 NxHxWx3; float-converted per batch
    y = torch.tensor(ys, dtype=torch.float32)
    return x, y


def calibrate_conf_shift(model, area: str, data_dir: Path, device: str, rng) -> dict:
    """Set model.conf_shift so the scorer's fixed 0.3 threshold keeps >=
    MIN_KEEP_RATE of crops in every lighting bucket (TRAIN split only)."""
    meta = load_meta(area, data_dir)
    crops = list_crops(area, meta["width"], meta["height"], "train")
    model.eval()
    z_by_bucket = {}
    with torch.no_grad():
        for bucket in LIGHTING_BUCKETS:
            img = np.asarray(Image.open(area_dir(area, data_dir) / "relight" / f"{bucket}.png"))
            picks = rng.choice(len(crops), size=min(CAL_CROPS_PER_BUCKET, len(crops)),
                               replace=False)
            xs = []
            for i in picks:
                c = crops[i]
                angle = float(rng.uniform(0, 360))
                xs.append(extract_crop(img, c["cx"], c["cy"], angle))
            xb_all = torch.from_numpy(np.stack(xs))
            confs = []
            for i in range(0, len(xb_all), 64):
                xb = xb_all[i:i + 64].to(device).permute(0, 3, 1, 2).contiguous().float().div_(255.0)
                out = model(xb)
                confs.append(out[:, 2].cpu().numpy())
            conf_values = np.concatenate(confs)
            c = np.clip(conf_values, 1e-6, 1 - 1e-6)
            z_by_bucket[bucket] = np.log(c / (1 - c))

    t_per_bucket = {b: float(np.quantile(z, 1.0 - MIN_KEEP_RATE)) for b, z in z_by_bucket.items()}
    T = min(t_per_bucket.values())
    with torch.no_grad():
        model.conf_shift.fill_(T - float(np.log(SCORER_CONF_THRESHOLD / (1.0 - SCORER_CONF_THRESHOLD))) - 1e-4)
    return {
        "conf_shift": float(model.conf_shift.item()),
        "cal_logit_threshold": float(T),
        "cal_keep_rate_per_bucket": {b: float(np.mean(z > T - 1e-4)) for b, z in z_by_bucket.items()},
    }


def train_area(area: str, out_dir: Path, data_dir: Path, epochs: int,
               max_crops_per_bucket: int, seed: int) -> dict:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    device = "mps" if torch.backends.mps.is_available() else \
             "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.time()
    x, y = load_training_tensors(area, data_dir, max_crops_per_bucket, rng)
    model = build_model().to(device)
    trunk_params = list(model.features.parameters())
    trunk_ids = {id(p) for p in trunk_params}
    head_params = [p for p in model.parameters() if id(p) not in trunk_ids]
    opt = torch.optim.Adam([
        {"params": trunk_params, "lr": 1e-4},
        {"params": head_params, "lr": 1e-3},
    ])
    n = len(x)
    print(f"[{area}] {n} crops, device={device}")
    for epoch in range(epochs):
        perm = torch.randperm(n)
        losses = []
        for i in range(0, n, 64):
            idx = perm[i:i + 64]
            xb = x[idx].to(device).permute(0, 3, 1, 2).contiguous().float().div_(255.0)
            yb = y[idx].to(device)
            out, logits = model(xb, return_logits=True)
            loss = loss_fn(out, logits, yb)
            opt.zero_grad(); loss.backward(); opt.step()
            losses.append(loss.item())
        print(f"[{area}] epoch {epoch + 1}/{epochs} loss={np.mean(losses):.4f}")

    cal = calibrate_conf_shift(model, area, data_dir, device, rng)

    models_dir = out_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = models_dir / f"{area}.onnx"
    export_onnx(model.cpu(), str(onnx_path))
    info = {
        "area": area,
        "n_train_crops": n,
        "epochs": epochs,
        "device": device,
        "train_seconds": round(time.time() - t0, 1),
        "onnx_bytes": onnx_path.stat().st_size,
        # §9: log init strategy per experiment
        "init": "pretrained:mobilenet_v3_small IMAGENET1K_V1 features[0..8] (torchvision, BSD-3)",
        "train_realizations": TRAIN_REALIZATIONS,
    }
    info.update(cal)
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--max-crops-per-bucket", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR
    out_dir = Path(args.out_dir)
    info = train_area(args.area, out_dir, data_dir, args.epochs,
                      args.max_crops_per_bucket, args.seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    train_log = out_dir / "train_info.json"
    logs = json.loads(train_log.read_text()) if train_log.exists() else []
    logs.append(info)
    train_log.write_text(json.dumps(logs, indent=2))
    print(json.dumps(info))


if __name__ == "__main__":
    main()
