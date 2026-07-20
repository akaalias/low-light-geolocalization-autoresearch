"""FROZEN (see /FROZEN) — shared helpers for the data pipeline.

Everything here is bbox-parameterized; no area-specific constants allowed.
"""

import json
import zlib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

# The six lighting buckets of §4, with their synthetic ambient level
# (1.0 = full daylight, 0 = no natural light). Artificial lights stay on
# regardless of ambient — that separation happens in relight.py.
LIGHTING_BUCKETS = {
    "morning": 0.55,
    "midday": 1.00,
    "afternoon": 0.75,
    "early_evening": 0.22,
    "evening": 0.07,
    "night": 0.012,
}

GSD_M = 10.0  # ground sample distance of the reference raster, meters/pixel
CROP_PX = 128  # model input crop size (1.28 km footprint at 10 m/px)


def stable_hash(s: str) -> int:
    """Deterministic across runs/machines (unlike Python's hash())."""
    return zlib.crc32(s.encode("utf-8"))


def load_areas(path: Path | None = None) -> dict:
    p = path or (REPO_ROOT / "areas.yaml")
    with open(p) as f:
        return yaml.safe_load(f)["areas"]


def parse_bbox(s: str) -> list[float]:
    """Parse 'west,south,east,north' degrees."""
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be west,south,east,north")
    w, s_, e, n = parts
    if not (w < e and s_ < n and -180 <= w <= 180 and -90 <= s_ <= 90):
        raise ValueError(f"invalid bbox: {parts}")
    return parts


def utm_epsg_for(bbox: list[float]) -> int:
    """UTM zone EPSG for the bbox center — meter-true local grid for any bbox."""
    lon = (bbox[0] + bbox[2]) / 2.0
    lat = (bbox[1] + bbox[3]) / 2.0
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def area_dir(area: str, data_dir: Path | None = None) -> Path:
    return (data_dir or DATA_DIR) / area


def load_meta(area: str, data_dir: Path | None = None) -> dict:
    with open(area_dir(area, data_dir) / "meta.json") as f:
        return json.load(f)


def save_meta(area: str, meta: dict, data_dir: Path | None = None) -> None:
    d = area_dir(area, data_dir)
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)


def px_to_lonlat(meta: dict, px: float, py: float) -> tuple[float, float]:
    """Pixel coords in the reference raster -> (lon, lat)."""
    from rasterio.warp import transform as rio_transform

    x0, y0 = meta["origin_xy"]  # UTM coords of raster origin (top-left)
    x = x0 + px * meta["gsd_m"]
    y = y0 - py * meta["gsd_m"]
    lons, lats = rio_transform(f"EPSG:{meta['epsg']}", "EPSG:4326", [x], [y])
    return lons[0], lats[0]
