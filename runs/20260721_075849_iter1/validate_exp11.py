import os
import time

import numpy as np
import torch

from model.model import build_model, export_onnx, loss_fn

m = build_model(pretrained=True)  # strict=True load inside — fails loudly on mismatch
print("strict pretrained load: OK")
print("total params:", sum(p.numel() for p in m.parameters()))

m.eval()
x = torch.rand(2, 3, 128, 128)
with torch.no_grad():
    out, logits = m(x, return_logits=True)
print("out:", tuple(out.shape), "logits:", tuple(logits.shape))
assert out.shape == (2, 3) and logits.shape == (2, 1024)
assert (out[:, :2] >= 0).all() and (out[:, :2] <= 1).all()
y = torch.rand(2, 2)
print("loss:", float(loss_fn(out, logits, y)))

m.train()
out, logits = m(x, return_logits=True)
loss_fn(out, logits, y).backward()
g = m.features[0][0].weight.grad
print("trunk grad flows:", g is not None and float(g.abs().sum()) > 0)

onnx_path = "/tmp/exp11_test.onnx"
m.eval()
export_onnx(m, onnx_path)
print(f"ONNX size: {os.path.getsize(onnx_path)/1048576:.2f} MiB (gate 4 MiB)")

import onnxruntime as ort
sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
feed = dict(frame=np.random.rand(1, 3, 128, 128).astype(np.float32))
sess.run(None, feed)  # warmup
t0 = time.time()
for _ in range(20):
    r = sess.run(None, feed)
print(f"latency proxy: {(time.time()-t0)/20*1000:.2f} ms (gate 250 ms)")
print("uvc:", r[0][0])

with torch.no_grad():
    ot = m(torch.from_numpy(feed["frame"])).numpy()
print("torch/onnx max abs diff:", float(abs(ot - r[0]).max()))
