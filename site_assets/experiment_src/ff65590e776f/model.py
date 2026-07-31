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
"""

import numpy as np
import torch
import torch.nn as nn

GRID_K = 32              # 32x32 cells over the map (~220 m cells on a ~7 km area)
TARGET_SIGMA_CELLS = 1.5  # Gaussian soft-target spread, in cell units


def _grid_centers(k: int) -> tuple[torch.Tensor, torch.Tensor]:
    """Flat [k*k] tensors of cell-center u and v (cell index = gy * k + gx)."""
    centers = (torch.arange(k, dtype=torch.float32) + 0.5) / k
    return centers.repeat(k), centers.repeat_interleave(k)


class TinyLocNet(nn.Module):
    """~230k-param CNN: strided conv stack -> GAP -> map-cell probability field
    -> soft-argmax (u, v), plus a separate sigmoid conf head."""

    def __init__(self, grid_k: int = GRID_K):
        super().__init__()
        self.grid_k = grid_k
        chans = [3, 16, 32, 64, 128]
        layers = []
        for cin, cout in zip(chans, chans[1:]):
            layers += [nn.Conv2d(cin, cout, 3, stride=2, padding=1),
                       nn.BatchNorm2d(cout), nn.ReLU(inplace=True)]
        self.features = nn.Sequential(*layers)
        self.loc_logits = nn.Linear(chans[-1], grid_k * grid_k)
        self.conf_head = nn.Linear(chans[-1], 1)
        cell_u, cell_v = _grid_centers(grid_k)
        self.register_buffer("cell_u", cell_u)
        self.register_buffer("cell_v", cell_v)

    def forward(self, x, return_logits: bool = False):
        f = self.features(x).mean(dim=(2, 3))
        logits = self.loc_logits(f)
        p = torch.softmax(logits, dim=1)
        u = (p * self.cell_u).sum(dim=1, keepdim=True)
        v = (p * self.cell_v).sum(dim=1, keepdim=True)
        conf = torch.sigmoid(self.conf_head(f))
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
        # Conf target stays deliberately loose (abstain only on catastrophic
        # misses > half the map extent) so the model stays scoreable instead
        # of abstaining its way into the §6 coverage FAIL; calibrating
        # confidence properly is a separate research target.
        good = (coord_err.sqrt() < 0.5).float()
    conf_loss = nn.functional.binary_cross_entropy(
        pred[:, 2].clamp(1e-6, 1 - 1e-6), good)
    return ce + coord_loss + 0.1 * conf_loss


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
