"""One-off read-only diagnostic for iter 7: does the kept best model fit its
own training locations, or is it underfitting everywhere?  (No hamburg.)"""
import numpy as np, onnxruntime as ort
from PIL import Image
from pipeline.common import DATA_DIR, area_dir, load_meta
from pipeline.dataset import list_crops, extract_crop, error_meters

area = "berlin"
meta = load_meta(area, DATA_DIR)
img = np.asarray(Image.open(area_dir(area, DATA_DIR) / "relight" / "midday.png"))
sess = ort.InferenceSession(f"runs/20260720_195206_iter1/models/{area}.onnx",
                            providers=["CPUExecutionProvider"])
rng = np.random.default_rng(0)

for split, ang_mode in [("train", "zero"), ("train", "rand"), ("eval", "frozen")]:
    crops = list_crops(area, meta["width"], meta["height"], split)
    picks = rng.choice(len(crops), size=200, replace=False)
    errs = []
    for i in picks:
        c = crops[i]
        if ang_mode == "zero":
            ang = 0.0
        elif ang_mode == "rand":
            ang = float(rng.uniform(0, 360))
        else:
            ang = c["angle"]
        x = extract_crop(img, c["cx"], c["cy"], ang)
        x = x.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        u, v, conf = sess.run(None, {"frame": x})[0][0]
        errs.append(error_meters(meta, float(u), float(v), c["cx"], c["cy"]))
    errs = np.array(errs)
    print(f"{split:5s} angle={ang_mode:6s} median={np.median(errs):8.1f} m  mean={errs.mean():8.1f} m")
print("meta:", meta["width"], meta["height"], meta["gsd_m"])
