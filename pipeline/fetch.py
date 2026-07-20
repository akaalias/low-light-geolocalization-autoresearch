"""FROZEN (see /FROZEN) — reference imagery fetch, §4 step 2.

Fetches open-licensed daytime reference imagery for an arbitrary bbox onto a
north-up grid in the bbox's local UTM zone at the registry's target GSD
(default 1 m/px — matched to a UAV camera footprint at ~100 m AGL).

Sources come from pipeline/sources.yaml (a data file, keeping this code
bbox-generic): regional open-data DOP orthophoto WMS services where coverage
exists (20-40 cm native, server-resampled to the target GSD), with global
Sentinel-2 L2A (10 m/px, credential-free AWS COGs via Earth Search STAC) as
fallback. No Google/Bing tiles anywhere, per spec.

Usage:
  python -m pipeline.fetch --area berlin
  python -m pipeline.fetch --name mytown --bbox 9.10,48.70,9.20,48.76
"""

import argparse
import datetime
import io
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
import yaml
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

from pipeline.common import (DATA_DIR, REPO_ROOT, area_dir, load_areas,
                             parse_bbox, save_meta, utm_epsg_for)

STAC_URL = "https://earth-search.aws.element84.com/v1/search"
# Fixed default acquisition window so Sentinel fetches are reproducible.
DEFAULT_DATERANGE = "2025-04-01T00:00:00Z/2025-09-30T23:59:59Z"
MAX_CLOUD = 8.0
TILE_PX = 2048           # target-grid tile size per WMS request
WMS_OVERSAMPLE = 1.15    # request slightly finer than target to protect detail
WMS_RETRIES = 3


def load_sources():
    with open(REPO_ROOT / "pipeline" / "sources.yaml") as f:
        cfg = yaml.safe_load(f)
    return cfg["target_gsd_m"], cfg["sources"]


def pick_source(bbox, sources):
    def contains(cov):
        return (cov[0] <= bbox[0] and cov[1] <= bbox[1]
                and cov[2] >= bbox[2] and cov[3] >= bbox[3])
    candidates = [s for s in sources if contains(s["coverage"])]
    if not candidates:
        raise SystemExit(f"no imagery source covers bbox {bbox}")
    return min(candidates, key=lambda s: s["native_gsd_m"])


def make_target_grid(bbox, gsd):
    epsg = utm_epsg_for(bbox)
    dst_crs = f"EPSG:{epsg}"
    left, bottom, right, top = transform_bounds("EPSG:4326", dst_crs, *bbox)
    left, top = np.floor(left / gsd) * gsd, np.ceil(top / gsd) * gsd
    width = int(np.ceil((right - left) / gsd))
    height = int(np.ceil((top - bottom) / gsd))
    return epsg, dst_crs, from_origin(left, top, gsd, gsd), width, height, (left, top)


# --- WMS path -------------------------------------------------------------

