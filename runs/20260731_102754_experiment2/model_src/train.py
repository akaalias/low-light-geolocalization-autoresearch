"""AGENT-EDITABLE — training procedure. One model per area (CLAUDE.md §1).

Current: map-cell classification. Each EPOCH redraws a fresh random subset of
the full train lattice with fresh random rotations, so over the run the model
sees epochs*max_crops_per_bucket distinct (position, heading) vantages — the
coverage the C-way cell classifier needs, since one fixed draw of 6,000 crops
cannot cover ~3,000 cells.

Usage: python -m model.train --area berlin --out-dir runs/<id> [--epochs 2]
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from model.model import CELL_PX, build_model, export_onnx, grid_dims, loss_fn
from pipeline.common import DATA_DIR, LIGHTING_BUCKETS, area_dir, load_meta
from pipeline.dataset import extract_crop, list_crops


def load_scene(area: str, data_dir: Path):
    """Meta + the relight image(s). One pass-through bucket on this branch."""
    meta = load_meta(area, data_dir)
    imgs = [np.asarray(Image.open(area_dir(area, data_dir) / "relight" / f"{b}.png"))
            for b in LIGHTING_BUCKETS]
    crops = list_crops(area, meta["width"], meta["height"], "train")
    return meta, imgs, crops


def sample_epoch(meta, imgs, crops, max_crops_per_bucket: int, rng):
    """Draw a fresh crop subset with fresh rotations; return (x, cell_idx, off)."""
    gw, _ = grid_dims(meta)
    xs, cells, offs = [], [], []
    for img in imgs:
        picks = rng.choice(len(crops), size=min(max_crops_per_bucket, len(crops)),
                           replace=False)
        for i in picks:
            c = crops[i]
            cx, cy = c["cx"], c["cy"]
            angle = float(rng.uniform(0, 360))  # heading augmentation
            xs.append(extract_crop(img, cx, cy, angle))
            cells.append((cy // CELL_PX) * gw + (cx // CELL_PX))
            offs.append(((cx % CELL_PX) / CELL_PX - 0.5,
                         (cy % CELL_PX) / CELL_PX - 0.5))
    x = torch.from_numpy(np.stack(xs)).permute(0, 3, 1, 2).contiguous().float() / 255.0
    return (x, torch.tensor(cells, dtype=torch.int64),
            torch.tensor(offs, dtype=torch.float32))


def train_area(area: str, out_dir: Path, data_dir: Path, epochs: int,
               max_crops_per_bucket: int, seed: int) -> dict:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    device = "mps" if torch.backends.mps.is_available() else \
             "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.time()
    meta, imgs, crops = load_scene(area, data_dir)
    model = build_model(meta).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    n = 0
    print(f"[{area}] {len(crops)} lattice positions, {model.n_cells} cells, "
          f"device={device}")
    for epoch in range(epochs):
        # Fresh vantages every epoch, not one extract-once set reused.
        x, cell_idx, off = sample_epoch(meta, imgs, crops, max_crops_per_bucket, rng)
        n = len(x)
        model.train()
        perm = torch.randperm(n)
        losses = []
        for i in range(0, n, 64):
            idx = perm[i:i + 64]
            xb = x[idx].to(device)
            cb, ob = cell_idx[idx].to(device), off[idx].to(device)
            logits, off_pred = model.training_outputs(xb)
            loss = loss_fn(logits, off_pred, cb, ob)
            opt.zero_grad(); loss.backward(); opt.step()
            losses.append(loss.item())
        print(f"[{area}] epoch {epoch + 1}/{epochs} loss={np.mean(losses):.4f}")

    models_dir = out_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = models_dir / f"{area}.onnx"
    export_onnx(model.cpu(), str(onnx_path))
    return {
        "area": area,
        "n_train_crops": n,
        "epochs": epochs,
        "device": device,
        "train_seconds": round(time.time() - t0, 1),
        "onnx_bytes": onnx_path.stat().st_size,
        "init": "from-scratch",  # §9: log init strategy per experiment
        "n_cells": model.n_cells,
        "distinct_vantages_seen": epochs * max_crops_per_bucket,
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
