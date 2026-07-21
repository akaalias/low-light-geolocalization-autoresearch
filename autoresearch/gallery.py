"""Static HTML research dashboard rendered from the SQLite lineage
log (§7), styled after the human's prior research dashboards (Tufte cream /
ink / Palatino vocabulary: airloom log, Heuristic Kitchen dashboard,
FMDiscovery autoresearch dashboard) — including their UX patterns:
plain-language framing, column tooltips + help disclosure, and an
interlinked chart <-> table (hover highlights, click opens the detail row).

Not frozen (presentation only — the data it renders comes solely from
experiments.sqlite and runs/ artifacts).

Renders two pages sharing the airloom top-navigation pattern:
  gallery/index.html            — the research log (chart + lineage table)
  gallery/inference-paths.html  — "Proposed Inference Paths": every
                                  pre-registered architecture figure
Planned but deliberately held out for now: a lineage page and a results
page (see the publishing roadmap).

Usage: python -m autoresearch.gallery   # writes both pages
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

#gh-ribbon{position:fixed;right:-56px;bottom:36px;z-index:80;
  transform:rotate(-45deg);background:#111111;color:#fffff8;
  font:600 11px var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.12em;white-space:nowrap;
  padding:7px 64px;text-decoration:none;border:none;
  outline:1px solid rgba(255,255,248,.4);outline-offset:-4px;
  box-shadow:0 1px 8px rgba(0,0,0,.3)}
#gh-ribbon:hover{background:#8c2f1f;color:#fffff8}

.topnav{display:flex;gap:28px;justify-content:center;align-items:baseline;
  border-bottom:1px solid var(--rule);padding:18px 0 12px;margin:0 0 6px}
.topnav .brand{font:italic 14px var(--serif);color:var(--faint)}
.topnav a{font:600 12px var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.09em;color:var(--muted);
  border-bottom:2px solid transparent;padding-bottom:3px}
.topnav a:hover{color:var(--ink);border-bottom-color:transparent}
.topnav a.on{color:var(--ink);border-bottom-color:var(--ink)}

.paths-wrap{max-width:1080px;margin:0 auto;padding:14px 28px 96px}
.paths-wrap h1{font-weight:400;font-size:44px;line-height:1.15;
  letter-spacing:-.01em;text-align:center;margin:26px 0 14px}
p.psub{text-align:center;font-style:italic;color:var(--muted);
  font-size:15.5px;line-height:1.7;margin:0 auto 8px;max-width:820px}
p.psub.lead{font-size:19px;max-width:900px;margin-bottom:14px}
.pnote{max-width:780px;margin:20px auto 0;font-size:14.5px;line-height:1.7;
  color:#4a473e}
.pnote p{margin:0 0 10px}
.pnote b{color:var(--ink)}
.stats{display:flex;flex-wrap:wrap;gap:18px 56px;justify-content:center;
  margin:30px auto 10px;text-align:center}
.stat b{display:block;font-size:34px;line-height:1.1;font-weight:600;
  font-variant-numeric:lining-nums tabular-nums}
.stat span{font:600 11px var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
.sec-h{font:600 12px var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.08em;color:var(--muted);
  text-align:center;margin:44px 0 10px}
.explore{max-width:780px;margin:0 auto}
.explore a.card{display:block;border:1px solid var(--rule);border-radius:2px;
  padding:14px 18px;margin:0 0 12px;color:inherit}
.explore a.card:hover{border-color:var(--ink)}
.explore .card b{font-size:16px}
.explore .card span{display:block;font-size:13.5px;color:var(--muted);
  margin-top:3px;line-height:1.55}

.contract-fig{max-width:980px;margin:34px auto 4px}
.contract-fig svg{width:100%;height:auto;display:block}
.contract-cap{max-width:760px;margin:10px auto 0;font-size:13px;
  line-height:1.65;color:var(--muted);text-align:center;font-style:italic}
.pkey{display:flex;flex-wrap:wrap;gap:8px 26px;justify-content:center;
  font-size:13.5px;color:var(--muted);margin:22px auto 4px}
.pkey .sw{display:inline-block;width:16px;height:0;border-top:3px solid;
  vertical-align:middle;margin-right:7px}
.fig-entry{margin:54px 0 0;border-left:2px solid var(--rule-soft);
  padding:4px 0 8px 26px}
.fig-entry.kept{border-left-color:var(--ink)}
.fig-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 14px;
  margin:0 0 2px}
.fig-no{font:600 12px var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.08em;color:var(--faint);
  white-space:nowrap}
.fig-title{font-size:19px;font-weight:600;line-height:1.35}
.fig-status{font-size:13px;color:var(--faint);font-style:italic;
  white-space:nowrap}
.fig-status b{color:var(--ink)}
.fig-status .fail{color:var(--accent);font-weight:600}
.chip-cur{display:inline-block;font:600 10.5px var(--serif);font-style:normal;
  font-feature-settings:"smcp" 1;text-transform:uppercase;letter-spacing:.07em;
  color:var(--paper);background:var(--ink);padding:2px 8px 3px;
  border-radius:2px;vertical-align:1px}
.fig-svg{margin:10px 0 4px;overflow-x:auto;cursor:zoom-in}
.fig-svg svg{width:100%;min-width:720px;height:auto;display:block}
.contract-fig>svg{cursor:zoom-in}

#svgov{position:fixed;inset:0;background:var(--paper);z-index:60;
  display:none;flex-direction:column}
#svgov.on{display:flex}
.ov-bar{display:flex;align-items:baseline;gap:16px;padding:12px 26px;
  border-bottom:1px solid var(--rule);flex:none}
.ov-no{font:600 12px var(--serif);font-feature-settings:"smcp" 1;
  text-transform:uppercase;letter-spacing:.08em;color:var(--faint);
  white-space:nowrap}
.ov-title{font-size:15px;font-weight:600;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.ov-hint{margin-left:auto;font:600 10.5px var(--serif);
  font-feature-settings:"smcp" 1;text-transform:uppercase;
  letter-spacing:.06em;color:var(--faint);white-space:nowrap}
.ov-close{cursor:pointer;font:600 12px var(--serif);
  font-feature-settings:"smcp" 1;text-transform:uppercase;
  letter-spacing:.06em;color:var(--muted);background:none;
  border:1px solid var(--rule);border-radius:2px;padding:4px 12px}
.ov-close:hover{color:var(--ink);border-color:var(--ink)}
.ov-canvas{flex:1;overflow:hidden;cursor:grab;touch-action:none;
  user-select:none;-webkit-user-select:none}
.ov-canvas.dragging{cursor:grabbing}
.ov-inner{width:100%;height:100%;transform-origin:0 0}
.ov-inner svg{width:100%;height:100%;display:block}
.fig-cap{max-width:880px;font-size:14.5px;line-height:1.65;color:#4a473e}
.fig-cap p{margin:0 0 4px}
.fig-cap .fig-lead{font-weight:600;color:var(--ink)}
.fig-meta{font-size:12.5px;color:var(--faint);margin-top:2px}
.fig-meta .chg{color:var(--accent)}
.fig-meta a{white-space:nowrap}

.dash-head{max-width:92vw;margin:0 auto;padding:18px 0 6px}
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
  // deep link from other pages: index.html#r<id> opens + flashes that row
  var hm=location.hash.match(/^#r(\\d+)$/);
  if(hm){
    var hr=document.getElementById('r'+hm[1]),
        hd=document.getElementById('d'+hm[1]);
    if(hr){
      if(hd&&hd.style.display==='none')toggle(+hm[1]);
      hr.scrollIntoView({behavior:'smooth',block:'center'});
      hr.classList.add('row-flash');
    }
  }
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


# Zoom/pan overlay for the inference-paths page: click any figure to open it
# full-screen (SVG, so zoom is lossless); wheel = zoom about the cursor,
# drag = pan, double-click = reset, Esc or the close button to exit.
PATHS_JS = """
var ov,ovIn,ovCv,sc=1,px=0,py=0,drag=null;
function ovApply(){ovIn.style.transform=
  'translate('+px+'px,'+py+'px) scale('+sc+')'}
