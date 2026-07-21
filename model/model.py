"""AGENT-EDITABLE — model architecture + deployment inference wrapper.

The autoresearch loop may rewrite anything here (architecture, loss,
confidence mechanism, unified vs. dispatcher+specialists, pretrained init
per CLAUDE.md §3/§9) as long as:
  - train.py exports one ONNX per area at <out>/models/<area>.onnx taking a
    1x3x128x128 float32 input in [0,1] and returning [[u, v, conf]] with
    u, v normalized map coords and conf in [0,1];
  - the export passes pipeline/score.py's frozen deployment gates.

Current approach: DSNT-style spatial probability field. The conv stack's
global feature maps to logits over a GRID_K x GRID_K grid of map cells; the
predicted coordinate is the differentiable soft-argmax (probability-weighted
expected value) over fixed cell centers, trained with cross-entropy against
Gaussian-smoothed cell targets plus an expected-coordinate L2 term. Unlike
hard cell classification + offset regression (archived exp 5, reverted),
there is no argmax quantization and no decoupled head — the decode used at
inference is exactly what the loss optimizes.

Exp 10: the field head reads a spatial layout code alongside the GAP
descriptor. GAP alone is a bag-of-textures — it destroys WHERE features sit
in the crop, which is what distinguishes lookalike districts. A 1x1 conv
squeezes the 8x8x128 feature map to 8 channels; the flattened 512-d layout
code is concatenated with the 128-d GAP vector before the logits FC, making
the head a low-rank linear read of the full feature map (a strict superset
of the old GAP-only head).

Exp 11: the from-scratch 4-conv stack is replaced by an ImageNet-pretrained
MobileNetV3-Small trunk (torchvision, BSD-3-licensed; first 9 feature blocks
= stem + 8 inverted-residual blocks, 190k params, stride 16 -> the same 8x8
spatial grid the exp-10 head already reads, now 48 channels instead of 128).
Weights load strict from model/pretrained/mnv3s_features8.pt (verbatim
IMAGENET1K_V1 tensors). ImageNet mean/std normalization is baked into
forward() as buffers so the ONNX input contract ([0,1] float, no external
preprocessing) is unchanged. The layout-squeeze + GAP + field head are
otherwise identical to exp 10, only re-widthed for 48 input channels.

Exp 12: exp 11 was kept and, for the first time in the project's history,
produced a clear per-lighting-bucket gradient instead of a flat error
profile -- night is worst in all four development areas (e.g. Munich night
2010 m vs Munich midday 1381 m), meaning the single shared field head is
being asked to serve both a well-lit regime the pretrained features handle
well and a low-light regime it does not. A second, cheap "dark expert" field
head (Linear on the 48-d GAP descriptor only, 50k params -- no layout code,
since the spatial layout signal is assumed to be the least reliable part of
the descriptor once texture is mostly gone) is blended with the existing
layout-aware head via a per-example learned gate. The gate reads the crop's
own raw-pixel mean brightness plus the 48-d GAP descriptor -- both computed
from the frame itself, so the frozen (frame in) -> (lat, lon, conf) contract
is untouched -- through a tiny 2-layer MLP into a sigmoid blend weight. This
is a budget-safe MoE-lite stand-in for a full dispatcher+specialist design
(a second full 560->1024 head would cost ~2.2 MB, blowing the 4 MiB ONNX
gate on top of exp 11's 2.94 MiB); the cheap dark head + gate adds ~200 KB.

Exp 14: expected-value soft-argmax over the full field returns the
posterior MEAN, so any diffuse or multimodal residual mass shrinks every
prediction toward the map centroid -- the error profile after exp 10-12
(medians 1.0-1.9 km vs. a ~3.2 km center-guess floor, mean/median ratio
only ~1.2 in every area x bucket cell) is the shrinkage signature of
exactly this effect, not heavy-tailed mode-commitment error. Decoding from
softmax(DECODE_BETA * logits) instead sharpens the field before the
soft-argmax, committing to its dominant mode while leaving a uniform field
exactly uniform (so an untrained model still decodes near the map center --
the same bounded-downside floor every kept experiment has relied on). The
field itself still trains on the same calibrated Gaussian-bump CE at
temperature 1 (loss_fn is unchanged); only the coordinate L2's decode is
sharpened, so training now grades the committed answer that would fly.

Exp 15: the frozen scorer already implements selective prediction (conf <
0.3 abstains, coverage >= 0.2 required per cell) but coverage has been
1.000 in every logged cell -- the confidence head never learned to predict
anything but "always sure". It is replaced with a calibrated hit predictor
over the DECODE'S OWN SHAPE (sharpened-field peak mass, normalized field
entropy, and the distance between the sharpened and unsharpened decodes --
all detached, so no confidence gradient reaches the trunk/heads/gate),
trained to predict whether the committed decode lands within
GOOD_ERR_UV. A registered conf_shift buffer (calibrated post-training by
train.py, baked into the ONNX export) converts that hit probability into
the frozen 0.3 abstention threshold with a per-bucket >= 40% keep floor.
"""

