"""Self-refreshing HTML research dashboard rendered from the SQLite lineage
log (§7), styled after the human's prior research dashboards (Tufte cream /
ink / Palatino vocabulary: airloom log, Heuristic Kitchen dashboard,
FMDiscovery autoresearch dashboard).

Not frozen (presentation only — the data it renders comes solely from
experiments.sqlite and runs/ artifacts).

Usage: python -m autoresearch.gallery   # writes gallery/index.html
"""

import datetime
import html
import json
import math
from pathlib import Path

from autoresearch.db import REPO_ROOT, connect

OUT = REPO_ROOT / "gallery" / "index.html"
TARGET_M = 20.0
FAIL = 1e9

CSS = """
:root{
  --paper:#fffff8; --ink:#111111; --muted:#6b6a60; --faint:#9b998c;
  --rule:#d9d5c3; --rule-soft:#ece9da; --accent:#8c2f1f;
  --kept:#111111; --disc:#b9b6a6; --ochre:#8a6a1e;
  --serif:"Palatino","Palatino Linotype","Book Antiqua","URW Palladio L",Georgia,serif;
  --mono:ui-monospace,"SF Mono",Menlo,monospace;
}
*{box-sizing:border-box}
html{background:var(--paper)}
body{margin:0;background:var(--paper);color:var(--ink);
  font:16px/1.55 var(--serif);font-feature-settings:"onum" 1,"liga" 1;
  -webkit-font-smoothing:antialiased;overflow-x:auto}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid transparent}
a:hover{border-bottom-color:var(--accent)}
.smcp{font-feature-settings:"smcp" 1;text-transform:uppercase;letter-spacing:.05em}
.num{font-variant-numeric:lining-nums tabular-nums}
.mono{font-family:var(--mono);font-size:12px}

.dash-head{max-width:92vw;margin:0 auto;padding:40px 0 6px}
.eyebrow{font:600 12px var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.09em;color:var(--muted);margin-bottom:10px}
.dash-head h1{font-size:34px;margin:0 0 8px;font-weight:600}
.dash-head .sub{margin:0 0 14px;color:var(--muted)}
.dash-meta{display:flex;flex-wrap:wrap;align-items:baseline;gap:14px 26px;
  font-size:13.5px;color:var(--muted)}
.k{display:inline-flex;align-items:center;gap:7px}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block}
.dot.kept{background:var(--ink)} .dot.disc{background:var(--disc)}
.ring{width:9px;height:9px;border-radius:50%;display:inline-block;
  border:1.5px solid var(--ochre);background:transparent}
.bar{width:16px;height:0;border-top:2px solid var(--ink);display:inline-block}
.bar.dash{border-top-style:dashed;border-top-color:var(--accent)}
.x{color:var(--accent);font-weight:700}
#updated{color:var(--faint);font-style:italic;margin-left:auto}

.dash-wrap{max-width:92vw;margin:0 auto;padding:4px 0 64px}
.chart-card{border-top:1px solid var(--rule);padding:14px 0 4px;margin-top:18px}
.chart-card svg{width:100%;height:auto;display:block}
.axis-lab{font:11px var(--serif);fill:var(--faint)}
.tick-line{stroke:var(--rule-soft);stroke-width:1}

.tbl-card{border-top:1.5px solid var(--ink);margin-top:26px}
table.main{width:100%;border-collapse:collapse;font-size:14px}
table.main th{font:600 11.5px/1.2 var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.05em;color:var(--muted);
  border-bottom:1.5px solid var(--ink);white-space:nowrap;text-align:left;
  padding:9px 12px 9px 0}
table.main td{border-bottom:1px solid var(--rule-soft);padding:9px 12px 9px 0;
  vertical-align:baseline;text-align:left}
tr.row-main{cursor:pointer}
tr.row-main:hover{background:#f7f3e3}
tr.kept-row{box-shadow:inset 2px 0 0 var(--ink)}
tr.kept-row td:first-child{padding-left:12px}
td.title-cell b{font-weight:600}
.caret{color:var(--faint);display:inline-block;width:12px;transition:transform .15s}
tr.open .caret{transform:rotate(90deg)}
.st-kept{color:var(--ink);font-weight:600}
.st-disc{color:var(--faint)}
.st-fail{color:var(--accent);font-weight:600}
.st-hold{color:var(--ochre);font-weight:600}
.cat{color:var(--muted);font:600 11.5px var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.05em}

tr.detail td{background:#fcfbf2;padding:0;border-bottom:1px solid var(--rule)}
.detail-inner{padding:16px 18px 20px 38px}
.explain{display:flex;flex-direction:column;gap:12px;max-width:920px}
.eb{border-left:2px solid var(--rule);padding:7px 14px 8px 16px;background:#fff;
  box-shadow:0 1px 7px rgba(60,50,30,.08);border-radius:0 3px 3px 0}
.eb-h{font:800 11px/1 var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:5px}
.eb p{margin:0;font-size:13.5px;line-height:1.55;color:#33312b}
.eb-hyp{border-left-color:var(--muted)}
.eb-met{border-left-color:var(--ochre)} .eb-met .eb-h{color:var(--ochre)}
.eb-exp{border-left-color:var(--rule)}
.eb-res{border-left-color:var(--ink)} .eb-res .eb-h{color:var(--ink)}
.eb-con{border-left-color:var(--accent)} .eb-con .eb-h{color:var(--accent)}

table.cells{border-collapse:collapse;font-size:12.5px;margin:16px 0 4px}
table.cells th{font:600 10.5px/1.2 var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.05em;color:var(--muted);
  border-bottom:1px solid var(--ink);padding:5px 14px 5px 0;text-align:left}
table.cells td{border-bottom:1px solid var(--rule-soft);padding:4px 14px 4px 0}
.cov{color:var(--faint);font-size:11px}
.cell-bad{color:var(--accent);font-weight:600}
.cell-good{color:var(--ink);font-weight:600}

.thumbs{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
.thumbs figure{margin:0}
.thumbs img{height:120px;display:block;border:1px solid var(--rule)}
.thumbs figcaption{font:11px var(--serif);color:var(--faint);margin-top:3px}
.gates{font-size:12.5px;color:var(--muted);margin-top:14px}
"""

