"""Scratch copy of model/train.py (champion, exp 35) with timing
instrumentation added to train_area. NOT part of the repo's agent-editable
surface -- shipped to Modal directly as a string via infra/modal_client.py's
own mechanism, never written into the live model/ directory, so it can't
collide with the autoresearch loop's in-flight iter-61 design/implement work.

Only change from the real model/train.py: timing collection around each
phase of train_area, added to the returned info dict as "timing_breakdown".
"""

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import rasterio
import torch
from PIL import Image

from model.model import GRID_K, build_model, export_onnx, loss_fn
from pipeline.common import DATA_DIR, LIGHTING_BUCKETS, area_dir, load_meta, stable_hash
from pipeline.dataset import crop_center_norm, extract_crop, list_crops
from pipeline.relight import relight

CAL_CROPS_PER_BUCKET = 400
MIN_KEEP_RATE = 0.40
SCORER_CONF_THRESHOLD = 0.3
TRAIN_REALIZATIONS = 3
EPOCH_MULT = 3
CONFUSABILITY_ALPHA = 0.5
NEIGHBOR_EXCLUDE_R = 1


def compute_cell_weights(area, data_dir, meta):
    k = GRID_K
    with rasterio.open(area_dir(area, data_dir) / "reference.tif") as src:
        ref = src.read().transpose(1, 2, 0)
    row_splits = np.array_split(ref, k, axis=0)
    cells = [np.array_split(r, k, axis=1) for r in row_splits]
    desc = np.zeros((k, k, 4), dtype=np.float64)
    for gy in range(k):
        for gx in range(k):
            block = cells[gy][gx].reshape(-1, 3).astype(np.float64)
            lum = block.mean(axis=1)
            desc[gy, gx] = [block[:, 0].mean(), block[:, 1].mean(), block[:, 2].mean(), lum.std()]
    flat = desc.reshape(k * k, 4)
    d2 = ((flat[:, None, :] - flat[None, :, :]) ** 2).sum(-1)
    gyy, gxx = np.divmod(np.arange(k * k), k)
    cheb = np.maximum(np.abs(gxx[:, None] - gxx[None, :]), np.abs(gyy[:, None] - gyy[None, :]))
    d2 = np.where(cheb <= NEIGHBOR_EXCLUDE_R, np.inf, d2)
    nearest_d = np.sqrt(d2.min(axis=1))
    w = 1.0 / (nearest_d + 1e-3)
    del ref
    return w / w.mean()


def prepare_realizations(area, data_dir, out_dir):
    cache_root = Path(os.environ.get("RENDER_CACHE", "render_cache"))
    renders_dir = cache_root / area
    renders_dir.mkdir(parents=True, exist_ok=True)
    todo = [(b, r) for b in LIGHTING_BUCKETS for r in range(1, TRAIN_REALIZATIONS)
            if not (renders_dir / f"{b}_r{r}.png").exists()]
    if not todo:
        return renders_dir
    meta = load_meta(area, data_dir)
    with rasterio.open(area_dir(area, data_dir) / "reference.tif") as src:
        ref = src.read().transpose(1, 2, 0)
    for bucket, r in todo:
        img = relight(ref, LIGHTING_BUCKETS[bucket], meta["gsd_m"],
                     stable_hash(f"{area}:{bucket}:trainreal:{r}"))
        tmp = renders_dir / f".{bucket}_r{r}.png.tmp"
        Image.fromarray(img).save(tmp, format="PNG")
        tmp.rename(renders_dir / f"{bucket}_r{r}.png")
        del img
    del ref
    return renders_dir


def sample_epoch(area, meta, crops, renders_dir, data_dir, max_crops_per_bucket, rng, crop_probs):
    xs, ys = [], []
    for bucket in LIGHTING_BUCKETS:
        picks = rng.choice(len(crops), size=min(max_crops_per_bucket, len(crops)),
                           replace=False, p=crop_probs)
        for r in range(TRAIN_REALIZATIONS):
            part = picks[r::TRAIN_REALIZATIONS]
            if r == 0:
                img = np.asarray(Image.open(area_dir(area, data_dir) / "relight" / f"{bucket}.png"))
            else:
                img = np.asarray(Image.open(renders_dir / f"{bucket}_r{r}.png"))
            for i in part:
                c = crops[i]
                angle = float(rng.uniform(0, 360))
                xs.append(extract_crop(img, c["cx"], c["cy"], angle))
                ys.append(crop_center_norm(meta, c["cx"], c["cy"]))
            del img
    x = torch.from_numpy(np.stack(xs))
    y = torch.tensor(ys, dtype=torch.float32)
    return x, y


