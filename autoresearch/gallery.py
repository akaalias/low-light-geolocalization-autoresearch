"""Static HTML research dashboard rendered from the SQLite lineage
log (§7), styled after the human's prior research dashboards (Tufte cream /
ink / Palatino vocabulary: airloom log, Heuristic Kitchen dashboard,
FMDiscovery autoresearch dashboard) — including their UX patterns:
plain-language framing, column tooltips + help disclosure, and an
interlinked chart <-> table (hover highlights, click opens the detail row).

Not frozen (presentation only — the data it renders comes solely from
experiments.sqlite and runs/ artifacts).

Usage: python -m autoresearch.gallery   # writes gallery/index.html
"""

import datetime
import html
import json
import math
from pathlib import Path

from autoresearch import workedexample
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
.dash-head .sub{margin:0 0 6px;color:var(--muted);max-width:960px}
.dash-head .sub b{color:var(--ink)}
.intro{max-width:960px;font-size:14.5px;line-height:1.6;color:#4a473e;margin:10px 0 16px}
.intro p{margin:0 0 8px}
.intro b{color:var(--ink)}
.dash-meta{display:flex;flex-wrap:wrap;align-items:baseline;gap:14px 26px;
  font-size:13.5px;color:var(--muted)}
.k{display:inline-flex;align-items:center;gap:7px;cursor:default}
.k[title]{cursor:help}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block}
.dot.kept{background:var(--ink)} .dot.disc{background:var(--disc)}
.ring{width:9px;height:9px;border-radius:50%;display:inline-block;
  border:1.5px solid var(--ochre);background:transparent}
.bar{width:16px;height:0;border-top:2px solid var(--ink);display:inline-block}
.bar.dash{border-top-style:dashed;border-top-color:var(--accent)}
.vrule{width:0;height:12px;border-left:1px dashed var(--faint);display:inline-block}
.x{color:var(--accent);font-weight:700}
#updated{color:var(--faint);font-style:italic;margin-left:auto}

.dash-wrap{max-width:92vw;margin:0 auto;padding:4px 0 64px}
.chart-card{border-top:1px solid var(--rule);padding:14px 0 4px;margin-top:18px}
.chart-title{font:600 12px var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:2px 0 6px}
.chart-card svg{width:100%;height:auto;display:block}
.axis-lab{font:11px var(--serif);fill:var(--faint)}
.tick-line{stroke:var(--rule-soft);stroke-width:1}
.pt{cursor:pointer}
circle.pt.big{r:7px}
text.pt.big{font-size:17px}

#tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--paper);
  font:12.5px/1.45 var(--serif);padding:7px 10px;max-width:340px;opacity:0;
  transition:opacity .08s;z-index:10}
#tip b{color:#fffff8}
#tip .t-note{color:#cbc8ba;display:block;margin-top:3px}

.tbl-card{border-top:1.5px solid var(--ink);margin-top:26px}
table.main{width:100%;border-collapse:collapse;font-size:14px}
table.main th{font:600 11.5px/1.2 var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.05em;color:var(--muted);
  border-bottom:1.5px solid var(--ink);white-space:nowrap;text-align:left;
  padding:9px 12px 9px 0}
table.main th[title]{cursor:help}
table.main th[title]::after{content:"\\00b0";color:var(--faint)}
table.main td{border-bottom:1px solid var(--rule-soft);padding:9px 12px 9px 0;
  vertical-align:baseline;text-align:left}