JS = """
function toggle(id){
  var d=document.getElementById('d'+id), r=document.getElementById('r'+id);
  var open=d.style.display!=='none';
  d.style.display=open?'none':'table-row';
  r.classList.toggle('open',!open);
  try{
    var s=JSON.parse(sessionStorage.getItem('open')||'[]');
    if(open){s=s.filter(function(x){return x!==id})}else{s.push(id)}
    sessionStorage.setItem('open',JSON.stringify(s));
  }catch(e){}
}
window.addEventListener('load',function(){
  try{JSON.parse(sessionStorage.getItem('open')||'[]').forEach(function(id){
    var d=document.getElementById('d'+id);
    if(d){d.style.display='table-row';
      document.getElementById('r'+id).classList.add('open')}
  })}catch(e){}
});
"""


def esc(s):
    return html.escape(str(s if s is not None else ""))


def fmt_m(v):
    if v is None:
        return "—"
    if v >= FAIL:
        return "×"
    return f"{v:,.1f}"


def chart_svg(exps):
    """Static SVG progress chart: primary error per experiment, log y,
    running-best step line, dashed target rule, Tufte marks."""
    W, H = 1000, 300
    ml, mr, mt, mb = 58, 16, 14, 34
    iw, ih = W - ml - mr, H - mt - mb
    devs = [e for e in exps if e["kind"] != "holdout_check"]
    if not devs:
        return ""
    finite = [e["primary_metric"] for e in exps
              if e["primary_metric"] and e["primary_metric"] < FAIL]
    ymax = max(finite + [TARGET_M * 4]) * 1.6
    ymin = min([TARGET_M / 2] + [v for v in finite]) / 1.6
    ymin = max(ymin, 1.0)

    def y(v):
        v = max(min(v, ymax), ymin)
        return mt + ih * (1 - (math.log10(v) - math.log10(ymin)) /
                          (math.log10(ymax) - math.log10(ymin)))

    n = len(exps)
    def x(i):
        return ml + iw * (0.5 if n == 1 else i / (n - 1)) * (0.96 if n > 1 else 1)

    parts = [f"<svg viewBox='0 0 {W} {H}' role='img' aria-label='primary error per experiment'>"]
    # y ticks: decades and target
    t = 1.0
    while t <= ymax:
        for v in (t, 2 * t, 5 * t):
            if ymin <= v <= ymax:
                parts.append(f"<line class='tick-line' x1='{ml}' x2='{W-mr}' y1='{y(v):.1f}' y2='{y(v):.1f}'/>")
                parts.append(f"<text class='axis-lab' x='{ml-8}' y='{y(v)+3:.1f}' text-anchor='end'>{int(v):,}</text>")
        t *= 10
    parts.append(f"<text class='axis-lab' x='{ml-8}' y='{mt-2}' text-anchor='end'>m</text>")
    # target rule
    parts.append(f"<line x1='{ml}' x2='{W-mr}' y1='{y(TARGET_M):.1f}' y2='{y(TARGET_M):.1f}' "
                 f"stroke='#8c2f1f' stroke-width='1.5' stroke-dasharray='6 5'/>")
    parts.append(f"<text class='axis-lab' x='{W-mr}' y='{y(TARGET_M)-5:.1f}' text-anchor='end' fill='#8c2f1f'>target 20 m</text>")

    # Running-best step line follows keep/revert lineage: each kept dev
    # experiment SETS the best (the loop only keeps improvements; a kept
    # value that goes up marks a deliberate reset, e.g. a data-era change).
    best, pts = None, []
    for i, e in enumerate(exps):
        if e["kind"] == "holdout_check":
            continue
        v = e["primary_metric"]
        if v and v < FAIL and e["kept"]:
            if best is not None:
                pts.append((x(i), y(best)))
            best = v
            pts.append((x(i), y(best)))
    if best is not None:
        pts.append((x(n - 1), y(best)))
    if len(pts) > 1:
        d = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        parts.append(f"<path d='{d}' fill='none' stroke='#111' stroke-width='2'/>")

    # marks
    for i, e in enumerate(exps):
        v = e["primary_metric"]
        tip = f"#{e['id']} {esc(e['title'])} — {fmt_m(v)} m"
        if v is None:
            continue
        if v >= FAIL:
            parts.append(f"<text x='{x(i):.1f}' y='{mt+10}' text-anchor='middle' "
                         f"fill='#8c2f1f' font-weight='700' font-size='13'>"
                         f"×<title>{tip} (gated fail)</title></text>")
        elif e["kind"] == "holdout_check":
            parts.append(f"<circle cx='{x(i):.1f}' cy='{y(v):.1f}' r='4.5' fill='none' "
                         f"stroke='#8a6a1e' stroke-width='1.5'><title>{tip} (holdout)</title></circle>")
        elif e["kept"]:
            parts.append(f"<circle cx='{x(i):.1f}' cy='{y(v):.1f}' r='4.5' fill='#111'>"
                         f"<title>{tip}</title></circle>")
        else:
            parts.append(f"<circle cx='{x(i):.1f}' cy='{y(v):.1f}' r='4' fill='#b9b6a6'>"
                         f"<title>{tip}</title></circle>")
        parts.append(f"<text class='axis-lab' x='{x(i):.1f}' y='{H-12}' text-anchor='middle'>{e['id']}</text>")
    parts.append(f"<text class='axis-lab' x='{ml+iw/2:.0f}' y='{H-1}' text-anchor='middle'>experiment №</text>")
    parts.append("</svg>")
    return "\n".join(parts)


