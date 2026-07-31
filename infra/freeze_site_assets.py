"""Freeze the handful of images the published site needs into plain git.

WHY THIS EXISTS
---------------
Every image the pages link lives in runs/, which .gitattributes routes through
Git LFS. That made publishing depend on LFS being available: CI ran
`git lfs pull` to hydrate ~1.8 GB of pointers before it could build. On
2026-07-31 the account's LFS budget ran out and the deploy stopped dead — not
because anything was wrong with the site, but because the build could not
fetch binaries it barely uses.

It barely uses them because the pages reference **20 images**, and slimmed
they come to about 5 MB. The other ~1,790 MB is the research record: every
experiment's heatmaps, samples and worked examples, most of which no page has
ever linked.

So: slim exactly the referenced images, once, here — on a machine where LFS is
already hydrated — and commit the result to site_assets/ as ordinary git
objects. .gitattributes only routes `runs/**`, so nothing here goes through
LFS. build_site.sh then prefers these and never needs to hydrate anything, and
a deploy can no longer be held hostage by a binary budget.

The full-resolution originals in runs/ remain the research record and are
untouched. This directory is a *derived publishing artifact* — delete it and
re-run this script and you get it back byte-for-byte.

Slimming matches build_site.sh exactly, so the published pixels do not change:
heatmaps become 1400 px JPEG (photographic, ~4.6 MB as PNG), everything else
is copied as-is, and all of it is deduped by content hash.

Usage (run from a checkout with LFS hydrated, after gallery.py has rendered):
  .venv/bin/python infra/freeze_site_assets.py
"""

import hashlib
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "site_assets"
MANIFEST = ASSETS / "manifest.json"
PAGES = ["index.html"] + sorted(p.name and f"gallery/{p.name}"
                                for p in (ROOT / "gallery").glob("*.html"))


def referenced_paths() -> set[str]:
    """Every runs/ image the rendered pages actually link."""
    refs: set[str] = set()
    for rel in PAGES:
        f = ROOT / rel
        if not f.exists():
            continue
        for m in re.finditer(r"(?:\.\./)?(runs/[^\"'\s>)]+?\.(?:png|jpg))",
                             f.read_text()):
            refs.add(m.group(1))
    return refs


def slim(src: Path) -> tuple[bytes, str]:
    """Return (bytes, suffix) for the published copy of one image."""
    if src.name.startswith("heatmap_"):
        img = Image.open(src).convert("RGB")
        if img.width > 1400:
            img = img.resize((1400, round(img.height * 1400 / img.width)),
                             Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=87, optimize=True)
        return buf.getvalue(), ".jpg"
    return src.read_bytes(), src.suffix


def main() -> int:
    refs = referenced_paths()
    if not refs:
        print("no runs/ image references found — run autoresearch.gallery first",
              file=sys.stderr)
        return 1

    ASSETS.mkdir(exist_ok=True)
    for old in ASSETS.glob("*"):
        if old.is_file():
            old.unlink()

    manifest: dict[str, str] = {}
    seen: dict[str, str] = {}
    total = 0
    unhydrated = []
    for rel in sorted(refs):
        src = ROOT / rel
        if not src.exists():
            unhydrated.append(rel)
            continue
        # An unhydrated LFS pointer is a ~130-byte text file. Publishing one
        # would silently ship a broken image, so refuse rather than guess.
        if src.stat().st_size < 1024 and src.read_bytes().startswith(b"version "):
            unhydrated.append(rel)
            continue
        data, suffix = slim(src)
        h = hashlib.sha256(data).hexdigest()[:20]
        name = seen.get(h)
        if name is None:
            name = f"{h}{suffix}"
            (ASSETS / name).write_bytes(data)
            seen[h] = name
            total += len(data)
        manifest[rel] = name

    if unhydrated:
        print(f"REFUSING: {len(unhydrated)} referenced image(s) are missing or "
              f"are unhydrated LFS pointers — run `git lfs pull` first, or this "
              f"would publish broken images:", file=sys.stderr)
        for p in unhydrated[:10]:
            print(f"  {p}", file=sys.stderr)
        return 1

    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(f"froze {len(manifest)} referenced images -> {len(seen)} unique files, "
          f"{total/1e6:.1f} MB in site_assets/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
