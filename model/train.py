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

Exp 20: per-epoch location resampling. The kept trainer built ONE tensor --
6,000 locations per bucket, each at one frozen heading and one frozen relight
realization -- and passed over it every epoch, making per-crop memorization
the cheapest way down the training loss even though ~39k other enumerable
train locations per bucket were never seen. Locations, headings, and
realization assignment are now redrawn fresh at the start of every epoch
(same per-epoch crop count and gradient-step count), raising distinct
locations seen per bucket to ~30k over an 8-epoch run, each seen only ~1-2
times and never twice identically. Model, losses, decode, and calibration
are unchanged.

Exp 25: convergence-scaled training. A read-only probe of the kept exp-20
model showed train-split and eval-split unfiltered medians both ~1 km --
the fresh-draw sampler removed memorization, but the 8-epoch constant-LR
schedule (sized in the bootstrap era, when a few passes over one frozen
tensor sufficed to memorize) was cutting training off while loss was still
falling ~0.065/epoch. Training now runs 3x the epochs (EPOCH_MULT) with a
per-step cosine LR anneal to zero, so the same fresh-draw sampler is
finally trained to convergence instead of truncated mid-descent.

Usage: python -m model.train --area berlin --out-dir runs/<id> [--epochs 2]
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
MIN_KEEP_RATE = 0.40          # per-bucket keep floor at calibration (2x the scorer's 0.2 coverage floor)
SCORER_CONF_THRESHOLD = 0.3   # mirrors pipeline/score.py's frozen CONF_THRESHOLD; restated here, not imported
TRAIN_REALIZATIONS = 3        # exp 17: seeded relight re-renders per bucket, incl. the stored eval-matched one
EPOCH_MULT = 3                 # exp 25: convergence scaling -- the harness's --epochs is an outer budget fixed
                                # at bootstrap; the exp-20 fresh-draw sampler needs ~3x the steps to converge
                                # (loss still falling ~0.065/epoch at the old cutoff)
CONFUSABILITY_ALPHA = 0.5   # blend weight: 0=pure uniform (today), 1=pure confusability
NEIGHBOR_EXCLUDE_R = 1      # Chebyshev radius of spatially-adjacent cells to exclude when finding each cell's nearest lookalike, so the weight targets genuine distant confusion, not trivial local blur


def compute_cell_weights(area: str, data_dir: Path, meta: dict) -> np.ndarray:
    """One-time-per-area confusability weight per grid cell (exp 35): a cell
    whose average color/texture closely matches some DISTANT cell (excluding
    itself and its 8 spatial neighbors) gets a higher weight, so the sampler
    can oversample confusable cells relative to distinctive ones. Computed
    straight from reference.tif -- no per-epoch cost."""
    k = GRID_K
    with rasterio.open(area_dir(area, data_dir) / "reference.tif") as src:
        ref = src.read().transpose(1, 2, 0)  # HxWx3 uint8
    row_splits = np.array_split(ref, k, axis=0)
    cells = [np.array_split(r, k, axis=1) for r in row_splits]
    desc = np.zeros((k, k, 4), dtype=np.float64)
    for gy in range(k):
        for gx in range(k):
            block = cells[gy][gx].reshape(-1, 3).astype(np.float64)
            lum = block.mean(axis=1)
            desc[gy, gx] = [block[:, 0].mean(), block[:, 1].mean(), block[:, 2].mean(), lum.std()]
    flat = desc.reshape(k * k, 4)  # flat index = gy*k + gx, matches model.py's _grid_centers convention
    d2 = ((flat[:, None, :] - flat[None, :, :]) ** 2).sum(-1)  # [1024,1024]
    gyy, gxx = np.divmod(np.arange(k * k), k)
    cheb = np.maximum(np.abs(gxx[:, None] - gxx[None, :]), np.abs(gyy[:, None] - gyy[None, :]))
    d2 = np.where(cheb <= NEIGHBOR_EXCLUDE_R, np.inf, d2)  # exclude self + 8 neighbors
    nearest_d = np.sqrt(d2.min(axis=1))
    w = 1.0 / (nearest_d + 1e-3)
    del ref
    return w / w.mean()  # length-1024 array, mean 1.0


