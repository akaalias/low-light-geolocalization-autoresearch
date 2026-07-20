"""Self-refreshing HTML gallery rendered from the SQLite lineage log (§7).

Not frozen (presentation only — the loop may improve it, but the data it
renders comes solely from experiments.sqlite and runs/ artifacts).

Usage: python -m autoresearch.gallery   # writes gallery/index.html
Open gallery/index.html in a browser; it re-reads itself every 30 s.
"""

import html
import json
from pathlib import Path

from autoresearch.db import REPO_ROOT, connect

OUT = REPO_ROOT / "gallery" / "index.html"

CSS = """
body{font-family:-apple-system,Helvetica,sans-serif;background:#111;color:#ddd;margin:2em}
h1{font-weight:600} .exp{border:1px solid #333;border-radius:8px;margin:1.5em 0;padding:1em;background:#1a1a1a}
.exp.kept{border-color:#2a6} .exp.reverted{opacity:.65} .exp.holdout{border-color:#26a}
.metric{font-size:1.6em;font-weight:700} .pass{color:#4c4}.fail{color:#e55}
table{border-collapse:collapse;margin:.5em 0}td,th{border:1px solid #333;padding:.25em .6em;font-size:.85em}
img{max-width:260px;margin:.3em;border-radius:4px;vertical-align:top}
.desc{white-space:pre-wrap;color:#aaa;font-size:.9em}
.tag{font-size:.75em;padding:.15em .5em;border-radius:4px;background:#333;margin-left:.5em}
"""


def fmt_metric(v):
    if v is None:
        return "?"
    return "GATED FAIL" if v >= 1e9 else f"{v:.1f} m"


def render():
    conn = connect()
    conn.row_factory = lambda cur, row: {d[0]: row[i] for i, d in enumerate(cur.description)}
    exps = conn.execute("SELECT * FROM experiments ORDER BY id DESC").fetchall()
    parts = [f"<meta http-equiv='refresh' content='30'><meta charset='utf-8'>"
             f"<title>autoresearch — low-light geolocalization</title>"
             f"<style>{CSS}</style>",
             "<h1>UAV low-light geolocalization — experiment lineage</h1>",
             f"<p>{len(exps)} experiments · target: worst-case median error ≤ 20 m "
             f"across lighting buckets × development areas</p>"]
    for e in exps:
        status = ("holdout" if e["kind"] == "holdout_check"
                  else "kept" if e["kept"] else "reverted")
        ok = e["primary_metric"] is not None and e["primary_metric"] <= 20
        parts.append(f"<div class='exp {status}'>")
        parts.append(
            f"<div><b>#{e['id']} {html.escape(e['title'] or '')}</b> "
            f"<span class='tag'>{status}</span>"
            f"<span class='tag'>{html.escape(str(e['category']))}</span>"
            f"<span class='tag'>{html.escape(e['git_commit'][:10])}</span>"
            f"<span class='tag'>{html.escape(e['ts'][:19])}</span>"
            f"<span class='tag'>init: {html.escape(str(e['init_strategy']))}</span></div>")
        parts.append(f"<div class='metric {'pass' if ok else 'fail'}'>"
                     f"{fmt_metric(e['primary_metric'])}</div>")
        for label in ("hypothesis", "method", "expected_outcome", "result", "conclusion"):
            if e.get(label):
                parts.append(f"<div class='desc'><b>{label.replace('_', ' ')}:</b> "
                             f"{html.escape(e[label])}</div>")

        rows = conn.execute(
            "SELECT * FROM area_results WHERE experiment_id=? ORDER BY area, bucket",
            (e["id"],)).fetchall()
        if rows:
            parts.append("<table><tr><th>area</th><th>bucket</th><th>median m</th>"
                         "<th>mean m</th><th>coverage</th><th>n</th></tr>")
            for r in rows:
                parts.append(
                    f"<tr><td>{r['area']}</td><td>{r['bucket']}</td>"
                    f"<td>{r['median_error_m']}</td><td>{r['mean_error_m']}</td>"
                    f"<td>{r['coverage']}</td><td>{r['n_eval']}</td></tr>")
            parts.append("</table>")

        gates = json.loads(e["metrics_json"] or "{}")
        parts.append(f"<div class='desc'>max model size: {e['model_bytes_max']} B · "
                     f"host latency proxy: {e['latency_ms_host_proxy']} ms</div>")
        art = Path(e["artifacts_dir"] or "")
        if (REPO_ROOT / art).exists():
            imgs = sorted((REPO_ROOT / art).glob("samples/*.png")) + \
                   sorted((REPO_ROOT / art).glob("heatmaps/*.png"))
            for p in imgs:
                rel = Path("..") / p.relative_to(REPO_ROOT)
                parts.append(f"<img src='{rel}' title='{p.name}'>")
        parts.append("</div>")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(parts))
    print(f"wrote {OUT} ({len(exps)} experiments)")


if __name__ == "__main__":
    render()