tr.row-main{cursor:pointer}
tr.row-main:hover,tr.row-main.hl{background:#f7f3e3}
tr.kept-row{box-shadow:inset 2px 0 0 var(--ink)}
tr.kept-row td:first-child{padding-left:12px}
tr.row-flash td{animation:rowflash 1.8s ease-out}
@keyframes rowflash{0%,30%{background:#f0e2c4}100%{background:transparent}}
td.title-cell b{font-weight:600}
.caret{color:var(--faint);display:inline-block;width:12px;transition:transform .15s}
tr.open .caret{transform:rotate(90deg)}
.st-kept{color:var(--ink);font-weight:600}
.st-disc{color:var(--faint)}
.st-fail{color:var(--accent);font-weight:600}
.st-hold{color:var(--ochre);font-weight:600}
.cat{color:var(--muted);font:600 11.5px var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.05em}
.delta-up{color:var(--faint);font-size:12px}
.delta-dn{color:var(--ink);font-size:12px;font-weight:600}

tr.detail td{background:#fcfbf2;padding:0;border-bottom:1px solid var(--rule)}
.detail-inner{padding:18px 18px 22px 38px}
.detail-grid{display:grid;grid-template-columns:minmax(380px,1.1fr) minmax(420px,1fr);
  gap:16px 34px;align-items:start}
@media(max-width:1100px){.detail-grid{grid-template-columns:1fr}}
.explain{display:flex;flex-direction:column;gap:12px}
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
.eb-eli{border-left-color:var(--ink);background:#fbf8ea}
.eb-eli p{font-size:14.5px}

.arch{margin:0 0 20px}
.arch-h{font:600 12px var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 10px}
.arch-h .chg{color:var(--accent)}
.wex-row{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:flex-start}
.wex-row figure{margin:0;flex:none}
.wex-row a{border-bottom:none}
.wex-frame img{width:230px;height:230px;display:block;border:1px solid var(--rule)}
.wex-map img{width:340px;height:auto;display:block;border:1px solid var(--rule)}
.wex-row figcaption{font-size:11.5px;color:var(--muted);line-height:1.5;
  margin-top:6px}
.wex-frame figcaption{max-width:230px}
.wex-map figcaption{max-width:340px}
.wex-row figcaption b{color:var(--ink);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.05em}
.wex-arr{color:var(--faint);font-size:18px;height:230px;display:flex;
  align-items:center;flex:none}
.wex-stats{display:flex;flex-direction:column;gap:16px;padding:14px 0 0 10px}
.wex-num{font-size:27px;line-height:1.1;color:var(--ink)}
.wex-lab{font:600 10.5px var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-top:2px}
.wex-pipe{font-size:12.5px;color:var(--muted);line-height:1.7;margin-top:12px;
  max-width:1240px}
.wex-pipe b{color:var(--ink);font-weight:600;font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.05em;font-size:11.5px}
.wex-pipe b.chg{color:var(--accent)}
.wex-pipe .pd{color:#7a4438}
.wex-pipe .sep{color:var(--faint)}
.arch-svg{max-width:1120px;margin:2px 0 20px;overflow-x:auto}
.arch-svg svg{width:100%;min-width:760px;height:auto;display:block}

.score-head{font:600 12px var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 4px}
.score-sub{font-size:12.5px;color:var(--faint);font-style:italic;margin:0 0 8px}
table.cells{border-collapse:collapse;font-size:12.5px;width:100%}
table.cells th{font:600 10.5px/1.2 var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.05em;color:var(--muted);
  border-bottom:1px solid var(--ink);padding:5px 12px 5px 0;text-align:left}
table.cells td{border-bottom:1px solid var(--rule-soft);padding:4px 12px 4px 0}
.cov{color:var(--faint);font-size:11px}
.cell-bad{color:var(--accent);font-weight:600}
.cell-good{color:var(--ink);font-weight:600}
.cell-worst{box-shadow:inset 0 -2px 0 var(--accent)}
.gates{font-size:13px;color:#4a473e;margin-top:12px;border-left:2px solid var(--rule);
  padding:4px 0 4px 14px}
.gates b{color:var(--ink)}
.gates .ok{color:var(--ink);font-weight:600}
.gates .bad{color:var(--accent);font-weight:600}
.provenance{font-size:11.5px;color:var(--faint);margin-top:14px;
  font-feature-settings:"smcp" 1;text-transform:uppercase;letter-spacing:.04em}
pre.prompt{font:12px/1.5 var(--mono);white-space:pre-wrap;background:#fff;
  border-left:2px solid var(--rule);padding:12px 16px;margin:8px 0 0;
  max-width:920px;max-height:420px;overflow:auto;color:#33312b;
  box-shadow:0 1px 7px rgba(60,50,30,.08)}
.figs-intro{font-size:13px;color:#4a473e;max-width:920px;margin:2px 0 8px}
.figs-intro i{color:var(--faint)}
#lightbox{position:fixed;inset:0;background:rgba(17,17,17,.92);z-index:50;
  display:none;align-items:center;justify-content:center;cursor:zoom-out;
  flex-direction:column;gap:10px}
#lightbox.on{display:flex}
#lightbox img{max-width:96vw;max-height:90vh;border:1px solid #444}
#lightbox .lb-cap{color:#cbc8ba;font:13.5px var(--serif);font-style:italic}
#lightbox .lb-hint{color:#77746a;font:11px var(--serif);
  font-feature-settings:"smcp" 1;text-transform:uppercase;letter-spacing:.06em}

.figs{margin-top:16px}
.figs-h{font:600 12px var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:14px 0 6px}
.thumbs{display:flex;flex-wrap:wrap;gap:12px}
.thumbs figure{margin:0}
.thumbs img{height:130px;display:block;border:1px solid var(--rule)}
.thumbs.maps{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:14px}
.thumbs.maps figure{min-width:0}
.thumbs.maps a{display:block;aspect-ratio:1/1;overflow:hidden;
  border:1px solid var(--rule)}
.thumbs.maps img{width:100%;height:100%;object-fit:cover;border:none}
.thumbs.maps figcaption{margin-top:5px;font-size:11.5px;line-height:1.45}
.thumbs.maps figcaption b{color:var(--ink);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.05em;display:block}
.thumbs figcaption{font:11px var(--serif);color:var(--faint);margin-top:3px}
details.trywrap{margin:12px 0 0}
details.trywrap>summary{cursor:pointer;color:var(--muted);font-weight:600;
  font-size:12px;font-feature-settings:"smcp" 1;text-transform:uppercase;
  letter-spacing:.04em;list-style:none}
details.trywrap>summary::-webkit-details-marker{display:none}
details.trywrap>summary::before{content:"\\25b8  ";color:var(--faint)}
details.trywrap[open]>summary::before{content:"\\25be  "}

.help{margin-top:16px;font-size:13.5px;color:#4a473e;max-width:960px}
.help>summary{cursor:pointer;color:var(--muted);font-weight:600;list-style:none;
  font-feature-settings:"smcp" 1;text-transform:uppercase;letter-spacing:.04em;
  font-size:12.5px}
.help>summary::-webkit-details-marker{display:none}
.help>summary::before{content:"\\25b8  ";color:var(--faint)}
.help[open]>summary::before{content:"\\25be  "}
.help-grid{margin:12px 0 2px;display:grid;grid-template-columns:max-content 1fr;
  gap:8px 18px;align-items:baseline}
.help-grid dt{font-weight:700;color:var(--ink);white-space:nowrap}
.help-grid dd{margin:0}
.help .foot{margin-top:10px;color:var(--muted);font-style:italic}
"""

JS = """
var tip;
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
function showTip(ev,el){
  tip.innerHTML=el.dataset.tip;
  tip.style.opacity=1;
  var x=Math.min(ev.clientX+14,window.innerWidth-tip.offsetWidth-8);
  tip.style.left=x+'px';
  tip.style.top=Math.min(ev.clientY+14,window.innerHeight-tip.offsetHeight-8)+'px';
}
window.addEventListener('load',function(){
  tip=document.getElementById('tip');
  try{JSON.parse(sessionStorage.getItem('open')||'[]').forEach(function(id){
    var d=document.getElementById('d'+id);
    if(d){d.style.display='table-row';
      document.getElementById('r'+id).classList.add('open')}
  })}catch(e){}
  // chart <-> table interlink
  document.querySelectorAll('.pt').forEach(function(el){
    var id=el.dataset.id, row=document.getElementById('r'+id);
    el.addEventListener('mousemove',function(ev){showTip(ev,el)});
    el.addEventListener('mouseenter',function(){if(row)row.classList.add('hl')});
    el.addEventListener('mouseleave',function(){tip.style.opacity=0;
      if(row)row.classList.remove('hl')});
    el.addEventListener('click',function(){
      if(!row)return;
      var d=document.getElementById('d'+id);
      if(d&&d.style.display==='none')toggle(+id);
      row.scrollIntoView({behavior:'smooth',block:'center'});
      row.classList.remove('row-flash');void row.offsetWidth;
      row.classList.add('row-flash');
    });
  });
  document.querySelectorAll('tr.row-main').forEach(function(row){
    var id=row.id.slice(1);
    var mk=document.querySelector('.pt[data-id="'+id+'"]');
    if(!mk)return;
    row.addEventListener('mouseenter',function(){mk.classList.add('big')});
    row.addEventListener('mouseleave',function(){mk.classList.remove('big')});
  });
  // image lightbox: any figure image opens a full-screen modal
  var lb=document.getElementById('lightbox'),
      lbImg=lb.querySelector('img'), lbCap=lb.querySelector('.lb-cap');
  document.body.addEventListener('click',function(ev){
    var a=ev.target.closest('.thumbs a,.wex-row a');
    if(!a)return;
    ev.preventDefault();ev.stopPropagation();
    lbImg.src=a.getAttribute('href');
    var cap=a.parentElement.querySelector('figcaption');
    lbCap.textContent=cap?cap.textContent:'';
    lb.classList.add('on');
  });
  lb.addEventListener('click',function(){lb.classList.remove('on');lbImg.src=''});
  window.addEventListener('keydown',function(ev){
    if(ev.key==='Escape'&&lb.classList.contains('on')){
      lb.classList.remove('on');lbImg.src=''}
  });
});
"""


def esc(s):
    return html.escape(str(s if s is not None else ""))


def fmt_dur(s):
    if s is None:
        return "—"
    s = int(s)
    return f"{s // 60} m {s % 60:02d} s" if s >= 60 else f"{s} s"


def fmt_m(v):
    if v is None:
        return "—"
    if v >= FAIL:
        return "gated fail"
    if v >= 1000:
        return f"{v/1000:,.2f} km"
    return f"{v:,.1f} m"


def chart_svg(exps):
    """Static SVG progress chart: worst-case error per experiment, log y,
    running-best step line, dashed target rule, Tufte marks. Marks carry
    data-id/data-tip for the JS chart<->table interlink."""
    W, H = 1000, 300
    ml, mr, mt, mb = 58, 16, 16, 34
    iw, ih = W - ml - mr, H - mt - mb
    if not exps:
        return ""
    finite = [e["primary_metric"] for e in exps
              if e["primary_metric"] and e["primary_metric"] < FAIL]
    ymax = max(finite + [TARGET_M * 4]) * 1.6
    ymin = max(min([TARGET_M / 2] + finite) / 1.6, 1.0)

    def y(v):
        v = max(min(v, ymax), ymin)
        return mt + ih * (1 - (math.log10(v) - math.log10(ymin)) /
                          (math.log10(ymax) - math.log10(ymin)))

    n = len(exps)

    def x(i):
        return ml + iw * (0.5 if n == 1 else i / (n - 1)) * (0.96 if n > 1 else 1)

    parts = [f"<svg viewBox='0 0 {W} {H}' role='img' "
             f"aria-label='worst-case position error per experiment'>"]
    t = 1.0
    while t <= ymax:
        for v in (t, 2 * t, 5 * t):
            if ymin <= v <= ymax:
                parts.append(f"<line class='tick-line' x1='{ml}' x2='{W-mr}' y1='{y(v):.1f}' y2='{y(v):.1f}'/>")
                parts.append(f"<text class='axis-lab' x='{ml-8}' y='{y(v)+3:.1f}' text-anchor='end'>{int(v):,}</text>")
        t *= 10
    parts.append(f"<text class='axis-lab' x='{ml-8}' y='{mt-4}' text-anchor='end'>m</text>")
    parts.append(f"<line x1='{ml}' x2='{W-mr}' y1='{y(TARGET_M):.1f}' y2='{y(TARGET_M):.1f}' "
                 f"stroke='#8c2f1f' stroke-width='1.5' stroke-dasharray='6 5'/>")
    parts.append(f"<text class='axis-lab' x='{W-mr}' y='{y(TARGET_M)-5:.1f}' "
                 f"text-anchor='end' fill='#8c2f1f'>goal — locate the drone to within 20 m</text>")

    # Running-best step line, one segment per evaluation era. Within an era
    # the line only ever steps DOWN (the loop keeps only improvements). A
    # kept experiment that scores worse than the running best is, by loop
    # semantics, impossible — so it marks a deliberate eval-set change
    # (bootstrap data revisions): the line BREAKS there and restarts, and a
    # vertical rule labels the discontinuity.
    best = None
    segments, cur, resets = [], [], []
    for i, e in enumerate(exps):
        if e["kind"] == "holdout_check":
            continue
        v = e["primary_metric"]
        if not v or v >= FAIL or not e["kept"]:
            continue
        if best is None:
            best, cur = v, [(x(i), y(v))]
        elif v < best:
            cur.append((x(i), y(best)))
            best = v
            cur.append((x(i), y(v)))
        else:  # eval-set reset — new ruler, new segment
            segments.append(cur)
            resets.append(x(i))
            best, cur = v, [(x(i), y(v))]
    if cur:
        cur.append((x(n - 1), y(best)))
        segments.append(cur)
    # Reset labels: a paper-colored halo (paint-order stroke) keeps them
    # legible wherever the data line runs; stagger vertically only when two
    # rules sit close enough for their labels to collide.
    LABEL_W = 130
    prev_rx, prev_row = None, 0
    for rx in resets:
        row = (prev_row + 1) % 2 if (prev_rx is not None and rx - prev_rx < LABEL_W) else 0
        prev_rx, prev_row = rx, row
        parts.append(f"<line x1='{rx:.1f}' x2='{rx:.1f}' y1='{mt}' y2='{H-mb}' "
                     f"stroke='#9b998c' stroke-width='1' stroke-dasharray='3 4'/>")
        parts.append(f"<text class='axis-lab' x='{rx+5:.1f}' y='{mt+11+row*13}' "
                     f"stroke='#fffff8' stroke-width='4' "
                     f"style='paint-order:stroke'>eval set changed</text>")
    for seg in segments:
        if len(seg) > 1:
            d = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in seg)
            parts.append(f"<path d='{d}' fill='none' stroke='#111' stroke-width='2'/>")

    for i, e in enumerate(exps):
        v = e["primary_metric"]
        if v is None:
            continue
        kind = ("holdout check — logged, never drives keep/revert"
                if e["kind"] == "holdout_check"
                else "kept" if e["kept"] else "discarded")
        tip = (f"<b>#{e['id']} {esc(e['title'])}</b>"
               f"<span class='t-note'>{fmt_m(v)} · {kind} · click to open</span>")
        tip_attr = esc(tip)
        common = f"class='pt' data-id='{e['id']}' data-tip=\"{tip_attr}\""
        if v >= FAIL:
            parts.append(f"<text {common} x='{x(i):.1f}' y='{mt+11}' text-anchor='middle' "
                         f"fill='#8c2f1f' font-weight='700' font-size='14'>×</text>")
        elif e["kind"] == "holdout_check":
            parts.append(f"<circle {common} cx='{x(i):.1f}' cy='{y(v):.1f}' r='4.5' "
                         f"fill='#fffff8' stroke='#8a6a1e' stroke-width='1.5'/>")
        elif e["kept"]:
            parts.append(f"<circle {common} cx='{x(i):.1f}' cy='{y(v):.1f}' r='4.5' fill='#111'/>")
        else:
            parts.append(f"<circle {common} cx='{x(i):.1f}' cy='{y(v):.1f}' r='4' fill='#b9b6a6'/>")
        parts.append(f"<text class='axis-lab' x='{x(i):.1f}' y='{H-12}' text-anchor='middle'>{e['id']}</text>")
    parts.append(f"<text class='axis-lab' x='{ml+iw/2:.0f}' y='{H-1}' text-anchor='middle'>experiment №</text>")
    parts.append("</svg>")
    return "\n".join(parts)


def cells_table(metrics):
    areas = metrics.get("areas", [])
    if not areas:
        return "<p class='score-sub'>No per-area results recorded for this run.</p>"
    buckets = list(next((a["buckets"] for a in areas if a.get("buckets")), {}))
    if not buckets:
        return "<p class='score-sub'>No per-area results recorded for this run.</p>"
    worst = max((c["score"] for a in areas for c in a.get("buckets", {}).values()
                 if c["score"] is not None), default=None)
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
            classes = []
            if med is not None and c["score"] <= TARGET_M:
                classes.append("cell-good")
            if c["score"] is not None and c["score"] >= FAIL:
                classes.append("cell-bad")
            if worst is not None and c["score"] == worst and worst < FAIL:
                classes.append("cell-worst")
            cls = f" class='{' '.join(classes)}'" if classes else ""
            val = "abstained" if med is None else f"{med:,.0f}"
            rows.append(f"<td{cls}><span class='num'>{val}</span> "
                        f"<span class='cov'>cov {c['coverage']:.2f}</span></td>")
        rows.append("</tr>")
    rows.append("</table>")
    return "".join(rows)


def gates_block(e, metrics):
    failed = [a["gates"].get("failed") for a in metrics.get("areas", [])
              if a.get("gates", {}).get("failed")]
    size = e["model_bytes_max"]
    lat = e["latency_ms_host_proxy"]
    size_s = f"<span class='ok num'>{size/1024:,.0f} KB</span>" if size else "—"
    lat_s = f"<span class='ok num'>{lat:.1f} ms</span>" if lat else "—"
    verdict = (f"<span class='bad'>gate violated — {esc('; '.join(failed))}</span>"
               if failed else "<span class='ok'>all deployment gates passed</span>")
    return (f"<div class='gates'><b>Fits the aircraft?</b> {verdict}<br>"
            f"largest per-area model {size_s} (limit 4,096 KB) · "
            f"single-frame inference {lat_s} on one CPU thread "
            f"(proxy limit 250 ms)</div>")


def figures(artifacts_dir, metrics):
    art = REPO_ROOT / (artifacts_dir or "")
    if not art.exists():
        return ""
    heat = sorted(art.glob("heatmaps/*.png"))
    samp = sorted(art.glob("samples/*.png"))
    med_range = {}
    for a in metrics.get("areas", []):
        meds = [c["median_error_m"] for c in a.get("buckets", {}).values()
                if c.get("median_error_m") is not None]
        if meds:
            med_range[a["area"]] = (min(meds), max(meds))
    out = []
    if heat:
        figs = []
        for p in heat:
            rel = Path("..") / p.relative_to(REPO_ROOT)
            area = p.stem.replace("heatmap_", "")
            lo_hi = med_range.get(area)
            stat = (f"median miss {lo_hi[0]:,.0f}–{lo_hi[1]:,.0f} m across "
                    f"lighting" if lo_hi else "")
            figs.append(f"<figure><a href='{rel}'><img src='{rel}' loading='lazy'></a>"
                        f"<figcaption><b>{esc(area)}</b>{stat}</figcaption></figure>")
        out.append(
            "<div class='figs-h'>Where the model was tested — and how far off it was</div>"
            "<div class='figs-intro'>Each map is one full test area. Every dot is one "
            "held-out test location (all six lighting conditions overlaid): the model was "
            "shown a 128 m crop centered there and asked for its position. Dot color = the "
            "distance between its answer and the truth — <b style='color:#3c9c3c'>green ≤ 20 m "
            "(at goal)</b>, <b style='color:#8a6a1e'>amber ≤ 50 m</b>, "
            "<b style='color:#8c2f1f'>red beyond</b>. <i>A working model turns these maps "
            "green; spatial clusters of red reveal which parts of an area confuse it.</i></div>"
            f"<div class='thumbs maps'>{''.join(figs)}</div>")
    if samp:
        by_area = {}
        for p in samp:
            area = p.stem.split("_")[0]
            by_area.setdefault(area, []).append(p)
        inner = [
            "<div class='figs-intro'>One example 256 m patch per area, rendered under the "
            "six synthetic lighting conditions the model must handle. These illustrate the "
            "<i>dataset</i>, not this experiment's performance — the actual training set is "
            "thousands of distinct crops per area (see “training data” above), and these "
            "renderings only change when the relighting method changes.</div>"]
        for area, ps in sorted(by_area.items()):
            figs = []
            for p in ps:
                rel = Path("..") / p.relative_to(REPO_ROOT)
                bucket = p.stem[len(area) + 1:].replace("_", " ")
                figs.append(f"<figure><a href='{rel}'><img src='{rel}' loading='lazy'></a>"
                            f"<figcaption>{esc(area)} · {esc(bucket)}</figcaption></figure>")
            inner.append(f"<div class='figs-h'>{esc(area)}</div>"
                         f"<div class='thumbs'>{''.join(figs)}</div>")
        out.append(f"<details class='trywrap'><summary>What the six lighting conditions "
                   f"look like (example patches — illustration, not the training set)"
                   f"</summary>{''.join(inner)}</details>")
    return f"<div class='figs'>{''.join(out)}</div>" if out else ""


def train_block(artifacts_dir):
    """Summarize the actual training data used, from train_info.json."""
    p = REPO_ROOT / (artifacts_dir or "") / "train_info.json"
    if not p.exists():
        return ""
    try:
        infos = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return ""
    if not infos:
        return ""
    rows = ["<table class='cells' style='margin-top:12px'>"
            "<tr><th>training data</th><th>crops</th><th>epochs</th>"
            "<th>train time</th><th>device</th></tr>"]
    for i in infos:
        secs = i.get("train_seconds")
        rows.append(
            f"<tr><td class='smcp'>{esc(i['area'])}</td>"
            f"<td class='num'>{i['n_train_crops']:,}</td>"
            f"<td class='num'>{i['epochs']}</td>"
            f"<td class='num'>{f'{secs:,.0f} s' if secs is not None else '—'}</td>"
            f"<td class='mono'>{esc(i.get('device', '—'))}</td></tr>")
    rows.append("</table>")
    rows.append("<div class='score-sub' style='margin-top:6px'>crops are sampled "
                "fresh each run from the frozen train split (~45,000 distinct "
                "positions per area, times random rotation), never from eval "
                "blocks; how many to use is the experiment's own choice</div>")
    return "".join(rows)


def arch_block(e):
    """One REAL worked example — the same held-out night crop for every
    experiment, run through the run's actual exported ONNX model — plus a
    one-line pipeline sentence from the pre-registered architecture stages
    (changed stages in accent red). Replaces an earlier icon strip: real
    model output shows mechanism differences icons cannot."""
    if e["kind"] == "holdout_check":
        return ""
    try:
        arch = json.loads(e.get("arch_json") or "null")
    except (TypeError, json.JSONDecodeError):
        arch = None
    stages = arch.get("stages") if isinstance(arch, dict) else None

    segs = []
    for s in (stages or []):
        chg = bool(s.get("changed"))
        seg = f"<b{" class='chg'" if chg else ''}>{esc(s.get('name', '?'))}</b>"
        if chg and s.get("detail"):
            seg += f" <span class='pd'>— {esc(s['detail'])}</span>"
        sep = (" <span class='sep'>&nbsp;+&nbsp;</span> " if s.get("train_only")
               else " <span class='sep'>→</span> ")
        segs.append((sep, seg))
    pipe = "".join((sep if i else "") + seg for i, (sep, seg) in enumerate(segs))

    info = workedexample.ensure(e["artifacts_dir"])
    fig = ""
    if info:
        rd = Path("..") / (e["artifacts_dir"] or "")
        fr, mp = rd / info["frame"], rd / info["map"]
        if info.get("has_field"):
            fstat = (f"red glow = its <b>actual internal probability field</b> "
                     f"recovered from the deployed model — the sharpest cell holds "
                     f"<span class='num'>{info['peak_pct']}%</span> of the probability mass "
                     f"(a uniform “no idea” field would be {info['uniform_pct']}%)")
        else:
            fstat = ("this design points at a coordinate directly — it has no "
                     "internal probability field to show")
        fig = f"""<div class='wex-row'>
<figure class='wex-frame'><a href='{fr}'><img src='{fr}' loading='lazy'></a>
<figcaption><b>what the camera saw</b> — a real held-out 128 m crop,
{esc(info['area'])} at {esc(info['bucket'])}; its true spot is the ○ on the map.
Every experiment is shown this same crop.</figcaption></figure>
<div class='wex-arr'>→</div>
<figure class='wex-map'><a href='{mp}'><img src='{mp}' loading='lazy'></a>
<figcaption><b>what this model actually computed</b> — {fstat}.
○ true location · × its answer.</figcaption></figure>
<div class='wex-stats'>
<div><div class='wex-num num'>{fmt_m(info['miss_m'])}</div>
<div class='wex-lab'>miss, this crop</div></div>
<div><div class='wex-num num'>{info['conf']:.2f}</div>
<div class='wex-lab'>self-reported confidence</div></div>
</div></div>"""
    svg = e.get("arch_svg") or ""
    svg = svg if svg.lstrip().startswith("<svg") else ""
    if not fig and not pipe and not svg:
        return ""
    note = (" — <span class='chg'>red = what this experiment changed</span>"
            if (svg or (stages and any(s.get("changed") for s in stages)))
            else "")
    out = []
    if svg:
        out.append(f"<div class='arch-h'>The design under test — technical "
                   f"diagram{note}</div><div class='arch-svg'>{svg}</div>")
    elif pipe:
        out.append(f"<div class='arch-h'>The pipeline this run used{note}</div>"
                   f"<div class='wex-pipe' style='margin:0 0 14px'>{pipe}</div>")
    if fig:
        out.append(f"<div class='arch-h'>One real test, end to end"
                   f"{'' if svg or pipe else note}</div>{fig}")
    return f"<div class='arch'>{''.join(out)}</div>"



def prompt_block(e):
    """The exact prompt the headless agent was given for this experiment."""
    prompt = e.get("agent_prompt")
    if prompt:
        return (f"<details class='trywrap'><summary>The exact prompt given to the "
                f"headless agent</summary><pre class='prompt'>{esc(prompt)}</pre>"
                f"</details>")
    if e["kind"] == "holdout_check":
        return ""
    return ("<div class='provenance'>no headless prompt — designed interactively "
            "during the bootstrap session</div>")


def status_of(e):
    if e["kind"] == "holdout_check":
        return "<span class='st-hold smcp'>holdout</span>"
    if e["primary_metric"] is not None and e["primary_metric"] >= FAIL:
        return "<span class='st-fail smcp'>gated fail</span>"
    if e["kept"]:
        return "<span class='st-kept smcp'>kept</span>"
    return "<span class='st-disc smcp'>discarded</span>"


HELP = f"""
<details class="help"><summary>What do the columns and marks mean?</summary>
<dl class="help-grid">
<dt>Worst-case error</dt><dd>The single number the loop optimizes. Every
experiment trains <b>one model per area</b>; each model is then tested on
held-out map crops it never saw during training, under each of the
<b>6 simulated lighting conditions</b> (morning → night). That gives a median
position error for every area × lighting cell — and the score is the
<b>worst</b> of those cells, not the average. An average would let a good
Berlin-at-noon result hide a hopeless rural-night one; the worst cell can't
hide anything. Mission target: <b>≤ 20 m</b>.</dd>
<dt>gated fail (×)</dt><dd>The §6 score also enforces the aircraft's hard
limits: the exported model must fit the ESP32-P4 flight computer
(<b>≤ 4 MiB</b>) and answer within the latency budget (≤ 250 ms host proxy),
and it may not dodge hard cases by refusing to answer (a cell where it
abstains on &gt; 80% of frames counts as failed). Any violation scores the
whole experiment as failed regardless of accuracy.</dd>
<dt>cov (coverage)</dt><dd>Share of test frames the model was confident
enough to answer at all. Abstaining honestly on bad frames is allowed —
down to the 20% floor above.</dd>
<dt>Kept / Discarded</dt><dd>Karpathy-style loop discipline: branch from the
best code, run one focused experiment, <b>keep</b> the change (git commit)
only if the worst-case error improves — otherwise <b>revert</b> it. The
step line in the chart is the running best.</dd>
<dt>Eval-set reset (┆)</dt><dd>During the bootstrap phase the frozen
evaluation data itself was revised twice (10 m satellite → 1 m orthophotos;
then a split rebalance). Scores on different eval sets are measurements on
different rulers and must not be compared — the dashed vertical rule marks
the break, and the running-best line restarts there instead of pretending
continuity. From Phase 2 on, the eval set does not change.</dd>
<dt>Holdout (○)</dt><dd>Hamburg is the blind fifth area: structurally
different (port, river, spread-out), never seen by the loop, scored only as
a periodic read-only check. If its error diverges from the four development
areas, the pipeline has learned their quirks rather than a general method.
Its result never influences keep/revert.</dd>
<dt>Category</dt><dd>Which lever the experiment pulls: architecture, loss,
augmentation, relighting, training procedure, or quantization.</dd>
<dt>Init</dt><dd>Weight initialization: trained from scratch, or started
from a permissively-licensed pretrained backbone.</dd>
<dt>Model / Latency</dt><dd>Largest per-area exported model, and
single-frame inference time on one CPU thread (a documented proxy for the
flight computer, not a measurement of it).</dd>
<dt>Training set</dt><dd>Each area offers ~45,000 distinct training
positions (1 m/px, 128 m crops, times random rotation); how many crops an
experiment actually samples per lighting condition is its own choice and is
shown in the detail view. Training crops never overlap the eval blocks —
enforced by the frozen split, not by convention.</dd>
<dt>Agent prompt</dt><dd>Every loop experiment records the exact prompt its
headless agent received — expandable in the detail view, so any experiment
can be re-run or audited later.</dd>
<dt>In plain words</dt><dd>Each experiment's own jargon-free explanation of
what it tried, pre-registered alongside the technical design — read this
first if the title looks like alphabet soup.</dd>
<dt>One real test</dt><dd>The figure at the top of each detail view is not
an illustration: the same held-out Berlin night crop is fed to that
experiment's actual exported model, and the red glow on the map is the
probability field recovered from the deployed ONNX artifact itself —
with the true location (○), the model's answer (×), and the real miss
distance. Because every experiment sees the identical crop, any difference
between two figures is the mechanism change, not the example. The pipeline
sentence beneath names the stages; <b style="color:var(--accent)">red</b>
marks what that experiment changed (a “+” stage is training-only and never
flies).</dd>
</dl>
<div class="foot">Click any row — or any point in the chart — to see the
experiment's pre-registered hypothesis, method and expected outcome, the
measured result, the per-area × lighting scoreboard, and what the model
actually looked at.</div>
</details>"""


def render():
    conn = connect()
    conn.row_factory = lambda cur, row: {d[0]: row[i] for i, d in enumerate(cur.description)}
    exps = conn.execute("SELECT * FROM experiments ORDER BY id ASC").fetchall()
    n_dev = sum(1 for e in exps if e["kind"] != "holdout_check")
    n_kept = sum(1 for e in exps if e["kept"] and e["kind"] != "holdout_check")
    best = next((e["primary_metric"] for e in reversed(exps)
                 if e["kept"] and e["kind"] != "holdout_check"
                 and e["primary_metric"] and e["primary_metric"] < FAIL),
                None)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    best_size = next((e["model_bytes_max"] for e in reversed(exps)
                      if e["kept"] and e["kind"] != "holdout_check"
                      and e["model_bytes_max"]), None)
    size_note = (f"currently <b class='num'>{best_size/1024:,.0f} KB</b>, hard limit "
                 f"<b class='num'>4 MiB</b>" if best_size else "hard limit <b>4 MiB</b>")
    if best is None:
        status_line = "No scoreable model yet."
    elif best <= TARGET_M:
        status_line = (f"<b>Goal reached:</b> worst-case median miss "
                       f"<b class='num'>{fmt_m(best)}</b> — at or under the 20 m goal.")
    else:
        status_line = (
            f"Status: in its hardest area × lighting combination, the best model's "
            f"<b>median miss is {fmt_m(best)}</b> — half its position estimates land "
            f"farther than that from the drone's true location. The goal is a median "
            f"miss of <b class='num'>≤ 20 m</b> in <i>every</i> combination — "
            f"<b class='num'>{best/TARGET_M:,.0f}×</b> better than today.")

    body = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=1100">
<title>Low-Light Geolocalization — Autoresearch Progress</title>
<style>{CSS}</style><script>{JS}</script></head><body>
<header class="dash-head">
  <div class="eyebrow">Alexis Rondeau · live research log</div>
  <h1>Can a drone find itself in the dark?</h1>
  <p class="sub">A 5-inch UAV built to fly <b>without a GPS module at all</b>.
  In place of satellite navigation it carries a low-light camera and a tiny
  neural network ({size_note}) that has memorized what its flight area looks
  like from above — by day, by dusk, and by night. It looks down at one frame
  and answers: <b>where am I?</b> No satellites to jam or lose, no stored
  maps, no internet.</p>
  <div class="intro">
  <p>An autonomous research loop (one headless coding agent per iteration)
  rewrites the model and its training code, one pre-registered experiment at a
  time, and is judged by a single frozen ruler: the <b>worst</b> median
  position error across 6 lighting conditions × 4 German test areas — dense
  Berlin, rural Prignitz, Munich, Frankfurt — on held-out map crops. Hamburg
  stays blind as the generalization check. Every model must fit the
  <b>ESP32-P4</b> flight computer: ≤ 4 MiB, within the latency budget, under
  ~2 W.</p>
  <p>{status_line} · {n_dev} experiment{'s' if n_dev != 1 else ''},
  {n_kept} kept.</p>
  </div>
  <div class="dash-meta">
    <span class="k" title="This change improved the worst-case error and was committed."><span class="dot kept"></span>Kept improvement</span>
    <span class="k" title="No improvement — the code change was reverted; only the record remains."><span class="dot disc"></span>Discarded</span>
    <span class="k" title="Best worst-case error achieved so far."><span class="bar"></span>Running best</span>
    <span class="k" title="Mission target: worst cell at or below 20 m."><span class="bar dash"></span>Target 20 m</span>
    <span class="k" title="Violated a deployment gate (model size, latency, or abstained too much) — scored as failure regardless of accuracy."><span class="x">×</span>Gated fail</span>
    <span class="k" title="Blind Hamburg check — logged for honesty, never used to decide keep/revert."><span class="ring"></span>Holdout check</span>
    <span class="k" title="The frozen evaluation data itself was revised (bootstrap phase only). Scores before and after are measured on different test sets and cannot be compared; the running-best line restarts."><span class="vrule"></span>Eval-set reset</span>
    <span id="updated">updated {now}</span>
  </div>
</header>
<div class="dash-wrap">
<div class="chart-card">
<div class="chart-title">Worst-case position error per experiment — log scale, lower is better</div>
{chart_svg(exps)}</div>
<div class="tbl-card"><table class="main">
<thead><tr><th></th><th>#</th><th>Experiment</th>
<th title="Which lever the experiment pulls: architecture, loss, augmentation, relighting, training, quantization.">Category</th>
<th title="Weight initialization: from scratch, or a permissively-licensed pretrained backbone.">Init</th>
<th title="Worst median position error across 6 lighting conditions x 4 areas, on held-out crops. The one number the loop optimizes. Target: at or below 20 m.">Worst-case error</th>
<th title="Largest per-area exported model. Hard limit: 4 MiB (ESP32-P4 flight computer).">Model</th>
<th title="Single-frame inference on one CPU thread - a documented proxy for the flight computer, budget 250 ms.">Latency</th>
<th title="Wall time of the whole iteration: agent design + training all areas + scoring.">Time</th>
<th>Status</th></tr></thead><tbody>"""]

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
<td class="num">{fmt_dur(e.get('duration_s'))}</td>
<td>{status_of(e)}</td></tr>""")

        blocks = []
        if e.get("eli5"):
            blocks.append(f"<div class='eb eb-eli'><div class='eb-h'>In plain "
                          f"words</div><p>{esc(e['eli5'])}</p></div>")
        for key, cls, label in (("hypothesis", "eb-hyp", "Hypothesis"),
                                ("method", "eb-met", "Method"),
                                ("expected_outcome", "eb-exp", "Expected outcome"),
                                ("result", "eb-res", "Result"),
                                ("conclusion", "eb-con", "Conclusion")):
            if e.get(key):
                blocks.append(f"<div class='eb {cls}'><div class='eb-h'>{label}</div>"
                              f"<p>{esc(e[key])}</p></div>")
        metrics = json.loads(e["metrics_json"] or "{}")
        body.append(f"""<tr class="detail" id="d{e['id']}" style="display:none"><td colspan="10">
<div class="detail-inner">
{arch_block(e)}
<div class="detail-grid">
<div class="explain">{''.join(blocks)}</div>
<div>
<div class="score-head">Scoreboard — median error (m) per area × lighting</div>
<div class="score-sub">the worst cell (underlined) is the experiment's score;
red = failed cell, ink = at target</div>
{cells_table(metrics)}
{gates_block(e, metrics)}
{train_block(e['artifacts_dir'])}
<div class="provenance">ts {esc(e['ts'][:19])} · commit {esc(e['git_commit'][:12])} ·
parent {esc((e['parent_commit'] or '')[:12]) or '—'} · artifacts {esc(e['artifacts_dir'] or '—')} ·
agent model {esc(e.get('agent_model') or '—')} · took {fmt_dur(e.get('duration_s'))}</div>
{prompt_block(e)}
</div>
</div>
{figures(e['artifacts_dir'], metrics)}
</div></td></tr>""")

    body.append(f"</tbody></table>{HELP}</div>")
    body.append("<div id='lightbox'><img alt=''><div class='lb-cap'></div>"
                "<div class='lb-hint'>click anywhere or press Esc to close</div></div>")
    body.append("<div id='tip'></div></body></html>")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(body))
    print(f"wrote {OUT} ({len(exps)} experiments)")


if __name__ == "__main__":
    render()
