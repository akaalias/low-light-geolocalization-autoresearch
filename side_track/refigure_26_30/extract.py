"""One-off: dump experiments 26-30's design fields into side-track design.json
files, isolated from runs/pending_experiment.json (which the live loop owns).
"""
import json
import pathlib
import sqlite3

con = sqlite3.connect("experiments.sqlite")
con.row_factory = sqlite3.Row
cur = con.cursor()
cur.execute(
    "SELECT id, title, hypothesis, method, category, init_strategy, eli5, "
    "arch_json, arch_svg FROM experiments WHERE id BETWEEN 26 AND 30 ORDER BY id"
)
base = pathlib.Path(__file__).parent
for row in cur.fetchall():
    d = dict(row)
    eid = d["id"]
    out_dir = base / f"exp{eid}"
    out_dir.mkdir(exist_ok=True)
    design = {
        "title": d["title"],
        "hypothesis": d["hypothesis"],
        "method": d["method"],
        "category": d["category"],
        "init_strategy": d["init_strategy"],
        "eli5": d["eli5"],
        "architecture": json.loads(d["arch_json"]),
    }
    (out_dir / "design.json").write_text(json.dumps(design, indent=2))
    (out_dir / "original.svg").write_text(d["arch_svg"] or "")
    print(f"wrote {out_dir}/design.json and original.svg ({eid}: {d['title'][:60]})")
