"""AGENT-EDITABLE — model architecture + deployment inference wrapper.

The autoresearch loop may rewrite anything here (architecture, loss,
confidence mechanism, unified vs. dispatcher+specialists, pretrained init
per CLAUDE.md §3/§9) as long as:
  - train.py exports one ONNX per area at <out>/models/<area>.onnx taking a
    1x3x128x128 float32 input in [0,1] and returning [[u, v, conf]] with
    u, v normalized map coords and conf in [0,1];
  - the export passes pipeline/score.py's frozen deployment gates.

Current: the map is a GRID x GRID checkerboard and the trunk classifies which
cell the frame came from. Coordinates are a soft-argmax over the posterior;
confidence is the mass in the best CONF_POOL x CONF_POOL neighborhood.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

GRID = 64          # map is diced into GRID x GRID cells
LABEL_SIGMA = 1.0  # Gaussian soft-label width, in cells
CONF_POOL = 5      # confidence = posterior mass in the best 5x5 neighborhood


def _cell_centers(device=None):
    """Normalized (u, v) centers of the GRID*GRID cells, row-major."""
    k = torch.arange(GRID * GRID, device=device)
    cell_u = ((k % GRID).float() + 0.5) / GRID
    cell_v = ((k // GRID).float() + 0.5) / GRID
    return cell_u, cell_v


class TinyLocNet(nn.Module):
    """~630k-param CNN: strided conv stack -> GAP -> GRID^2 cell logits."""

    def __init__(self):
        super().__init__()
        chans = [3, 16, 32, 64, 128]
        layers = []
        for cin, cout in zip(chans, chans[1:]):
            layers += [nn.Conv2d(cin, cout, 3, stride=2, padding=1),
                       nn.BatchNorm2d(cout), nn.ReLU(inplace=True)]
        self.features = nn.Sequential(*layers)
        self.head = nn.Linear(chans[-1], GRID * GRID)
        cell_u, cell_v = _cell_centers()
        self.register_buffer("cell_u", cell_u)
        self.register_buffer("cell_v", cell_v)

    def forward_logits(self, x):
        """Raw per-cell logits, (B, GRID*GRID). The training-time graph."""
        f = self.features(x).mean(dim=(2, 3))
        return self.head(f)

    def forward(self, x):
        logits = self.forward_logits(x)
        p = torch.softmax(logits, dim=1)
        u = (p * self.cell_u).sum(dim=1, keepdim=True)
        v = (p * self.cell_v).sum(dim=1, keepdim=True)
        # Mass in the best CONF_POOL-wide neighborhood: a peaked posterior is
        # confident, a diffuse one abstains.
        pm = p.reshape(-1, 1, GRID, GRID)
        neigh = F.avg_pool2d(pm, CONF_POOL, stride=1,
                             padding=CONF_POOL // 2) * (CONF_POOL ** 2)
        conf = neigh.amax(dim=(1, 2, 3)).unsqueeze(1).clamp(0.0, 1.0)
        return torch.cat([u, v, conf], dim=1)


def build_model() -> nn.Module:
    return TinyLocNet()


_CELL_CACHE = {}


def _cached_cell_centers(device):
    key = str(device)
    if key not in _CELL_CACHE:
        _CELL_CACHE[key] = _cell_centers(device)
    return _CELL_CACHE[key]


def loss_fn(logits: torch.Tensor, target_uv: torch.Tensor) -> torch.Tensor:
    """Gaussian-soft-label cross-entropy over cells + soft-argmax aux MSE.

    logits: (B, GRID*GRID) from TinyLocNet.forward_logits; target_uv: (B, 2).
    """
    cell_u, cell_v = _cached_cell_centers(logits.device)
    gu = target_uv[:, 0] * GRID - 0.5
    gv = target_uv[:, 1] * GRID - 0.5
    with torch.no_grad():
        axis = torch.arange(GRID, device=logits.device, dtype=logits.dtype)
        # (B, GRID, GRID): v/rows on dim 1, u/cols on dim 2 — same row-major
        # layout as forward()'s reshape.
        d2 = ((axis - gu[:, None, None]) ** 2
              + (axis[:, None] - gv[:, None, None]) ** 2)
        q = torch.softmax(-d2.flatten(1) / (2 * LABEL_SIGMA ** 2), dim=1)
    ce = -(q * torch.log_softmax(logits, dim=1)).sum(dim=1).mean()
    p = torch.softmax(logits, dim=1)
    uv_hat = torch.stack([(p * cell_u).sum(dim=1), (p * cell_v).sum(dim=1)], dim=1)
    aux = ((uv_hat - target_uv) ** 2).sum(dim=1).mean()
    return ce + 10.0 * aux


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
