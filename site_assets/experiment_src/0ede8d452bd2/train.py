"""AGENT-EDITABLE — training procedure. One model per area (CLAUDE.md §1).

Train TinyLocNet to convergence on train-split crops from every relight bucket:
crop SELECTION is re-drawn at random from the full train list before every
epoch, and crop EXTRACTION is re-run every epoch with fresh random rotations,
so a long budget buys dataset-scale coverage instead of memorizing one frozen
subset of vantage points.

Usage: python -m model.train --area berlin --out-dir runs/<id> [--epochs 2]
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from model.model import build_model, export_onnx, loss_fn
from pipeline.common import DATA_DIR, LIGHTING_BUCKETS, area_dir, load_meta
from pipeline.dataset import crop_center_norm, extract_crop, list_crops


# The harness passes --epochs 8 (loop.sh EPOCHS, sized for the harness-proving
# baseline); 12x gives the 96 effective epochs this design needs to converge.
EPOCH_MULT = 12
ROT_POOL = 8          # fallback: pre-rotated variants per crop
EXTRACT_BUDGET_S = 15.0  # per-epoch extraction cost above which we fall back


def load_area_assets(area: str, data_dir: Path):
    """Load the per-bucket relight images and the FULL train-split crop list once.

    No sampling happens here — which positions get trained on is decided fresh
    every epoch by sample_epoch_plan.
    """
    meta = load_meta(area, data_dir)
    buckets = [(bucket,
                np.asarray(Image.open(area_dir(area, data_dir) / "relight" / f"{bucket}.png")))
               for bucket in LIGHTING_BUCKETS]
    crops = list_crops(area, meta["width"], meta["height"], "train")
    return meta, buckets, crops


def sample_epoch_plan(buckets, crops, meta, max_crops_per_bucket, rng):
    """Draw this epoch's crop positions at random from the full train list.

    Targets are rotation-invariant (extract_crop rotates about the crop center),
    so y depends only on the drawn positions, not on the heading.
    """
    plan, ys = [], []
    for _bucket, img in buckets:
        picks = rng.choice(len(crops), size=min(max_crops_per_bucket, len(crops)),
                           replace=False)
        for i in picks:
            c = crops[i]
            plan.append((img, c["cx"], c["cy"]))
            ys.append(crop_center_norm(meta, c["cx"], c["cy"]))
    y = torch.tensor(ys, dtype=torch.float32)
    return plan, y


def _to_tensor(xs) -> torch.Tensor:
    return torch.from_numpy(np.stack(xs)).permute(0, 3, 1, 2).contiguous().float() / 255.0


def epoch_tensor(plan, rng) -> torch.Tensor:
    """This epoch's crops, each at a fresh random heading."""
    return _to_tensor([extract_crop(img, cx, cy, float(rng.uniform(0, 360)))
                       for img, cx, cy in plan])


def build_rot_pool(plan, rng) -> list:
    """Fallback when per-epoch extraction is too slow: ROT_POOL rotated uint8
    variants per crop, sampled from thereafter."""
    return [np.stack([extract_crop(img, cx, cy, float(rng.uniform(0, 360)))
                      for _ in range(ROT_POOL)]) for img, cx, cy in plan]


def epoch_tensor_from_pool(pool, rng) -> torch.Tensor:
    return _to_tensor([variants[rng.integers(ROT_POOL)] for variants in pool])


def train_area(area: str, out_dir: Path, data_dir: Path, epochs: int,
               max_crops_per_bucket: int, seed: int) -> dict:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    device = "mps" if torch.backends.mps.is_available() else \
             "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.time()
    total_epochs = epochs * EPOCH_MULT
    meta, buckets, crops = load_area_assets(area, data_dir)
    model = build_model().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        opt, T_max=total_epochs, eta_min=1e-5)
    n = len(buckets) * min(max_crops_per_bucket, len(crops))
    print(f"[{area}] {n} crops/epoch drawn from {len(crops)} train positions, "
          f"device={device}, epochs={total_epochs}")
    pool, plan, y = None, None, None
    for epoch in range(total_epochs):
        if pool is None:
            # Fresh draw of positions every epoch: over the full budget the model
            # sees essentially the whole train split, not one frozen subset.
            plan, y = sample_epoch_plan(buckets, crops, meta,
                                        max_crops_per_bucket, rng)
        te = time.time()
        x = epoch_tensor_from_pool(pool, rng) if pool is not None \
            else epoch_tensor(plan, rng)
        extract_s = time.time() - te
        n = len(plan)
        perm = torch.randperm(n)
        losses = []
        for i in range(0, n, 64):
            idx = perm[i:i + 64]
            xb, yb = x[idx].to(device), y[idx].to(device)
            loss = loss_fn(model.forward_logits(xb), yb)
            opt.zero_grad(); loss.backward(); opt.step()
            losses.append(loss.item())
        scheduler.step()
        print(f"[{area}] epoch {epoch + 1}/{total_epochs} "
              f"loss={np.mean(losses):.4f} extract={extract_s:.1f}s")
        if pool is None and extract_s > EXTRACT_BUDGET_S:
            # Too slow to re-extract every epoch: freeze this epoch's positions
            # and amortize into a sampled rotation pool rather than dropping
            # fresh rotations altogether. No further position resampling.
            print(f"[{area}] extraction {extract_s:.1f}s > {EXTRACT_BUDGET_S}s, "
                  f"freezing positions and switching to a {ROT_POOL}-variant "
                  f"rotation pool")
            pool = build_rot_pool(plan, rng)

    models_dir = out_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = models_dir / f"{area}.onnx"
    export_onnx(model.cpu(), str(onnx_path))
    return {
        "area": area,
        "n_train_crops": n,
        "epochs": total_epochs,
        "harness_epochs": epochs,
        "epoch_mult": EPOCH_MULT,
        "device": device,
        "train_seconds": round(time.time() - t0, 1),
        "onnx_bytes": onnx_path.stat().st_size,
        "init": "from-scratch",  # §9: log init strategy per experiment
        "position_sampling": "per-epoch",
        "distinct_positions_available": len(crops),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--max-crops-per-bucket", type=int, default=800)
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