def wms_getmap(src, bbox4326, px_w, px_h):
    """One GetMap request in EPSG:4326, version-aware axis order."""
    w, s, e, n = bbox4326
    v = src["wms_version"]
    params = {
        "SERVICE": "WMS", "VERSION": v, "REQUEST": "GetMap",
        "LAYERS": src["layer"], "STYLES": "",
        "WIDTH": str(px_w), "HEIGHT": str(px_h), "FORMAT": "image/png",
    }
    if v == "1.3.0":
        params["CRS"] = "EPSG:4326"
        params["BBOX"] = f"{s},{w},{n},{e}"   # 1.3.0: lat,lon order
    else:
        params["SRS"] = "EPSG:4326"
        params["BBOX"] = f"{w},{s},{e},{n}"
    url = src["url"] + ("&" if "?" in src["url"] else "?") + urllib.parse.urlencode(params)
    last_err = None
    for attempt in range(WMS_RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                data = r.read()
            if not data.startswith(b"\x89PNG"):
                raise IOError(f"non-PNG response ({data[:80]!r})")
            return data
        except Exception as e:  # noqa: BLE001 — retry any transport error
            last_err = e
            time.sleep(3 * (attempt + 1))
    raise IOError(f"WMS GetMap failed after {WMS_RETRIES} tries: {last_err}")


def fetch_wms(src, dst_crs, dst_transform, width, height, gsd):
    """Tile over the target grid; each tile: WMS 4326 image -> warp to UTM."""
    mosaic = np.zeros((3, height, width), dtype=np.uint8)
    n_tiles_x = int(np.ceil(width / TILE_PX))
    n_tiles_y = int(np.ceil(height / TILE_PX))
    for ty in range(n_tiles_y):
        for tx in range(n_tiles_x):
            x0, y0 = tx * TILE_PX, ty * TILE_PX
            tw, th = min(TILE_PX, width - x0), min(TILE_PX, height - y0)
            # Tile bounds in target CRS, then in EPSG:4326.
            left = dst_transform.c + x0 * gsd
            top = dst_transform.f - y0 * gsd
            tile_bounds = (left, top - th * gsd, left + tw * gsd, top)
            b4326 = transform_bounds(dst_crs, "EPSG:4326", *tile_bounds)
            req_w = int(tw * WMS_OVERSAMPLE)
            req_h = int(th * WMS_OVERSAMPLE)
            png = wms_getmap(src, b4326, req_w, req_h)
            print(f"  tile {tx},{ty} ({tw}x{th}px) fetched", flush=True)
            # Wrap the PNG with its known 4326 georeferencing, warp into place.
            with MemoryFile(png) as mem, mem.open() as ds:
                arr = ds.read()
                if arr.shape[0] == 1:
                    arr = np.repeat(arr, 3, axis=0)
                t4326 = rasterio.transform.from_bounds(
                    b4326[0], b4326[1], b4326[2], b4326[3], ds.width, ds.height)
                profile = {"driver": "GTiff", "count": 3, "dtype": "uint8",
                           "width": ds.width, "height": ds.height,
                           "crs": "EPSG:4326", "transform": t4326}
                with MemoryFile() as gmem:
                    with gmem.open(**profile) as gds:
                        gds.write(arr[:3])
                    with gmem.open() as gds, WarpedVRT(
                            gds, crs=dst_crs,
                            transform=rasterio.transform.from_origin(left, top, gsd, gsd),
                            width=tw, height=th) as vrt:
                        mosaic[:, y0:y0 + th, x0:x0 + tw] = vrt.read()
    return mosaic, {"tiles": n_tiles_x * n_tiles_y}


# --- Sentinel-2 fallback path --------------------------------------------

def stac_search(bbox, daterange, limit=30):
    body = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": daterange,
        "query": {"eo:cloud_cover": {"lt": MAX_CLOUD}},
        "limit": limit,
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
    }
    req = urllib.request.Request(
        STAC_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["features"]


def fetch_sentinel(bbox, daterange, dst_crs, dst_transform, width, height):
    items = stac_search(bbox, daterange)
    if not items:
        raise SystemExit(f"No Sentinel-2 scenes for bbox {bbox} in {daterange}")
    mosaic = np.zeros((3, height, width), dtype=np.uint8)
    used = []
    for item in items:
        if not (mosaic == 0).any():
            break
        href = item["assets"]["visual"]["href"]
        print(f"  reading {item['id']} (cloud {item['properties']['eo:cloud_cover']:.2f}%)")
        try:
            with rasterio.open(href) as s2, WarpedVRT(
                    s2, crs=dst_crs, transform=dst_transform,
                    width=width, height=height) as vrt:
                arr = vrt.read()
        except rasterio.errors.RasterioIOError as e:
            print(f"    skipped (read error: {e})")
            continue
        empty = (mosaic == 0).all(axis=0)
        has_data = (arr != 0).any(axis=0)
        fill = empty & has_data
        if fill.any():
            mosaic[:, fill] = arr[:, fill]
            used.append(item["id"])
    return mosaic, {"stac_items": used, "daterange": daterange}


# --- entry point ----------------------------------------------------------

def fetch_area(name: str, bbox: list[float], data_dir=None,
               daterange=DEFAULT_DATERANGE):
    target_gsd, sources = load_sources()
    src = pick_source(bbox, sources)
    gsd = max(target_gsd, src["native_gsd_m"])
    epsg, dst_crs, dst_transform, width, height, (left, top) = \
        make_target_grid(bbox, gsd)
    print(f"  source={src['name']} gsd={gsd} m/px grid={width}x{height}px")

    if src["kind"] == "wms":
        mosaic, extra = fetch_wms(src, dst_crs, dst_transform, width, height, gsd)
    elif src["kind"] == "sentinel2_stac":
        mosaic, extra = fetch_sentinel(bbox, daterange, dst_crs, dst_transform,
                                       width, height)
    else:
        raise SystemExit(f"unknown source kind {src['kind']}")

    coverage = float(((mosaic != 0).any(axis=0)).mean())
    if coverage < 0.995:
        print(f"WARNING: mosaic only {coverage*100:.1f}% covered")

    d = area_dir(name, data_dir)
    d.mkdir(parents=True, exist_ok=True)
    out = d / "reference.tif"
    with rasterio.open(
            out, "w", driver="GTiff", width=width, height=height, count=3,
            dtype="uint8", crs=dst_crs, transform=dst_transform,
            compress="lzw", tiled=True) as dst:
        dst.write(mosaic)

    save_meta(name, {
        "area": name,
        "pipeline_data_version": 2,
        "bbox": bbox,
        "epsg": epsg,
        "origin_xy": [left, top],
        "gsd_m": gsd,
        "width": width,
        "height": height,
        "source": src["name"],
        "coverage": coverage,
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "attribution": src["attribution"],
        **extra,
    }, data_dir)
    print(f"  wrote {out} ({width}x{height}px @ {gsd}m, {coverage*100:.1f}% covered)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", help="named area from areas.yaml")
    ap.add_argument("--name", help="name for an ad-hoc bbox area")
    ap.add_argument("--bbox", help="west,south,east,north (EPSG:4326)")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--daterange", default=DEFAULT_DATERANGE,
                    help="sentinel2 fallback only")
    args = ap.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR
    if args.area:
        areas = load_areas()
        if args.area not in areas:
            raise SystemExit(f"unknown area {args.area}; known: {list(areas)}")
        name, bbox = args.area, areas[args.area]["bbox"]
    elif args.name and args.bbox:
        name, bbox = args.name, parse_bbox(args.bbox)
    else:
        raise SystemExit("need --area OR (--name AND --bbox)")

    print(f"Fetching {name} bbox={bbox}")
    fetch_area(name, bbox, data_dir, args.daterange)


if __name__ == "__main__":
    main()