function ovOpen(svg,no,title){
  ovIn.innerHTML='';ovIn.appendChild(svg.cloneNode(true));
  document.querySelector('.ov-no').textContent=no;
  document.querySelector('.ov-title').textContent=title;
  sc=1;px=0;py=0;ovApply();
  ov.classList.add('on');document.body.style.overflow='hidden';
}
function ovClose(){ov.classList.remove('on');
  document.body.style.overflow='';ovIn.innerHTML=''}
window.addEventListener('load',function(){
  ov=document.getElementById('svgov');
  ovIn=ov.querySelector('.ov-inner');
  ovCv=ov.querySelector('.ov-canvas');
  document.querySelectorAll('.fig-entry').forEach(function(sec){
    var holder=sec.querySelector('.fig-svg'),svg=holder&&holder.querySelector('svg');
    if(!svg)return;
    holder.addEventListener('click',function(){
      ovOpen(svg,sec.querySelector('.fig-no').textContent,
             sec.querySelector('.fig-title').textContent)});
  });
  var cf=document.querySelector('.contract-fig>svg');
  if(cf)cf.addEventListener('click',function(){
    ovOpen(cf,'','The frozen contract — where the experiments happen')});
  ov.querySelector('.ov-close').addEventListener('click',ovClose);
  window.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&ov.classList.contains('on'))ovClose()});
  ovCv.addEventListener('wheel',function(e){
    e.preventDefault();
    var r=ovCv.getBoundingClientRect(),
        mx=e.clientX-r.left,my=e.clientY-r.top,
        ns=Math.min(16,Math.max(0.5,sc*Math.exp(-e.deltaY*0.002))),
        k=ns/sc;
    px=mx-k*(mx-px);py=my-k*(my-py);sc=ns;ovApply();
  },{passive:false});
  ovCv.addEventListener('pointerdown',function(e){
    drag={x:e.clientX,y:e.clientY,px:px,py:py};
    ovCv.setPointerCapture(e.pointerId);
    ovCv.classList.add('dragging');
  });
  ovCv.addEventListener('pointermove',function(e){
    if(!drag)return;
    px=drag.px+e.clientX-drag.x;py=drag.py+e.clientY-drag.y;ovApply();
  });
  ovCv.addEventListener('pointerup',function(){
    drag=null;ovCv.classList.remove('dragging')});
  ovCv.addEventListener('dblclick',function(){sc=1;px=0;py=0;ovApply()});
});
"""


def esc(s):
    return html.escape(str(s if s is not None else ""))


# Shared top navigation, airloom pattern (centered, italic brand, smallcaps
# links, active page underlined in ink). The overview lives at the repo root
# (index.html) and the other pages under gallery/, so hrefs are resolved per
# page location. Lineage + results pages are planned but held out for now —
# add them here when they exist so every page's nav updates together.
NAV_PAGES = (("overview", "overview"),
             ("log", "research log"),
             ("paths", "inference paths"))


def topnav(active, root=False):
    hrefs = {"overview": "index.html" if root else "../index.html",
             "log": "gallery/index.html" if root else "index.html",
             "paths": ("gallery/inference-paths.html" if root
                       else "inference-paths.html")}
    links = []
    for key, label in NAV_PAGES:
        cls = " class='on'" if key == active else ""
        links.append(f"<a href='{hrefs[key]}'{cls}>{label}</a>")
    return ("<nav class='topnav'><span class='brand'>Low-Light "
            "Geolocalization</span>" + "".join(links) + "</nav>")


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
            "<div class='figs-intro'>Every frame in this project is rendered as a "
            "<b>starlight-class low-light sensor</b> (Sony STARVIS2 / IMX585 class — the "
            "airframe's chosen camera) would see it, not as a normal camera would. That is "
            "why the <i>night</i> renders look uncannily close to daylight: at high gain such "
            "a sensor recovers scene structure from moonlight, skyglow and artificial "
            "lighting, paying for it in noise, lifted shadows and washed-out color — exactly "
            "what these renders simulate. Below, one example 256 m patch per area under the "
            "six lighting conditions the model must handle. These illustrate the "
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
                   f"look like through the simulated low-light sensor (example patches — "
                   f"illustration, not the training set)"
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
        cls = " class='chg'" if chg else ""  # 3.11-compatible (pod venv): no nested same-quote f-string
        seg = f"<b{cls}>{esc(s.get('name', '?'))}</b>"
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
        legend = (" — <span style='color:var(--faint)'>gray = frozen contract"
                  "</span> · ink = the current design · "
                  "<span class='chg'>red = this experiment's change</span>")
        out.append(f"<div class='arch-h'>The design under test — technical "
                   f"diagram{legend}</div><div class='arch-svg'>{svg}</div>")
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


# License attribution for imagery-derived figures — required by the data
# sources' terms on any published page (dl-de/by-2-0, CC BY 4.0, Copernicus).
CREDITS = """<footer style="margin:48px auto 24px;max-width:960px;color:#9b998c;
font-size:12.5px;line-height:1.5;border-top:1px solid #e6e4da;padding-top:10px">
Imagery-derived figures are based on open geodata:
© GeoBasis-DE/LGB (dl-de/by-2-0) · © Bayerische Vermessungsverwaltung (CC BY 4.0)
· © HVBG Hessen (dl-de/by-2-0) · © Freie und Hansestadt Hamburg, LGV (dl-de/by-2-0)
· Contains modified Copernicus Sentinel data.
Code: MIT License —
<a href="https://github.com/akaalias/low-light-geolocalization-autoresearch"
style="color:inherit">source repository</a>.</footer>
<a id="gh-ribbon" href="https://github.com/akaalias/low-light-geolocalization-autoresearch"
target="_blank" rel="noopener">view on GitHub</a>"""

PATHS_OUT = REPO_ROOT / "gallery" / "inference-paths.html"
OVERVIEW_OUT = REPO_ROOT / "index.html"


def render_overview(exps):
    """index.html at the repo root — the project's front door: what this is,
    live status numbers from the lineage DB, and links into the gallery
    pages. Same airloom-style typography and shared topnav as the rest."""
    dev = [e for e in exps if e["kind"] != "holdout_check"]
    n_kept = sum(1 for e in dev if e["kept"])
    best = next((e["primary_metric"] for e in reversed(dev)
                 if e["kept"] and e["primary_metric"]
                 and e["primary_metric"] < FAIL), None)
    best_size = next((e["model_bytes_max"] for e in reversed(dev)
                      if e["kept"] and e["model_bytes_max"]), None)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    best_s = fmt_m(best) if best is not None else "—"
    size_s = f"{best_size/1024:,.0f} KB" if best_size else "—"
    factor = (f"{best/TARGET_M:,.0f}×" if best and best > TARGET_M
              else "at goal" if best else "—")

    html_page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=1100">
<title>Not all who wander are lost — Low-Light Geolocalization</title>
<style>{CSS}</style></head><body>
{topnav('overview', root=True)}
<div class="paths-wrap">
<div class="eyebrow" style="text-align:center">Alexis Rondeau · an autonomous research project</div>
<h1>&ldquo;Not all who wander are lost&rdquo; &mdash; a 5-inch drone learns
to find itself in the dark, with no GPS, no maps on board, and a $4 flight
computer</h1>
<p class="psub lead">Where other aircraft ask satellites, this one
<i>remembers</i>: a neural network small enough to fit in 4&nbsp;MiB has
memorized what its flight area looks like from above — by day, by dusk, by
night — and turns one glance of a low-light camera into
<i>(lat,&nbsp;lon,&nbsp;confidence)</i>. No satellites to jam or lose, no
internet. And the research to get there is not done by me: an
<b>autonomous loop of coding agents</b> designs, trains, and scores one
pre-registered experiment at a time, keeping only what measurably helps.
This site is its live lab notebook.</p>

<div class="stats">
  <div class="stat"><b>{best_s}</b><span>worst-case median miss, best model</span></div>
  <div class="stat"><b>≤ 20 m</b><span>the goal — {factor} to go</span></div>
  <div class="stat"><b>{len(dev)}</b><span>experiments · {n_kept} kept</span></div>
  <div class="stat"><b>{size_s}</b><span>deployed model · limit 4 MiB</span></div>
</div>

<div class="sec-h">How it works — think globally, memorize locally</div>
<div class="pnote">
<p>The model family is <b>scene-coordinate regression</b>: one compact
network per flight area that encodes "what does this place look like from
above, under which lighting" directly into its weights — the pipeline works
for any bounding box on Earth, but each trained model knows exactly one
patch of it by heart. No reference imagery on the aircraft, no retrieval,
no matching. Training data comes
from a frozen pipeline that fetches open-licensed aerial orthophotos for
any bounding box and re-renders them under six lighting conditions, from
morning to night, <b>as seen by a simulated starlight-class low-light
sensor</b> (Sony STARVIS2 / IMX585 class — the aircraft's chosen camera).
That sensor choice is the premise of the whole project: at high gain it
keeps daylight-like scene structure deep into the night — trading it for
noise and washed-out color, which is exactly what the night renders below
show — so a single compact model can localize from morning to midnight.</p>
<p>The research loop is Karpathy-style autoresearch: each iteration, a
headless coding agent reads the full experiment history, pre-registers ONE
focused change — hypothesis, method, expected outcome, and a hand-drawn
architecture figure — then the harness trains and scores it against a
single frozen ruler: the <b>worst</b> median position error across 6
lighting conditions × 4 German test areas (dense Berlin, rural Prignitz,
Munich, Frankfurt), on held-out map crops. Improvements are kept as git
commits; everything else is reverted but stays in the record. Hamburg is
never touched by the loop — it exists only as a blind check that the
method generalizes.</p>
</div>

<div class="sec-h">Explore</div>
<div class="explore">
<a class="card" href="gallery/index.html"><b>The research log</b>
<span>Every experiment ever run, failures included: pre-registered
hypotheses, results, per-area × lighting scoreboards, the exact prompts
the agents received, and one real worked example per experiment — the same
night crop through each model's actual deployed weights.</span></a>
<a class="card" href="gallery/inference-paths.html"><b>Proposed inference
paths</b>
<span>The technical figures: each experiment's model design, drawn by the
agent itself before training, in one shared visual language — frozen
endpoints aligned so you can scroll and compare designs directly.</span></a>
</div>

<p class="psub num" style="margin-top:34px">updated {now} · experiments run
around the clock on a rented RTX 4090; the loop commits every result to
git as it goes</p>
</div>
{CREDITS}</body></html>"""
    OVERVIEW_OUT.write_text(html_page)
    print(f"wrote {OVERVIEW_OUT}")


