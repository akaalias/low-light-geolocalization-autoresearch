#!/usr/bin/env bash
# Assemble the public Pages site — used identically by CI and locally, so a
# locally-verified page IS the live page:
#
#   infra/build_site.sh            # renders + assembles into _site/
#   open _site/gallery/index.html  # exact preview of what goes live
#
# One renderer (autoresearch/gallery.py) produces the pages; this script only
# packages its untouched output next to the runs/ artifacts the pages link
# with their existing relative paths (../runs/...). No rewriting, no
# CI-specific templating — change gallery.py, verify locally, push, and the
# workflow publishes the same bytes.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-_site}"
PY="${PY:-.venv/bin/python}"; [ -x "$PY" ] || PY=python3

$PY -m autoresearch.gallery

rm -rf "$OUT"; mkdir -p "$OUT"
cp -R gallery "$OUT/gallery"
# Ship only what the pages reference: figures + the small JSON records
# (browsable provenance). Model binaries stay out of the site.
rsync -a --prune-empty-dirs \
  --include '*/' --include '*.png' --include '*.json' --include '*.md' \
  --exclude '*' runs/ "$OUT/runs/"
cp experiments.sqlite "$OUT/experiments.sqlite" 2>/dev/null || true
# Web-size the heatmaps IN THE SITE COPY only — the full-res originals in
# runs/ remain the research record. Heatmaps are full-area photographic
# renders (~4.6 MB each); at 100+ of them they blew past the Pages deploy
# timeout. 1400 px wide is crisp for the detail view and ~4-6x smaller.
$PY - "$OUT" <<'PYRESIZE'
import sys
from pathlib import Path
from PIL import Image
out = Path(sys.argv[1])
before = after = n = 0
for f in out.glob("runs/*/**/heatmap_*.png"):
    b = f.stat().st_size
    img = Image.open(f)
    if img.width > 1400:
        img = img.resize((1400, round(img.height * 1400 / img.width)),
                         Image.LANCZOS)
        img.save(f, optimize=True)
    before += b; after += f.stat().st_size; n += 1
print(f"heatmaps web-sized: {n} files, "
      f"{before/1e6:,.0f} MB -> {after/1e6:,.0f} MB")
PYRESIZE
# The site's front door is the rendered project overview (gallery.py writes
# it to the repo root alongside the gallery pages).
cp index.html "$OUT/index.html"
touch "$OUT/.nojekyll"
echo "site assembled in $OUT/ — open $OUT/gallery/index.html to preview exactly what goes live"
