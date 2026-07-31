"""AGENT-EDITABLE — training procedure. One model per area (CLAUDE.md §1).

Current: map-cell classification with FULL-LATTICE coverage. Each EPOCH is one
complete pass over ALL train-lattice positions (not a random subsample), with a
fresh random rotation drawn per position per epoch, so over the run the model
sees epochs*len(crops) distinct (position, heading) vantages and every map cell
is visited many times — the coverage a C-way cell classifier needs to memorize
its box. Positions are streamed in shuffled chunks of CHUNK_SIZE so only one
chunk of pixels is ever resident. `--max-crops-per-bucket` is still accepted for
CLI compatibility but no longer controls sampling; it is logged as
`max_crops_per_bucket_arg`.

Usage: python -m model.train --area berlin --out-dir runs/<id> [--epochs 2]
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from model.model import CELL_PX, build_model, export_onnx, grid_dims, loss_fn
from pipeline.common import DATA_DIR, LIGHTING_BUCKETS, area_dir, load_meta
from pipeline.dataset import extract_crop, list_crops

CHUNK_SIZE = 4096  # lattice positions extracted at a time (bounds memory)
BATCH_SIZE = 64


def load_scene(area: str, data_dir: Path):
    """Meta + the relight image(s). One pass-through bucket on this branch."""
    meta = load_meta(area, data_dir)
    imgs = [np.asarray(Image.open(area_dir(area, data_dir) / "relight" / f"{b}.png"))
            for b in LIGHTING_BUCKETS]
    crops = list_crops(area, meta["width"], meta["height"], "train")
    return meta, imgs, crops


def extract_chunk(meta, img, crops, indices, rng):
    """Extract one chunk of vantages; return (x_uint8, cell_idx, offset)."""
    gw, _ = grid_dims(meta)
    xs, cells, offs = [], [], []
    for i in indices:
        c = crops[i]
        cx, cy = c["cx"], c["cy"]
        angle = float(rng.uniform(0, 360))  # heading augmentation
        xs.append(extract_crop(img, cx, cy, angle))
        cells.append((cy // CELL_PX) * gw + (cx // CELL_PX))
        offs.append(((cx % CELL_PX) / CELL_PX - 0.5,
                     (cy % CELL_PX) / CELL_PX - 0.5))
    x = torch.from_numpy(np.stack(xs)).permute(0, 3, 1, 2).contiguous()
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
    # A 12x-longer schedule wants a decaying LR, not the constant 1e-3.
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs,
                                                       eta_min=1e-4)
    print(f"[{area}] {len(crops)} lattice positions, {model.n_cells} cells, "
          f"device={device}")
    final_top1 = 0.0
    for epoch in range(epochs):
        model.train()
        loss_sum, correct, conf_sum, seen = 0.0, 0, 0.0, 0
        for img in imgs:
            # One full pass over the whole lattice, shuffled, fresh rotations.
            order = rng.permutation(len(crops))
            for start in range(0, len(order), CHUNK_SIZE):
                x_u8, cell_idx, off = extract_chunk(
                    meta, img, crops, order[start:start + CHUNK_SIZE], rng)
                n = len(x_u8)
                perm = torch.randperm(n)
                for i in range(0, n, BATCH_SIZE):
                    idx = perm[i:i + BATCH_SIZE]
                    xb = x_u8[idx].to(device).float() / 255.0
                    cb, ob = cell_idx[idx].to(device), off[idx].to(device)
                    logits, off_pred = model.training_outputs(xb)
                    loss = loss_fn(logits, off_pred, cb, ob)
                    opt.zero_grad(); loss.backward(); opt.step()
                    with torch.no_grad():
                        loss_sum += loss.item() * len(idx)
                        correct += int((logits.argmax(dim=1) == cb).sum())
                        conf_sum += float(F.softmax(logits, dim=1).max(dim=1).values.sum())
                        seen += len(idx)
                del x_u8, cell_idx, off
        sched.step()
        final_top1 = correct / max(seen, 1)
        print(f"[{area}] epoch {epoch + 1}/{epochs} loss={loss_sum / max(seen, 1):.4f} "
              f"top1={final_top1:.4f} mean_max_softmax={conf_sum / max(seen, 1):.4f} "
              f"views={seen} lr={sched.get_last_lr()[0]:.2e}")

    models_dir = out_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = models_dir / f"{area}.onnx"
    export_onnx(model.cpu(), str(onnx_path))
    return {
        "area": area,
        "n_train_crops": epochs * len(crops) * len(imgs),
        "epochs": epochs,
        "device": device,
        "train_seconds": round(time.time() - t0, 1),
        "onnx_bytes": onnx_path.stat().st_size,
        "init": "from-scratch",  # §9: log init strategy per experiment
        "n_cells": model.n_cells,
        "distinct_vantages_seen": epochs * len(crops) * len(imgs),
        "full_lattice_epochs": True,
        "final_train_top1": round(final_top1, 4),
        "chunk_size": CHUNK_SIZE,
        "max_crops_per_bucket_arg": max_crops_per_bucket,
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
