"""Iter 6 probe part 4: full candidate dry-run — deepened dilated trunk
features[:11] + re-widthed heads, ONNX export, FC-head int8 quantization,
size + single-thread latency exactly as the frozen scorer measures.
Read-only wrt the repo; no training, no hamburg."""
import sys
sys.path.insert(0, ".")
import numpy as np, time, torch, torch.nn as nn
from pathlib import Path
from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights

GRID_K, DECODE_BETA = 32, 3.0
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def _grid_centers(k):
    centers = (torch.arange(k, dtype=torch.float32) + 0.5) / k
    return centers.repeat(k), centers.repeat_interleave(k)


def _c4_stack(x):
    r90 = x.transpose(2, 3).flip(2)
    r180 = x.flip(2).flip(3)
    r270 = x.transpose(2, 3).flip(3)
    return torch.cat([x, r90, r180, r270], dim=0)


def build_trunk11():
    m = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1)
    trunk = m.features[:11]
    # block 9: stride 2 -> 1 on its depthwise conv (keeps 8x8 grid)
    dw9 = trunk[9].block[1][0]
    assert dw9.stride == (2, 2) and dw9.groups == dw9.in_channels
    dw9.stride = (1, 1)
    # block 10: dilate the 5x5 dw conv to preserve pretrained RF geometry
    dw10 = trunk[10].block[1][0]
    assert dw10.groups == dw10.in_channels and dw10.kernel_size == (5, 5)
    dw10.dilation = (2, 2)
    dw10.padding = (4, 4)
    return trunk


class CandNet(nn.Module):
    def __init__(self, grid_k=GRID_K, layout_ch=8, gate_hidden=16):
        super().__init__()
        self.grid_k = grid_k
        self.features = build_trunk11()
        self.register_buffer("norm_mean", torch.tensor(IMAGENET_MEAN).view(1, 3, 1, 1))
        self.register_buffer("norm_std", torch.tensor(IMAGENET_STD).view(1, 3, 1, 1))
        with torch.no_grad():
            probe = self.features(torch.zeros(1, 3, 128, 128))
        feat_ch, fmap_hw = probe.shape[1], probe.shape[2]
        print("trunk out:", probe.shape)
        self.layout_squeeze = nn.Conv2d(feat_ch, layout_ch, 1)
        self.loc_logits = nn.Linear(feat_ch + layout_ch * fmap_hw * fmap_hw, grid_k * grid_k)
        self.dark_logits = nn.Linear(feat_ch, grid_k * grid_k)
        self.gate = nn.Sequential(nn.Linear(feat_ch + 1, gate_hidden), nn.ReLU(),
                                  nn.Linear(gate_hidden, 1))
        self.conf_head = nn.Sequential(nn.Linear(feat_ch + 3, 32), nn.ReLU(), nn.Linear(32, 1))
        self.register_buffer("conf_shift", torch.zeros(1))
        cell_u, cell_v = _grid_centers(grid_k)
        self.register_buffer("cell_u", cell_u)
        self.register_buffer("cell_v", cell_v)

    def forward(self, x):
        n = x.shape[0]
        lum = x.mean(dim=(1, 2, 3)).unsqueeze(1)
        x4 = _c4_stack(x)
        fmap = self.features((x4 - self.norm_mean) / self.norm_std)
        f4 = fmap.mean(dim=(2, 3))
        layout4 = self.layout_squeeze(fmap).flatten(1)
        lum4 = lum.repeat(4, 1)
        bright_logits4 = self.loc_logits(torch.cat([f4, layout4], dim=1))
        dark_logits4 = self.dark_logits(f4)
        g4 = torch.sigmoid(self.gate(torch.cat([lum4, f4], dim=1)))
        logits4 = (1 - g4) * bright_logits4 + g4 * dark_logits4
        logits = logits4.reshape(4, n, -1).mean(dim=0)
        f = f4.reshape(4, n, -1).mean(dim=0)
        p = torch.softmax(DECODE_BETA * logits, dim=1)
        u = (p * self.cell_u).sum(dim=1, keepdim=True)
        v = (p * self.cell_v).sum(dim=1, keepdim=True)
        p1 = torch.softmax(logits, dim=1)
        u1 = (p1 * self.cell_u).sum(dim=1, keepdim=True)
        v1 = (p1 * self.cell_v).sum(dim=1, keepdim=True)
        pd = p.detach()
        peak = pd.max(dim=1, keepdim=True).values
        ent = -(pd * torch.log(pd + 1e-9)).sum(dim=1, keepdim=True) / float(np.log(self.grid_k * self.grid_k))
        gap = torch.sqrt((u.detach() - u1.detach()) ** 2 + (v.detach() - v1.detach()) ** 2 + 1e-12)
        z = self.conf_head(torch.cat([f.detach(), peak, ent, gap], dim=1))
        conf = torch.sigmoid(z - self.conf_shift)
        return torch.cat([u, v, conf], dim=1)


model = CandNet()
n_total = sum(p.numel() for p in model.parameters())
n_trunk = sum(p.numel() for p in model.features.parameters())
print("params: total %d trunk %d heads %d" % (n_total, n_trunk, n_total - n_trunk))

model.eval()
fp32_path, int8_path = "/tmp/cand_fp32.onnx", "/tmp/cand_int8.onnx"
torch.onnx.export(model, torch.zeros(1, 3, 128, 128), fp32_path,
                  input_names=["frame"], output_names=["uvc"], opset_version=17, dynamo=False)
from onnxruntime.quantization import quantize_dynamic, QuantType
quantize_dynamic(fp32_path, int8_path, weight_type=QuantType.QInt8,
                 op_types_to_quantize=["MatMul", "Gemm"])
import os
print("fp32 bytes:", os.path.getsize(fp32_path), " int8 bytes:", os.path.getsize(int8_path),
      " gate:", 4 * 1024 * 1024)

# scorer-identical latency measurement
import onnxruntime as ort
opts = ort.SessionOptions()
opts.intra_op_num_threads = 1
opts.inter_op_num_threads = 1
sess = ort.InferenceSession(int8_path, sess_options=opts, providers=["CPUExecutionProvider"])
x = np.zeros((1, 3, 128, 128), np.float32)
for _ in range(3):
    sess.run(None, {"frame": x})
ts = []
for _ in range(20):
    t0 = time.perf_counter()
    sess.run(None, {"frame": x})
    ts.append((time.perf_counter() - t0) * 1000)
print("int8 single-thread latency median %.1f ms (gate 250)" % np.median(ts))

# torch-vs-onnx-int8 agreement on a random input (sanity that quantized graph runs same math)
xr = torch.rand(1, 3, 128, 128)
with torch.no_grad():
    a = model(xr).numpy()[0]
b = sess.run(None, {"frame": xr.numpy()})[0][0]
print("torch fp32 out:", a, " onnx int8 out:", b)