def contract_svg():
    """The meta-figure at the top of the inference-paths page: the frozen
    contract (camera frame in, (u, v, conf) out, both gray) with a dashed
    placeholder box for everything an experiment may redraw, and the ochre
    training-signals lane beneath it. Same glyph geometry and palette as the
    per-experiment figures (see archive/arch_svg_reference.py)."""
    INK, MUT, FAINT, ACC, OCH = ("#111111", "#6b6a60", "#9b998c",
                                 "#8c2f1f", "#8a6a1e")
    FONT = "Palatino,Georgia,serif"
    IC = 112  # inference lane center y

    def txt(x, y, s, size=10, color=MUT, w=400, anchor="middle", style=""):
        return (f"<text x='{x:.0f}' y='{y:.0f}' font-family='{FONT}' "
                f"font-size='{size}' fill='{color}' font-weight='{w}' "
                f"text-anchor='{anchor}' {style}>{s}</text>")

    def harrow(x1, x2, y, color=FAINT):
        return (f"<line x1='{x1}' y1='{y}' x2='{x2 - 5}' y2='{y}' "
                f"stroke='{color}' stroke-width='1'/>"
                f"<path d='M {x2},{y} l -6,-3 v 6 Z' fill='{color}'/>")

    b = []
    # lane labels, identical to the per-experiment figures
    b.append(txt(8, 26, "INFERENCE PATH — WHAT FLIES", 9, FAINT, 600, "start",
                 "letter-spacing='1.8'"))
    b.append(txt(8, 236, "TRAINING SIGNALS — NEVER FLY", 9, OCH, 600, "start",
                 "letter-spacing='1.8'"))
    # frozen input: pixel-textured camera frame (gray)
    x0, s = 26, 54
    y0 = IC - s / 2
    b.append(f"<rect x='{x0}' y='{y0}' width='{s}' height='{s}' "
             f"fill='#00000008' stroke='{FAINT}' stroke-width='1.4'/>")
    n = 6
    for i in range(1, n):
        b.append(f"<line x1='{x0 + i * s / n:.0f}' y1='{y0}' "
                 f"x2='{x0 + i * s / n:.0f}' y2='{y0 + s}' stroke='{FAINT}' "
                 f"stroke-width='0.4' opacity='0.3'/>")
        b.append(f"<line x1='{x0}' y1='{y0 + i * s / n:.0f}' x2='{x0 + s}' "
                 f"y2='{y0 + i * s / n:.0f}' stroke='{FAINT}' "
                 f"stroke-width='0.4' opacity='0.3'/>")
    for (a, c, o) in ((1, 2, .35), (3, 1, .5), (2, 4, .4), (4, 3, .3), (0, 4, .25)):
        b.append(f"<rect x='{x0 + a * s / n:.0f}' y='{y0 + c * s / n:.0f}' "
                 f"width='{s / n:.0f}' height='{s / n:.0f}' fill='{FAINT}' "
                 f"opacity='{o * 0.35}'/>")
    b.append(txt(53, IC - 40, "128²×3", 9, FAINT))
    b.append(txt(53, IC + 48, "camera frame", 10.5, MUT, 600))
    b.append(txt(53, IC + 60, "one night exposure", 9.5, FAINT))
    b.append(txt(53, IC + 73, "frozen contract", 8.5, FAINT,
                 style="font-style='italic'"))
    b.append(harrow(x0 + s + 8, 176, IC))
    # the placeholder: everything between the endpoints is the search space
    bx, by, bw, bh = 180, 40, 560, 144
    b.append(f"<rect x='{bx}' y='{by}' width='{bw}' height='{bh}' fill='none' "
             f"stroke='{ACC}' stroke-width='1.6' stroke-dasharray='9 7'/>")
    cx = bx + bw / 2
    b.append(txt(cx, IC - 14, "the experiment goes here", 14, INK, 600))
    b.append(txt(cx, IC + 6,
                 "architecture · feature extraction · decode · confidence — "
                 "the agent may redraw all of it", 10, MUT))
    b.append(txt(cx, IC + 22,
                 "each figure below is one proposal for the inside of this box",
                 9.5, FAINT, style="font-style='italic'"))
    # deployment gate note, hanging off the box like a margin annotation
    b.append(txt(972, by + bh + 16,
                 "whatever fills the box must export to one ONNX file "
                 "≤ 4 MiB and answer in ≤ 250 ms", 9, FAINT, anchor="end",
                 style="font-style='italic'"))
    # frozen output
    b.append(harrow(bx + bw + 6, 796, IC))
    ox = 812
    b.append(f"<line x1='{ox - 7}' y1='{IC}' x2='{ox + 7}' y2='{IC}' "
             f"stroke='{FAINT}' stroke-width='1.4'/>"
             f"<line x1='{ox}' y1='{IC - 7}' x2='{ox}' y2='{IC + 7}' "
             f"stroke='{FAINT}' stroke-width='1.4'/>"
             f"<circle cx='{ox}' cy='{IC}' r='3.9' fill='none' "
             f"stroke='{FAINT}' stroke-width='1.4'/>"
             f"<circle cx='{ox}' cy='{IC}' r='1.5' fill='{FAINT}'/>")
    b.append(txt(ox + 16, IC - 18, "frozen contract", 8.5, FAINT,
                 anchor="start", style="font-style='italic'"))
    b.append(txt(ox + 16, IC - 2, "(lat, lon, confidence)", 13, MUT, 600, "start"))
    b.append(txt(ox + 16, IC + 12, "position fix + confidence", 9, FAINT,
                 anchor="start"))
    # training-signals lane: scaffolding attached to the box, discarded later
    for lx in (cx - 90, cx + 90):
        b.append(f"<line x1='{lx}' y1='{by + bh}' x2='{lx}' y2='{252}' "
                 f"stroke='{OCH}' stroke-width='1' stroke-dasharray='2 4'/>")
    b.append(txt(cx, 250, "losses · supervision targets · samplers", 10, OCH, 600))
    b.append(txt(cx, 263,
                 "scaffolding that shapes the weights during training — torn "
                 "down before flight, never in the exported model", 9.5, OCH))
    return ("<svg viewBox='0 0 980 290' xmlns='http://www.w3.org/2000/svg' "
            "role='img'>" + "".join(b) + "</svg>")


