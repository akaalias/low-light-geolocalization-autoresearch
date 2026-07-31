"""Cheapest-possible feasibility probe: is embedding + nearest-neighbor
RETRIEVAL (no map-cell classification field, no fixed grid) a meaningfully
different accuracy regime than the champion's 743m worst-case median?

Not a production pipeline -- a quick, isolated side-track script. Reuses
the FROZEN pipeline utilities (pipeline.dataset, pipeline.common) read-only,
and the champion's pretrained trunk (model.model._build_pretrained_trunk)
read-only, purely as library imports. Writes nothing back into model/ or
any frozen file. Runs entirely locally (data/berlin + render_cache/berlin
are already warm), no Modal call needed.

Protocol, mirroring pipeline/score.py's train/eval split and error metric:
  1. Train a small contrastive (InfoNCE) projection head on top of the
     pretrained trunk, over a modest sample of TRAIN-split locations across
     all 6 lighting buckets + random heading -- same-location crops (any
     two lighting/heading draws) are positives, other locations in the
     batch are negatives.
  2. Build a retrieval INDEX: embeddings for N_INDEX train-split locations
     (one embedding per location, from one random lighting/heading draw).
  3. Evaluate: for each EVAL-split location x each of the 6 buckets, embed
     the crop, 1-NN lookup against the index, error = pixel distance to the
     true location x meta['gsd_m'] -- identical formula to
     pipeline.dataset.error_meters, just computed directly in pixel space.
  4. Report median error per bucket and the worst-case across buckets, the
     same shape of number as the champion's 743m, for a direct sanity
     comparison -- not a claim of final quality.
"""
import sys
import time

import numpy as np
import rasterio
import torch
import torch.nn as nn
import torch.nn.functional as F

from pathlib import Path

sys.path.insert(0, ".")
from pipeline.common import LIGHTING_BUCKETS, area_dir, load_meta
from pipeline.dataset import crop_center_norm, extract_crop, list_crops
from PIL import Image
from torchvision.models import mobilenet_v3_small

# Vendored from the champion's model/train.py (same commit, same reasoning as
# the model.py vendoring below): the exp-35 confusability-weighted sampler,
# reused here to bias which locations get contrasted against each other
# toward genuinely look-alike places, instead of uniform random pairs.
GRID_K = 32
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

# Vendored from the champion's model/model.py (commit 9421cc39, read via `git
# show`, NOT imported live) -- model/model.py is currently being rewritten
# in-flight by the autoresearch loop's iter-61 implement agent (a from-scratch
# pivot with no pretrained trunk at all), so importing it here would be
# unstable and could break mid-run. Only the static binary weights file
# (model/pretrained/mnv3s_features8.pt, a tracked git asset unrelated to
# whatever model.py currently contains) is reused, by explicit repo-root path.
PRETRAINED_TRUNK_PATH = Path("model/pretrained/mnv3s_features8.pt")
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def _build_pretrained_trunk():
    trunk = mobilenet_v3_small(weights=None).features[:9]
    state_dict = torch.load(PRETRAINED_TRUNK_PATH, map_location="cpu", weights_only=True)
    stripped = {k[len("features."):]: v for k, v in state_dict.items()}
    trunk.load_state_dict(stripped, strict=True)
    return trunk

AREA = "berlin"
DATA_DIR = None  # default (pipeline.common.DATA_DIR)
EMBED_DIM = 64
N_INDEX = 8000             # retrieval-gallery locations (~78m avg spacing over 7km bbox)
N_VIEWS_PER_INDEX = 4      # views averaged per index location (query stays single-view)
N_EVAL_PER_BUCKET = 150    # eval crops per lighting bucket
# Round 1 (batch=64, 800 steps) collapsed: training loss hit ~0.03 but eval
# retrieval was 2699m, far worse than the 743m champion -- the textbook sign
# of too-easy in-batch negatives (64 random locations rarely include a truly
# confusable one). Round 2: much larger batch (more negatives/step, the
# highest-leverage fix per SimCLR-style ablations), confusability-weighted
# anchor sampling (reusing the champion's own exp-35 trick, so batches are
# biased toward locations that actually look alike), and sampling batches
# WITHOUT replacement (round 1 could and often did draw the same location
# twice in one batch of 64 from a 3000-anchor pool, silently mislabeling a
# true positive as a negative).
BATCH = 256
STEPS = 1200
TEMP = 0.07
DEVICE = "mps" if torch.backends.mps.is_available() else \
         "cuda" if torch.cuda.is_available() else "cpu"

