"""Freeze each experiment's recovered model source into plain git.

WHY THIS EXISTS
---------------
The gallery shows every experiment's agent-editable source inline, because the
whole search space is two files (model/model.py, model/train.py) and an
experiment IS a diff of them. That source comes from one of two places:

  * runs/<id>/model_src/ -- the exact bytes that trained, snapshotted by
    loop.sh. Plain git already, nothing to do here.
  * the experiment's own git commit tree -- for KEPT experiments that predate
    the snapshot guard (added 2026-07-31). Reading those needs git history.

And needing git history is the problem. CI checks out with `actions/checkout`
at its default fetch-depth of 1, so `git show <old-commit>:model/model.py`
returns nothing there. It fails quietly: the renderer would fall through to
"source not retained" for all of them and publish a page that looks correct
but has silently lost 16 experiments' code. Deepening the checkout is worse --
.git is 8.8 GB, and that job has already exhausted its disk once.

This is the same failure the images had. On 2026-07-31 publishing died because
the build hydrated ~1.8 GB of LFS to serve ~9 MB of pictures; the fix was to
freeze exactly what the pages reference into site_assets/ as ordinary git
objects. The recovered source is 147 KB. Freeze it for the same reason.

Keyed by commit hash, so a row finds its own source with no era/id mapping to
drift. site_assets/ is not routed through LFS (.gitattributes only matches
runs/**), so nothing here needs hydrating either.

Like site_assets/, this is a *derived* artifact: delete it, re-run this, and
you get it back byte-for-byte. The commits remain the record.

Usage (from a full checkout, i.e. a dev machine, not CI):
  .venv/bin/python infra/freeze_experiment_src.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autoresearch import gallery as g  # noqa: E402

OUT = g.FROZEN_SRC
MANIFEST = OUT / "manifest.json"


def rows():
    """Every experiment row across all eras, current era last."""
    seen = []
    hist, _ = g.load_history()
    seen += hist
    conn = g.connect()
    conn.row_factory = lambda cur, r: {d[0]: r[i]
                                       for i, d in enumerate(cur.description)}
    seen += conn.execute("SELECT * FROM experiments").fetchall()
    conn.close()
    return seen


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest, wrote, skipped, already = {}, 0, [], 0
    for e in rows():
        commit = (e.get("git_commit") or "").strip()
        if not commit or not e.get("kept"):
            continue                                  # see source_of(): a
            # reverted row's git_commit is not its code, so it is never a
            # candidate -- freezing it would bake in the champion's source
            # under the wrong experiment's name.
        art = e.get("artifacts_dir")
        if art and (g.REPO_ROOT / art / "model_src" / "model.py").exists():
            already += 1
            continue                                  # exact snapshot exists
        key = commit[:12]
        if key in manifest:
            continue
        src = g.git_src(commit)
        if not src:
            skipped.append(key)
            continue
        d = OUT / key
        d.mkdir(parents=True, exist_ok=True)
        for name, text in src.items():
            p = d / name
            if not p.exists() or p.read_text(encoding="utf-8") != text:
                p.write_text(text, encoding="utf-8")
                wrote += 1
        manifest[key] = sorted(src)

    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    total = sum(len((OUT / k / n).read_bytes())
                for k, ns in manifest.items() for n in ns)
    print(f"froze {len(manifest)} commits -> "
          f"{sum(len(v) for v in manifest.values())} files, {total/1024:.0f} KB "
          f"({wrote} written this run)")
    print(f"  {already} experiments already have an exact model_src snapshot")
    if skipped:
        # Not an error: some archived rows reference commits that no longer
        # exist in this history at all. Named so the count is never a mystery.
        print(f"  {len(skipped)} commit(s) unreachable, left unavailable: "
              f"{', '.join(skipped[:6])}{' ...' if len(skipped) > 6 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
