"""FROZEN (see /FROZEN) — crop sampling and train/eval split, §4 step 4.

The split holds out VIEWPOINTS, not REGIONS. This is the v2 design; see the
"why" below, because the v1 design was wrong in a way that invalidated ~60
experiments and it must not be reintroduced.

  train  — every lattice position (STRIDE_PX) across the WHOLE raster. The
           model is meant to memorize its one bounding box, so it is shown
           all of it. This is the product: one model per bbox, deployed only
           over that bbox.
  eval   — OFF-LATTICE viewpoints over the same, fully-mapped ground: each
           sits EVAL_OFF_MIN..EVAL_OFF_MAX px from the lattice in x and y, so
           it is 11-17 m from the nearest training framing (17 m is the
           largest offset a 24 m lattice permits, so these are the most novel
           viewpoints available), and carries a deterministic rotation. The
           GROUND is mapped; the VIEW is new. That is the deployment
           condition: an aircraft over a mapped area photographs it from an
           arbitrary position and yaw, never from exactly a training vantage.
  holdout_region
         — a small diagnostic (1 block in HOLDOUT_MOD) genuinely excluded
           from training, buffered so no training crop sees a pixel of it.
           Logged, NEVER scored into the §6 metric. Its only job is to catch
           a model that is a pure lookup table with no spatial structure.

WHY v1 WAS WRONG (2026-07-31). v1 held out one block in five and dropped any
train crop whose window touched an eval block. Consequence, measured: 28.2%
of Berlin appeared in NO training crop, 100% of eval questions were centred
on never-seen ground, and 65% of eval frames contained zero familiar pixels.
The geometry forces it — a train crop's content stops 28 px short of any eval
block (92 px centre buffer - 64 px crop half), so only eval centres within
36 px of a block edge could see anything familiar at all. The model was asked
to locate places it had never been shown. That is unanswerable for a
memorization architecture, it contradicts this project's own premise, and it
is stricter than the prior art the spec cites (DSAC/ACE evaluate held-out
trajectories through a FULLY MAPPED scene, not unmapped parts of one).

Eval crops get a deterministic per-crop rotation angle so the eval set is
heading-agnostic from day 1 (a UAV frame has arbitrary yaw). Train-time
augmentation policy is the loop's business (model/), not fixed here.

Ground truth per crop = raster pixel coords of the crop center, converted to
meters via the UTM grid.
"""

import numpy as np
from PIL import Image

from pipeline.common import CROP_PX, stable_hash

STRIDE_PX = 24         # training lattice: one memorized vantage every 24 m
BLOCK_PX = 360         # only used to carve the region-holdout diagnostic
HOLDOUT_MOD = 32       # 1 block in 32 is held out of training entirely
EVAL_MOD = 5           # 1 lattice cell in 5 spawns an off-lattice eval view
# Offset of an eval viewpoint inside its stride cell. [8,16] keeps every eval
# view >= 8 px from the lattice in BOTH axes => 11.3-17.0 m from the nearest
# training framing. Must stay < CROP_PX//2 (64) or the eval centre's own
# ground would fall outside every training crop — the v1 bug, in miniature.
EVAL_OFF_MIN, EVAL_OFF_MAX = 8, 16
# Window big enough to rotate CROP_PX without corner voids: ceil(128 * sqrt(2))
WINDOW_PX = 182


def block_role(area: str, bx: int, by: int) -> str:
    """'holdout' for the small never-trained diagnostic region, else 'mapped'."""
    return ("holdout" if stable_hash(f"{area}:holdout:{bx}:{by}") % HOLDOUT_MOD == 0
            else "mapped")


def _window_hits_holdout(area: str, cx: int, cy: int, half_w: int) -> bool:
    bxs = range((cx - half_w) // BLOCK_PX, (cx + half_w) // BLOCK_PX + 1)
    bys = range((cy - half_w) // BLOCK_PX, (cy + half_w) // BLOCK_PX + 1)
    return any(block_role(area, bx, by) == "holdout" for bx in bxs for by in bys)


def list_crops(area: str, width: int, height: int, split: str) -> list[dict]:
    """Enumerate crop records for one split. Coordinates are raster pixels.

    split: 'train' | 'eval' | 'holdout_region'
    """
    if split not in ("train", "eval", "holdout_region"):
        raise ValueError(f"unknown split {split!r}")
    half_w = WINDOW_PX // 2 + 1
    out = []
    for cy in range(half_w, height - half_w, STRIDE_PX):
        for cx in range(half_w, width - half_w, STRIDE_PX):
            if split == "train":
                # Everything except the buffered region-holdout diagnostic.
                if not _window_hits_holdout(area, cx, cy, half_w):
                    out.append({"cx": cx, "cy": cy, "angle": 0.0})
                continue

            # eval / holdout_region: one off-lattice viewpoint per EVAL_MOD cells
            if stable_hash(f"{area}:evalpick:{cx}:{cy}") % EVAL_MOD:
                continue
            span = EVAL_OFF_MAX - EVAL_OFF_MIN + 1
            ex = cx + EVAL_OFF_MIN + stable_hash(f"{area}:dx:{cx}:{cy}") % span
            ey = cy + EVAL_OFF_MIN + stable_hash(f"{area}:dy:{cx}:{cy}") % span
            if ex >= width - half_w or ey >= height - half_w:
                continue
            hits = _window_hits_holdout(area, ex, ey, half_w)
            if split == "eval":
                # Eval must sit on ground training actually covered, so apply
                # the SAME buffer rule as train — otherwise eval questions
                # drift back into never-seen territory.
                if hits:
                    continue
            else:  # holdout_region: centre must be inside a holdout block
                if block_role(area, ex // BLOCK_PX, ey // BLOCK_PX) != "holdout":
                    continue
            angle = (stable_hash(f"{area}:angle:{ex}:{ey}") % 3600) / 10.0
            out.append({"cx": ex, "cy": ey, "angle": angle})
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
