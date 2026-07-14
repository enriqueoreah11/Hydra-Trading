"""Interfaz JARVIS: red neuronal de partículas viva (estilo del video de referencia).

Sin nodos fijos ni líneas sólidas: filamentos que convergen en puntos-agente ocultos.
Al acercar el mouse se revela qué agente es. Voz neural (servidor) + palabra mágica.
"""

BRAIN_HTML = r"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>HYDRA · núcleo</title>
<style>
:root{ --cyan:#38e6ff; --alert:#ff5d73; --text:#cfe8f2; --dim:#6f879a;
  --ease-out:cubic-bezier(.23,1,.32,1); --ease-in-out:cubic-bezier(.77,0,.175,1); --ease-drawer:cubic-bezier(.32,.72,0,1); }
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:#04070e;color:var(--text);
  font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace;overflow:hidden}
#scan{position:fixed;inset:0;pointer-events:none;z-index:6;opacity:.35;
  background:linear-gradient(#38e6ff00 0,#38e6ff00 49%,#38e6ff10 50%,#38e6ff00 51%);background-size:100% 6px;animation:scan 9s linear infinite}
@keyframes scan{to{background-position:0 100vh}}
.corner{position:fixed;width:34px;height:34px;border:2px solid #1c586b;z-index:7;pointer-events:none}
.corner.tl{top:14px;left:14px;border-right:0;border-bottom:0}.corner.tr{top:14px;right:14px;border-left:0;border-bottom:0}
.corner.bl{bottom:14px;left:14px;border-right:0;border-top:0}.corner.br{bottom:14px;right:14px;border-left:0;border-top:0}
#top{position:fixed;top:0;left:0;right:0;z-index:20;display:flex;align-items:center;gap:12px;padding:14px 22px;flex-wrap:wrap}
#top .brand{font-weight:800;letter-spacing:5px;font-size:22px;color:#dffaff;text-shadow:0 0 22px #38e6ff}
.chip{font-size:11px;padding:4px 10px;border:1px solid #143a49;border-radius:99px;color:var(--dim);background:#07131fbb;white-space:nowrap}
.chip b{color:#dbeafe}
.spacer{flex:1}
.btn{cursor:pointer;font-family:inherit;font-size:11.5px;letter-spacing:1px;color:#02141b;background:linear-gradient(180deg,#66f0ff,#22d3ee);border:0;padding:8px 13px;border-radius:8px;font-weight:800;box-shadow:0 0 16px #22d3ee66;transition:transform .14s var(--ease-out),box-shadow .18s var(--ease-out),background .18s ease,color .18s ease,border-color .18s ease}
.btn.ghost{background:#08131d;color:#9fe6ff;border:1px solid #164a5f;box-shadow:none}
.btn:active{transform:scale(.96)}
@media(hover:hover) and (pointer:fine){.btn:hover{box-shadow:0 0 24px #22d3eeaa}.btn.ghost:hover{border-color:#2b6f88;color:#dffaff}}
#stage{position:absolute;inset:0;z-index:5}
#corefx{position:absolute;inset:0;width:100%;height:100%}
#tip{position:absolute;z-index:12;pointer-events:none;background:#06131feb;border:1px solid #1f7f97;
  border-radius:10px;padding:8px 11px;font-size:12px;color:#dffaff;max-width:230px;box-shadow:0 6px 26px #000a;
  opacity:0;transform:translateY(-50%) scale(.96);transform-origin:left center;transition:opacity .14s var(--ease-out),transform .14s var(--ease-out)}
#tip.show{opacity:1;transform:translateY(-50%) scale(1)}
#tip b{color:#7ff6ff}#tip span{color:#8fb0c2;font-size:10.5px}
#wave{position:fixed;left:0;right:0;bottom:0;height:120px;width:100%;z-index:4;pointer-events:none;opacity:.9}
/* VOZ (botones compactos en la barra de arriba, sin panel ni micrófono gigante) */
.btn.on{background:linear-gradient(180deg,#66f0ff,#22d3ee);color:#02141b;border:0;box-shadow:0 0 16px #22d3ee66}
.btn.mic-on{animation:micpulse 1.1s ease-in-out infinite}
@keyframes micpulse{0%,100%{box-shadow:0 0 12px #38e6ff66}50%{box-shadow:0 0 26px #38e6ff,0 0 44px #38e6ff55}}
#vstatus{font-size:11px;color:#7ff6ff;background:#06131fcc;border:1px solid #17495d;border-radius:99px;padding:4px 11px;max-width:38vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:none}
#vstatus b{color:#dffaff}
/* BOOT */
#boot{position:fixed;inset:0;z-index:60;background:radial-gradient(900px 700px at 50% 45%,#08202f,#03060c 70%);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:22px;transition:opacity .7s}
#boot.hide{opacity:0;pointer-events:none}
#boot .bt{font-weight:800;letter-spacing:10px;font-size:44px;color:#dffaff;text-shadow:0 0 30px #38e6ff}
#boot .bs{color:#7fd9ee;letter-spacing:3px;font-size:12px}
#boot .bcore{width:120px;height:120px;border-radius:50%;background:radial-gradient(circle at 50% 42%,#eaffff,#5ff0ff 45%,#0b7f99 78%,#053745);box-shadow:0 0 50px #38e6ff,0 0 110px #22d3ee88;animation:bp 1.6s ease-in-out infinite;position:relative}
#boot .bring{position:absolute;inset:-18px;border-radius:50%;border:2px solid #0e5a6e;border-top-color:#eaffff;animation:spin 3s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes bp{0%,100%{box-shadow:0 0 40px #38e6ff,0 0 90px #22d3ee66}50%{box-shadow:0 0 70px #7ff6ff,0 0 130px #22d3eeaa}}
#activate{cursor:pointer;font-family:inherit;font-weight:800;letter-spacing:2px;font-size:15px;color:#02141b;background:linear-gradient(180deg,#7ff6ff,#22d3ee);border:0;padding:14px 30px;border-radius:12px;box-shadow:0 0 30px #38e6ff88}
#activate:active{transform:translateY(1px)}
/* DRAWER */
#drawer{position:fixed;top:0;right:0;height:100%;width:min(440px,94vw);z-index:30;background:linear-gradient(180deg,#06121cf5,#04080ef5);border-left:1px solid #12414f;box-shadow:-20px 0 60px #000b;transform:translateX(105%);transition:transform .42s var(--ease-drawer);display:flex;flex-direction:column}
#drawer.open{transform:none}
@media(prefers-reduced-motion:reduce){
  *{animation:none!important}
  #drawer{transition:transform .2s ease}
  .btn:active,#activate:active{transform:none}
}
#drawer .hd{padding:18px;border-bottom:1px solid #103040;display:flex;gap:12px;align-items:center}
#drawer .hd .e{font-size:34px}#drawer .hd h2{margin:0;font-size:18px;color:#e6f7ff;letter-spacing:1px}
#drawer .hd .role{font-size:12px;color:var(--dim);margin-top:3px}
#drawer .x{margin-left:auto;cursor:pointer;color:#5f7387;font-size:22px;line-height:1}
#drawer .body{padding:16px 18px;overflow:auto;flex:1}
#drawer iframe{width:100%;height:100%;border:0;border-radius:8px;background:#fff}
.badge{display:inline-block;font-size:11px;padding:3px 9px;border-radius:99px;border:1px solid #1e3a4a;margin:0 4px 6px 0}
.badge.active{color:#02141b;background:var(--cyan)}.badge.idle{color:#9fe6ff;border-color:#2b6b83}
.badge.off{color:#8aa;background:#111a24}.badge.alert{color:#fff;background:var(--alert)}
.feed{list-style:none;padding:0;margin:12px 0 0}
.feed li{border:1px solid #10293650;border-left:2px solid #38e6ff55;border-radius:8px;padding:9px 11px;margin-bottom:9px;background:#08131e88}
.feed .k{color:#7ff6ff;font-size:11px}.feed .t{color:#5f7387;font-size:10.5px;float:right}
.feed .c{color:#a9bcd0;font-size:11.5px;margin-top:5px;white-space:pre-wrap;word-break:break-word;max-height:150px;overflow:auto}
.empty{color:#5f7387;font-size:12.5px;padding:10px 0}
.cal-day{color:#7ff6ff;font-size:11px;letter-spacing:1px;text-transform:uppercase;margin:16px 0 7px;border-bottom:1px solid #10293650;padding-bottom:4px}
.cal-row{display:flex;align-items:center;gap:9px;padding:7px 9px;border-radius:8px;font-size:12px}
.cal-row.watched{background:#0a1f2c88;border-left:2px solid #38e6ff}
.cal-t{color:#5f7387;font-size:11px;width:44px;flex:none}
.cal-dot{width:8px;height:8px;border-radius:99px;flex:none;box-shadow:0 0 8px currentColor}
.cal-cur{color:#cfe6f2;font-weight:700;width:38px;flex:none;font-size:11px}
.cal-title{color:#a9bcd0}.cal-det{color:#5f7387;font-size:10.5px}
#banner{position:fixed;left:50%;bottom:78px;transform:translateX(-50%);z-index:25;background:#08192af0;border:1px solid #1a4a5f;border-radius:12px;padding:11px 16px;max-width:min(760px,94vw);font-size:12.5px;color:#bfe6f5;box-shadow:0 10px 40px #000a}
#banner code{background:#03121b;padding:2px 7px;border-radius:6px;color:#7ff6ff;border:1px solid #12303f}#banner a{color:#7ff6ff}
#hint{position:fixed;left:50%;top:60px;transform:translateX(-50%);z-index:8;color:#4d6675;font-size:11px;letter-spacing:1px;pointer-events:none}
#toast{position:fixed;left:50%;top:88px;z-index:40;background:#08192af5;border:1px solid #1a4a5f;border-radius:10px;padding:10px 16px;color:#dffaff;font-size:12.5px;pointer-events:none;opacity:0;transform:translateX(-50%) translateY(-6px);transition:opacity .18s var(--ease-out),transform .18s var(--ease-out)}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
</style></head>
<body>
<div id="scan"></div>
<div class="corner tl"></div><div class="corner tr"></div><div class="corner bl"></div><div class="corner br"></div>
<canvas id="wave"></canvas>

<div id="boot">
  <div class="bcore"><div class="bring"></div></div>
  <div class="bt">HYDRA</div><div class="bs">RED NEURONAL · 11 AGENTES</div>
  <button id="activate">⏻ ACTIVAR SISTEMA</button>
  <div class="bs" style="opacity:.6">pulsa para encender voz y micrófono</div>
</div>

<div id="top">
  <span class="brand">◈ HYDRA</span>
  <span class="chip" id="c-mode">modo —</span>
  <span class="chip" id="c-conn">conexión —</span>
  <span class="chip" id="c-bal">balance —</span>
  <span class="chip" id="c-pb">playbook —</span>
  <span id="vstatus"></span>
  <span class="spacer"></span>
  <button class="btn ghost" id="b-mic" title="Hablar (clic, o di “Oye Hydra”)">🎙️</button>
  <button class="btn ghost on" id="b-wake" title="Palabra mágica: “Oye Hydra”">👂 OYE HYDRA</button>
  <button class="btn ghost" id="b-clap" title="Activar aplaudiendo 2 veces">👏 APLAUSO</button>
  <button class="btn ghost on" id="b-speak" title="Voz de respuesta">🔊 VOZ</button>
  <button class="btn" id="b-demo">▶ DEMO</button>
  <button class="btn ghost" id="b-cal">📅 CALENDARIO</button>
  <button class="btn ghost" id="b-halt">⏸ HALT</button>
  <button class="btn ghost" id="b-refresh">⟳</button>
</div>

<div id="hint">cada círculo es un agente · pasa el cursor para ver qué hace y con quién se conecta</div>
<div id="stage"><canvas id="corefx"></canvas><div id="tip"></div></div>

<div id="drawer">
  <div class="hd"><div class="e" id="d-e">🔍</div>
    <div><h2 id="d-name">Agente</h2><div class="role" id="d-role"></div></div>
    <div class="x" onclick="closeDrawer()">✕</div></div>
  <div class="body" id="d-body"></div>
</div>

<div id="toast"></div><div id="banner" style="display:none"></div>

<script>
const $=s=>document.querySelector(s);
let DATA=null, selected=null, halted=false;
const norm=s=>(s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');
function fmtTime(ts){ if(!ts)return"—"; const d=new Date(ts*1000);
  return d.toLocaleString('es',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}); }

async function load(){ let d; try{ d=await (await fetch('/agents')).json(); }catch(e){ return; }
  DATA=d; renderCore(d.core); banner(d.core); if(selected) renderDrawer(selected); }
function renderCore(c){
  halted=c.halted;
  $('#c-mode').innerHTML='modo <b>'+(c.dry_run?'PAPEL':'REAL')+'</b>';
  $('#c-conn').innerHTML=c.connected?'conexión <b style="color:#34d399">viva</b>':(c.oauth_ok?'conexión <b style="color:#fbbf24">esperando</b>':'conexión <b style="color:#ff5d73">sin cTrader</b>');
  $('#c-bal').innerHTML='balance <b>'+(c.balance!=null?c.balance:'—')+'</b>';
  $('#c-pb').innerHTML='playbook <b>v'+c.playbook_version+'</b>';
  $('#b-halt').textContent=c.halted?'▶ RESUME':'⏸ HALT';
  $('#b-cal').style.display='';
  if(c.voice_enabled===false)['b-mic','b-wake','b-clap','b-speak'].forEach(id=>{const e=$('#'+id);if(e)e.style.display='none';});
  ttsServer=!!c.tts_server;
}
function agentByKey(k){ return DATA?DATA.agents.find(a=>a.key===k):null; }
function openAgent(k){ selected=k; renderDrawer(k); $('#drawer').classList.add('open'); const a=agentByKey(k); if(a)speak(a.name+'. '+a.role); }
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
  else if(!c.oauth_ok) m='🔌 Cerebro listo, sin cuenta. Di <b>“Oye Hydra, corre el demo”</b>. Para operar, <a href="/oauth/login">conecta cTrader</a>.';
  else if(!c.connected) m='⏳ Autorizado, conectando con cTrader…';
  b.style.display=m?'block':'none'; b.innerHTML=m; }
function toast(t){ const el=$('#toast'); el.textContent=t; el.classList.add('show'); clearTimeout(el._t); el._t=setTimeout(()=>el.classList.remove('show'),3800); }

$('#b-refresh').onclick=load; $('#b-halt').onclick=doHalt; $('#b-demo').onclick=runDemo; $('#b-cal').onclick=openCalendar;
async function doHalt(){ const halt=$('#b-halt').textContent.includes('HALT'); await fetch(halt?'/halt':'/resume',{method:'POST'}); toast(halt?'Sistema DETENIDO':'Sistema reanudado'); speak(halt?'Sistema detenido, señor.':'Sistema reanudado, señor.'); load(); }
async function openCalendar(){ selected=null;
  $('#d-e').textContent='📅'; $('#d-name').textContent='Calendario económico'; $('#d-role').textContent='Próximos 7 días'; $('#d-body').innerHTML='<div class="empty">Cargando eventos…</div>'; $('#drawer').classList.add('open');
  let d; try{ d=await (await fetch('/calendar')).json(); }catch(e){ $('#d-body').innerHTML='<div class="empty" style="color:#ff5d73">No se pudo cargar el calendario.</div>'; return; }
  const ev=d.events||[];
  if(!ev.length){ $('#d-body').innerHTML='<div class="empty">Sin eventos'+(d.error?': '+escapeHtml(d.error):' en la ventana.')+'</div>'; return; }
  const ic={high:'#ff5d73',medium:'#fbbf24',low:'#5ad1e6',holiday:'#8aa'};
  let last='', h='';
  ev.forEach(e=>{ const dt=new Date(e.ts*1000);
    const day=dt.toLocaleDateString('es',{weekday:'long',day:'numeric',month:'short'});
    if(day!==last){ h+='<div class="cal-day">'+day+'</div>'; last=day; }
    const col=ic[(e.impact||'low').toLowerCase()]||'#5ad1e6';
    const hm=dt.toLocaleTimeString('es',{hour:'2-digit',minute:'2-digit'});
    const det=[e.forecast&&'prev. '+e.forecast,e.previous&&'ant. '+e.previous].filter(Boolean).join(' · ');
    h+='<div class="cal-row'+(e.watched?' watched':'')+'"><span class="cal-t">'+hm+'</span>'
      +'<span class="cal-dot" style="background:'+col+'"></span>'
      +'<span class="cal-cur">'+escapeHtml(e.currency)+'</span>'
      +'<span class="cal-title">'+escapeHtml(e.title)+(det?'<span class="cal-det"> '+escapeHtml(det)+'</span>':'')+'</span></div>'; });
  $('#d-body').innerHTML='<p class="role">🔴 alto · 🟡 medio · 🔵 bajo impacto. Resaltados = afectan tus símbolos.</p>'+h; }
async function runDemo(){ toast('Corriendo demo…'); speak('Ejecutando análisis de demostración.');
  let r; try{ r=await fetch('/demo',{method:'POST'}); }catch(e){ toast('Error de red'); return; }
  if(!r.ok){ const t=await r.text(); openInfo('▶ Modo demo','<p style="color:#ff5d73">No se pudo correr el demo.</p><p>'+escapeHtml(t)+'</p><p>Configura la key: <code>fly secrets set ANTHROPIC_API_KEY=sk-ant-...</code></p>'); speak('No pude correr el demo. Falta la clave de Anthropic.'); return; }
  const data=await r.json(); renderDemo(data.results); load();
  const props=data.results.filter(x=>x.proposal.action==='propose').length; speak('Análisis completo, señor. '+props+' de '+data.results.length+' símbolos con oportunidad.'); }
function openInfo(t,h){ selected=null; $('#d-e').textContent='ℹ️'; $('#d-name').textContent=t; $('#d-role').textContent=''; $('#d-body').innerHTML=h; $('#drawer').classList.add('open'); }
function renderDemo(results){ let h='<p class="role">Datos sintéticos. Así lee el mercado el Analyst.</p>';
  results.forEach(r=>{ const p=r.proposal,m=r.market; const dir=p.action==='propose'?(p.direction==='buy'?'🟢 COMPRA':'🔴 VENTA'):'⚪ SIN OPERACIÓN';
    h+='<li style="list-style:none;border:1px solid #12303f;border-radius:10px;padding:12px;margin:10px 0;background:#08131e88"><b style="color:#7ff6ff">'+r.symbol+'</b> — '+dir+' <span style="color:#5f7387">(confianza '+(p.confidence||0)+')</span>';
    if(p.thesis)h+='<div class="c" style="margin-top:6px;color:#a9bcd0">'+escapeHtml(p.thesis)+'</div>';
    if(p.action==='propose')h+='<div style="color:#8aa;font-size:11px;margin-top:6px">entrada≈ '+p.last_close+' · SL '+p.stop_loss+' · TP '+p.take_profit+'</div>';
    if(r.risk_preview){ const rp=r.risk_preview; h+='<div style="margin-top:8px;font-size:11.5px;color:'+(rp.passes_deterministic?'#34d399':'#ff5d73')+'">'+(rp.passes_deterministic?'✅ pasa filtros del Risk Manager':'❌ sería vetada')+' (R:R '+rp.risk_reward+')</div>'; } h+='</li>'; });
  openInfo('▶ Resultado del demo',h); }

/* ===================== VOZ ===================== */
let esVoices=[], esVoice=null, speakOn=true, ttsServer=false, ttsAudio=null;
let speaking=false, listeningActive=false, wakeUntil=0;
const MALE_PRIORITY=['jorge','juan','diego','carlos','enrique','miguel','pablo','alvaro','google español de estados unidos','google español'];
function loadVoices(){ if(!('speechSynthesis'in window))return; esVoices=speechSynthesis.getVoices().filter(v=>/es(-|_)/i.test(v.lang));
  if(!esVoice){ for(const nm of MALE_PRIORITY){ const v=esVoices.find(v=>v.name.toLowerCase().includes(nm)); if(v){esVoice=v;break;} } if(!esVoice)esVoice=esVoices[0]||null; } }
if('speechSynthesis'in window){ loadVoices(); speechSynthesis.onvoiceschanged=loadVoices; }
$('#b-speak').onclick=()=>{ speakOn=!speakOn; $('#b-speak').classList.toggle('on',speakOn); toast(speakOn?'Voz activada':'Voz silenciada'); if(speakOn)speak('Voz activada.'); };
function speak(t){ if(!speakOn)return; if(ttsServer){ serverSpeak(t); return; } browserSpeak(t); }
async function serverSpeak(t){ try{ speaking=true; if(ttsAudio)ttsAudio.pause();
    const r=await fetch('/tts',{method:'POST',headers:{'Content-Type':'text/plain'},body:t}); if(!r.ok)throw 0;
    const url=URL.createObjectURL(await r.blob()); ttsAudio=new Audio(url);
    ttsAudio.onended=()=>{speaking=false;URL.revokeObjectURL(url);}; ttsAudio.onerror=()=>{speaking=false;browserSpeak(t);}; await ttsAudio.play();
  }catch(_){ speaking=false; browserSpeak(t); } }
function browserSpeak(t){ if(!('speechSynthesis'in window))return; try{ speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(t); u.lang=(esVoice&&esVoice.lang)||'es-ES'; u.rate=1.08; u.pitch=0.85; if(esVoice)u.voice=esVoice;
  u.onstart=()=>{speaking=true;}; u.onend=()=>{speaking=false;}; u.onerror=()=>{speaking=false;}; speechSynthesis.speak(u); }catch(_){}}

const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
let recog=null,running=false,wakeMode=true,awaiting=false,awaitTimer=null;
const WAKE=['oye hydra','hola hydra','hey hydra','oye idra','oye hidra','hydra','hidra','jarvis'];
function setV(t){ const el=$('#vstatus'); if(!el)return; el.innerHTML=t||''; el.style.display=t?'inline-block':'none'; if(el._t)clearTimeout(el._t); if(t)el._t=setTimeout(()=>{el.style.display='none';},6000); }
function coreHear(on){ listeningActive=on; $('#b-mic').classList.toggle('mic-on',on); }
function wakeFlash(){ wakeUntil=performance.now()+700; }
if(!SR){ setV('Voz no soportada — usa Chrome.'); }
else{ recog=new SR(); recog.lang='es-ES'; recog.interimResults=true; recog.continuous=true;
  recog.onresult=e=>{ let interim=''; for(let i=e.resultIndex;i<e.results.length;i++){ const r=e.results[i]; if(r.isFinal) handlePhrase(norm(r[0].transcript)); else interim+=r[0].transcript; } if(interim)setV('“'+interim+'”'); };
  recog.onerror=e=>{ if(e.error==='not-allowed')setV('Permiso de micrófono denegado.'); };
  recog.onend=()=>{ running=false; coreHear(false); if(wakeMode||awaiting){ setTimeout(startRecog,300);} else setV('Di <b>“Oye Hydra…”</b>'); };
}
function startRecog(){ if(!recog||running)return; try{ recog.start(); running=true; coreHear(true);}catch(_){}}
function handlePhrase(t){ if(awaiting){ clearTimeout(awaitTimer); awaiting=false; wakeFlash(); runCmd(t); return; }
  const w=WAKE.find(w=>t.includes(w)); if(!w)return; wakeFlash(); const rest=t.slice(t.indexOf(w)+w.length).trim();
  if(rest.length>2){ runCmd(rest); } else { speak('A la orden, señor.'); setV('<b>Le escucho…</b>'); awaiting=true; awaitTimer=setTimeout(()=>{awaiting=false;setV('Di <b>“Oye Hydra…”</b>');},9000); } }
$('#b-mic').onclick=()=>{ if(!SR){toast('Usa Chrome para la voz');return;} awaiting=true; setV('<b>Le escucho…</b>'); speak('Dígame, señor.'); if(!running)startRecog(); };
$('#b-wake').onclick=()=>{ wakeMode=!wakeMode; $('#b-wake').classList.toggle('on',wakeMode); if(wakeMode){ toast('Palabra mágica activada'); startRecog(); } else { toast('Palabra mágica apagada'); if(recog&&running)recog.stop(); } };

let clapOn=false,clapStream=null,clapRAF=null,clapTimes=[];
$('#b-clap').onclick=async()=>{ if(clapOn){stopClap();}else{await startClap();} };
async function startClap(){ try{ clapStream=await navigator.mediaDevices.getUserMedia({audio:true});
    const ctx=new (window.AudioContext||window.webkitAudioContext)(); const src=ctx.createMediaStreamSource(clapStream); const an=ctx.createAnalyser(); an.fftSize=1024; src.connect(an); const buf=new Uint8Array(an.fftSize);
    clapOn=true; $('#b-clap').classList.add('on'); toast('Aplauso activado: aplaude 2 veces');
    const loop=()=>{ if(!clapOn)return; an.getByteTimeDomainData(buf); let peak=0; for(let i=0;i<buf.length;i++){ const v=Math.abs(buf[i]-128)/128; if(v>peak)peak=v; }
      const now=performance.now(); if(peak>0.42&&(!clapTimes.length||now-clapTimes[clapTimes.length-1]>180)){ clapTimes.push(now); clapTimes=clapTimes.filter(t=>now-t<1000); if(clapTimes.length>=2){clapTimes=[];onClap();} }
      clapRAF=requestAnimationFrame(loop); }; loop();
  }catch(e){ toast('No pude usar el micrófono para aplauso'); } }
function stopClap(){ clapOn=false; $('#b-clap').classList.remove('on'); if(clapRAF)cancelAnimationFrame(clapRAF); if(clapStream)clapStream.getTracks().forEach(t=>t.stop()); }
function onClap(){ wakeFlash(); speak('A la orden, señor.'); setV('<b>Le escucho…</b>'); awaiting=true; if(!running)startRecog(); clearTimeout(awaitTimer); awaitTimer=setTimeout(()=>{awaiting=false;},9000); }

const AGENT_WORDS=[{k:'analyst',w:['analista','analisis']},{k:'risk_manager',w:['riesgo','gestor']},{k:'executor',w:['ejecutor','ordenes']},{k:'overnight',w:['nocturno','noche']},{k:'reviewer',w:['revisor','revision']},{k:'architect',w:['arquitecto','playbook']},{k:'sentinel',w:['sentinel','noticias','calendario','centinela']},{k:'watchdog',w:['watchdog','vigilante','salud']},{k:'auditor',w:['auditor','auditoria']},{k:'validator',w:['validador','backtest']},{k:'portfolio',w:['portafolio','cartera','correlacion']}];
function runCmd(t){
  if(/(demo|prueba|analiza|corre)/.test(t)){ runDemo(); return; }
  if(/(deten|para|alto|halt|pausa)/.test(t)){ if($('#b-halt').textContent.includes('HALT'))doHalt(); else speak('Ya está detenido, señor.'); return; }
  if(/(reanuda|continua|resume|activa el sistema)/.test(t)){ if($('#b-halt').textContent.includes('RESUME'))doHalt(); else speak('Ya está activo, señor.'); return; }
  if(/(estado|reporte|situacion|resumen|status|como vas)/.test(t)){ speakStatus(); return; }
  if(/(calendario|noticias)/.test(t)){ openCalendar(); speak('Abriendo el calendario.'); return; }
  if(/(actualiza|refresca|recarga)/.test(t)){ load(); speak('Datos actualizados, señor.'); return; }
  if(/(cierra|cerrar|oculta)/.test(t)){ closeDrawer(); return; }
  if(/(hola|buenas|quien eres|presenta)/.test(t)){ speak('Soy Hydra, a su servicio. Puedo correr el demo, darle el estado, o mostrarle cualquier agente. Diga, oye Hydra.'); return; }
  for(const a of AGENT_WORDS){ if(a.w.some(w=>t.includes(w))){ openAgent(a.k); return; } }
  speak('No le entendí, señor. Pruebe: corre el demo, dame el estado, o abre el analista.');
}
function speakStatus(){ if(!DATA){ speak('Aún cargando.'); return; } const c=DATA.core; const act=DATA.agents.filter(a=>a.state==='active').length;
  const conn=c.connected?'conectado a cTrader':(c.oauth_ok?'esperando conexión':'sin cuenta conectada');
  speak('Modo '+(c.dry_run?'papel':'real')+', '+conn+'. Balance '+(c.balance!=null?c.balance:'desconocido')+'. '+act+' de '+DATA.agents.length+' agentes activos, señor.'); }

$('#activate').onclick=()=>{ $('#boot').classList.add('hide'); setTimeout(()=>$('#boot').style.display='none',700);
  loadVoices(); speak('Sistemas en línea, señor. Los once agentes están conectados. Diga, oye Hydra, cuando me necesite.');
  if(SR){ wakeMode=true; $('#b-wake').classList.add('on'); startRecog(); setV('Escuchando… di <b>“Oye Hydra”</b>'); } };

/* ===================== ONDA DE AUDIO ===================== */
const wv=$('#wave'), wg=wv.getContext('2d'); let wt=0; const DPR=window.devicePixelRatio||1;
function wsize(){ wv.width=innerWidth*DPR; wv.height=120*DPR; wg.setTransform(DPR,0,0,DPR,0,0); } wsize(); addEventListener('resize',wsize);
function drawWave(){ const W=innerWidth,H=120; wg.clearRect(0,0,W,H); const target=speaking?1:(listeningActive?0.6:0.12); waveLevelG+=(target-waveLevelG)*0.08; wt+=0.055;
  for(let pass=0;pass<2;pass++){ wg.beginPath(); for(let x=0;x<=W;x+=6){ const env=Math.max(0,1-Math.abs(x/W-0.5)*1.6); const a=(14+70*waveLevelG)*env*(pass?0.55:1);
    const y=H*0.62+Math.sin(x*0.022+wt*(pass?1.7:1))*a*Math.sin(wt*0.7+x*0.005); x===0?wg.moveTo(x,y):wg.lineTo(x,y); }
    wg.strokeStyle=pass?'rgba(56,230,255,.30)':'rgba(120,246,255,.85)'; wg.lineWidth=pass?4:2; wg.shadowColor='#38e6ff'; wg.shadowBlur=pass?18:10; wg.stroke(); }
  requestAnimationFrame(drawWave); }
let waveLevelG=0.12; requestAnimationFrame(drawWave);

/* ============ CONSTELACIÓN DE AGENTES (estrella de datos + agentes + ramas) ============ */
(function(){
  const cv=$('#corefx'), g=cv.getContext('2d');
  let W=0,H=0,CX=0,CY=0,S=0,Rh=0,Rlab=0, mx=-9999,my=-9999, hoverKey=null, dirty=true;
  const dpr=Math.min(window.devicePixelRatio||1,1.5);
  function rs(){ W=cv.clientWidth||innerWidth; H=cv.clientHeight||innerHeight; cv.width=W*dpr; cv.height=H*dpr; g.setTransform(dpr,0,0,dpr,0,0); CX=W/2; CY=H*0.53; S=Math.min(W,H); Rh=S*0.25; Rlab=S*0.44; dirty=true; }
  rs(); addEventListener('resize',rs);
  function stateOf(k){ const a=agentByKey(k); return a?a.state:'idle'; }
  function entriesOf(k){ const a=agentByKey(k); return a&&a.entries?a.entries.length:0; }
  const PAL=['#ffd24a','#ff7a59','#c07cff','#4ad1c8','#5aa0ff','#9be36b','#7ff6ff','#ff5d73','#ff9f43','#6ee7ff','#e879f9'];
  function hx2(h){ h=(h||'').replace('#',''); if(h.length===3)h=h.split('').map(c=>c+c).join(''); const n=parseInt(h,16); if(isNaN(n))return '127,246,255'; return (n>>16&255)+','+(n>>8&255)+','+(n&255); }
  function rng(a){ return function(){ a|=0; a=a+0x6D2B79F5|0; let t=Math.imul(a^a>>>15,1|a); t=t+Math.imul(t^t>>>7,61|t)^t; return ((t^t>>>14)>>>0)/4294967296; }; }
  // árbol de ramas que crece hacia afuera desde el agente (sus tareas/funciones)
  function makeTree(hx,hy,phi,seed,extra){
    const r=rng(seed), segs=[], leaves=[], B=3+((r()*3)|0);
    for(let b=0;b<B;b++){ const a1=phi+(b-(B-1)/2)*(1.6/B)+(r()-0.5)*0.15, L1=S*0.075+r()*S*0.04;
      const x1=hx+Math.cos(a1)*L1, y1=hy+Math.sin(a1)*L1; segs.push([hx,hy,x1,y1]); leaves.push([x1,y1,1.9,r()*6.28]);
      const C=2+((r()*(2+extra))|0);
      for(let c=0;c<C;c++){ const a2=a1+(r()-0.5)*0.85, L2=S*0.05+r()*S*0.035;
        const x2=x1+Math.cos(a2)*L2, y2=y1+Math.sin(a2)*L2; segs.push([x1,y1,x2,y2]); leaves.push([x2,y2,1.4+r()*1.6,r()*6.28]);
        if(r()<0.6){ const a3=a2+(r()-0.5)*0.85, L3=S*0.033+r()*S*0.025, x3=x2+Math.cos(a3)*L3, y3=y2+Math.sin(a3)*L3;
          segs.push([x2,y2,x3,y3]); leaves.push([x3,y3,1.2+r()*1.3,r()*6.28]); } } }
    return {segs,leaves};
  }
  // conexiones entre agentes = el flujo real del cerebro (qué se conecta con qué)
  const LINKS=[['sentinel','analyst'],['analyst','risk_manager'],['risk_manager','portfolio'],['portfolio','executor'],
    ['executor','auditor'],['overnight','executor'],['reviewer','architect'],['architect','validator'],
    ['validator','analyst'],['watchdog','executor'],['watchdog','sentinel']];
  let A=[], byKey={};
  function build(){
    const ags=DATA?DATA.agents:[], N=ags.length||1;
    A=ags.map((a,i)=>{ const ang=-Math.PI/2 + i/N*Math.PI*2;
      const x=CX+Math.cos(ang)*Rh, y=CY+Math.sin(ang)*Rh, lx=CX+Math.cos(ang)*Rlab, ly=CY+Math.sin(ang)*Rlab;
      const extra=Math.min(2,(entriesOf(a.key)/4)|0);
      const t=makeTree(x,y,ang,(i+1)*131+7,extra), sg=t.segs;
      // grafo del árbol: segmentos raíz (salen del agente) y segmentos hijos (para el flujo de energía)
      const roots=[], next=sg.map(()=>[]);
      sg.forEach((s,si)=>{ if(Math.abs(s[0]-x)<0.5&&Math.abs(s[1]-y)<0.5) roots.push(si);
        sg.forEach((s2,sj)=>{ if(si!==sj&&Math.abs(s2[0]-s[2])<0.5&&Math.abs(s2[1]-s[3])<0.5) next[si].push(sj); }); });
      const sparks=[], ns=Math.max(3,Math.round(sg.length*0.55));
      for(let s=0;s<ns;s++){ const seg=roots.length?roots[(Math.random()*roots.length)|0]:0; sparks.push({seg,t:Math.random(),sp:0.012+Math.random()*0.020}); }
      return {key:a.key,name:a.name,emoji:a.emoji,role:a.role,x,y,lx,ly,ang,rgb:hx2(a.ring||PAL[i%PAL.length]),segs:sg,leaves:t.leaves,roots,next,sparks}; });
    byKey={}; A.forEach(a=>byKey[a.key]=a); dirty=false;
  }
  const star=[];
  function starSpawn(n){ for(let i=0;i<n;i++){ const a=Math.random()*6.283, sp=0.6+Math.random()*3.6;
    star.push({x:CX,y:CY,vx:Math.cos(a)*sp,vy:Math.sin(a)*sp,life:1,dl:0.009+Math.random()*0.013,c:Math.random()<0.5?'255,214,120':'150,240,255'});
    if(star.length>360)star.shift(); } }
  function qpt(a,c,b,t){ const u=1-t; return [u*u*a[0]+2*u*t*c[0]+t*t*b[0], u*u*a[1]+2*u*t*c[1]+t*t*b[1]]; }
  cv.addEventListener('mousemove',e=>{ const r=cv.getBoundingClientRect(); mx=e.clientX-r.left; my=e.clientY-r.top; });
  cv.addEventListener('mouseleave',()=>{ mx=my=-9999; });
  cv.addEventListener('click',()=>{ if(hoverKey) openAgent(hoverKey); else { speakStatus(); toast('HYDRA · '+(DATA?DATA.agents.length:0)+' agentes'); } });
  function frame(now){
    if(!DATA){ requestAnimationFrame(frame); return; }
    if(dirty||A.length!==(DATA.agents||[]).length) build();
    hoverKey=null; let hd=1e9; for(const a of A){ const dx=a.x-mx,dy=a.y-my,d=dx*dx+dy*dy; if(d<1100&&d<hd){hd=d;hoverKey=a.key;} }
    cv.style.cursor=hoverKey?'pointer':'default';
    const flash=now<wakeUntil?1:0;
    g.globalCompositeOperation='source-over'; g.fillStyle='#04070e'; g.fillRect(0,0,W,H);
    g.globalCompositeOperation='lighter'; g.shadowBlur=0;
    // radios centro→agente
    g.strokeStyle='rgba(80,150,180,0.10)'; g.lineWidth=1; g.beginPath();
    for(const a of A){ g.moveTo(CX,CY); g.lineTo(a.x,a.y); } g.stroke();
    // conexiones entre agentes (curvas hacia el centro)
    for(const L of LINKS){ const a=byKey[L[0]], b=byKey[L[1]]; if(!a||!b) continue;
      const hot=hoverKey&&(L[0]===hoverKey||L[1]===hoverKey);
      const cx=(a.x+b.x)/2+(CX-(a.x+b.x)/2)*0.42, cy=(a.y+b.y)/2+(CY-(a.y+b.y)/2)*0.42;
      g.strokeStyle=hot?'rgba(127,246,255,0.85)':'rgba(90,150,180,0.13)'; g.lineWidth=hot?1.7:1;
      g.beginPath(); g.moveTo(a.x,a.y); g.quadraticCurveTo(cx,cy,b.x,b.y); g.stroke();
      if(hot){ const p=qpt([a.x,a.y],[cx,cy],[b.x,b.y],(now*0.0006)%1); g.fillStyle='rgba(190,250,255,1)'; g.beginPath(); g.arc(p[0],p[1],2.2,0,7); g.fill(); } }
    // ramas de cada agente
    for(const a of A){ const h=a.key===hoverKey, dim=hoverKey&&!h;
      g.strokeStyle='rgba('+a.rgb+','+(dim?0.10:(h?0.95:0.42))+')'; g.lineWidth=h?1.6:1.1;
      g.beginPath(); for(const s of a.segs){ g.moveTo(s[0],s[1]); g.lineTo(s[2],s[3]); } g.stroke();
      for(const l of a.leaves){ const tw=0.55+0.45*Math.sin(now*0.004+l[3]); const al=(dim?0.12:(h?1:0.62))*tw;
        g.fillStyle='rgba('+a.rgb+','+al+')'; g.beginPath(); g.arc(l[0],l[1],l[2]*(h?1.4:1),0,7); g.fill(); }
      // energía fluyendo del agente hacia sus ramas (raíz→hoja)
      for(const sp of a.sparks){ sp.t+=sp.sp*(h?1.8:1);
        if(sp.t>=1){ const nx=a.next[sp.seg]; sp.seg=(nx&&nx.length)?nx[(Math.random()*nx.length)|0]:(a.roots.length?a.roots[(Math.random()*a.roots.length)|0]:0); sp.t=0; }
        const s=a.segs[sp.seg]; if(!s) continue; const x=s[0]+(s[2]-s[0])*sp.t, y=s[1]+(s[3]-s[1])*sp.t;
        const tt=Math.max(0,sp.t-0.22), tx=s[0]+(s[2]-s[0])*tt, ty=s[1]+(s[3]-s[1])*tt;
        g.strokeStyle='rgba('+a.rgb+','+(dim?0.20:0.75)+')'; g.lineWidth=h?2:1.4; g.beginPath(); g.moveTo(tx,ty); g.lineTo(x,y); g.stroke();
        g.fillStyle='rgba('+a.rgb+','+(dim?0.35:1)+')'; g.beginPath(); g.arc(x,y,h?2.3:1.7,0,7); g.fill(); } }
    // estrella de datos (núcleo) — más grande, con halo
    starSpawn(halted?1:(speaking?16:11));
    for(let i=star.length-1;i>=0;i--){ const p=star[i]; const px=p.x,py=p.y; p.x+=p.vx; p.y+=p.vy; p.vx*=0.975; p.vy*=0.975; p.life-=p.dl;
      if(p.life<=0){ star.splice(i,1); continue; } const al=p.life;
      g.strokeStyle='rgba('+p.c+','+(al*0.8)+')'; g.lineWidth=1.3; g.beginPath(); g.moveTo(px,py); g.lineTo(p.x,p.y); g.stroke(); }
    const hg=g.createRadialGradient(CX,CY,0,CX,CY,S*0.15); hg.addColorStop(0,halted?'rgba(255,110,130,0.22)':'rgba(255,214,150,0.20)'); hg.addColorStop(1,'rgba(0,0,0,0)');
    g.fillStyle=hg; g.beginPath(); g.arc(CX,CY,S*0.15,0,7); g.fill();
    g.shadowColor=halted?'#ff5d73':'#ffe0a0'; g.shadowBlur=34+flash*26;
    g.fillStyle=halted?'rgba(255,150,165,.98)':'rgba(255,244,214,.98)'; g.beginPath(); g.arc(CX,CY,7+flash*4,0,7); g.fill(); g.shadowBlur=0;
    // círculos de agente (visibles) con ícono
    for(const a of A){ const st=stateOf(a.key), h=a.key===hoverKey, on=st==='active'||st==='alert', dim=hoverKey&&!h;
      const R=h?18:14;
      if(on||h){ g.shadowColor='rgba('+a.rgb+',1)'; g.shadowBlur=h?26:13; } else g.shadowBlur=0;
      g.fillStyle='#05090f'; g.beginPath(); g.arc(a.x,a.y,R,0,7); g.fill();
      g.shadowBlur=0; g.lineWidth=h?2.4:1.7; g.strokeStyle='rgba('+a.rgb+','+(dim?0.4:(h?1:0.85))+')'; g.beginPath(); g.arc(a.x,a.y,R,0,7); g.stroke();
      if(st==='alert'){ g.strokeStyle='rgba(255,93,115,'+(0.5+0.5*Math.sin(now*0.006))+')'; g.lineWidth=2; g.beginPath(); g.arc(a.x,a.y,R+4,0,7); g.stroke(); }
      g.globalAlpha=dim?0.5:1; g.font=(h?'16px':'13px')+' system-ui,"Segoe UI Emoji",sans-serif'; g.textAlign='center'; g.textBaseline='middle'; g.fillStyle='#eaffff'; g.fillText(a.emoji,a.x,a.y+0.5); g.globalAlpha=1; }
    // etiquetas (nombres de agente)
    g.font='11px system-ui,sans-serif'; g.textAlign='center'; g.textBaseline='middle';
    for(const a of A){ const dim=hoverKey&&a.key!==hoverKey; g.fillStyle='rgba(214,236,246,'+(dim?0.22:0.82)+')'; g.fillText(a.name.toUpperCase(),a.lx,a.ly); }
    // tooltip: rol + con quién colabora
    const tip=$('#tip'); if(hoverKey){ const a=byKey[hoverKey];
      const nb=LINKS.filter(L=>L[0]===hoverKey||L[1]===hoverKey).map(L=>L[0]===hoverKey?L[1]:L[0]).map(k=>byKey[k]?byKey[k].name:k);
      tip.style.left=(a.x+22)+'px'; tip.style.top=a.y+'px';
      tip.innerHTML=a.emoji+' <b>'+a.name+'</b> · '+stateOf(a.key)+'<br><span>'+a.role+'</span>'+(nb.length?'<br><span>↔ '+nb.join(', ')+'</span>':'');
      tip.classList.add('show'); } else tip.classList.remove('show');
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();

addEventListener('resize',()=>{});
load(); setInterval(load,5000);
</script>
</body></html>
"""