def calibrate_conf_shift(model, area, data_dir, device, rng):
    meta = load_meta(area, data_dir)
    crops = list_crops(area, meta["width"], meta["height"], "train")
    model.eval()
    z_by_bucket = {}
    with torch.no_grad():
        for bucket in LIGHTING_BUCKETS:
            img = np.asarray(Image.open(area_dir(area, data_dir) / "relight" / f"{bucket}.png"))
            picks = rng.choice(len(crops), size=min(CAL_CROPS_PER_BUCKET, len(crops)), replace=False)
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


def train_area(area, out_dir, data_dir, epochs, max_crops_per_bucket, seed):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    device = "mps" if torch.backends.mps.is_available() else \
             "cuda" if torch.cuda.is_available() else "cpu"

    def sync():
        if device == "cuda":
            torch.cuda.synchronize()

    timing = {"setup": 0.0, "render_prep": 0.0, "sample_epoch": 0.0,
              "transfer": 0.0, "forward_backward": 0.0, "calibrate": 0.0,
              "export": 0.0}

    t0 = time.time()
    t_a = time.time()
    meta = load_meta(area, data_dir)
    crops = list_crops(area, meta["width"], meta["height"], "train")
    cell_w = compute_cell_weights(area, data_dir, meta)
    crop_cell = np.array([
        (min(int(meta_v * GRID_K), GRID_K - 1)) * GRID_K + min(int(meta_u * GRID_K), GRID_K - 1)
        for meta_u, meta_v in (crop_center_norm(meta, c["cx"], c["cy"]) for c in crops)
    ])
    raw_w = cell_w[crop_cell]
    uniform = np.full(len(crops), 1.0 / len(crops))
    weighted = raw_w / raw_w.sum()
    crop_probs = CONFUSABILITY_ALPHA * weighted + (1 - CONFUSABILITY_ALPHA) * uniform
    crop_probs = crop_probs / crop_probs.sum()
    total_epochs = epochs * EPOCH_MULT
    n_per_epoch = 6 * min(max_crops_per_bucket, len(crops))
    steps_per_epoch = (n_per_epoch + 63) // 64
    total_steps = steps_per_epoch * total_epochs
    timing["setup"] = time.time() - t_a

    t_a = time.time()
    renders_dir = prepare_realizations(area, data_dir, out_dir)
    timing["render_prep"] = time.time() - t_a

    model = build_model().to(device)
    trunk_params = list(model.features.parameters())
    trunk_ids = {id(p) for p in trunk_params}
    head_params = [p for p in model.parameters() if id(p) not in trunk_ids]
    opt = torch.optim.Adam([
        {"params": trunk_params, "lr": 1e-4},
        {"params": head_params, "lr": 1e-3},
    ])
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=total_steps, eta_min=0.0)
    n = 0
    for epoch in range(total_epochs):
        epoch_rng = np.random.default_rng([seed, epoch])
        t_a = time.time()
        x, y = sample_epoch(area, meta, crops, renders_dir, data_dir,
                            max_crops_per_bucket, epoch_rng, crop_probs)
        timing["sample_epoch"] += time.time() - t_a
        n = len(x)
        print(f"[{area}] epoch {epoch + 1}/{total_epochs} {n} crops, device={device}")
        perm = torch.randperm(n)
        losses = []
        for i in range(0, n, 64):
            idx = perm[i:i + 64]
            t_a = time.time()
            xb = x[idx].to(device).permute(0, 3, 1, 2).contiguous().float().div_(255.0)
            yb = y[idx].to(device)
            sync()
            timing["transfer"] += time.time() - t_a

            t_a = time.time()
            out, logits = model(xb, return_logits=True)
            loss = loss_fn(out, logits, yb)
            opt.zero_grad(); loss.backward(); opt.step(); sched.step()
            losses.append(loss.item())  # forces a sync via .item()
            timing["forward_backward"] += time.time() - t_a
        print(f"[{area}] epoch {epoch + 1}/{total_epochs} loss={np.mean(losses):.4f}")
        del x, y

    t_a = time.time()
    cal = calibrate_conf_shift(model, area, data_dir, device, rng)
    timing["calibrate"] = time.time() - t_a

    t_a = time.time()
    models_dir = out_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = models_dir / f"{area}.onnx"
    export_onnx(model.cpu(), str(onnx_path))
    timing["export"] = time.time() - t_a

    info = {
        "area": area,
        "n_train_crops": n,
        "epochs": epochs,
        "device": device,
        "train_seconds": round(time.time() - t0, 1),
        "onnx_bytes": onnx_path.stat().st_size,
        "total_epochs_run": total_epochs,
        "timing_breakdown": {k: round(v, 2) for k, v in timing.items()},
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
