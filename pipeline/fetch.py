"""FROZEN (see /FROZEN) — reference imagery fetch, §4 step 2.

Fetches open-licensed daytime Sentinel-2 L2A true-color imagery for an
arbitrary bbox from the AWS Open Data COG mirror (no credentials needed),
via the Element84 Earth Search STAC API, and reprojects it onto a 10 m/px
north-up grid in the bbox's local UTM zone.

License: Copernicus Sentinel data — free for any use with attribution
("Contains modified Copernicus Sentinel data"). No Google/Bing tiles, per spec.

Usage:
  python -m pipeline.fetch --area berlin
  python -m pipeline.fetch --name mytown --bbox 9.10,48.70,9.20,48.76
"""

import argparse
import datetime
import json
import urllib.request

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

from pipeline.common import (GSD_M, DATA_DIR, area_dir, load_areas, parse_bbox,
                             save_meta, utm_epsg_for)

STAC_URL = "https://earth-search.aws.element84.com/v1/search"
# Fixed default acquisition window so fetches are reproducible.
DEFAULT_DATERANGE = "2025-04-01T00:00:00Z/2025-09-30T23:59:59Z"
MAX_CLOUD = 8.0


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


def fetch_area(name: str, bbox: list[float], data_dir=None, daterange=DEFAULT_DATERANGE):
    epsg = utm_epsg_for(bbox)
    dst_crs = f"EPSG:{epsg}"
    left, bottom, right, top = transform_bounds("EPSG:4326", dst_crs, *bbox)
    # Snap grid to whole 10 m cells.
    left, top = np.floor(left / GSD_M) * GSD_M, np.ceil(top / GSD_M) * GSD_M
    width = int(np.ceil((right - left) / GSD_M))
    height = int(np.ceil((top - bottom) / GSD_M))
    dst_transform = from_origin(left, top, GSD_M, GSD_M)

    items = stac_search(bbox, daterange)
    if not items:
        raise SystemExit(f"No Sentinel-2 scenes found for bbox {bbox} in {daterange}")

    mosaic = np.zeros((3, height, width), dtype=np.uint8)
    used = []
    for item in items:
        if not (mosaic == 0).any():
            break
        href = item["assets"]["visual"]["href"]
        print(f"  reading {item['id']} (cloud {item['properties']['eo:cloud_cover']:.2f}%)")
        try:
            with rasterio.open(href) as src, WarpedVRT(
                    src, crs=dst_crs, transform=dst_transform,
                    width=width, height=height) as vrt:
                arr = vrt.read()
        except rasterio.errors.RasterioIOError as e:
            print(f"    skipped (read error: {e})")
            continue
        # TCI uses 0 as nodata; fill only pixels still empty in the mosaic.
        empty = (mosaic == 0).all(axis=0)
        has_data = (arr != 0).any(axis=0)
        fill = empty & has_data
        if fill.any():
            mosaic[:, fill] = arr[:, fill]
            used.append(item["id"])

    coverage = float(((mosaic != 0).any(axis=0)).mean())
    if coverage < 0.995:
        print(f"WARNING: mosaic only {coverage*100:.1f}% covered; consider a wider daterange")

    d = area_dir(name, data_dir)
    d.mkdir(parents=True, exist_ok=True)
    out = d / "reference.tif"
    with rasterio.open(
            out, "w", driver="GTiff", width=width, height=height, count=3,
            dtype="uint8", crs=dst_crs, transform=dst_transform,
            compress="lzw") as dst:
        dst.write(mosaic)

    save_meta(name, {
        "area": name,
        "bbox": bbox,
        "epsg": epsg,
        "origin_xy": [left, top],
        "gsd_m": GSD_M,
        "width": width,
        "height": height,
        "daterange": daterange,
        "stac_items": used,
        "coverage": coverage,
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "attribution": "Contains modified Copernicus Sentinel data",
    }, data_dir)
    print(f"  wrote {out} ({width}x{height} px, {coverage*100:.1f}% covered, "
          f"{len(used)} scenes)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", help="named area from areas.yaml")
    ap.add_argument("--name", help="name for an ad-hoc bbox area")
    ap.add_argument("--bbox", help="west,south,east,north (EPSG:4326)")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--daterange", default=DEFAULT_DATERANGE)
    args = ap.parse_args()

    from pathlib import Path
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
