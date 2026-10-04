"""Interactive viewer: a single self-contained HTML file (no internet, no extra packages).

Controls (also shown inside the page):
  Space / K      play / pause
  Left / Right   1 step back / forward
  J / L          about 10 seconds back / forward  (Shift+Left / Shift+Right also work)
  [ / ]          previous / next disruption
  slider         drag to any time step;  click an event in the list to jump just before it
"10 seconds" means 10 seconds of playback at the current speed, i.e. 10 * steps-per-second * speed steps.
"""
import json
from .vizdata import prepare

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>__TITLE__</title>
<style>
 body{font-family:Segoe UI,Arial,sans-serif;margin:10px;background:#f4f5f7;color:#222}
 h2{margin:2px 0 8px;font-size:17px}
 #app{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}
 #left{flex:0 0 auto}
 #right{flex:1 1 300px;min-width:280px;max-width:430px}
 canvas{background:#fff;border:1px solid #999;display:block}
 #banner{min-height:22px;margin:6px 0;padding:4px 8px;border-radius:4px;font-weight:600;font-size:14px;background:#e9ecef;color:#555}
 #banner.hot{background:#c1121f;color:#fff}
 button,select{font-size:13px;padding:5px 9px;margin:2px;border:1px solid #888;border-radius:4px;background:#fff;cursor:pointer}
 button:hover{background:#e8f0fe}
 #slidewrap{position:relative;margin:6px 2px 2px}
 #slider{width:100%;margin:0}
 #marks{position:relative;height:10px}
 .mk{position:absolute;top:0;width:3px;height:10px;border-radius:1px}
 #info{font-size:13px;margin:2px 4px;color:#333}
 #hover{font-size:13px;height:18px;margin:2px 4px;color:#0b3d91}
 .box{background:#fff;border:1px solid #bbb;border-radius:6px;padding:6px 8px;margin-bottom:10px}
 .box h3{margin:0 0 4px;font-size:13px}
 #events{max-height:170px;overflow:auto}
 .ev{padding:3px 4px;border-bottom:1px solid #eee;font-size:12px;cursor:pointer}
 .ev:hover{background:#eef3ff}
 .ev.cur{background:#fff3cd}
 table{border-collapse:collapse;width:100%;font-size:12px}
 td,th{padding:1px 4px;text-align:left}
 tr.chg td{background:#ffe8cc;font-weight:600}
 tr.bad td{color:#c1121f;font-weight:600}
 tr.done td{color:#999}
 .sw{display:inline-block;width:11px;height:11px;border:1px solid #333;border-radius:50%;vertical-align:middle}
 #help{font-size:12px;line-height:1.5}
 kbd{background:#eee;border:1px solid #bbb;border-radius:3px;padding:0 4px;font-size:11px}
 .lg span{display:inline-block;width:12px;height:12px;vertical-align:middle;margin-right:4px;border:1px solid #333}
 .lg div{font-size:12px;margin:2px 0}
</style></head><body>
<h2>__TITLE__</h2>
<div id="app">
 <div id="left">
  <canvas id="cv"></canvas>
  <div id="banner"></div>
  <div id="controls">
   <button id="bB10"></button><button id="bB1">&#9664; 1 step</button>
   <button id="bPlay">Pause</button>
   <button id="bF1">1 step &#9654;</button><button id="bF10"></button>
   <select id="speed"><option value="0.25">0.25x</option><option value="0.5">0.5x</option><option value="1" selected>1x</option><option value="2">2x</option><option value="4">4x</option></select>
   <button id="bPE">&#9198; prev event</button><button id="bNE">next event &#9197;</button>
  </div>
  <div id="slidewrap"><input type="range" id="slider" min="0" value="0"><div id="marks"></div></div>
  <div id="info"></div>
  <div id="hover">Hover a cell to see what is in it.</div>
 </div>
 <div id="right">
  <div class="box"><h3>Disruptions (click = jump to 3 steps before it, paused)</h3><div id="events"></div></div>
  <div class="box"><h3>Which agent is in which cell</h3><table id="tbl"><thead><tr><th></th><th>Agent</th><th>Cell (x,y)</th><th>Next goal</th><th>Status</th></tr></thead><tbody></tbody></table></div>
  <div class="box lg"><h3>Legend</h3>
   <div><span style="background:#5b5b5b"></span>shelf (static obstacle)</div>
   <div><span style="background:#e63946"></span>dynamic blocked cell (coordinates printed in it)</div>
   <div><span style="background:#e63946;border:3px solid #ffd60a"></span>newly blocked cell (gold outline for 3 steps)</div>
   <div><span style="background:#fff;border:3px solid #ff9f1c;border-radius:50%"></span>agent that was just re-planned</div>
   <div>solid line = current plan &nbsp; dashed grey = plan before the repair &nbsp; small square = next goal</div>
   <div><span style="background:#222;border-radius:50%"></span>broken robot (red cross)</div>
  </div>
  <div class="box" id="help"><h3>Controls</h3>
   <kbd>Space</kbd> / <kbd>K</kbd> play-pause &nbsp; <kbd>&larr;</kbd><kbd>&rarr;</kbd> 1 step<br>
   <kbd>J</kbd> / <kbd>L</kbd> or <kbd>Shift</kbd>+<kbd>&larr;</kbd><kbd>&rarr;</kbd> about 10 s back / forward<br>
   <kbd>[</kbd> <kbd>]</kbd> previous / next disruption &nbsp; <kbd>Home</kbd><kbd>End</kbd> start / end<br>
   10 s = 10 &times; steps-per-second &times; speed (at 1x: __TEN__ steps).</div>
 </div>
</div>
<script>
const D = __DATA__;
const W = D.w, H = D.h, N = D.frames.length, FPS = D.fps;
const CS = Math.max(18, Math.floor(640 / Math.max(W, H))), M = 22;
const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
const dpr = window.devicePixelRatio || 1;
cv.style.width = (W*CS+M) + 'px'; cv.style.height = (H*CS+M) + 'px';
cv.width = (W*CS+M)*dpr; cv.height = (H*CS+M)*dpr; ctx.scale(dpr, dpr);
const staticSet = new Set(D.static.map(c => c[0]+','+c[1]));
let k = 0, playing = true, speed = 1, acc = 0, last = performance.now(), hoverCell = null;

function ten(){ return Math.max(1, Math.round(10 * FPS * speed)); }
function clamp(v){ return Math.max(0, Math.min(N-1, v)); }
function lum(hex){ const r=parseInt(hex.substr(1,2),16), g=parseInt(hex.substr(3,2),16), b=parseInt(hex.substr(5,2),16); return 0.299*r+0.587*g+0.114*b; }
function cx(x){ return M + x*CS + CS/2; } function cy(y){ return M + y*CS + CS/2; }

function drawPath(p){ ctx.beginPath(); p.forEach((c,i)=>{ i ? ctx.lineTo(cx(c[0]),cy(c[1])) : ctx.moveTo(cx(c[0]),cy(c[1])); }); ctx.stroke(); }

function draw(){
  const f = D.frames[k];
  ctx.clearRect(0,0,W*CS+M,H*CS+M);
  ctx.font = '10px Arial'; ctx.fillStyle = '#555'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  for(let x=0;x<W;x++) ctx.fillText(x, cx(x), M/2);
  for(let y=0;y<H;y++) ctx.fillText(y, M/2, cy(y));
  for(let x=0;x<W;x++) for(let y=0;y<H;y++){
    ctx.fillStyle = staticSet.has(x+','+y) ? '#5b5b5b' : '#fbfbfb';
    ctx.fillRect(M+x*CS, M+y*CS, CS, CS);
    ctx.strokeStyle = staticSet.has(x+','+y) ? '#444' : '#cfcfcf'; ctx.lineWidth = 1;
    ctx.strokeRect(M+x*CS+.5, M+y*CS+.5, CS-1, CS-1);
  }
  const nb = new Set(f.new_blocks.map(c => c[0]+','+c[1]));
  f.blocks.forEach(c => {
    const fresh = nb.has(c[0]+','+c[1]);
    ctx.fillStyle = '#e63946'; ctx.fillRect(M+c[0]*CS, M+c[1]*CS, CS, CS);
    ctx.strokeStyle = fresh ? '#ffd60a' : '#9d0208'; ctx.lineWidth = fresh ? 4 : 1.5;
    ctx.strokeRect(M+c[0]*CS+(fresh?2:.5), M+c[1]*CS+(fresh?2:.5), CS-(fresh?4:1), CS-(fresh?4:1));
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.2; ctx.beginPath();
    ctx.moveTo(M+c[0]*CS+5, M+c[1]*CS+5); ctx.lineTo(M+(c[0]+1)*CS-5, M+(c[1]+1)*CS-5);
    ctx.moveTo(M+(c[0]+1)*CS-5, M+c[1]*CS+5); ctx.lineTo(M+c[0]*CS+5, M+(c[1]+1)*CS-5); ctx.stroke();
    ctx.fillStyle = '#fff'; ctx.font = 'bold 8px Arial'; ctx.textAlign='center'; ctx.textBaseline='bottom';
    ctx.fillText(c[0]+','+c[1], cx(c[0]), M+(c[1]+1)*CS-1);
  });
  ctx.setLineDash([5,4]); ctx.strokeStyle = '#777'; ctx.lineWidth = 1.6;
  Object.keys(f.old).forEach(i => drawPath(f.old[i]));
  ctx.setLineDash([]);
  Object.keys(f.path).forEach(i => {
    if (f.status[i] === 'active' && f.path[i].length > 1){ ctx.globalAlpha = .75; ctx.strokeStyle = D.colors[i]; ctx.lineWidth = 2.2; drawPath(f.path[i]); ctx.globalAlpha = 1; }
  });
  Object.keys(f.target).forEach(i => { const c = f.target[i]; if(!c) return;
    ctx.fillStyle = D.colors[i]; ctx.strokeStyle = '#000'; ctx.lineWidth = 1;
    ctx.fillRect(cx(c[0])-5, cy(c[1])-5, 10, 10); ctx.strokeRect(cx(c[0])-5, cy(c[1])-5, 10, 10); });
  const chg = new Set(f.changed.map(String));
  Object.keys(f.pos).forEach(i => {
    const p = f.pos[i], st = f.status[i], x = cx(p[0]), y = cy(p[1]), r = CS*0.4;
    ctx.beginPath(); ctx.arc(x, y, r, 0, 2*Math.PI);
    if (st === 'done'){ ctx.globalAlpha = .4; ctx.fillStyle = D.colors[i]; ctx.fill(); ctx.globalAlpha = 1; ctx.fillStyle = '#444'; }
    else if (st === 'broken' || st === 'failed'){ ctx.fillStyle = '#222'; ctx.fill(); ctx.strokeStyle = '#ff4d4d'; ctx.lineWidth = 2; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(x-r*.7,y-r*.7); ctx.lineTo(x+r*.7,y+r*.7); ctx.moveTo(x+r*.7,y-r*.7); ctx.lineTo(x-r*.7,y+r*.7); ctx.stroke(); ctx.fillStyle = '#fff'; }
    else { ctx.fillStyle = D.colors[i]; ctx.fill(); const ch = chg.has(i); ctx.strokeStyle = ch ? '#ff9f1c' : '#000'; ctx.lineWidth = ch ? 3.5 : 1; ctx.stroke(); ctx.fillStyle = lum(D.colors[i]) < 120 ? '#fff' : '#000'; }
    ctx.font = 'bold ' + Math.round(CS*0.42) + 'px Arial'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(i, x, y+1);
  });
  if (hoverCell){ ctx.strokeStyle = '#0b3d91'; ctx.lineWidth = 2.5; ctx.strokeRect(M+hoverCell[0]*CS+1, M+hoverCell[1]*CS+1, CS-2, CS-2); }
  updatePanels(f);
}

const tb = document.querySelector('#tbl tbody');
D.agents.forEach(i => { const tr = document.createElement('tr'); tr.id = 'row'+i;
  tr.innerHTML = '<td><span class="sw" style="background:'+D.colors[i]+'"></span></td><td>'+i+'</td><td></td><td></td><td></td>'; tb.appendChild(tr); });
const evBox = document.getElementById('events');
D.events.forEach((e, n) => { const d = document.createElement('div'); d.className = 'ev'; d.id = 'ev'+n;
  d.textContent = 't=' + e.t + '  ' + e.text + (e.level ? '  (repair level ' + e.level + ')' : ''); d.onclick = () => { jump(Math.max(0, tIndex(e.t) - 3)); setPlay(false); };
  evBox.appendChild(d); });
const marks = document.getElementById('marks');
D.events.forEach(e => { const m = document.createElement('div'); m.className = 'mk';
  m.style.left = (100*tIndex(e.t)/(N-1)) + '%'; m.style.background = e.kind==='block' ? '#e63946' : e.kind==='break' ? '#222' : e.kind==='emergency' ? '#ff9f1c' : '#2a9d8f';
  m.title = 't=' + e.t + ' ' + e.text; marks.appendChild(m); });
function tIndex(t){ let b = 0; for(let i=0;i<N;i++){ if (D.frames[i].t <= t) b = i; } return b; }

function updatePanels(f){
  D.agents.forEach(i => { const tr = document.getElementById('row'+i), td = tr.children, p = f.pos[i], g = f.target[i], st = f.status[i];
    td[2].textContent = '(' + p[0] + ', ' + p[1] + ')'; td[3].textContent = g ? '(' + g[0] + ', ' + g[1] + ')' : '-';
    td[4].textContent = st === 'active' ? (f.changed.includes(i) ? 're-planned' : 'moving') : st;
    tr.className = f.changed.includes(i) ? 'chg' : (st==='broken'||st==='failed') ? 'bad' : st==='done' ? 'done' : ''; });
  const done = Object.values(f.status).filter(s => s === 'done').length;
  document.getElementById('info').textContent = 't = ' + f.t + ' / ' + D.frames[N-1].t + '    done ' + done + '/' + D.agents.length + '    (' + (f.t/(FPS*speed)).toFixed(1) + ' s at ' + speed + 'x)';
  const b = document.getElementById('banner'); b.textContent = f.msg || 'No disruption in the last few steps'; b.className = f.msg ? 'hot' : '';
  document.getElementById('slider').value = k;
  document.getElementById('bB10').textContent = '\u23EA -10 s (' + ten() + ' steps)'; document.getElementById('bF10').textContent = '+10 s (' + ten() + ' steps) \u23E9';
  let cur = -1; D.events.forEach((e, n) => { if (e.t <= f.t) cur = n; });
  D.events.forEach((e, n) => document.getElementById('ev'+n).classList.toggle('cur', n === cur && f.t - D.events[cur].t <= 6));
}

function jump(v){ k = clamp(v); acc = 0; draw(); }
function setPlay(v){ playing = v; document.getElementById('bPlay').textContent = v ? 'Pause' : 'Play'; if (v && k >= N-1) k = 0; last = performance.now(); }
function evJump(dir){ const t = D.frames[k].t; let target = null;
  if (dir > 0){ for (const e of D.events){ if (e.t > t){ target = e.t; break; } } }
  else { for (let n = D.events.length-1; n >= 0; n--){ if (D.events[n].t < t){ target = D.events[n].t; break; } } }
  if (target !== null){ jump(tIndex(target)); setPlay(false); } }

document.getElementById('bPlay').onclick = () => setPlay(!playing);
document.getElementById('bB1').onclick = () => { setPlay(false); jump(k-1); };
document.getElementById('bF1').onclick = () => { setPlay(false); jump(k+1); };
document.getElementById('bB10').onclick = () => jump(k - ten());
document.getElementById('bF10').onclick = () => jump(k + ten());
document.getElementById('bPE').onclick = () => evJump(-1);
document.getElementById('bNE').onclick = () => evJump(1);
document.getElementById('speed').onchange = e => { speed = parseFloat(e.target.value); draw(); };
const sl = document.getElementById('slider'); sl.max = N-1; sl.oninput = () => jump(parseInt(sl.value));
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'SELECT') return;
  const key = e.key;
  if (key === ' ' || key === 'k' || key === 'K'){ e.preventDefault(); setPlay(!playing); }
  else if (key === 'ArrowLeft'){ e.preventDefault(); e.shiftKey ? jump(k-ten()) : (setPlay(false), jump(k-1)); }
  else if (key === 'ArrowRight'){ e.preventDefault(); e.shiftKey ? jump(k+ten()) : (setPlay(false), jump(k+1)); }
  else if (key === 'j' || key === 'J') jump(k - ten());
  else if (key === 'l' || key === 'L') jump(k + ten());
  else if (key === '[') evJump(-1); else if (key === ']') evJump(1);
  else if (key === 'Home') jump(0); else if (key === 'End') jump(N-1);
});
cv.addEventListener('mousemove', e => { const r = cv.getBoundingClientRect(), x = Math.floor((e.clientX - r.left - M)/CS), y = Math.floor((e.clientY - r.top - M)/CS);
  const hv = document.getElementById('hover');
  if (x < 0 || y < 0 || x >= W || y >= H){ hoverCell = null; hv.textContent = 'Hover a cell to see what is in it.'; draw(); return; }
  hoverCell = [x, y]; const f = D.frames[k]; let s = 'Cell (' + x + ', ' + y + '): ';
  const ag = Object.keys(f.pos).filter(i => f.pos[i][0] === x && f.pos[i][1] === y);
  if (staticSet.has(x+','+y)) s += 'shelf (static obstacle)';
  else { const parts = []; if (f.blocks.some(c => c[0]===x && c[1]===y)) parts.push('BLOCKED (dynamic obstacle)');
    if (ag.length) parts.push('agent ' + ag.join(', ') + ' (' + f.status[ag[0]] + ')'); s += parts.length ? parts.join(' + ') : 'free'; }
  hv.textContent = s; draw(); });
cv.addEventListener('mouseleave', () => { hoverCell = null; draw(); });

function loop(now){ const dt = (now - last)/1000; last = now;
  if (playing){ acc += dt * FPS * speed; const n = Math.floor(acc); if (n > 0){ acc -= n; k += n; if (k >= N-1){ k = N-1; setPlay(false); } draw(); } }
  requestAnimationFrame(loop); }
draw(); requestAnimationFrame(loop);
</script></body></html>
"""


def export_html(sim, out="demo.html", fps=5, title="Multi-robot warehouse: disruption and plan repair"):
    """Write the interactive viewer for a simulation recorded with Config(record=True)."""
    if not sim.frames:
        raise ValueError("No frames recorded: run the simulation with Config(record=True)")
    data = prepare(sim)
    data["fps"] = fps
    html = (_TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))
            .replace("__TITLE__", title).replace("__TEN__", str(10 * fps)))
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