bucket_names = list(LIGHTING_BUCKETS)
rng = np.random.default_rng(0)

# Same fix as model/train.py's sample_epoch bug: decode each of the 18
# bucket/realization PNGs ONCE and reuse the array, instead of re-opening a
# ~120MB PNG on every single crop draw (the first version of this probe did
# that and was on track to take hours instead of minutes).
_IMG_CACHE = {}


def load_bucket_img(bucket, realization):
    key = (bucket, realization)
    if key not in _IMG_CACHE:
        import os
        from pathlib import Path
        cache_root = Path(os.environ.get("RENDER_CACHE", "render_cache"))
        if realization == 0:
            path = area_dir(AREA, DATA_DIR) / "relight" / f"{bucket}.png"
        else:
            path = cache_root / AREA / f"{bucket}_r{realization}.png"
        _IMG_CACHE[key] = np.asarray(Image.open(path))
    return _IMG_CACHE[key]


class Embedder(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = _build_pretrained_trunk()
        self.register_buffer("norm_mean", torch.tensor(IMAGENET_MEAN).view(1, 3, 1, 1))
        self.register_buffer("norm_std", torch.tensor(IMAGENET_STD).view(1, 3, 1, 1))
        self.proj = nn.Linear(48, EMBED_DIM)

    def forward(self, x):  # x: [N,3,128,128] uint8-range float in [0,1]
        x = (x - self.norm_mean) / self.norm_std
        feat = self.features(x)
        gap = feat.mean(dim=(2, 3))
        z = self.proj(gap)
        return F.normalize(z, dim=1)


def crop_tensor(img, cx, cy, angle):
    c = extract_crop(img, cx, cy, angle)
    return torch.from_numpy(c).permute(2, 0, 1).float().div_(255.0)


def sample_view(area, meta, crop):
    bucket = bucket_names[rng.integers(len(bucket_names))]
    realization = rng.integers(3)
    img = load_bucket_img(bucket, realization)
    angle = float(rng.uniform(0, 360))
    return crop_tensor(img, crop["cx"], crop["cy"], angle), bucket


def main():
    t0 = time.time()
    meta = load_meta(AREA, DATA_DIR)
    train_crops = list_crops(AREA, meta["width"], meta["height"], "train")
    eval_crops = list_crops(AREA, meta["width"], meta["height"], "eval")
    print(f"[{time.time()-t0:.0f}s] {len(train_crops)} train crops, {len(eval_crops)} eval crops, device={DEVICE}")

    model = Embedder().to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)

    print(f"[{time.time()-t0:.0f}s] computing confusability weights (exp-35 trick, reused)...")
    crop_cell = np.array([
        (min(int(v * GRID_K), GRID_K - 1)) * GRID_K + min(int(u * GRID_K), GRID_K - 1)
        for u, v in (crop_center_norm(meta, c["cx"], c["cy"]) for c in train_crops)
    ])
    cell_w = compute_cell_weights(AREA, DATA_DIR, meta)
    raw_w = cell_w[crop_cell]
    uniform = np.full(len(train_crops), 1.0 / len(train_crops))
    weighted = raw_w / raw_w.sum()
    crop_probs = CONFUSABILITY_ALPHA * weighted + (1 - CONFUSABILITY_ALPHA) * uniform
    crop_probs = crop_probs / crop_probs.sum()

    print(f"[{time.time()-t0:.0f}s] training contrastive head, {STEPS} steps, batch={BATCH}...")
    model.train()
    for step in range(STEPS):
        batch_locs = rng.choice(len(train_crops), size=BATCH, replace=False, p=crop_probs)
        xa, xb = [], []
        for i in batch_locs:
            c = train_crops[i]
            va, _ = sample_view(AREA, meta, c)
            vb, _ = sample_view(AREA, meta, c)
            xa.append(va); xb.append(vb)
        xa = torch.stack(xa).to(DEVICE)
        xb = torch.stack(xb).to(DEVICE)
        za = model(xa)
        zb = model(xb)
        logits = za @ zb.T / TEMP
        labels = torch.arange(len(batch_locs), device=DEVICE)
        loss = 0.5 * (F.cross_entropy(logits, labels) + F.cross_entropy(logits.T, labels))
        opt.zero_grad(); loss.backward(); opt.step()
        if step % 100 == 0:
            print(f"[{time.time()-t0:.0f}s] step {step}/{STEPS} loss={loss.item():.4f}")

    print(f"[{time.time()-t0:.0f}s] building retrieval index ({N_INDEX} locations, "
          f"{N_VIEWS_PER_INDEX} views/location averaged)...")
    # Round 2 (bigger batch + confusability weighting) didn't move the needle
    # at all vs round 1 -- still ~2700-2800m, still near-zero training loss.
    # Round 3 isolates a different suspect: the index stored only ONE random
    # (lighting, heading) sample per location, so a query under different
    # view conditions than its true match's stored sample could easily land
    # closer to some OTHER location's index entry that happens to share
    # similar view conditions. Average several views per index location to
    # cancel that view-specific noise. The QUERY side stays single-view --
    # a real deployment only ever has one live camera frame to match, so
    # only the offline-built index (built from data, not from live inference)
    # is allowed multiple views.
    model.eval()
    index_idx = rng.choice(len(train_crops), size=min(N_INDEX, len(train_crops)), replace=False)
    index_embs, index_cx, index_cy = [], [], []
    with torch.no_grad():
        for start in range(0, len(index_idx), 256):
            batch_i = index_idx[start:start + 256]
            view_sum = None
            for _ in range(N_VIEWS_PER_INDEX):
                xs = [sample_view(AREA, meta, train_crops[i])[0] for i in batch_i]
                z = model(torch.stack(xs).to(DEVICE)).cpu().numpy()
                view_sum = z if view_sum is None else view_sum + z
            z_avg = view_sum / N_VIEWS_PER_INDEX
            z_avg = z_avg / np.linalg.norm(z_avg, axis=1, keepdims=True)
            index_embs.append(z_avg)
            index_cx.extend(train_crops[i]["cx"] for i in batch_i)
            index_cy.extend(train_crops[i]["cy"] for i in batch_i)
    index_embs = np.concatenate(index_embs, axis=0)
    index_cx = np.array(index_cx); index_cy = np.array(index_cy)
    print(f"[{time.time()-t0:.0f}s] index built: {index_embs.shape}")

    print(f"[{time.time()-t0:.0f}s] evaluating retrieval error per bucket...")
    results = {}
    with torch.no_grad():
        for bucket in bucket_names:
            picks = rng.choice(len(eval_crops), size=min(N_EVAL_PER_BUCKET, len(eval_crops)), replace=False)
            errs = []
            for i in picks:
                c = eval_crops[i]
                realization = rng.integers(3)
                img = load_bucket_img(bucket, realization)
                angle = float(rng.uniform(0, 360))
                xq = crop_tensor(img, c["cx"], c["cy"], angle).unsqueeze(0).to(DEVICE)
                zq = model(xq).cpu().numpy()[0]
                sims = index_embs @ zq
                nn_i = int(np.argmax(sims))
                pred_cx, pred_cy = index_cx[nn_i], index_cy[nn_i]
                err_m = float(np.hypot((pred_cx - c["cx"]) * meta["gsd_m"],
                                       (pred_cy - c["cy"]) * meta["gsd_m"]))
                errs.append(err_m)
            median_err = float(np.median(errs))
            results[bucket] = median_err
            print(f"[{time.time()-t0:.0f}s]   {bucket}: median {median_err:.1f} m (n={len(errs)})")

    worst = max(results.values())
    print(f"\n=== RESULT ===")
    for b, e in results.items():
        print(f"  {b}: {e:.1f} m")
    print(f"worst-case median across buckets: {worst:.1f} m")
    print(f"(champion classification-decode baseline: 743.1 m)")


if __name__ == "__main__":
    main()
