"""AGENT-EDITABLE — model architecture + deployment inference wrapper.

The autoresearch loop may rewrite anything here (architecture, loss,
confidence mechanism, unified vs. dispatcher+specialists, pretrained init
per CLAUDE.md §3/§9) as long as:
  - train.py exports one ONNX per area at <out>/models/<area>.onnx taking a
    1x3x128x128 float32 input in [0,1] and returning [[u, v, conf]] with
    u, v normalized map coords and conf in [0,1];
  - the export passes pipeline/score.py's frozen deployment gates.

Baseline: deliberately naive tiny CNN direct-coordinate regressor, from-scratch
init. It exists to prove the harness, not to be good.
"""

import numpy as np
import torch
import torch.nn as nn


class TinyLocNet(nn.Module):
    """~300k-param CNN: strided conv stack -> GAP -> (u, v, conf)."""

    def __init__(self):
        super().__init__()
        chans = [3, 16, 32, 64, 128]
        layers = []
        for cin, cout in zip(chans, chans[1:]):
            layers += [nn.Conv2d(cin, cout, 3, stride=2, padding=1),
                       nn.BatchNorm2d(cout), nn.ReLU(inplace=True)]
        self.features = nn.Sequential(*layers)
        self.head = nn.Linear(chans[-1], 3)

    def forward(self, x):
        f = self.features(x).mean(dim=(2, 3))
        out = self.head(f)
        uv = torch.sigmoid(out[:, :2])
        conf = torch.sigmoid(out[:, 2:3])
        return torch.cat([uv, conf], dim=1)


def build_model() -> nn.Module:
    return TinyLocNet()


def loss_fn(pred: torch.Tensor, target_uv: torch.Tensor) -> torch.Tensor:
    """MSE on coords + BCE training the conf head to predict 'error is small'."""
    coord_err = ((pred[:, :2] - target_uv) ** 2).sum(dim=1)
    coord_loss = coord_err.mean()
    with torch.no_grad():
        good = (coord_err.sqrt() < 0.05).float()  # within 5% of map extent
    conf_loss = nn.functional.binary_cross_entropy(
        pred[:, 2].clamp(1e-6, 1 - 1e-6), good)
    return coord_loss + 0.1 * conf_loss


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