def paths_status(e, is_current):
    if e["primary_metric"] is not None and e["primary_metric"] >= FAIL:
        return "<span class='fail'>gated fail</span> — reverted"
    if e["kept"]:
        cur = " <span class='chip-cur'>current design</span>" if is_current else ""
        return f"<b>kept</b> — new best, <b class='num'>{fmt_m(e['primary_metric'])}</b>{cur}"
    return f"discarded — <span class='num'>{fmt_m(e['primary_metric'])}</span>, reverted"


def render_paths(exps):
    """gallery/inference-paths.html — every experiment's pre-registered
    architecture figure (the `architecture_svg` each agent must draw before
    training), presented chronologically as one evolving design record."""
    figs = [e for e in exps
            if e["kind"] != "holdout_check"
            and (e.get("arch_svg") or "").lstrip().startswith("<svg")]
    n_kept = sum(1 for e in figs if e["kept"])
    current_id = next((e["id"] for e in reversed(figs) if e["kept"]), None)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    body = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=1100">
<title>Proposed Inference Paths — Low-Light Geolocalization</title>
<style>{CSS}</style><script>{PATHS_JS}</script></head><body>
{topnav('paths')}
<div class="paths-wrap">
<div class="eyebrow" style="text-align:center">Alexis Rondeau · live research log</div>
<h1>Proposed Inference Paths</h1>
<p class="psub lead">Before it may train anything, every iteration of the
research loop has to draw the model it proposes to fly — a proper technical
figure of its <b>inference path</b>: the computation one camera frame takes
through the deployed network, left to right, from pixels to
<i>(lat,&nbsp;lon,&nbsp;confidence)</i>. These are those figures — every
proposal ever made, reverted branches included.</p>
<div class="pnote">
<p>Each figure is drawn by the experimenting agent itself, under one shared
visual contract — tensors drawn as tensors (an image is pixels, a feature map
is a slab, a vector is a bar of ticks), operations as operations, no labeled
boxes — so independent proposals read like figures from a single paper. The
two endpoints are gray because they are the <b>frozen contract</b>: the
camera crop coming in and the coordinate going out are fixed by the harness,
outside the search space. Everything in ink between them is that
experiment's design; red is reserved for the one thing the experiment
changed; ochre exists only during training and never flies.</p>
<p>Read top to bottom and you watch the design evolve: a <b>kept</b>
proposal (ink rule on the left) becomes the trunk the next experiment
branches from; a <b>discarded</b> one was trained, scored, and reverted —
drawn to the same standard, because the dead branches are part of the record
too. Each caption is the experiment's own pre-registered plain-words
explanation; the full record (hypothesis, method, scoreboard) is one click
away in the <a href="index.html">research log</a>. (One honesty note:
figures 1–6 predate the loop — those experiments were designed
interactively during the bootstrap phase and pre-registered their designs
as text; their figures were drawn to this standard after the fact. From
experiment 7 on, every figure is the headless agent's own, drawn before
training ran.)</p>
</div>
<div class="contract-fig">{contract_svg()}
<p class="contract-cap">The shape every figure on this page shares. The gray
endpoints are the harness's frozen contract — one low-light camera crop in,
one <i>(lat,&nbsp;lon,&nbsp;confidence)</i> answer out — and the dashed box
is the entire search space: each experiment below is one way of filling it.
The ochre lane underneath holds the training signals: the losses, targets
and samplers that shape the weights during training and are torn down before
flight — they never board the aircraft.</p>
</div>
<div class="pkey">
  <span class="k"><span class="sw" style="border-top-color:var(--faint)"></span>frozen contract — harness endpoints</span>
  <span class="k"><span class="sw" style="border-top-color:var(--ink)"></span>the design under test</span>
  <span class="k"><span class="sw" style="border-top-color:var(--accent)"></span>what this experiment changed</span>
  <span class="k"><span class="sw" style="border-top-color:var(--ochre)"></span>training-only — never flies</span>
