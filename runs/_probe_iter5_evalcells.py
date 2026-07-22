"""Read-only probe (design stage, session iter5): does the kept exp-20 model
structurally avoid committing its decode to eval-block cells?

Train crop centers never lie inside eval blocks (dataset.py drops train
windows touching one), so the flat 1024-way FC head's rows for eval-covering
cells are supervised only by Gaussian tail mass from >=~0.8-cell-distant
train targets. If the head is structurally biased against eval terrain, the
committed decode for EVAL crops (whose truth is always inside an eval block)
should land inside eval blocks far less often than truth does (100%).

Conditions per area (berlin, prignitz), midday + night, 300 eval crops:
  - P(decode lands in an eval block)   [truth: 100%]
  - median distance decode -> nearest eval-block terrain
  - control: for TRAIN crops, P(decode in eval block) and the eval-block
    area fraction (base rate ~20%).
"""
import sys
sys.path.insert(0, "/workspace/low-light-geolocalization-autoresearch")

import numpy as np
from PIL import Image
from pipeline.common import DATA_DIR, area_dir, load_meta
from pipeline.dataset import BLOCK_PX, block_split, error_meters, extract_crop, list_crops
from pipeline.score import load_session, predict

MODEL_DIR = "runs/20260721_175707_iter1/models"  # exp 20, the kept best (839.12 m)

for area in ["berlin", "prignitz"]:
    meta = load_meta(area, DATA_DIR)
    sess = load_session(f"{MODEL_DIR}/{area}.onnx")
    # eval-block area fraction over the raster
    nbx, nby = meta["width"] // BLOCK_PX + 1, meta["height"] // BLOCK_PX + 1
    frac = np.mean([[block_split(area, bx, by) == "eval" for bx in range(nbx)]
                    for by in range(nby)])
    print(f"\n{area}: eval-block base rate = {frac:.3f}")
    for bucket in ["midday", "night"]:
        img = np.asarray(Image.open(area_dir(area, DATA_DIR) / "relight" / f"{bucket}.png"))
        for split in ["eval", "train"]:
            crops = list_crops(area, meta["width"], meta["height"], split)
            idx = np.linspace(0, len(crops) - 1, 300).astype(int)
            in_eval, errs = [], []
            for i in idx:
                c = crops[i]
                u, v, conf = predict(sess, extract_crop(img, c["cx"], c["cy"], c["angle"]))
                px, py = u * meta["width"], v * meta["height"]
                in_eval.append(block_split(area, int(px) // BLOCK_PX, int(py) // BLOCK_PX) == "eval")
                errs.append(error_meters(meta, u, v, c["cx"], c["cy"]))
            print(f"  {bucket:7s} {split:5s}: P(decode in eval block)={np.mean(in_eval):.3f}  "
                  f"median err={np.median(errs):7.1f} m")