def cells_table(metrics):
    areas = metrics.get("areas", [])
    if not areas:
        return ""
    buckets = list(next((a["buckets"] for a in areas if a.get("buckets")), {}))
    if not buckets:
        return ""
    rows = ["<table class='cells'><tr><th>area</th>"]
    rows += [f"<th>{b.replace('_', ' ')}</th>" for b in buckets]
    rows.append("</tr>")
    for a in areas:
        rows.append(f"<tr><td class='smcp'>{esc(a['area'])}</td>")
        for b in buckets:
            c = a.get("buckets", {}).get(b)
            if not c:
                rows.append("<td>—</td>")
                continue
            med = c["median_error_m"]
            cls = "" if med is None else \
                  " class='cell-good'" if c["score"] <= TARGET_M else \
                  " class='cell-bad'" if c["score"] >= FAIL else ""
            val = "abstained" if med is None else f"{med:,.0f}"
            rows.append(f"<td{cls}><span class='num'>{val}</span> "
                        f"<span class='cov'>cov {c['coverage']:.2f}</span></td>")
        rows.append("</tr>")
    rows.append("</table>")
    return "".join(rows)


def thumbs(artifacts_dir):
    art = REPO_ROOT / (artifacts_dir or "")
    if not art.exists():
        return ""
    imgs = sorted(art.glob("heatmaps/*.png")) + sorted(art.glob("samples/*.png"))
    if not imgs:
        return ""
    figs = []
    for p in imgs:
        rel = Path("..") / p.relative_to(REPO_ROOT)
        figs.append(f"<figure><a href='{rel}'><img src='{rel}' loading='lazy'></a>"
                    f"<figcaption>{esc(p.stem.replace('_', ' '))}</figcaption></figure>")
    return f"<div class='thumbs'>{''.join(figs)}</div>"


def status_of(e):
    if e["kind"] == "holdout_check":
        return "<span class='st-hold smcp'>holdout</span>"
    if e["primary_metric"] is not None and e["primary_metric"] >= FAIL:
        return "<span class='st-fail smcp'>gated fail</span>"
    if e["kept"]:
        return "<span class='st-kept smcp'>kept</span>"
    return "<span class='st-disc smcp'>discarded</span>"