</div>
<p class="psub num">{len(figs)} proposals · {n_kept} kept ·
updated {now}</p>"""]

    for e in figs:
        try:
            arch = json.loads(e.get("arch_json") or "null")
        except (TypeError, json.JSONDecodeError):
            arch = None
        stages = arch.get("stages") if isinstance(arch, dict) else None
        changed = [s.get("name", "?") for s in (stages or []) if s.get("changed")]
        chg = (f"<span class='chg'>changed: {esc(', '.join(changed))}</span> · "
               if changed else "")
        kept_cls = " kept" if e["kept"] else ""
        eli5 = (f"<p><span class='fig-lead'>In plain words.</span> "
                f"{esc(e['eli5'])}</p>" if e.get("eli5") else "")
        body.append(f"""<section class="fig-entry{kept_cls}" id="e{e['id']}">
<div class="fig-head">
  <span class="fig-no num">Fig. {e['id']}</span>
  <span class="fig-title">{esc(e['title'])}</span>
  <span class="fig-status">{paths_status(e, e['id'] == current_id)}</span>
</div>
<div class="fig-svg">{e['arch_svg']}</div>
<div class="fig-cap">
{eli5}
<p class="fig-meta">{esc(e['category'] or '—')} · {esc(e['init_strategy'] or '—')}
· {chg}{esc(e['ts'][:10])} · commit
<span class="mono">{esc(e['git_commit'][:8])}</span> ·
<a href="index.html#r{e['id']}">full experiment record →</a></p>
</div>
</section>""")

    body.append("""</div>
<div id="svgov"><div class="ov-bar"><span class="ov-no"></span>
<span class="ov-title"></span>
<span class="ov-hint">scroll to zoom · drag to pan · double-click to reset</span>
<button class="ov-close">Esc · close</button></div>
<div class="ov-canvas"><div class="ov-inner"></div></div></div>
""" + CREDITS + "</body></html>")
    PATHS_OUT.parent.mkdir(exist_ok=True)
    PATHS_OUT.write_text("\n".join(body))
    print(f"wrote {PATHS_OUT} ({len(figs)} figures)")


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
{topnav('log')}
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
    body.append("<div id='tip'></div>" + CREDITS + "</body></html>")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(body))
    print(f"wrote {OUT} ({len(exps)} experiments)")
    render_paths(exps)
    render_overview(exps)


if __name__ == "__main__":
    render()
