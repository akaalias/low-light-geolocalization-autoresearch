"""Iter 6 probe part 2: int8-quantize ONLY the FC (MatMul/Gemm) heads of the
current best model — convs stay fp32. Measure size, latency, decode deviation.
Read-only, no hamburg."""
import sys
sys.path.insert(0, ".")
import numpy as np, time
from pathlib import Path
from onnxruntime.quantization import quantize_dynamic, QuantType
import onnxruntime as ort
import onnx

src = Path("runs/20260721_210436_iter5/models/berlin.onnx")
dst = Path("/tmp/berlin_fc8.onnx")
quantize_dynamic(src, dst, weight_type=QuantType.QInt8,
                 op_types_to_quantize=["MatMul", "Gemm"])
print("fp32 bytes:", src.stat().st_size, " fc-int8 bytes:", dst.stat().st_size)
m = onnx.load(dst)
ops = {}
for n in m.graph.node:
    ops[n.op_type] = ops.get(n.op_type, 0) + 1
interesting = [k for k in ops if "Int" in k or "Quant" in k or k in ("Conv", "MatMul", "Gemm")]
print("graph ops of interest:", dict((k, ops[k]) for k in sorted(interesting)))

from PIL import Image
from pipeline.common import DATA_DIR, area_dir, load_meta
from pipeline.dataset import list_crops, extract_crop, error_meters

meta = load_meta("berlin", DATA_DIR)
crops = list_crops("berlin", meta["width"], meta["height"], "eval")
rng = np.random.default_rng(0)
picks = rng.choice(len(crops), 60, replace=False)
s32 = ort.InferenceSession(str(src), providers=["CPUExecutionProvider"])
s8 = ort.InferenceSession(str(dst), providers=["CPUExecutionProvider"])
for name in ("night", "midday"):
    im = np.asarray(Image.open(area_dir("berlin", DATA_DIR) / "relight" / (name + ".png")))
    d_uv, d_conf, e32, e8 = [], [], [], []
    for i in picks:
        c = crops[i]
        x = extract_crop(im, c["cx"], c["cy"], c["angle"]).astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        a = s32.run(None, {"frame": x})[0][0]
        b = s8.run(None, {"frame": x})[0][0]
        d_uv.append(float(np.hypot(a[0] - b[0], a[1] - b[1])))
        d_conf.append(abs(float(a[2]) - float(b[2])))
        e32.append(error_meters(meta, float(a[0]), float(a[1]), c["cx"], c["cy"]))
        e8.append(error_meters(meta, float(b[0]), float(b[1]), c["cx"], c["cy"]))
    print("%s: median|d_uv|=%.5f max=%.5f  median|dconf|=%.4f  medianerr fp32=%.1fm fc8=%.1fm"
          % (name, np.median(d_uv), max(d_uv), np.median(d_conf), np.median(e32), np.median(e8)))

x = np.zeros((1, 3, 128, 128), np.float32)
for _ in range(5):
    s8.run(None, {"frame": x})
t0 = time.time()
for _ in range(20):
    s8.run(None, {"frame": x})
print("fc-int8 latency ~ %.2f ms" % ((time.time() - t0) / 20 * 1000))