def prepare_realizations(area: str, data_dir: Path, out_dir: Path) -> Path:
    """Render each bucket's extra relight realizations (exp 17's seeded scheme)
    so per-epoch sampling only loads PNGs instead of re-running the relight sim.

    These renders are a DETERMINISTIC function of the frozen reference imagery,
    the frozen relight sim, and a stable per-(area, bucket, realization) seed —
    byte-identical every run. So they are cached PER AREA under RENDER_CACHE
    (default <repo>/render_cache/<area>/) and reused across experiments, instead
    of re-rendered into the per-run scratch that the loop purges (~1.5 GB and
    minutes of CPU per area, previously paid every experiment). Only missing
    realizations are rendered, so a warm cache skips the relight sim entirely.
    Writes are atomic (temp + rename) so an interrupted render can't leave a
    truncated PNG that later looks cached. Clear render_cache/ if the relight
    pipeline or the imagery ever changes."""
    cache_root = Path(os.environ.get("RENDER_CACHE", "render_cache"))
    renders_dir = cache_root / area
    renders_dir.mkdir(parents=True, exist_ok=True)
    todo = [(b, r) for b in LIGHTING_BUCKETS for r in range(1, TRAIN_REALIZATIONS)
            if not (renders_dir / f"{b}_r{r}.png").exists()]
    if not todo:
        return renders_dir  # warm cache — no relight sim needed
    meta = load_meta(area, data_dir)
    with rasterio.open(area_dir(area, data_dir) / "reference.tif") as src:
        ref = src.read().transpose(1, 2, 0)  # HxWx3 uint8
    for bucket, r in todo:
        img = relight(ref, LIGHTING_BUCKETS[bucket], meta["gsd_m"],
                     stable_hash(f"{area}:{bucket}:trainreal:{r}"))
        tmp = renders_dir / f".{bucket}_r{r}.png.tmp"
        Image.fromarray(img).save(tmp, format="PNG")  # ext is .tmp, so be explicit
        tmp.rename(renders_dir / f"{bucket}_r{r}.png")
        del img
    del ref
    return renders_dir


def sample_epoch(area: str, meta: dict, crops: list[dict], renders_dir: Path,
                 data_dir: Path, max_crops_per_bucket: int, rng, crop_probs):
    """Fresh draw of locations, headings, and realization assignment for one
    epoch (exp 20): only cues that transfer between locations reduce the
    training loss, since no crop is seen twice identically. Exp 35: the draw
    is confusability-weighted (crop_probs) instead of uniform."""
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
                angle = float(rng.uniform(0, 360))  # heading augmentation
                xs.append(extract_crop(img, c["cx"], c["cy"], angle))
                ys.append(crop_center_norm(meta, c["cx"], c["cy"]))
            del img
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
    crop_probs = crop_probs / crop_probs.sum()  # renormalize after the blend
    total_epochs = epochs * EPOCH_MULT
    n_per_epoch = 6 * min(max_crops_per_bucket, len(crops))
    steps_per_epoch = (n_per_epoch + 63) // 64
    total_steps = steps_per_epoch * total_epochs
    renders_dir = prepare_realizations(area, data_dir, out_dir)
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
        x, y = sample_epoch(area, meta, crops, renders_dir, data_dir,
                            max_crops_per_bucket, epoch_rng, crop_probs)
        n = len(x)
        print(f"[{area}] epoch {epoch + 1}/{total_epochs} {n} crops, device={device}")
        perm = torch.randperm(n)
        losses = []
        for i in range(0, n, 64):
            idx = perm[i:i + 64]
            xb = x[idx].to(device).permute(0, 3, 1, 2).contiguous().float().div_(255.0)
            yb = y[idx].to(device)
            out, logits = model(xb, return_logits=True)
            loss = loss_fn(out, logits, yb)
            opt.zero_grad(); loss.backward(); opt.step(); sched.step()
            losses.append(loss.item())
        print(f"[{area}] epoch {epoch + 1}/{total_epochs} loss={np.mean(losses):.4f}")
        del x, y

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
        "epoch_location_resampling": True,
        "total_epochs_run": total_epochs,
        "epoch_mult": EPOCH_MULT,
        "lr_schedule": f"cosine-per-step to 0 over {total_steps} steps",
        "confusability_alpha": CONFUSABILITY_ALPHA,
        "cell_weight_ratio_p90_p10": float(np.quantile(cell_w, 0.9) / np.quantile(cell_w, 0.1)),
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
