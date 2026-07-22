"""Iter 6 probe part 3: build the candidate deepened trunk (MNv3-Small
features[:11], block 9 stride 2->1, block 10 dw dilation 2), load pretrained
weights strict, wire the re-widthed heads, export ONNX, quantize FC heads to
int8, and check size + SINGLE-THREAD latency exactly as the frozen scorer
measures it. Read-only wrt the repo; no training, no hamburg."""
import sys
sys.path.insert(0, ".")
import numpy as np, time, torch, torch.nn as nn
from pathlib import Path
from torchvision.models import mobilenet_v3_small

sd = torch.load("model/pretrained/mnv3s_features8.pt", map_location="cpu", weights_only=True)
print("pretrained file keys cover blocks:", sorted(set(k.split(".")[1] for k in sd)))

# Do we have blocks 9,10 weights on disk? If not, need full download availability.
full = mobilenet_v3_small(weights=None).features[:11]
need = set(k for k, _ in full.named_parameters()) | set(
    k for k, _ in full.named_buffers() if "num_batches" not in k)
have = set(k[len("features."):] for k in sd)
missing = sorted(k for k in need if k not in have)
print("missing param tensors for features[:11]:", len(missing), missing[:4], "...")
