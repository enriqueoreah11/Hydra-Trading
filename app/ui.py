"""Interfaz JARVIS: el cerebro Hydra con los agentes orbitando y conectados.

Pagina 100% autocontenida (HTML+CSS+JS inline). Los datos vienen por fetch a /agents.
"""

BRAIN_HTML = r"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>HYDRA · núcleo</title>
<style>
:root{
  --bg:#05070d; --panel:#0b1220cc; --line:#1b2b3a; --cyan:#22d3ee; --cyan2:#38bdf8;
  --active:#22d3ee; --idle:#3a4a5a; --off:#243040; --alert:#fb7185; --ok:#34d399;
  --text:#cbd5e1; --dim:#7c8ba1;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--text);
  font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace;overflow:hidden}
body{background:
  radial-gradient(1200px 800px at 50% 42%, #0c1a2e 0%, #070c16 55%, #04060b 100%);}
#grid{position:fixed;inset:0;pointer-events:none;opacity:.25;
  background-image:linear-gradient(#0e1c2e 1px,transparent 1px),linear-gradient(90deg,#0e1c2e 1px,transparent 1px);
  background-size:44px 44px;mask-image:radial-gradient(circle at 50% 45%,#000 30%,transparent 78%);}
#top{position:fixed;top:0;left:0;right:0;z-index:20;display:flex;align-items:center;gap:14px;
  padding:12px 18px;background:linear-gradient(#05070dcc,#05070d00);flex-wrap:wrap}
#top .brand{font-weight:700;letter-spacing:3px;font-size:20px;color:#e2f6ff;
  text-shadow:0 0 18px #22d3ee88}
.chip{font-size:11.5px;padding:4px 10px;border:1px solid var(--line);border-radius:99px;
  color:var(--dim);background:#0a1220aa;white-space:nowrap}
.chip b{color:#dbeafe}
.spacer{flex:1}
.btn{cursor:pointer;font-family:inherit;font-size:12px;letter-spacing:1px;color:#031018;
  background:linear-gradient(180deg,#4be3ff,#22d3ee);border:0;padding:8px 14px;border-radius:8px;
  font-weight:700;box-shadow:0 0 18px #22d3ee55}
.btn.ghost{background:#0b1220;color:#9fe6ff;border:1px solid #164a5f;box-shadow:none}
.btn:active{transform:translateY(1px)}
#stage{position:absolute;inset:0}
svg#links{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.link{stroke:#12303f;stroke-width:1.4;fill:none}
.link.active{stroke:url(#flow);stroke-width:2;stroke-dasharray:5 9;animation:flow 1s linear infinite}
.link.alert{stroke:#5b2330}
@keyframes flow{to{stroke-dashoffset:-28}}
#core{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);z-index:10;
  width:150px;height:150px;border-radius:50%;display:flex;flex-direction:column;
  align-items:center;justify-content:center;text-align:center;cursor:pointer;
  background:radial-gradient(circle at 50% 40%,#0b3a4d,#071a26 70%);
  border:1.5px solid #1fd8ff66;box-shadow:0 0 60px #22d3ee55,inset 0 0 40px #0891b255;
  animation:breathe 3.6s ease-in-out infinite}
#core.halted{border-color:#fb718588;box-shadow:0 0 60px #fb718555,inset 0 0 40px #7f1d1d55}
#core .t{font-weight:700;letter-spacing:4px;font-size:19px;color:#dffaff;text-shadow:0 0 14px #22d3ee}
#core .s{font-size:10px;color:#7fd9ee;margin-top:4px;letter-spacing:1px}
@keyframes breathe{0%,100%{box-shadow:0 0 55px #22d3ee44,inset 0 0 40px #0891b244}
  50%{box-shadow:0 0 85px #22d3ee88,inset 0 0 55px #0891b277}}
.ring{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);border-radius:50%;
  border:1px dashed #123143;pointer-events:none}
.node{position:absolute;transform:translate(-50%,-50%);z-index:11;width:96px;
  display:flex;flex-direction:column;align-items:center;cursor:pointer;user-select:none}
.node .orb{width:60px;height:60px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:26px;background:#0a1622;border:1.5px solid var(--idle);
  transition:.25s;position:relative}
.node .nm{margin-top:7px;font-size:11px;letter-spacing:.5px;color:#9fb2c8;text-align:center}
.node .dot{position:absolute;right:-2px;top:-2px;width:12px;height:12px;border-radius:50%;
  background:var(--idle);border:2px solid #05070d}
.node.active .orb{border-color:var(--active);box-shadow:0 0 24px #22d3ee88,inset 0 0 14px #22d3ee33}
.node.active .dot{background:var(--active);box-shadow:0 0 10px var(--active);animation:pulse 1.3s infinite}
.node.active .nm{color:#dbeafe}
.node.idle .orb{border-color:#2b6b83}
.node.idle .dot{background:#2b6b83}
.node.off{opacity:.42}
.node.off .dot{background:var(--off)}
.node.alert .orb{border-color:var(--alert);box-shadow:0 0 24px #fb718588}
.node.alert .dot{background:var(--alert);animation:pulse 1s infinite}
.node:hover .orb{transform:scale(1.08)}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.35);opacity:.7}}
.part{fill:#7ff0ff;filter:drop-shadow(0 0 5px #22d3ee)}
#drawer{position:fixed;top:0;right:0;height:100%;width:min(420px,92vw);z-index:30;
  background:linear-gradient(180deg,#081018f2,#05070df2);border-left:1px solid #143446;
  box-shadow:-20px 0 60px #000a;transform:translateX(105%);transition:.32s cubic-bezier(.2,.8,.2,1);
  display:flex;flex-direction:column}
#drawer.open{transform:none}
#drawer .hd{padding:18px;border-bottom:1px solid #12303f;display:flex;gap:12px;align-items:center}
#drawer .hd .e{font-size:34px}
#drawer .hd h2{margin:0;font-size:18px;color:#e6f7ff;letter-spacing:1px}
#drawer .hd .role{font-size:12px;color:var(--dim);margin-top:3px}
#drawer .x{margin-left:auto;cursor:pointer;color:#5f7387;font-size:22px;line-height:1}
#drawer .body{padding:16px 18px;overflow:auto;flex:1}
.badge{display:inline-block;font-size:11px;padding:3px 9px;border-radius:99px;border:1px solid #1e3a4a}
.badge.active{color:#031018;background:var(--active)}
.badge.idle{color:#9fe6ff;border-color:#2b6b83}
.badge.off{color:#8aa;background:#111a24}
.badge.alert{color:#fff;background:var(--alert)}
.feed{list-style:none;padding:0;margin:14px 0 0}
.feed li{border:1px solid #11293650;border-left:2px solid #22d3ee55;border-radius:8px;
  padding:9px 11px;margin-bottom:9px;background:#0a141e88}
.feed .k{color:#7ff0ff;font-size:11px;letter-spacing:.5px}
.feed .t{color:#5f7387;font-size:10.5px;float:right}
.feed .c{color:#a9bcd0;font-size:11.5px;margin-top:5px;white-space:pre-wrap;word-break:break-word;max-height:150px;overflow:auto}
.empty{color:#5f7387;font-size:12.5px;padding:10px 0}
#banner{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:25;
  background:#0b1b2af0;border:1px solid #1c4a5f;border-radius:12px;padding:12px 16px;
  max-width:min(720px,94vw);font-size:12.5px;color:#bfe6f5;box-shadow:0 10px 40px #000a}
#banner code{background:#04121b;padding:2px 7px;border-radius:6px;color:#7ff0ff;border:1px solid #12303f}
#banner a{color:#7ff0ff}
#toast{position:fixed;left:50%;top:64px;transform:translateX(-50%);z-index:40;
  background:#0b1b2af5;border:1px solid #1c4a5f;border-radius:10px;padding:10px 16px;
  color:#dffaff;font-size:12.5px;display:none}
</style></head>
<body>
<div id="grid"></div>
<div id="top">
  <span class="brand">◈ HYDRA</span>
  <span class="chip" id="c-mode">modo —</span>
  <span class="chip" id="c-env">entorno —</span>
  <span class="chip" id="c-conn">conexión —</span>
  <span class="chip" id="c-bal">balance —</span>
  <span class="chip" id="c-model">modelo —</span>
  <span class="chip" id="c-pb">playbook —</span>
  <span class="spacer"></span>
  <button class="btn" id="b-demo">▶ PROBAR DEMO</button>
  <button class="btn ghost" id="b-halt">⏸ HALT</button>
  <button class="btn ghost" id="b-refresh">⟳</button>
</div>

<div id="stage">
  <svg id="links"><defs>
    <linearGradient id="flow" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#0b6f8a"/><stop offset="1" stop-color="#5ff0ff"/>
    </linearGradient></defs>
  </svg>
  <div class="ring" id="ring1"></div>
  <div class="ring" id="ring2"></div>
  <div id="core" title="Núcleo Hydra">
    <div class="t">HYDRA</div><div class="s" id="core-s">cerebro</div>
  </div>
</div>

<div id="drawer">
  <div class="hd"><div class="e" id="d-e">🔍</div>
    <div><h2 id="d-name">Agente</h2><div class="role" id="d-role"></div></div>
    <div class="x" onclick="closeDrawer()">✕</div>
  </div>
  <div class="body" id="d-body"></div>
</div>

<div id="toast"></div>
<div id="banner" style="display:none"></div>

<script>
const $ = s => document.querySelector(s);
let DATA = null, NODES = {}, LINKS = [], PARTS = [], selected = null;

function fmtTime(ts){ if(!ts) return "—"; const d=new Date(ts*1000);
  return d.toLocaleString('es', {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}); }

async function load(){
  let d; try{ d = await (await fetch('/agents')).json(); }catch(e){ return; }
  DATA = d; renderCore(d.core); ensureNodes(d.agents); updateNodes(d.agents);
  layout(); banner(d.core);
  if(selected) renderDrawer(selected);
}

function renderCore(c){
  $('#c-mode').innerHTML = 'modo <b>'+(c.dry_run?'PAPEL':'REAL')+'</b>';
  $('#c-env').innerHTML = 'entorno <b>'+c.env+'</b>';
  $('#c-conn').innerHTML = c.connected ? 'conexión <b style="color:#34d399">viva</b>'
    : (c.oauth_ok ? 'conexión <b style="color:#fbbf24">esperando</b>' : 'conexión <b style="color:#fb7185">sin cTrader</b>');
  $('#c-bal').innerHTML = 'balance <b>'+(c.balance!=null?c.balance:'—')+'</b>';
  $('#c-model').innerHTML = 'modelo <b>'+c.model+'</b>';
  $('#c-pb').innerHTML = 'playbook <b>v'+c.playbook_version+'</b>';
  const core = $('#core'); core.classList.toggle('halted', c.halted);
  $('#core-s').textContent = c.halted ? 'DETENIDO' : (c.connected?'operando':'en espera');
  $('#b-halt').textContent = c.halted ? '▶ RESUME' : '⏸ HALT';
}

function ensureNodes(agents){
  if(Object.keys(NODES).length) return;
  const stage = $('#stage');
  agents.forEach(a => {
    const n = document.createElement('div');
    n.className = 'node'; n.dataset.key = a.key;
    n.innerHTML = '<div class="orb">'+a.emoji+'<span class="dot"></span></div><div class="nm">'+a.name+'</div>';
    n.onclick = () => openAgent(a.key);
    stage.appendChild(n); NODES[a.key] = n;
  });
}

function updateNodes(agents){
  agents.forEach(a => { const n = NODES[a.key]; if(!n) return;
    n.className = 'node ' + a.state; });
}

function layout(){
  if(!DATA) return;
  const stage = $('#stage'), W = stage.clientWidth, H = stage.clientHeight;
  const cx = W/2, cy = H/2, base = Math.min(W,H);
  const R1 = Math.max(120, base*0.24), R2 = Math.max(210, base*0.40);
  $('#ring1').style.width=$('#ring1').style.height=(R1*2)+'px';
  $('#ring2').style.width=$('#ring2').style.height=(R2*2)+'px';
  const inner = DATA.agents.filter(a=>a.ring==='core');
  const outer = DATA.agents.filter(a=>a.ring==='auto');
  const svg = $('#links'); svg.setAttribute('viewBox','0 0 '+W+' '+H);
  [...svg.querySelectorAll('.link')].forEach(l=>l.remove());
  LINKS = [];
  const place = (arr,R,off) => arr.forEach((a,i)=>{
    const ang = (-90 + off + i*(360/arr.length)) * Math.PI/180;
    const x = cx + R*Math.cos(ang), y = cy + R*Math.sin(ang);
    const n = NODES[a.key]; n.style.left = x+'px'; n.style.top = y+'px';
    const ln = document.createElementNS('http://www.w3.org/2000/svg','line');
    ln.setAttribute('x1',cx); ln.setAttribute('y1',cy);
    ln.setAttribute('x2',x); ln.setAttribute('y2',y);
    ln.setAttribute('class','link'+(a.state==='active'?' active':a.state==='alert'?' alert':''));
    svg.appendChild(ln);
    LINKS.push({key:a.key,x1:cx,y1:cy,x2:x,y2:y,active:a.state==='active'});
  });
  place(inner,R1,0); place(outer,R2,36);
  buildParticles();
}

// ---- partículas de "energía" viajando por las conexiones activas ----
function buildParticles(){
  const svg = $('#links');
  PARTS.forEach(p=>p.el.remove()); PARTS = [];
  LINKS.filter(l=>l.active).forEach(l=>{
    const c = document.createElementNS('http://www.w3.org/2000/svg','circle');
    c.setAttribute('r','3.2'); c.setAttribute('class','part'); svg.appendChild(c);
    PARTS.push({el:c, l, t:Math.random()});
  });
}
function tick(){
  PARTS.forEach(p=>{ p.t += 0.012; if(p.t>1) p.t -= 1;
    const x = p.l.x1 + (p.l.x2-p.l.x1)*p.t, y = p.l.y1 + (p.l.y2-p.l.y1)*p.t;
    p.el.setAttribute('cx',x); p.el.setAttribute('cy',y); });
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

// ---- panel lateral ----
function agentByKey(k){ return DATA ? DATA.agents.find(a=>a.key===k) : null; }
function openAgent(k){ selected = k; renderDrawer(k); $('#drawer').classList.add('open'); }
function closeDrawer(){ selected = null; $('#drawer').classList.remove('open'); }
function renderDrawer(k){
  const a = agentByKey(k); if(!a) return;
  $('#d-e').textContent = a.emoji; $('#d-name').textContent = a.name; $('#d-role').textContent = a.role;
  const estados = {active:'ACTIVO',idle:'EN ESPERA',off:'DESACTIVADO',alert:'ALERTA'};
  let h = '<span class="badge '+a.state+'">'+estados[a.state]+'</span>' +
          ' <span class="badge idle">última actividad: '+fmtTime(a.last_ts)+'</span>';
  h += '<ul class="feed">';
  if(!a.entries.length){ h += '</ul><div class="empty">Sin actividad registrada todavía. '+
      'Este agente escribirá aquí en cuanto el cerebro empiece a trabajar.</div>'; }
  else {
    a.entries.forEach(e=>{ h += '<li><span class="t">'+fmtTime(e.ts)+'</span>'+
      '<span class="k">'+e.kind+(e.symbol?' · '+e.symbol:'')+'</span>'+
      '<div class="c">'+prettify(e.content)+'</div></li>'; });
    h += '</ul>';
  }
  $('#d-body').innerHTML = h;
}
function prettify(s){
  try{ const o = JSON.parse(s); return escapeHtml(JSON.stringify(o,null,1)); }
  catch(_){ return escapeHtml(s); }
}
function escapeHtml(s){ return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

// ---- banner de estado / próximos pasos ----
function banner(c){
  const b = $('#banner'); let msg = '';
  if(!c.has_anthropic){
    msg = '🔑 Falta la API key para que los agentes piensen. En tu terminal: '+
          '<code>fly secrets set ANTHROPIC_API_KEY=sk-ant-...</code> y espera ~30s.';
  } else if(!c.oauth_ok){
    msg = '🔌 Cerebro listo, sin cuenta cTrader. Pulsa <b>▶ PROBAR DEMO</b> para ver a los agentes en acción, '+
          'o <a href="/oauth/login">conecta tu cuenta</a> para operar.';
  } else if(!c.connected){
    msg = '⏳ Autorizado, estableciendo conexión con cTrader…';
  }
  b.style.display = msg ? 'block' : 'none'; b.innerHTML = msg;
}

// ---- acciones ----
function toast(t){ const el=$('#toast'); el.textContent=t; el.style.display='block';
  clearTimeout(el._t); el._t=setTimeout(()=>el.style.display='none',3500); }

$('#b-refresh').onclick = load;
$('#b-halt').onclick = async () => {
  const halt = $('#b-halt').textContent.includes('HALT');
  await fetch(halt?'/halt':'/resume',{method:'POST'}); toast(halt?'Sistema DETENIDO':'Sistema reanudado'); load();
};
$('#core').onclick = () => { toast('HYDRA · '+ (DATA?DATA.agents.length:0) +' agentes conectados'); };
$('#b-demo').onclick = async () => {
  toast('Corriendo demo… el Analyst está leyendo el mercado');
  let r; try{ r = await fetch('/demo',{method:'POST'}); }catch(e){ toast('Error de red'); return; }
  if(!r.ok){ const t = await r.text();
    openInfo('▶ Modo demo', '<p style="color:#fb7185">No se pudo correr el demo.</p><p>'+
      escapeHtml(t)+'</p><p>Configura la key con:<br><code>fly secrets set ANTHROPIC_API_KEY=sk-ant-...</code></p>');
    return; }
  const data = await r.json(); renderDemo(data.results); load();
};
function openInfo(title, html){
  selected = null; $('#d-e').textContent='ℹ️'; $('#d-name').textContent=title; $('#d-role').textContent='';
  $('#d-body').innerHTML = html; $('#drawer').classList.add('open');
}
function renderDemo(results){
  let h = '<p class="role">Datos sintéticos (no es mercado real). Así lee el mercado el Analyst y así lo evaluaría el Risk Manager.</p>';
  results.forEach(r=>{ const p=r.proposal, m=r.market;
    const dir = p.action==='propose' ? (p.direction==='buy'?'🟢 COMPRA':'🔴 VENTA') : '⚪ SIN OPERACIÓN';
    h += '<li style="list-style:none;border:1px solid #12303f;border-radius:10px;padding:12px;margin:10px 0;background:#0a141e88">';
    h += '<b style="color:#7ff0ff">'+r.symbol+'</b> — '+dir+' <span style="color:#5f7387">(confianza '+(p.confidence||0)+')</span>';
    if(p.thesis) h += '<div class="c" style="margin-top:6px;color:#a9bcd0">'+escapeHtml(p.thesis)+'</div>';
    if(p.action==='propose') h += '<div style="color:#8aa;font-size:11px;margin-top:6px">entrada≈ '+p.last_close+' · SL '+p.stop_loss+' · TP '+p.take_profit+'</div>';
    if(r.risk_preview){ const rp=r.risk_preview;
      h += '<div style="margin-top:8px;font-size:11.5px;color:'+(rp.passes_deterministic?'#34d399':'#fb7185')+'">'+
           (rp.passes_deterministic?'✅ pasa filtros del Risk Manager':'❌ sería vetada')+' (R:R '+rp.risk_reward+')</div>'; }
    h += '<div style="color:#4a5a6a;font-size:10.5px;margin-top:6px">EMA20 '+m.ema20+' · EMA50 '+m.ema50+' · EMA200 '+m.ema200+' · RSI '+m.rsi14+'</div>';
    h += '</li>';
  });
  openInfo('▶ Resultado del demo', h);
}

window.addEventListener('resize', layout);
load(); setInterval(load, 5000);
</script>
</body></html>
"""