import numpy as np
import torch
import torch.nn as nn
from pathlib import Path
from torchvision.models import mobilenet_v3_small

GRID_K = 32              # 32x32 cells over the map (~220 m cells on a ~7 km area)
TARGET_SIGMA_CELLS = 1.5  # Gaussian soft-target spread, in cell units
DECODE_BETA = 3.0  # inverse-temperature sharpening of the decode distribution (exp 14): softmax(β·logits) commits the soft-argmax to the dominant mode instead of the field mean; a uniform field stays uniform, so the untrained decode still starts at the map center
GOOD_ERR_UV = 0.05  # confidence 'hit' radius in normalized map units (~350 m on a ~7 km area, ~1.6 grid cells)

PRETRAINED_TRUNK_PATH = Path(__file__).parent / "pretrained" / "mnv3s_features8.pt"
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def _grid_centers(k: int) -> tuple[torch.Tensor, torch.Tensor]:
    """Flat [k*k] tensors of cell-center u and v (cell index = gy * k + gx)."""
    centers = (torch.arange(k, dtype=torch.float32) + 0.5) / k
    return centers.repeat(k), centers.repeat_interleave(k)


def _build_pretrained_trunk() -> nn.Module:
    """ImageNet-pretrained MobileNetV3-Small stem + first 8 inverted-residual
    blocks (torchvision, BSD-3). 128x128 in -> 48x8x8 out (stride 16)."""
    trunk = mobilenet_v3_small(weights=None).features[:9]
    state_dict = torch.load(PRETRAINED_TRUNK_PATH, map_location="cpu", weights_only=True)
    stripped = {k[len("features."):]: v for k, v in state_dict.items()}
    trunk.load_state_dict(stripped, strict=True)
    return trunk


