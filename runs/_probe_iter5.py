"""Read-only probe (design stage, iter5): separate heading-generalization vs
location-generalization as the binding failure of the last kept model.

Conditions, berlin + prignitz, midday (best-case lighting), 300 crops each:
  A) eval crops, stored random angle  -> the scored condition
  B) eval crops, angle=0              -> removes heading mismatch
  C) train crops, angle=0             -> removes held-out-location gap too
Report median error (no confidence filtering, and also conf-kept median).
"""
import numpy as np
from PIL import Image
from pipeline.common import DATA_DIR, area_dir, load_meta
from pipeline.dataset import error_meters, extract_crop, list_crops
from pipeline.score import load_session, predict

MODEL_DIR = "runs/20260721_141132_iter4/models"

for area in ["berlin", "prignitz"]:
    meta = load_meta(area, DATA_DIR)
    sess = load_session(f"{MODEL_DIR}/{area}.onnx")
    img = np.asarray(Image.open(area_dir(area, DATA_DIR) / "relight" / "midday.png"))
    for split, use_angle, label in [("eval", True, "A eval@stored-angle"),
                                    ("eval", False, "B eval@angle0     "),
                                    ("train", False, "C train@angle0    ")]:
        crops = list_crops(area, meta["width"], meta["height"], split)
        idx = np.linspace(0, len(crops) - 1, 300).astype(int)
        errs, kept = [], []
        for i in idx:
            c = crops[i]
            ang = c["angle"] if use_angle else 0.0
            u, v, conf = predict(sess, extract_crop(img, c["cx"], c["cy"], ang))
            e = error_meters(meta, u, v, c["cx"], c["cy"])
            errs.append(e)
            if conf >= 0.3:
                kept.append(e)
        print(f"{area:9s} {label} median_all={np.median(errs):7.1f} m  "
              f"median_kept={np.median(kept) if kept else float('nan'):7.1f} m  "
              f"cov={len(kept)/len(errs):.2f}")
