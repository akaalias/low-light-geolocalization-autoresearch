"""FROZEN (see /FROZEN) — scoring, §6.

Primary metric (optimized by the loop): worst-case (max) median position
error in meters across all lighting buckets x the DEVELOPMENT areas given,
on eval-split crops. Target <= 20 m.

Gates folded into the scalar (§6): a per-area exported ONNX must fit the
ESP32-P4 envelope — file size <= MODEL_MAX_BYTES and single-thread host CPU
latency <= LATENCY_MAX_MS (a documented *proxy* for on-target latency, not a
measurement of it). Coverage rule: predictions with confidence < CONF_THRESHOLD
are abstentions; a (area, bucket) cell with coverage < MIN_COVERAGE scores
FAIL_SCORE — a model cannot pass by abstaining its way out.

Holdout (§5): scoring hamburg requires --holdout, writes to a separate output,
and must never feed the keep/revert decision (enforced in loop.sh).

Usage:
  python -m pipeline.score --areas berlin,prignitz --model-dir runs/X/models --out runs/X/metrics.json
  python -m pipeline.score --areas hamburg --holdout --model-dir ... --out runs/X/holdout.json
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from pipeline.common import (CROP_PX, DATA_DIR, LIGHTING_BUCKETS, area_dir,
                             load_areas, load_meta)
from pipeline.dataset import error_meters, extract_crop, list_crops

MODEL_MAX_BYTES = 4 * 1024 * 1024   # ESP32-P4 flash/PSRAM envelope per model
LATENCY_MAX_MS = 250.0              # single-thread host-CPU proxy budget
CONF_THRESHOLD = 0.3
MIN_COVERAGE = 0.2
FAIL_SCORE = 1e9
MAX_EVAL_CROPS_PER_BUCKET = 400     # deterministic subsample cap for speed


def load_session(onnx_path: Path):
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    return ort.InferenceSession(str(onnx_path), sess_options=opts,
                                providers=["CPUExecutionProvider"])


def predict(sess, crop_u8: np.ndarray) -> tuple[float, float, float]:
    x = crop_u8.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
    u, v, conf = sess.run(None, {sess.get_inputs()[0].name: x})[0][0]
    return float(u), float(v), float(conf)


def measure_latency_ms(sess) -> float:
    x = np.zeros((CROP_PX, CROP_PX, 3), dtype=np.uint8)
    for _ in range(3):
        predict(sess, x)
    ts = []
    for _ in range(20):
        t0 = time.perf_counter()
        predict(sess, x)
        ts.append((time.perf_counter() - t0) * 1000)
    return float(np.median(ts))


def score_area(area: str, model_dir: Path, data_dir: Path, heatmap_dir: Path | None):
    meta = load_meta(area, data_dir)
    onnx_path = model_dir / f"{area}.onnx"
    result = {"area": area, "buckets": {}, "gates": {}}

    size = onnx_path.stat().st_size if onnx_path.exists() else None
    result["gates"]["model_bytes"] = size
    if size is None or size > MODEL_MAX_BYTES:
        result["gates"]["failed"] = "missing model" if size is None else "model too large"
        return result

    sess = load_session(onnx_path)
    lat = measure_latency_ms(sess)
    result["gates"]["latency_ms_host_proxy"] = round(lat, 2)
    if lat > LATENCY_MAX_MS:
        result["gates"]["failed"] = "latency over proxy budget"
        return result

    crops = list_crops(area, meta["width"], meta["height"], "eval")
    if len(crops) > MAX_EVAL_CROPS_PER_BUCKET:
        idx = np.linspace(0, len(crops) - 1, MAX_EVAL_CROPS_PER_BUCKET).astype(int)
        crops = [crops[i] for i in idx]

    heat_points = []
    for bucket in LIGHTING_BUCKETS:
        img = np.asarray(Image.open(area_dir(area, data_dir) / "relight" / f"{bucket}.png"))
        errs, n_conf = [], 0
        for c in crops:
            crop = extract_crop(img, c["cx"], c["cy"], c["angle"])
            u, v, conf = predict(sess, crop)
            if conf >= CONF_THRESHOLD:
                n_conf += 1
                e = error_meters(meta, u, v, c["cx"], c["cy"])
                errs.append(e)
                heat_points.append((c["cx"], c["cy"], e))
        coverage = n_conf / max(len(crops), 1)
        cell = {
            "n_eval": len(crops),
            "coverage": round(coverage, 4),
            "median_error_m": round(float(np.median(errs)), 2) if errs else None,
            "mean_error_m": round(float(np.mean(errs)), 2) if errs else None,
        }
        cell["score"] = FAIL_SCORE if coverage < MIN_COVERAGE else cell["median_error_m"]
        result["buckets"][bucket] = cell

    if heatmap_dir:
        render_heatmap(area, data_dir, heat_points, heatmap_dir / f"heatmap_{area}.png")
    return result


def render_heatmap(area, data_dir, points, out_path: Path):
    base = Image.open(area_dir(area, data_dir) / "relight" / "midday.png").convert("RGB")
    base = Image.eval(base, lambda p: p // 2)  # dim for contrast
    draw = ImageDraw.Draw(base)
    for cx, cy, e in points:
        color = (60, 220, 60) if e < 20 else (240, 200, 40) if e < 50 else (230, 60, 60)
        draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=color)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    base.save(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--areas", required=True, help="comma-separated area names")
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--heatmap-dir", default=None)
    ap.add_argument("--holdout", action="store_true",
                    help="required to score a holdout-role area")
    args = ap.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR
    areas_cfg = load_areas()
    names = args.areas.split(",")
    for n in names:
        role = areas_cfg.get(n, {}).get("role")
        if role == "holdout" and not args.holdout:
            raise SystemExit(f"{n} is the blind holdout (§5); scoring it requires "
                             f"--holdout and its result must not drive keep/revert.")
        if role == "development" and args.holdout:
            raise SystemExit(f"--holdout runs must only contain holdout areas, got {n}")

    heat = Path(args.heatmap_dir) if args.heatmap_dir else None
    per_area = [score_area(n, Path(args.model_dir), data_dir, heat) for n in names]

    cell_scores = []
    for a in per_area:
        if a["gates"].get("failed"):
            cell_scores.append(FAIL_SCORE)
        else:
            cell_scores.extend(c["score"] for c in a["buckets"].values())
    primary = float(max(cell_scores)) if cell_scores else FAIL_SCORE

    out = {
        "kind": "holdout_check" if args.holdout else "development",
        "areas": per_area,
        "primary_worst_median_error_m": primary,
        "target_m": 20.0,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    label = "HOLDOUT" if args.holdout else "PRIMARY"
    print(f"{label} worst-case median error: {primary:.2f} m (target <= 20 m)")


if __name__ == "__main__":
    main()
