"""AGENT-EDITABLE — training procedure. One model per area (CLAUDE.md §1).

Streams the FULL train lattice: each epoch consumes the next slice of a global
shuffled permutation of every lattice position, extracting each crop on the fly
with a freshly drawn rotation at every visit. Same step count as the previous
load-once-static-tensor procedure, spent on distinct vantages instead of a
small subsample replayed every epoch.

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


def train_area(area: str, out_dir: Path, data_dir: Path, epochs: int,
               max_crops_per_bucket: int, seed: int) -> dict:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    device = "mps" if torch.backends.mps.is_available() else \
             "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.time()

    meta = load_meta(area, data_dir)
    # The FULL lattice — never subsampled; the permutation below decides which
    # vantages a given epoch visits.
    crops = list_crops(area, meta["width"], meta["height"], "train")
    buckets = list(LIGHTING_BUCKETS)
    # Each bucket's scene stays uint8 in RAM; only a minibatch is ever float.
    images = {
        b: np.asarray(Image.open(area_dir(area, data_dir) / "relight" / f"{b}.png"))
        for b in buckets
    }

    model = build_model().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)

    crops_per_epoch = min(max_crops_per_bucket * len(buckets), len(crops))
    perm = rng.permutation(len(crops))
    cursor = 0
    visited = set()
    presentations = 0
    print(f"[{area}] {len(crops)} lattice vantages, {crops_per_epoch}/epoch, "
          f"device={device}")

    for epoch in range(epochs):
        if cursor + crops_per_epoch > len(perm):
            perm = rng.permutation(len(crops))
            cursor = 0
        epoch_idx = perm[cursor:cursor + crops_per_epoch]
        cursor += crops_per_epoch
        visited.update(int(i) for i in epoch_idx)

        losses = []
        for i in range(0, len(epoch_idx), 64):
            batch_idx = epoch_idx[i:i + 64]
            xs, ys = [], []
            for j in batch_idx:
                c = crops[int(j)]
                bucket = buckets[int(rng.integers(len(buckets)))]
                angle = float(rng.uniform(0, 360))  # fresh heading per visit
                xs.append(extract_crop(images[bucket], c["cx"], c["cy"], angle))
                ys.append(crop_center_norm(meta, c["cx"], c["cy"]))
            xb = torch.from_numpy(np.stack(xs)).permute(0, 3, 1, 2)
            xb = xb.contiguous().float().div_(255.0).to(device)
            yb = torch.tensor(ys, dtype=torch.float32).to(device)
            loss = loss_fn(model(xb), yb)
            opt.zero_grad(); loss.backward(); opt.step()
            losses.append(loss.item())
            presentations += len(batch_idx)
        print(f"[{area}] epoch {epoch + 1}/{epochs} loss={np.mean(losses):.4f}")

    models_dir = out_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = models_dir / f"{area}.onnx"
    export_onnx(model.cpu(), str(onnx_path))
    return {
        "area": area,
        # Semantic change vs. earlier experiments: this is now the total number
        # of crop presentations (epochs x crops_per_epoch), not the size of a
        # preloaded static subsample that was replayed each epoch.
        "n_train_crops": presentations,
        "distinct_train_vantages": len(visited),
        "presentations": presentations,
        "epochs": epochs,
        "device": device,
        "train_seconds": round(time.time() - t0, 1),
        "onnx_bytes": onnx_path.stat().st_size,
        "init": "from-scratch",  # §9: log init strategy per experiment
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