class TinyLocNet(nn.Module):
    """ImageNet-pretrained MobileNetV3-Small trunk (48x8x8) -> {GAP descriptor
    + 1x1-squeezed spatial layout code} -> map-cell probability field ->
    soft-argmax (u, v), plus a separate sigmoid conf head.

    Exp 12: the field logits are a per-example gated blend of two experts --
    the existing layout-aware head (GAP + layout code) and a cheap GAP-only
    "dark expert" -- so the network can compute a different effective
    cell-scoring function for low-light crops without duplicating the
    expensive layout-aware FC. The gate is a tiny MLP over [raw-pixel mean
    brightness, GAP descriptor], both derived from the input frame alone.
    """

    def __init__(self, grid_k: int = GRID_K, layout_ch: int = 8, gate_hidden: int = 16):
        super().__init__()
        self.grid_k = grid_k
        self.features = _build_pretrained_trunk()
        self.register_buffer("norm_mean", torch.tensor(IMAGENET_MEAN).view(1, 3, 1, 1))
        self.register_buffer("norm_std", torch.tensor(IMAGENET_STD).view(1, 3, 1, 1))
        with torch.no_grad():
            probe = self.features(torch.zeros(1, 3, 128, 128))
        feat_ch, fmap_hw = probe.shape[1], probe.shape[2]
        self.layout_squeeze = nn.Conv2d(feat_ch, layout_ch, 1)
        self.loc_logits = nn.Linear(feat_ch + layout_ch * fmap_hw * fmap_hw,
                                    grid_k * grid_k)
        self.dark_logits = nn.Linear(feat_ch, grid_k * grid_k)
        self.gate = nn.Sequential(
            nn.Linear(feat_ch + 1, gate_hidden), nn.ReLU(),
            nn.Linear(gate_hidden, 1),
        )
        self.conf_head = nn.Sequential(nn.Linear(feat_ch + 3, 32), nn.ReLU(), nn.Linear(32, 1))
        self.register_buffer("conf_shift", torch.zeros(1))
        cell_u, cell_v = _grid_centers(grid_k)
        self.register_buffer("cell_u", cell_u)
        self.register_buffer("cell_v", cell_v)

    def forward(self, x, return_logits: bool = False):
        lum = x.mean(dim=(1, 2, 3)).unsqueeze(1)  # raw-pixel brightness, [N,1] in [0,1]
        fmap = self.features((x - self.norm_mean) / self.norm_std)
        f = fmap.mean(dim=(2, 3))
        layout = self.layout_squeeze(fmap).flatten(1)
        bright_logits = self.loc_logits(torch.cat([f, layout], dim=1))
        dark_logits = self.dark_logits(f)
        g = torch.sigmoid(self.gate(torch.cat([lum, f], dim=1)))
        logits = (1 - g) * bright_logits + g * dark_logits
        p = torch.softmax(DECODE_BETA * logits, dim=1)
        u = (p * self.cell_u).sum(dim=1, keepdim=True)
        v = (p * self.cell_v).sum(dim=1, keepdim=True)
        p1 = torch.softmax(logits, dim=1)  # unsharpened field
        u1 = (p1 * self.cell_u).sum(dim=1, keepdim=True)
        v1 = (p1 * self.cell_v).sum(dim=1, keepdim=True)
        pd = p.detach()
        peak = pd.max(dim=1, keepdim=True).values  # sharpened-field peak mass
        ent = -(pd * torch.log(pd + 1e-9)).sum(dim=1, keepdim=True) / float(np.log(self.grid_k * self.grid_k))
        gap = torch.sqrt((u.detach() - u1.detach()) ** 2 + (v.detach() - v1.detach()) ** 2 + 1e-12)
        z = self.conf_head(torch.cat([f.detach(), peak, ent, gap], dim=1))
        conf = torch.sigmoid(z - self.conf_shift)
        out = torch.cat([u, v, conf], dim=1)
        if return_logits:
            return out, logits
        return out


def build_model() -> nn.Module:
    return TinyLocNet()


def loss_fn(pred: torch.Tensor, logits: torch.Tensor,
            target_uv: torch.Tensor) -> torch.Tensor:
    """CE against a Gaussian-smoothed cell target + expected-coord L2 + conf BCE."""
    k = GRID_K
    cell_u, cell_v = _grid_centers(k)
    cell_u, cell_v = cell_u.to(logits.device), cell_v.to(logits.device)
    du = (cell_u[None, :] - target_uv[:, 0:1]) * k  # distance in cell units
    dv = (cell_v[None, :] - target_uv[:, 1:2]) * k
    g = torch.exp(-(du ** 2 + dv ** 2) / (2 * TARGET_SIGMA_CELLS ** 2))
    g = g / g.sum(dim=1, keepdim=True)
    ce = -(g * torch.log_softmax(logits, dim=1)).sum(dim=1).mean()

    coord_err = ((pred[:, :2] - target_uv) ** 2).sum(dim=1)
    coord_loss = coord_err.mean()
    with torch.no_grad():
        # conf is now a calibrated hit predictor for selective prediction --
        # the frozen scorer treats conf < 0.3 as abstention and requires
        # coverage >= 0.2 per cell.
        good = (coord_err.sqrt() < GOOD_ERR_UV).float()
    conf_loss = nn.functional.binary_cross_entropy(
        pred[:, 2].clamp(1e-6, 1 - 1e-6), good)
    return ce + coord_loss + 0.3 * conf_loss


def export_onnx(model: nn.Module, path: str):
    model.eval()
    dummy = torch.zeros(1, 3, 128, 128)
    torch.onnx.export(model, dummy, path, input_names=["frame"],
                      output_names=["uvc"], opset_version=17, dynamo=False)


def estimate_position(frame: np.ndarray, onnx_path: str, meta: dict):
    """Deployment-shaped inference: frame (128x128x3 uint8) -> (lat, lon, conf).

    On-device this maps to the P4 runtime; here it runs the same ONNX artifact.
    """
    import onnxruntime as ort
    from pipeline.common import px_to_lonlat
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    x = frame.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
    u, v, conf = sess.run(None, {"frame": x})[0][0]
    lon, lat = px_to_lonlat(meta, float(u) * meta["width"], float(v) * meta["height"])
    return lat, lon, float(conf)
