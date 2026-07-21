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


def load_training_tensors(area: str, data_dir: Path, max_crops_per_bucket: int, rng):
    meta = load_meta(area, data_dir)
    crops = list_crops(area, meta["width"], meta["height"], "train")
    xs, ys = [], []
    for bucket in LIGHTING_BUCKETS:
        img = np.asarray(Image.open(area_dir(area, data_dir) / "relight" / f"{bucket}.png"))
        picks = rng.choice(len(crops), size=min(max_crops_per_bucket, len(crops)),
                           replace=False)
        for i in picks:
            c = crops[i]
            angle = float(rng.uniform(0, 360))  # heading augmentation
            xs.append(extract_crop(img, c["cx"], c["cy"], angle))
            ys.append(crop_center_norm(meta, c["cx"], c["cy"]))
    x = torch.from_numpy(np.stack(xs))  # uint8 NxHxWx3; float-converted per batch
    y = torch.tensor(ys, dtype=torch.float32)
    return x, y


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
        # §9: log init strategy per experiment
        "init": "pretrained:mobilenet_v3_small IMAGENET1K_V1 features[0..8] (torchvision, BSD-3)",
    }


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