def render():
    conn = connect()
    conn.row_factory = lambda cur, row: {d[0]: row[i] for i, d in enumerate(cur.description)}
    exps = conn.execute("SELECT * FROM experiments ORDER BY id ASC").fetchall()
    n_kept = sum(1 for e in exps if e["kept"] and e["kind"] != "holdout_check")
    # Best-so-far = the last kept dev experiment (keep/revert lineage
    # semantics, matches state/best.json), not a min across data eras.
    best = next((e["primary_metric"] for e in reversed(exps)
                 if e["kept"] and e["kind"] != "holdout_check"
                 and e["primary_metric"] and e["primary_metric"] < FAIL),
                None)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    body = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="30">
<meta name="viewport" content="width=1100">
<title>Low-Light Geolocalization — Autoresearch Progress</title>
<style>{CSS}</style><script>{JS}</script></head><body>
<header class="dash-head">
  <div class="eyebrow">Alexis Rondeau · live research log</div>
  <h1>UAV low-light geolocalization</h1>
  <p class="sub">{len(exps)} experiment{'s' if len(exps) != 1 else ''} ·
    {n_kept} kept · best so far
    <b class="num">{fmt_m(best)} m</b> · target
    <b class="num">≤ {TARGET_M:.0f} m</b> worst-case median error across
    lighting buckets × development areas</p>
  <div class="dash-meta">
    <span class="k"><span class="dot kept"></span>Kept improvement</span>
    <span class="k"><span class="dot disc"></span>Discarded</span>
    <span class="k"><span class="bar"></span>Running best</span>
    <span class="k"><span class="bar dash"></span>Target</span>
    <span class="k"><span class="x">×</span>Gated fail</span>
    <span class="k"><span class="ring"></span>Holdout check (never optimized)</span>
    <span id="updated">updated {now}</span>
  </div>
</header>
<div class="dash-wrap">
<div class="chart-card">{chart_svg(exps)}</div>
<div class="tbl-card"><table class="main">
<thead><tr><th></th><th>#</th><th>Experiment</th><th>Category</th><th>Init</th>
<th>Primary (m)</th><th>Model</th><th>Latency</th><th>Status</th></tr></thead><tbody>"""]

    for e in reversed(exps):
        kept_cls = " kept-row" if (e["kept"] and e["kind"] != "holdout_check") else ""
        size = f"{e['model_bytes_max']/1024:,.0f} KB" if e["model_bytes_max"] else "—"
        lat = f"{e['latency_ms_host_proxy']:.1f} ms" if e["latency_ms_host_proxy"] else "—"
        body.append(f"""<tr class="row-main{kept_cls}" id="r{e['id']}" onclick="toggle({e['id']})">
<td><span class="caret">▸</span></td>
<td class="num">{e['id']}</td>
<td class="title-cell"><b>{esc(e['title'])}</b>
  <span class="mono" style="color:var(--faint)"> {esc(e['git_commit'][:8])}</span></td>
<td><span class="cat">{esc(e['category'] or '—')}</span></td>
<td class="mono">{esc(e['init_strategy'] or '—')}</td>
<td class="num">{fmt_m(e['primary_metric'])}</td>
<td class="num">{size}</td><td class="num">{lat}</td>
<td>{status_of(e)}</td></tr>""")

        blocks = []
        for key, cls, label in (("hypothesis", "eb-hyp", "Hypothesis"),
                                ("method", "eb-met", "Method"),
                                ("expected_outcome", "eb-exp", "Expected outcome"),
                                ("result", "eb-res", "Result"),
                                ("conclusion", "eb-con", "Conclusion")):
            if e.get(key):
                blocks.append(f"<div class='eb {cls}'><div class='eb-h'>{label}</div>"
                              f"<p>{esc(e[key])}</p></div>")
        metrics = json.loads(e["metrics_json"] or "{}")
        body.append(f"""<tr class="detail" id="d{e['id']}" style="display:none"><td colspan="9">
<div class="detail-inner">
<div class="explain">{''.join(blocks)}</div>
{cells_table(metrics)}
<div class="gates smcp">ts {esc(e['ts'][:19])} · commit {esc(e['git_commit'][:12])} ·
parent {esc((e['parent_commit'] or '')[:12]) or '—'} · artifacts {esc(e['artifacts_dir'] or '—')}</div>
{thumbs(e['artifacts_dir'])}
</div></td></tr>""")

    body.append("</tbody></table></div></div></body></html>")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(body))
    print(f"wrote {OUT} ({len(exps)} experiments)")


if __name__ == "__main__":
    render()
