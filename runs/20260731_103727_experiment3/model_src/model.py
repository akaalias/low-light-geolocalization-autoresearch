"""AGENT-EDITABLE — model architecture + deployment inference wrapper.

The autoresearch loop may rewrite anything here (architecture, loss,
confidence mechanism, unified vs. dispatcher+specialists, pretrained init
per CLAUDE.md §3/§9) as long as:
  - train.py exports one ONNX per area at <out>/models/<area>.onnx taking a
    1x3x128x128 float32 input in [0,1] and returning [[u, v, conf]] with
    u, v normalized map coords and conf in [0,1];
  - the export passes pipeline/score.py's frozen deployment gates.

Current: localization as MAP-CELL CLASSIFICATION, from-scratch init. The map
is cut into CELL_PX-square cells (Berlin: 55x54 = 2970); a conv trunk feeds a
C-way softmax over cells plus a within-cell offset head. The deployed fix is
the winning cell's centre nudged by the offset, and confidence is the softmax
mass on that winning cell — so belief spread across many cells reads as low
confidence and the frame becomes a safe abstention rather than a false fix.
Cell size is chosen so the parameterization alone suffices: a 128 m cell's
half-diagonal is 90.5 m, inside the 100 m usable radius, so naming the right
cell is already a usable fix.

The whole decode (argmax -> cell-centre table lookup -> offset -> conf) lives
INSIDE the exported graph, because the scorer runs the ONNX directly.
"""

import math

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

CELL_PX = 128  # map cell edge in raster px (== metres at this GSD)


def grid_dims(meta: dict) -> tuple[int, int]:
    """(gw, gh): map-cell grid covering the area's raster."""
    return (math.ceil(meta["width"] / CELL_PX), math.ceil(meta["height"] / CELL_PX))


class CellLocNet(nn.Module):
    """Conv trunk -> GAP -> (C-way cell logits, within-cell offset).

    forward() is the DEPLOYED path and returns [B, 3] = (u, v, conf).
    training_outputs() exposes the raw (logits, offset) for the loss.
    """

    def __init__(self, meta: dict):
        super().__init__()
        gw, gh = grid_dims(meta)
        self.gw, self.gh = gw, gh
        self.n_cells = gw * gh
        width, height = meta["width"], meta["height"]

        chans = [3, 32, 64, 128, 160]
        layers = []
        for cin, cout in zip(chans, chans[1:]):
            layers += [nn.Conv2d(cin, cout, 3, stride=2, padding=1),
                       nn.BatchNorm2d(cout), nn.ReLU(inplace=True)]
        self.features = nn.Sequential(*layers)
        self.cls_head = nn.Linear(chans[-1], self.n_cells)
        self.off_head = nn.Linear(chans[-1], 2)

        # Cell-centre lookup tables, in normalized map coords. Registered as
        # buffers so they bake into the ONNX graph as constants.
        idx = np.arange(self.n_cells)
        cell_u = ((idx % gw) + 0.5) * CELL_PX / width
        cell_v = ((idx // gw) + 0.5) * CELL_PX / height
        self.register_buffer("cell_u", torch.tensor(cell_u, dtype=torch.float32))
        self.register_buffer("cell_v", torch.tensor(cell_v, dtype=torch.float32))
        self.scale_u = CELL_PX / width
        self.scale_v = CELL_PX / height

    def training_outputs(self, x):
        f = self.features(x).mean(dim=(2, 3))
        # tanh*0.5 keeps offsets inside the cell, in (-0.5, 0.5) cell units.
        return self.cls_head(f), torch.tanh(self.off_head(f)) * 0.5

    def forward(self, x):
        logits, offset = self.training_outputs(x)
        p = F.softmax(logits, dim=1)
        conf, idx = p.max(dim=1)
        u = self.cell_u.index_select(0, idx) + offset[:, 0] * self.scale_u
        v = self.cell_v.index_select(0, idx) + offset[:, 1] * self.scale_v
        return torch.stack([u.clamp(0.0, 1.0), v.clamp(0.0, 1.0), conf], dim=1)


def build_model(meta: dict) -> nn.Module:
    return CellLocNet(meta)


def loss_fn(logits: torch.Tensor, offset_pred: torch.Tensor,
            target_cell_idx: torch.Tensor, target_offset: torch.Tensor) -> torch.Tensor:
    """Cross-entropy on the true map cell + smooth-L1 on the within-cell offset.

    No confidence loss term: confidence IS the softmax mass on the winning
    cell, so honest abstention falls out of the parameterization rather than
    being trained against a proxy target. Label smoothing is light (0.05) so a
    memorized cell can still reach ~0.95 and clear the scorer's 0.3 threshold.
    """
    return (F.cross_entropy(logits, target_cell_idx, label_smoothing=0.05)
            + 1.0 * F.smooth_l1_loss(offset_pred, target_offset))


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
