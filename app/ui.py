"""Interfaz JARVIS (estilo Mark-XLVIII): reactor arc, HUD, agentes, VOZ + palabra mágica.

Pagina 100% autocontenida (HTML+CSS+JS inline). Datos por fetch a /agents.
Voz con la Web Speech API (reconocimiento es-ES + sintesis, voz masculina seleccionable),
palabra de activacion "Oye Hydra" y activacion por aplauso (Web Audio).
"""

BRAIN_HTML = r"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>HYDRA · núcleo</title>
<style>
:root{ --bg:#04070e; --cyan:#38e6ff; --active:#38e6ff; --idle:#2b6b83; --off:#26333f;
  --alert:#ff5d73; --text:#cfe8f2; --dim:#6f879a; }
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--text);
  font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace;overflow:hidden}
body{background:radial-gradient(1300px 900px at 50% 44%,#08192b 0%,#050c16 55%,#03060c 100%);}
#grid{position:fixed;inset:0;pointer-events:none;opacity:.22;
  background-image:linear-gradient(#0c2236 1px,transparent 1px),linear-gradient(90deg,#0c2236 1px,transparent 1px);
  background-size:46px 46px;mask-image:radial-gradient(circle at 50% 46%,#000 26%,transparent 76%);}
#scan{position:fixed;inset:0;pointer-events:none;z-index:2;opacity:.5;
  background:linear-gradient(#38e6ff00 0,#38e6ff00 49%,#38e6ff10 50%,#38e6ff00 51%);background-size:100% 6px;animation:scan 8s linear infinite}
@keyframes scan{to{background-position:0 100vh}}
.corner{position:fixed;width:34px;height:34px;border:2px solid #1c586b;z-index:3;pointer-events:none}
.corner.tl{top:14px;left:14px;border-right:0;border-bottom:0}.corner.tr{top:14px;right:14px;border-left:0;border-bottom:0}
.corner.bl{bottom:14px;left:14px;border-right:0;border-top:0}.corner.br{bottom:14px;right:14px;border-left:0;border-top:0}
#top{position:fixed;top:0;left:0;right:0;z-index:20;display:flex;align-items:center;gap:12px;padding:14px 22px;flex-wrap:wrap}
#top .brand{font-weight:800;letter-spacing:5px;font-size:22px;color:#dffaff;text-shadow:0 0 22px #38e6ff}
.chip{font-size:11px;padding:4px 10px;border:1px solid #143a49;border-radius:99px;color:var(--dim);background:#07131fbb;white-space:nowrap}
.chip b{color:#dbeafe}
.spacer{flex:1}
.btn{cursor:pointer;font-family:inherit;font-size:11.5px;letter-spacing:1px;color:#02141b;
  background:linear-gradient(180deg,#66f0ff,#22d3ee);border:0;padding:8px 13px;border-radius:8px;font-weight:800;box-shadow:0 0 16px #22d3ee66}
.btn.ghost{background:#08131d;color:#9fe6ff;border:1px solid #164a5f;box-shadow:none}
.btn:active{transform:translateY(1px)}
#stage{position:absolute;inset:0;z-index:5}
svg#links{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.link{stroke:#123645;stroke-width:1.3;fill:none}
.link.active{stroke:url(#flow);stroke-width:2;stroke-dasharray:5 9;animation:flow 1s linear infinite}
.link.alert{stroke:#5b2330}
@keyframes flow{to{stroke-dashoffset:-28}}

/* -------- REACTOR ARC -------- */
#core{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);z-index:10;
  width:230px;height:230px;border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center}
#core .listen{position:absolute;width:230px;height:230px;border-radius:50%;border:2px solid #38e6ff00;pointer-events:none}
#core.hearing .listen{border-color:#38e6ff;animation:hear 1.1s ease-out infinite}
@keyframes hear{0%{transform:scale(.8);opacity:.9}100%{transform:scale(1.25);opacity:0}}
.rcore{position:absolute;width:86px;height:86px;border-radius:50%;z-index:5;
  background:radial-gradient(circle at 50% 42%,#eaffff,#5ff0ff 40%,#0b7f99 75%,#053745);
  box-shadow:0 0 46px #38e6ff,0 0 100px #22d3ee88,inset 0 0 24px #ffffff88;animation:rpulse 2.6s ease-in-out infinite}
.rtxt{position:absolute;z-index:6;text-align:center;pointer-events:none}
.rtxt .t{font-weight:800;letter-spacing:3px;font-size:17px;color:#04222b;text-shadow:0 0 8px #fff}
.rtxt .s{font-size:9px;color:#053745;letter-spacing:1px;margin-top:1px;font-weight:700}
.rring{position:absolute;border-radius:50%;border:2px solid #0e5a6e}
.ra{width:132px;height:132px;border:2px solid #1fb6d4aa;border-top-color:#eaffff;animation:spin 6s linear infinite}
.rb{width:168px;height:168px;border:1.5px dashed #17849b88;animation:spin 15s linear infinite reverse}
.rc{width:206px;height:206px;border:2px solid #0e5a6e;border-left-color:#38e6ff;border-right-color:#38e6ff;animation:spin 9s linear infinite}
.rd{width:228px;height:228px;background:conic-gradient(from 0deg,#38e6ff00 0 10deg,#38e6ff2e 10deg 15deg,#38e6ff00 15deg 30deg);
  border:0;animation:spin 26s linear infinite;mix-blend-mode:screen}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes rpulse{0%,100%{box-shadow:0 0 38px #38e6ff,0 0 80px #22d3ee66,inset 0 0 22px #fff8}50%{box-shadow:0 0 66px #7ff6ff,0 0 130px #22d3eeaa,inset 0 0 30px #fff}}
#core.halted .rcore{background:radial-gradient(circle at 50% 42%,#fff0f2,#ff8a9a 40%,#b23048 75%,#5a1622);box-shadow:0 0 46px #ff5d73,0 0 100px #ff5d7388,inset 0 0 24px #fff8}
#core.halted .ra{border-top-color:#ffd6dc;border-color:#b23048aa}#core.halted .rc{border-left-color:#ff5d73;border-right-color:#ff5d73}

.ring{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);border-radius:50%;border:1px dashed #0f2c3b;pointer-events:none}
.node{position:absolute;transform:translate(-50%,-50%);z-index:11;width:96px;display:flex;flex-direction:column;align-items:center;cursor:pointer;user-select:none}
.node .orb{width:60px;height:60px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:26px;background:#07141f;border:1.5px solid var(--idle);transition:.25s;position:relative}
.node .nm{margin-top:7px;font-size:11px;letter-spacing:.5px;color:#93aabf;text-align:center}
.node .dot{position:absolute;right:-2px;top:-2px;width:12px;height:12px;border-radius:50%;background:var(--idle);border:2px solid #04070e}
.node.active .orb{border-color:var(--active);box-shadow:0 0 26px #38e6ff99,inset 0 0 14px #38e6ff33}
.node.active .dot{background:var(--active);box-shadow:0 0 10px var(--active);animation:pulse 1.3s infinite}
.node.active .nm{color:#dbeafe}
.node.idle .orb{border-color:#2b6b83}.node.idle .dot{background:#2b6b83}
.node.off{opacity:.4}.node.off .dot{background:var(--off)}
.node.alert .orb{border-color:var(--alert);box-shadow:0 0 26px #ff5d7399}.node.alert .dot{background:var(--alert);animation:pulse 1s infinite}
.node:hover .orb{transform:scale(1.09)}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.35);opacity:.7}}
.part{fill:#8ff6ff;filter:drop-shadow(0 0 5px #38e6ff)}

/* -------- VOZ -------- */
#voice{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);z-index:26;display:flex;align-items:center;gap:10px;
  background:#06131fe8;border:1px solid #17495d;border-radius:99px;padding:8px 12px 8px 8px;box-shadow:0 10px 40px #000a;max-width:96vw;flex-wrap:wrap;justify-content:center}
#mic{width:46px;height:46px;border-radius:50%;border:0;cursor:pointer;font-size:20px;background:radial-gradient(circle at 50% 40%,#66f0ff,#1596b3);color:#022;box-shadow:0 0 18px #38e6ff88}
#mic.on{animation:mic 1.1s ease-in-out infinite}
@keyframes mic{0%,100%{box-shadow:0 0 14px #38e6ff88}50%{box-shadow:0 0 30px #38e6ff,0 0 50px #38e6ff66}}
#vtext{font-size:12px;color:#bfe6f5;min-width:150px;max-width:40vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#vtext b{color:#7ff6ff}
.vtoggle{cursor:pointer;font-size:11px;color:#7fbfd0;border:1px solid #17495d;border-radius:99px;padding:5px 9px;white-space:nowrap}
.vtoggle.on{color:#02141b;background:#38e6ff;border-color:#38e6ff}
#v-voice{background:#08131d;color:#9fe6ff;border:1px solid #17495d;border-radius:99px;padding:5px 8px;font-family:inherit;font-size:11px;max-width:150px}

/* -------- BOOT -------- */
#boot{position:fixed;inset:0;z-index:60;background:radial-gradient(900px 700px at 50% 45%,#08202f,#03060c 70%);
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:22px;transition:opacity .7s}
#boot.hide{opacity:0;pointer-events:none}
#boot .bt{font-weight:800;letter-spacing:10px;font-size:44px;color:#dffaff;text-shadow:0 0 30px #38e6ff}
#boot .bs{color:#7fd9ee;letter-spacing:3px;font-size:12px}
#boot .bcore{width:120px;height:120px;border-radius:50%;background:radial-gradient(circle at 50% 42%,#eaffff,#5ff0ff 45%,#0b7f99 78%,#053745);
  box-shadow:0 0 50px #38e6ff,0 0 110px #22d3ee88;animation:rpulse 1.6s ease-in-out infinite;position:relative}
#boot .bring{position:absolute;inset:-18px;border-radius:50%;border:2px solid #0e5a6e;border-top-color:#eaffff;animation:spin 3s linear infinite}
#activate{cursor:pointer;font-family:inherit;font-weight:800;letter-spacing:2px;font-size:15px;color:#02141b;
  background:linear-gradient(180deg,#7ff6ff,#22d3ee);border:0;padding:14px 30px;border-radius:12px;box-shadow:0 0 30px #38e6ff88}
#activate:active{transform:translateY(1px)}

/* -------- DRAWER -------- */
#drawer{position:fixed;top:0;right:0;height:100%;width:min(440px,94vw);z-index:30;background:linear-gradient(180deg,#06121cf5,#04080ef5);
  border-left:1px solid #12414f;box-shadow:-20px 0 60px #000b;transform:translateX(105%);transition:.32s cubic-bezier(.2,.8,.2,1);display:flex;flex-direction:column}
#drawer.open{transform:none}
#drawer .hd{padding:18px;border-bottom:1px solid #103040;display:flex;gap:12px;align-items:center}
#drawer .hd .e{font-size:34px}#drawer .hd h2{margin:0;font-size:18px;color:#e6f7ff;letter-spacing:1px}
#drawer .hd .role{font-size:12px;color:var(--dim);margin-top:3px}
#drawer .x{margin-left:auto;cursor:pointer;color:#5f7387;font-size:22px;line-height:1}
#drawer .body{padding:16px 18px;overflow:auto;flex:1}
#drawer iframe{width:100%;height:100%;border:0;border-radius:8px;background:#fff}
.badge{display:inline-block;font-size:11px;padding:3px 9px;border-radius:99px;border:1px solid #1e3a4a;margin:0 4px 6px 0}
.badge.active{color:#02141b;background:var(--active)}.badge.idle{color:#9fe6ff;border-color:#2b6b83}
.badge.off{color:#8aa;background:#111a24}.badge.alert{color:#fff;background:var(--alert)}
.feed{list-style:none;padding:0;margin:12px 0 0}
.feed li{border:1px solid #10293650;border-left:2px solid #38e6ff55;border-radius:8px;padding:9px 11px;margin-bottom:9px;background:#08131e88}
.feed .k{color:#7ff6ff;font-size:11px}.feed .t{color:#5f7387;font-size:10.5px;float:right}
.feed .c{color:#a9bcd0;font-size:11.5px;margin-top:5px;white-space:pre-wrap;word-break:break-word;max-height:150px;overflow:auto}
.empty{color:#5f7387;font-size:12.5px;padding:10px 0}
#banner{position:fixed;left:50%;bottom:78px;transform:translateX(-50%);z-index:25;background:#08192af0;border:1px solid #1a4a5f;border-radius:12px;padding:11px 16px;max-width:min(720px,94vw);font-size:12.5px;color:#bfe6f5;box-shadow:0 10px 40px #000a}
#banner code{background:#03121b;padding:2px 7px;border-radius:6px;color:#7ff6ff;border:1px solid #12303f}
#banner a{color:#7ff6ff}
#toast{position:fixed;left:50%;top:66px;transform:translateX(-50%);z-index:40;background:#08192af5;border:1px solid #1a4a5f;border-radius:10px;padding:10px 16px;color:#dffaff;font-size:12.5px;display:none}
#wave{position:fixed;left:0;right:0;bottom:0;height:120px;width:100%;z-index:4;pointer-events:none;opacity:.9}
</style></head>
<body>
<div id="grid"></div><div id="scan"></div><canvas id="wave"></canvas>
<div class="corner tl"></div><div class="corner tr"></div><div class="corner bl"></div><div class="corner br"></div>

<div id="boot">
  <div class="bcore"><div class="bring"></div></div>
  <div class="bt">HYDRA</div>
  <div class="bs">NÚCLEO NEURAL · 11 AGENTES</div>
  <button id="activate">⏻ ACTIVAR SISTEMA</button>
  <div class="bs" style="opacity:.6">pulsa para encender voz y micrófono</div>
</div>

<div id="top">
  <span class="brand">◈ HYDRA</span>
  <span class="chip" id="c-mode">modo —</span>
  <span class="chip" id="c-conn">conexión —</span>
  <span class="chip" id="c-bal">balance —</span>
  <span class="chip" id="c-pb">playbook —</span>
  <span class="spacer"></span>
  <button class="btn" id="b-demo">▶ DEMO</button>
  <button class="btn ghost" id="b-cal">📅 CALENDARIO</button>
  <button class="btn ghost" id="b-halt">⏸ HALT</button>
  <button class="btn ghost" id="b-refresh">⟳</button>
</div>

<div id="stage">
  <svg id="links"><defs><linearGradient id="flow" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#0b6f8a"/><stop offset="1" stop-color="#7ff6ff"/></linearGradient></defs></svg>
  <div class="ring" id="ring1"></div><div class="ring" id="ring2"></div>
  <div id="core" title="Núcleo Hydra">
    <div class="listen"></div>
    <div class="rring rd"></div><div class="rring rc"></div><div class="rring rb"></div><div class="rring ra"></div>
    <div class="rcore"></div>
    <div class="rtxt"><div class="t">HYDRA</div><div class="s" id="core-s">cerebro</div></div>
  </div>
</div>

<div id="voice">
  <button id="mic" title="Hablar">🎙️</button>
  <div id="vtext">Di <b>“Oye Hydra…”</b></div>
  <span class="vtoggle on" id="v-wake" title="Palabra mágica">👂 oye hydra</span>
  <span class="vtoggle" id="v-clap" title="Activar con aplauso">👏 aplauso</span>
  <span class="vtoggle on" id="v-speak" title="Voz de respuesta">🔊 voz</span>
  <select id="v-voice" title="Elegir voz"></select>
</div>

<div id="drawer">
  <div class="hd"><div class="e" id="d-e">🔍</div>
    <div><h2 id="d-name">Agente</h2><div class="role" id="d-role"></div></div>
    <div class="x" onclick="closeDrawer()">✕</div></div>
  <div class="body" id="d-body"></div>
</div>

<div id="toast"></div><div id="banner" style="display:none"></div>

<script>
const $=s=>document.querySelector(s);
let DATA=null,NODES={},LINKS=[],PARTS=[],selected=null;
const norm=s=>(s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');
function fmtTime(ts){ if(!ts)return"—"; const d=new Date(ts*1000);
  return d.toLocaleString('es',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}); }

async function load(){ let d; try{ d=await (await fetch('/agents')).json(); }catch(e){ return; }
  DATA=d; renderCore(d.core); ensureNodes(d.agents); updateNodes(d.agents); layout(); banner(d.core);
  if(selected) renderDrawer(selected); }
function renderCore(c){
  $('#c-mode').innerHTML='modo <b>'+(c.dry_run?'PAPEL':'REAL')+'</b>';
  $('#c-conn').innerHTML=c.connected?'conexión <b style="color:#34d399">viva</b>':(c.oauth_ok?'conexión <b style="color:#fbbf24">esperando</b>':'conexión <b style="color:#ff5d73">sin cTrader</b>');
  $('#c-bal').innerHTML='balance <b>'+(c.balance!=null?c.balance:'—')+'</b>';
  $('#c-pb').innerHTML='playbook <b>v'+c.playbook_version+'</b>';
  $('#core').classList.toggle('halted',c.halted);
  $('#core-s').textContent=c.halted?'DETENIDO':(c.connected?'operando':'en espera');
  $('#b-halt').textContent=c.halted?'▶ RESUME':'⏸ HALT';
  $('#b-cal').style.display=c.calendar_embed_url?'':'none';
  if(c.voice_enabled===false)$('#voice').style.display='none';
}
function ensureNodes(a){ if(Object.keys(NODES).length)return; const st=$('#stage');
  a.forEach(x=>{ const n=document.createElement('div'); n.className='node'; n.dataset.key=x.key;
    n.innerHTML='<div class="orb">'+x.emoji+'<span class="dot"></span></div><div class="nm">'+x.name+'</div>';
    n.onclick=()=>openAgent(x.key); st.appendChild(n); NODES[x.key]=n; }); }
function updateNodes(a){ a.forEach(x=>{ const n=NODES[x.key]; if(n)n.className='node '+x.state; }); }
function layout(){ if(!DATA)return; const st=$('#stage'),W=st.clientWidth,H=st.clientHeight,cx=W/2,cy=H/2,base=Math.min(W,H);
  const R1=Math.max(150,base*0.27),R2=Math.max(240,base*0.43);
  $('#ring1').style.width=$('#ring1').style.height=(R1*2)+'px'; $('#ring2').style.width=$('#ring2').style.height=(R2*2)+'px';
  const inner=DATA.agents.filter(a=>a.ring==='core'),outer=DATA.agents.filter(a=>a.ring==='auto');
  const svg=$('#links'); svg.setAttribute('viewBox','0 0 '+W+' '+H); [...svg.querySelectorAll('.link')].forEach(l=>l.remove()); LINKS=[];
  const place=(arr,R,off)=>arr.forEach((a,i)=>{ const ang=(-90+off+i*(360/arr.length))*Math.PI/180,x=cx+R*Math.cos(ang),y=cy+R*Math.sin(ang);
    const n=NODES[a.key]; n.style.left=x+'px'; n.style.top=y+'px';
    const ln=document.createElementNS('http://www.w3.org/2000/svg','line');
    ln.setAttribute('x1',cx);ln.setAttribute('y1',cy);ln.setAttribute('x2',x);ln.setAttribute('y2',y);
    ln.setAttribute('class','link'+(a.state==='active'?' active':a.state==='alert'?' alert':'')); svg.appendChild(ln);
    LINKS.push({x1:cx,y1:cy,x2:x,y2:y,active:a.state==='active'}); });
  place(inner,R1,0); place(outer,R2,36); buildParticles(); }
function buildParticles(){ const svg=$('#links'); PARTS.forEach(p=>p.el.remove()); PARTS=[];
  LINKS.filter(l=>l.active).forEach(l=>{ const c=document.createElementNS('http://www.w3.org/2000/svg','circle');
    c.setAttribute('r','3.2'); c.setAttribute('class','part'); svg.appendChild(c); PARTS.push({el:c,l,t:Math.random()}); }); }
function tick(){ PARTS.forEach(p=>{ p.t+=0.012; if(p.t>1)p.t-=1;
    p.el.setAttribute('cx',p.l.x1+(p.l.x2-p.l.x1)*p.t); p.el.setAttribute('cy',p.l.y1+(p.l.y2-p.l.y1)*p.t); }); requestAnimationFrame(tick); }
requestAnimationFrame(tick);

function agentByKey(k){ return DATA?DATA.agents.find(a=>a.key===k):null; }
function openAgent(k){ selected=k; renderDrawer(k); $('#drawer').classList.add('open'); }
function closeDrawer(){ selected=null; $('#drawer').classList.remove('open'); }
function renderDrawer(k){ const a=agentByKey(k); if(!a)return;
  $('#d-e').textContent=a.emoji; $('#d-name').textContent=a.name; $('#d-role').textContent=a.role;
  const est={active:'ACTIVO',idle:'EN ESPERA',off:'DESACTIVADO',alert:'ALERTA'};
  let h='<span class="badge '+a.state+'">'+est[a.state]+'</span><span class="badge idle">última: '+fmtTime(a.last_ts)+'</span><ul class="feed">';
  if(!a.entries.length) h+='</ul><div class="empty">Sin actividad todavía. Escribirá aquí cuando el cerebro trabaje.</div>';
  else{ a.entries.forEach(e=>{ h+='<li><span class="t">'+fmtTime(e.ts)+'</span><span class="k">'+e.kind+(e.symbol?' · '+e.symbol:'')+'</span><div class="c">'+prettify(e.content)+'</div></li>'; }); h+='</ul>'; }
  $('#d-body').innerHTML=h; }
function prettify(s){ try{ return escapeHtml(JSON.stringify(JSON.parse(s),null,1)); }catch(_){ return escapeHtml(s);} }
function escapeHtml(s){ return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function banner(c){ const b=$('#banner'); let m='';
  if(!c.has_anthropic) m='🔑 Falta la key para que los agentes piensen: <code>fly secrets set ANTHROPIC_API_KEY=sk-ant-...</code>';
  else if(!c.oauth_ok) m='🔌 Cerebro listo, sin cuenta. Di <b>“Oye Hydra, corre el demo”</b> o pulsa ▶ DEMO. Para operar, <a href="/oauth/login">conecta cTrader</a>.';
  else if(!c.connected) m='⏳ Autorizado, conectando con cTrader…';
  b.style.display=m?'block':'none'; b.innerHTML=m; }
function toast(t){ const el=$('#toast'); el.textContent=t; el.style.display='block'; clearTimeout(el._t); el._t=setTimeout(()=>el.style.display='none',3800); }

$('#b-refresh').onclick=load; $('#b-halt').onclick=doHalt; $('#b-demo').onclick=runDemo; $('#b-cal').onclick=openCalendar;
$('#core').onclick=()=>{ const n=DATA?DATA.agents.filter(a=>a.state==='active').length:0; toast('HYDRA · '+(DATA?DATA.agents.length:0)+' agentes · '+n+' activos'); speak('Núcleo Hydra en línea. '+n+' agentes activos.'); };
async function doHalt(){ const halt=$('#b-halt').textContent.includes('HALT'); await fetch(halt?'/halt':'/resume',{method:'POST'}); toast(halt?'Sistema DETENIDO':'Sistema reanudado'); speak(halt?'Sistema detenido.':'Sistema reanudado.'); load(); }
function openCalendar(){ if(!DATA||!DATA.core.calendar_embed_url){ toast('Configura CALENDAR_EMBED_URL'); return; }
  $('#d-e').textContent='📅'; $('#d-name').textContent='Calendario'; $('#d-role').textContent='Fuente externa'; $('#d-body').innerHTML='<iframe src="'+DATA.core.calendar_embed_url+'"></iframe>'; selected=null; $('#drawer').classList.add('open'); }
async function runDemo(){ toast('Corriendo demo…'); speak('Ejecutando análisis de demostración.');
  let r; try{ r=await fetch('/demo',{method:'POST'}); }catch(e){ toast('Error de red'); return; }
  if(!r.ok){ const t=await r.text(); openInfo('▶ Modo demo','<p style="color:#ff5d73">No se pudo correr el demo.</p><p>'+escapeHtml(t)+'</p><p>Configura la key: <code>fly secrets set ANTHROPIC_API_KEY=sk-ant-...</code></p>'); speak('No pude correr el demo. Falta la clave de Anthropic.'); return; }
  const data=await r.json(); renderDemo(data.results); load();
  const props=data.results.filter(x=>x.proposal.action==='propose').length; speak('Análisis completo. '+props+' de '+data.results.length+' símbolos con oportunidad.'); }
function openInfo(t,h){ selected=null; $('#d-e').textContent='ℹ️'; $('#d-name').textContent=t; $('#d-role').textContent=''; $('#d-body').innerHTML=h; $('#drawer').classList.add('open'); }
function renderDemo(results){ let h='<p class="role">Datos sintéticos (no es mercado real). Así lee el mercado el Analyst.</p>';
  results.forEach(r=>{ const p=r.proposal,m=r.market; const dir=p.action==='propose'?(p.direction==='buy'?'🟢 COMPRA':'🔴 VENTA'):'⚪ SIN OPERACIÓN';
    h+='<li style="list-style:none;border:1px solid #12303f;border-radius:10px;padding:12px;margin:10px 0;background:#08131e88"><b style="color:#7ff6ff">'+r.symbol+'</b> — '+dir+' <span style="color:#5f7387">(confianza '+(p.confidence||0)+')</span>';
    if(p.thesis)h+='<div class="c" style="margin-top:6px;color:#a9bcd0">'+escapeHtml(p.thesis)+'</div>';
    if(p.action==='propose')h+='<div style="color:#8aa;font-size:11px;margin-top:6px">entrada≈ '+p.last_close+' · SL '+p.stop_loss+' · TP '+p.take_profit+'</div>';
    if(r.risk_preview){ const rp=r.risk_preview; h+='<div style="margin-top:8px;font-size:11.5px;color:'+(rp.passes_deterministic?'#34d399':'#ff5d73')+'">'+(rp.passes_deterministic?'✅ pasa filtros del Risk Manager':'❌ sería vetada')+' (R:R '+rp.risk_reward+')</div>'; } h+='</li>'; });
  openInfo('▶ Resultado del demo',h); }

/* ===================== VOZ (masculina) + PALABRA MÁGICA + APLAUSO ===================== */
let esVoices=[], esVoice=null, speakOn=true;
const MALE_PRIORITY=['jorge','juan','diego','carlos','enrique','miguel','pablo','álvaro','alvaro','google español de estados unidos','google español'];
function loadVoices(){ if(!('speechSynthesis'in window))return; esVoices=speechSynthesis.getVoices().filter(v=>/es(-|_)/i.test(v.lang));
  if(!esVoice){ for(const nm of MALE_PRIORITY){ const v=esVoices.find(v=>v.name.toLowerCase().includes(nm)); if(v){esVoice=v;break;} } if(!esVoice)esVoice=esVoices[0]||null; }
  const sel=$('#v-voice'); sel.innerHTML=''; esVoices.forEach((v,i)=>{ const o=document.createElement('option'); o.value=i; o.textContent=v.name.replace(/Microsoft|Online|\(Natural\)/gi,'').trim()+' · '+v.lang; if(esVoice&&v.name===esVoice.name)o.selected=true; sel.appendChild(o); });
  if(!esVoices.length){ const o=document.createElement('option'); o.textContent='(sin voces)'; sel.appendChild(o); } }
if('speechSynthesis'in window){ loadVoices(); speechSynthesis.onvoiceschanged=loadVoices; }
$('#v-voice').onchange=e=>{ esVoice=esVoices[+e.target.value]||esVoice; speak('Hola. Soy Hydra, tu asistente.'); };
$('#v-speak').onclick=()=>{ speakOn=!speakOn; $('#v-speak').classList.toggle('on',speakOn); if(speakOn)speak('Voz activada.'); };
let speaking=false, listeningActive=false, waveLevel=0.12;
function speak(t){ if(!speakOn||!('speechSynthesis'in window))return; try{ speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(t); u.lang=(esVoice&&esVoice.lang)||'es-ES'; u.rate=0.98; u.pitch=0.8; if(esVoice)u.voice=esVoice;
  u.onstart=()=>{speaking=true;}; u.onend=()=>{speaking=false;}; u.onerror=()=>{speaking=false;}; speechSynthesis.speak(u); }catch(_){}}

/* ---- onda de audio estilo JARVIS ---- */
const wv=$('#wave'), wctx=wv.getContext('2d'); let wt=0;
function wsize(){ wv.width=window.innerWidth*devicePixelRatio; wv.height=120*devicePixelRatio; wctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0); }
wsize(); window.addEventListener('resize',wsize);
function drawWave(){ const W=window.innerWidth,H=120; wctx.clearRect(0,0,W,H);
  const target=speaking?1.0:(listeningActive?0.62:0.12); waveLevel+=(target-waveLevel)*0.08; wt+=0.055;
  for(let pass=0;pass<2;pass++){ wctx.beginPath();
    for(let x=0;x<=W;x+=6){ const cen=1-Math.abs(x/W-0.5)*1.6; const env=Math.max(0,cen);
      const a=(14+70*waveLevel)*env*(pass?0.55:1);
      const y=H*0.62 + Math.sin(x*0.022 + wt*(pass?1.7:1) )*a*Math.sin(wt*0.7+x*0.005);
      x===0?wctx.moveTo(x,y):wctx.lineTo(x,y); }
    wctx.strokeStyle=pass? 'rgba(56,230,255,.30)':'rgba(120,246,255,.85)'; wctx.lineWidth=pass?4:2;
    wctx.shadowColor='#38e6ff'; wctx.shadowBlur=pass?18:10; wctx.stroke(); }
  requestAnimationFrame(drawWave); }
requestAnimationFrame(drawWave);

// reconocimiento
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
let recog=null,running=false,wakeMode=true,awaiting=false,awaitTimer=null;
const WAKE=['oye hydra','hola hydra','hey hydra','oye idra','oye hidra','hydra','hidra','jarvis'];
function setV(t){ $('#vtext').innerHTML=t; }
function coreHear(on){ listeningActive=on; $('#core').classList.toggle('hearing',on); $('#mic').classList.toggle('on',on); }
if(!SR){ setV('Voz no soportada — usa Chrome. Los botones sí funcionan.'); }
else{ recog=new SR(); recog.lang='es-ES'; recog.interimResults=true; recog.continuous=true;
  recog.onresult=e=>{ let interim=''; for(let i=e.resultIndex;i<e.results.length;i++){ const r=e.results[i];
      if(r.isFinal) handlePhrase(norm(r[0].transcript)); else interim+=r[0].transcript; }
    if(interim) setV('“'+interim+'”'); };
  recog.onerror=e=>{ if(e.error==='not-allowed') setV('Permiso de micrófono denegado.'); };
  recog.onend=()=>{ running=false; coreHear(false); if(wakeMode||awaiting){ setTimeout(startRecog,300); } else setV('Di <b>“Oye Hydra…”</b>'); };
}
function startRecog(){ if(!recog||running)return; try{ recog.start(); running=true; coreHear(true); }catch(_){}}
function handlePhrase(t){
  if(awaiting){ clearTimeout(awaitTimer); awaiting=false; wakeFlash(); runCmd(t); return; }
  const w=WAKE.find(w=>t.includes(w));
  if(!w) return; // en modo palabra mágica ignoramos lo que no la contenga
  wakeFlash(); const rest=t.slice(t.indexOf(w)+w.length).trim();
  if(rest.length>2){ runCmd(rest); }
  else{ speak('A la orden, señor.'); setV('<b>Le escucho…</b>'); awaiting=true; awaitTimer=setTimeout(()=>{awaiting=false;setV('Di <b>“Oye Hydra…”</b>');},9000); }
}
function wakeFlash(){ $('#core').classList.add('hearing'); }
$('#mic').onclick=()=>{ if(!SR){toast('Usa Chrome para la voz');return;} awaiting=true; setV('<b>Le escucho…</b>'); speak('Dígame, señor.'); if(!running)startRecog(); };
$('#v-wake').onclick=()=>{ wakeMode=!wakeMode; $('#v-wake').classList.toggle('on',wakeMode);
  if(wakeMode){ toast('Palabra mágica activada'); startRecog(); } else { toast('Palabra mágica apagada'); if(recog&&running)recog.stop(); } };

// aplauso (Web Audio)
let clapOn=false,clapStream=null,clapRAF=null,clapTimes=[];
$('#v-clap').onclick=async()=>{ if(clapOn){ stopClap(); } else { await startClap(); } };
async function startClap(){ try{ clapStream=await navigator.mediaDevices.getUserMedia({audio:true});
    const ctx=new (window.AudioContext||window.webkitAudioContext)(); const src=ctx.createMediaStreamSource(clapStream);
    const an=ctx.createAnalyser(); an.fftSize=1024; src.connect(an); const buf=new Uint8Array(an.fftSize);
    clapOn=true; $('#v-clap').classList.add('on'); toast('Aplauso activado: aplaude 2 veces');
    const loop=()=>{ if(!clapOn)return; an.getByteTimeDomainData(buf); let peak=0; for(let i=0;i<buf.length;i++){ const v=Math.abs(buf[i]-128)/128; if(v>peak)peak=v; }
      const now=performance.now(); if(peak>0.42 && (!clapTimes.length||now-clapTimes[clapTimes.length-1]>180)){ clapTimes.push(now); clapTimes=clapTimes.filter(t=>now-t<1000); if(clapTimes.length>=2){ clapTimes=[]; onClap(); } }
      clapRAF=requestAnimationFrame(loop); }; loop();
  }catch(e){ toast('No pude usar el micrófono para aplauso'); } }
function stopClap(){ clapOn=false; $('#v-clap').classList.remove('on'); if(clapRAF)cancelAnimationFrame(clapRAF); if(clapStream)clapStream.getTracks().forEach(t=>t.stop()); }
function onClap(){ wakeFlash(); speak('Te escucho.'); setV('<b>Te escucho…</b>'); awaiting=true; if(!running)startRecog(); clearTimeout(awaitTimer); awaitTimer=setTimeout(()=>{awaiting=false;},9000); }

// comandos
const AGENT_WORDS=[{k:'analyst',w:['analista','analisis']},{k:'risk_manager',w:['riesgo','gestor']},{k:'executor',w:['ejecutor','ordenes']},{k:'overnight',w:['nocturno','noche']},{k:'reviewer',w:['revisor','revision']},{k:'architect',w:['arquitecto','playbook']},{k:'sentinel',w:['sentinel','noticias','calendario','centinela']},{k:'watchdog',w:['watchdog','vigilante','salud']},{k:'auditor',w:['auditor','auditoria']},{k:'validator',w:['validador','backtest']},{k:'portfolio',w:['portafolio','cartera','correlacion']}];
function runCmd(t){
  if(/(demo|prueba|analiza|corre)/.test(t)){ runDemo(); return; }
  if(/(deten|para|alto|halt|pausa)/.test(t)){ if($('#b-halt').textContent.includes('HALT'))doHalt(); else speak('Ya está detenido.'); return; }
  if(/(reanuda|continua|resume|activa el sistema)/.test(t)){ if($('#b-halt').textContent.includes('RESUME'))doHalt(); else speak('Ya está activo.'); return; }
  if(/(estado|reporte|situacion|resumen|status|como vas)/.test(t)){ speakStatus(); return; }
  if(/(calendario|noticias)/.test(t)){ openCalendar(); speak('Abriendo el calendario.'); return; }
  if(/(actualiza|refresca|recarga)/.test(t)){ load(); speak('Datos actualizados.'); return; }
  if(/(cierra|cerrar|oculta)/.test(t)){ closeDrawer(); return; }
  if(/(hola|buenas|quien eres|presenta)/.test(t)){ speak('Soy Hydra. Puedo correr el demo, darte el estado, o abrir cualquier agente. Solo di, oye Hydra.'); return; }
  for(const a of AGENT_WORDS){ if(a.w.some(w=>t.includes(w))){ openAgent(a.k); const ag=agentByKey(a.k); if(ag)speak(ag.name+'. '+ag.role); return; } }
  speak('No te entendí. Prueba: corre el demo, dame el estado, o abre el analista.');
}
function speakStatus(){ if(!DATA){ speak('Aún cargando.'); return; } const c=DATA.core; const act=DATA.agents.filter(a=>a.state==='active').length;
  const conn=c.connected?'conectado a cTrader':(c.oauth_ok?'esperando conexión':'sin cuenta conectada');
  speak('Modo '+(c.dry_run?'papel':'real')+', '+conn+'. Balance '+(c.balance!=null?c.balance:'desconocido')+'. '+act+' de '+DATA.agents.length+' agentes activos.'); }

/* ===================== BOOT ===================== */
$('#activate').onclick=()=>{ $('#boot').classList.add('hide'); setTimeout(()=>$('#boot').style.display='none',700);
  loadVoices(); speak('Sistemas en línea, señor. Los once agentes están conectados. Diga, oye Hydra, cuando me necesite.');
  if(SR){ wakeMode=true; $('#v-wake').classList.add('on'); startRecog(); setV('Escuchando… di <b>“Oye Hydra”</b>'); }
};

window.addEventListener('resize',layout);
load(); setInterval(load,5000);
</script>
</body></html>
"""
