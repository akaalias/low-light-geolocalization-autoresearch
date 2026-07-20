"""FROZEN (see /FROZEN) — crop sampling and train/eval split, §4 step 4.

Deterministic, bbox-generic split: the raster is divided into square blocks;
exactly one block in five is eval, on a diagonal lattice offset by a stable
per-area hash — evenly spread spatially with low variance for any bbox size. A crop belongs to the split of the block under its center.
TRAIN crops are dropped if their (rotation-padded) window touches any eval
block — the model never sees a single eval-block pixel during training. Eval
windows may graze train blocks (their centers — the regression target — are
always inside eval blocks); this keeps eval sample counts usable and is
consistent across all experiments.

Eval crops get a deterministic per-crop rotation angle so the eval set is
heading-agnostic from day 1 (a UAV frame has arbitrary yaw). Train-time
augmentation policy is the loop's business (model/), not fixed here.

Ground truth per crop = raster pixel coords of the crop center, converted to
meters via the UTM grid (10 m/px).
"""

import numpy as np
from PIL import Image

from pipeline.common import CROP_PX, stable_hash

# 360 px blocks: large enough that the no-leakage buffer around eval blocks
# doesn't consume the train area (at 1 m/px this yields ~45k train and ~15k
# eval positions per ~7 km area, ~26% eval).
BLOCK_PX = 360
STRIDE_PX = 24
EVAL_FRACTION_MOD = 5  # exactly 1 in 5 blocks is eval (diagonal lattice)
# Window big enough to rotate CROP_PX without corner voids: ceil(128 * sqrt(2))
WINDOW_PX = 182


def block_split(area: str, bx: int, by: int) -> str:
    offset = stable_hash(f"{area}:offset") % EVAL_FRACTION_MOD
    lattice = (bx + 2 * by + offset) % EVAL_FRACTION_MOD
    return "eval" if lattice == 0 else "train"


def list_crops(area: str, width: int, height: int, split: str) -> list[dict]:
    """Enumerate crop records for one split. Coordinates are raster pixels."""
    half_w = WINDOW_PX // 2 + 1
    out = []
    for cy in range(half_w, height - half_w, STRIDE_PX):
        for cx in range(half_w, width - half_w, STRIDE_PX):
            own = block_split(area, cx // BLOCK_PX, cy // BLOCK_PX)
            if own != split:
                continue
            if own == "train":
                # Train windows must never include eval-block pixels.
                bxs = range((cx - half_w) // BLOCK_PX, (cx + half_w) // BLOCK_PX + 1)
                bys = range((cy - half_w) // BLOCK_PX, (cy + half_w) // BLOCK_PX + 1)
                if any(block_split(area, bx, by) == "eval" for bx in bxs for by in bys):
                    continue
            angle = 0.0
            if split == "eval":
                angle = (stable_hash(f"{area}:angle:{cx}:{cy}") % 3600) / 10.0
            out.append({"cx": cx, "cy": cy, "angle": angle})
    return out


def extract_crop(img: np.ndarray, cx: int, cy: int, angle: float,
                 size: int = CROP_PX) -> np.ndarray:
    """Extract a size x size crop centered at (cx, cy), rotated by angle deg.

    img: HxWx3 uint8 full-scene array. Rotation is about the crop center, so
    the ground-truth center coordinate is rotation-invariant.
    """
    half_w = WINDOW_PX // 2 + 1
    win = img[cy - half_w:cy + half_w, cx - half_w:cx + half_w]
    if angle:
        win = np.asarray(Image.fromarray(win).rotate(angle, resample=Image.BILINEAR))
    y0 = win.shape[0] // 2 - size // 2
    x0 = win.shape[1] // 2 - size // 2
    return win[y0:y0 + size, x0:x0 + size]


def crop_center_norm(meta: dict, cx: int, cy: int) -> tuple[float, float]:
    """Normalized (u, v) in [0,1] target for regression."""
    return cx / meta["width"], cy / meta["height"]


def norm_to_px(meta: dict, u: float, v: float) -> tuple[float, float]:
    return u * meta["width"], v * meta["height"]


def error_meters(meta: dict, u_pred: float, v_pred: float, cx: int, cy: int) -> float:
    px, py = norm_to_px(meta, u_pred, v_pred)
    return float(np.hypot((px - cx) * meta["gsd_m"], (py - cy) * meta["gsd_m"]))
