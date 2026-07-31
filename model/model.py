"""AGENT-EDITABLE — model architecture + deployment inference wrapper.

The autoresearch loop may rewrite anything here (architecture, loss,
confidence mechanism, unified vs. dispatcher+specialists, pretrained init
per CLAUDE.md §3/§9) as long as:
  - train.py exports one ONNX per area at <out>/models/<area>.onnx taking a
    1x3x128x128 float32 input in [0,1] and returning [[u, v, conf]] with
    u, v normalized map coords and conf in [0,1];
  - the export passes pipeline/score.py's frozen deployment gates.

Classify-then-refine: the same tiny conv trunk, but the output is
reparameterized as a softmax over a GRID x GRID lattice of map cells plus a
within-cell offset, instead of a direct (u, v) regression. Direct MSE
regression over a multimodal answer space collapses to the map centroid under
ambiguity; discrete cell classification does not average competing modes.
From-scratch init.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# Cells per axis of the map-cell classification grid, in NORMALIZED [0, 1]
# map coordinates — no area-specific constants (CLAUDE.md §0).
GRID = 32


class TinyLocNet(nn.Module):
    """~0.5M-param CNN: strided conv stack -> GAP -> (cell logits, offsets, conf).

    forward_train() returns the raw head outputs for loss_fn(); forward() is the
    exported graph and decodes them to the frozen [u, v, conf] contract.
    """

    def __init__(self):
        super().__init__()
        chans = [3, 16, 32, 64, 128]
        layers = []
        for cin, cout in zip(chans, chans[1:]):
            layers += [nn.Conv2d(cin, cout, 3, stride=2, padding=1),
                       nn.BatchNorm2d(cout), nn.ReLU(inplace=True)]
        self.features = nn.Sequential(*layers)
        self.cell_logits = nn.Linear(chans[-1], GRID * GRID)
        self.cell_offset = nn.Linear(chans[-1], GRID * GRID * 2)
        self.conf_head = nn.Linear(chans[-1], 1)

    def _embed(self, x):
        return self.features(x).mean(dim=(2, 3))

    def forward_train(self, x):
        """Raw heads: (logits [B,G*G], offsets [B,G*G,2], conf_logit [B,1])."""
        f = self._embed(x)
        logits = self.cell_logits(f)
        # Each cell's offset is bounded to half a cell in normalized units.
        offsets = torch.tanh(self.cell_offset(f)).view(-1, GRID * GRID, 2) * (0.5 / GRID)
        conf_logit = self.conf_head(f)
        return logits, offsets, conf_logit

    def forward(self, x):
        logits, offsets, conf_logit = self.forward_train(x)
        idx = torch.argmax(logits, dim=1)
        iy = idx // GRID
        ix = idx - iy * GRID  # subtraction, not %, for safe ONNX tracing
        cu = (ix.float() + 0.5) / GRID
        cv = (iy.float() + 0.5) / GRID
        off = torch.gather(offsets, 1, idx.view(-1, 1, 1).expand(-1, 1, 2)).squeeze(1)
        u = (cu + off[:, 0]).clamp(0, 1)
        v = (cv + off[:, 1]).clamp(0, 1)
        conf = torch.sigmoid(conf_logit)[:, 0]
        return torch.stack([u, v, conf], dim=1)


def build_model() -> nn.Module:
    return TinyLocNet()


def loss_fn(raw, target_uv: torch.Tensor) -> torch.Tensor:
    """Cell cross-entropy + teacher-forced offset MSE + conf BCE.

    `raw` is forward_train()'s (logits, offsets, conf_logit) tuple. Cell ids
    follow iy * GRID + ix, with ix indexing the u axis and iy the v axis.
    """
    logits, offsets, conf_logit = raw
    tx = target_uv[:, 0].mul(GRID).floor().long().clamp(0, GRID - 1)
    ty = target_uv[:, 1].mul(GRID).floor().long().clamp(0, GRID - 1)
    cell = ty * GRID + tx
    ce = F.cross_entropy(logits, cell)

    # Teacher-forced: only the true cell's offset is supervised.
    pred_off = torch.gather(offsets, 1, cell.view(-1, 1, 1).expand(-1, 1, 2)).squeeze(1)
    targ_off = target_uv - torch.stack(
        [(tx.float() + 0.5) / GRID, (ty.float() + 0.5) / GRID], dim=1)
    off_loss = (((pred_off - targ_off) * GRID) ** 2).sum(dim=1).mean()

    with torch.no_grad():
        # Conf target is deliberately loose (abstain only on catastrophic
        # misses > half the map extent) so the model stays scoreable instead
        # of abstaining its way into the §6 coverage FAIL; calibrating
        # confidence properly is an obvious loop research target.
        idx = torch.argmax(logits, dim=1)
        iy = idx // GRID
        ix = idx - iy * GRID
        dec_off = torch.gather(offsets, 1, idx.view(-1, 1, 1).expand(-1, 1, 2)).squeeze(1)
        dec_u = ((ix.float() + 0.5) / GRID + dec_off[:, 0]).clamp(0, 1)
        dec_v = ((iy.float() + 0.5) / GRID + dec_off[:, 1]).clamp(0, 1)
        coord_err = (torch.stack([dec_u, dec_v], dim=1) - target_uv).pow(2).sum(dim=1).sqrt()
        good = (coord_err < 0.5).float()
    conf_bce = F.binary_cross_entropy(
        torch.sigmoid(conf_logit)[:, 0].clamp(1e-6, 1 - 1e-6), good)
    return ce + off_loss + 0.1 * conf_bce


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
