"""Interfaz JARVIS: red neuronal de partículas viva (estilo del video de referencia).

Sin nodos fijos ni líneas sólidas: filamentos que convergen en puntos-agente ocultos.
Al acercar el mouse se revela qué agente es. Voz neural (servidor) + palabra mágica.
"""

BRAIN_HTML = r"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>HYDRA · núcleo</title>
<link rel="icon" type="image/svg+xml" href="/icon/4/mark.svg">
<link rel="icon" type="image/png" sizes="64x64" href="/icon/4/favicon.png">
<link rel="shortcut icon" href="/icon/4/favicon.png">
<link rel="apple-touch-icon" sizes="180x180" href="/icon/4/icon-180.png">
<link rel="apple-touch-icon-precomposed" sizes="180x180" href="/icon/4/icon-180.png">
<link rel="manifest" href="/manifest.webmanifest?v=4">
<meta name="theme-color" content="#04070e">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="HYDRA">
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
/* La pantalla de inicio NO tapa nada: la placa se ve detrás, apagada, y el icono
   con los ojos rojos lo dibuja el propio lienzo en su sitio definitivo. Aquí solo
   queda una zona de clic invisible — así al encender no hay ningún salto. */
#boot{position:fixed;inset:0;z-index:60;background:0;transition:opacity .7s;pointer-events:none}
#boot.hide{opacity:0}
@keyframes spin{to{transform:rotate(360deg)}}
/* pointer-events:none a proposito: el raton tiene que llegar al LIENZO para que la
   cara reaccione al pasar por encima. El clic lo recoge el lienzo y dispara este
   boton, que sigue existiendo para poder encender con el teclado. */
#activate{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;
  background:0;border:0;padding:0;font:inherit;color:transparent}
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
#sistema{position:fixed;top:0;right:0;height:100%;width:min(380px,94vw);z-index:32;background:linear-gradient(180deg,#06121cf7,#04080ef7);border-left:1px solid #12414f;box-shadow:-20px 0 60px #000b;transform:translateX(105%);transition:transform .42s var(--ease-drawer);display:flex;flex-direction:column}
#sistema.open{transform:none}
#sistema .hd{padding:16px 18px;border-bottom:1px solid #103040;display:flex;gap:12px;align-items:center}
#sistema .hd .e{font-size:26px}#sistema .hd h2{margin:0;font-size:16px;color:#e6f7ff;letter-spacing:1px}#sistema .hd .role{font-size:11px;color:var(--dim)}
#sistema .hd .x{margin-left:auto;cursor:pointer;color:#5f7387;font-size:16px}
#sistema .sbody{padding:14px 18px;overflow:auto}
.slbl{font-size:10px;letter-spacing:2px;color:#5f7387;margin:18px 0 9px}
.ssec{display:flex;flex-wrap:wrap;gap:8px}
.cfg{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:9px 2px;border-bottom:1px solid #10293650;font-size:12.5px;color:#a9bcd0}
.cfg span{color:#5f7387}.cfg b{color:#dffaff}.cfg code{background:#03121b;padding:1px 6px;border-radius:5px;color:#7ff6ff}
.wrow{display:flex;align-items:center;gap:7px;flex-wrap:wrap;padding:8px 0;border-bottom:1px solid #10293650}
.wrow .wsym{font-size:12.5px;color:#dffaff;letter-spacing:1px;min-width:74px}
.wrow .wx{margin-left:auto;cursor:pointer;color:#4a5f70;font-size:14px;padding:0 3px}
.wrow .wx:hover{color:#ff5d73}
.chip2{cursor:pointer;font-size:10px;letter-spacing:.6px;padding:3px 8px;border-radius:99px;
  border:1px solid #17323f;color:#4a6072;background:#08131d;transition:all .15s ease;white-space:nowrap}
.chip2.on{border-color:#38e6ff;color:#02141b;background:linear-gradient(180deg,#66f0ff,#22d3ee);
  box-shadow:0 0 12px #22d3ee55}
.wadd{display:flex;gap:7px;margin-top:12px}
.wadd input{flex:1;background:#08131d;color:#dffaff;border:1px solid #17495d;border-radius:8px;
  padding:7px 9px;font-family:inherit;font-size:12.5px;text-transform:uppercase}
.prm{margin:11px 0}.prm label{display:block;font-size:12px;color:#cfe6f2;margin-bottom:4px}
.prm input,.prm select{width:100%;background:#08131d;color:#dffaff;border:1px solid #17495d;border-radius:8px;padding:7px 9px;font-family:inherit;font-size:12.5px}
.phelp{font-size:10.5px;color:#5f7387;margin-top:3px}
.cal-day{color:#7ff6ff;font-size:11px;letter-spacing:1px;text-transform:uppercase;margin:16px 0 7px;border-bottom:1px solid #10293650;padding-bottom:4px}
.cal-row{display:flex;align-items:center;gap:9px;padding:7px 9px;border-radius:8px;font-size:12px}
.cal-row.watched{background:#0a1f2c88;border-left:2px solid #38e6ff}
.cal-t{color:#5f7387;font-size:11px;width:44px;flex:none}
.cal-dot{width:8px;height:8px;border-radius:99px;flex:none;box-shadow:0 0 8px currentColor}
.cal-cur{color:#cfe6f2;font-weight:700;width:38px;flex:none;font-size:11px}
.cal-title{color:#a9bcd0}.cal-det{color:#5f7387;font-size:10.5px}
#banner{position:fixed;left:50%;bottom:78px;transform:translateX(-50%);z-index:25;background:#08192af0;border:1px solid #1a4a5f;border-radius:12px;padding:11px 16px;max-width:min(760px,94vw);font-size:12.5px;color:#bfe6f5;box-shadow:0 10px 40px #000a}
#banner code{background:#03121b;padding:2px 7px;border-radius:6px;color:#7ff6ff;border:1px solid #12303f}#banner a{color:#7ff6ff}
/* PANTALLAS LATERALES: columna izquierda = sesiones + calendario de esa sesión;
   columna derecha = la configuración repartida en pantallas. */
.hudcol{position:fixed;top:64px;bottom:100px;width:268px;z-index:9;display:flex;flex-direction:column;
  gap:9px;pointer-events:none}
#colL{left:16px}#colR{right:16px}
.hud{flex:none;min-height:0;display:flex;flex-direction:column;pointer-events:auto;position:relative;
  background:linear-gradient(180deg,#061420b0,#04090fb0);border:1px solid #14414f;border-radius:4px;
  box-shadow:0 0 30px #0008,inset 0 0 40px #0a2b3a30;backdrop-filter:blur(2px);
  opacity:0;transform:translateX(var(--slide,0));transition:opacity .6s var(--ease-out),transform .6s var(--ease-out)}
.hud.grow{flex:1 1 auto;overflow:hidden}
.spacer-v{flex:1 1 auto;min-height:0}
.hud.in{opacity:1;transform:none}
#colL .hud{--slide:-24px}#colR .hud{--slide:24px}
.hud::before,.hud::after{content:'';position:absolute;width:12px;height:12px;border:1px solid #38e6ff88;pointer-events:none}
.hud::before{top:-1px;left:-1px;border-right:0;border-bottom:0}
.hud::after{bottom:-1px;right:-1px;border-left:0;border-top:0}
.hudhd{display:flex;align-items:center;gap:8px;padding:8px 11px;border-bottom:1px solid #10333f;
  font-size:9.5px;letter-spacing:2.4px;color:#5ad1e6;text-shadow:0 0 10px #38e6ff55}
.hudhd .dot{width:5px;height:5px;border-radius:99px;background:#38e6ff;box-shadow:0 0 8px #38e6ff;animation:hb 2.2s ease-in-out infinite}
@keyframes hb{0%,100%{opacity:.35}50%{opacity:1}}
.hudhd .tf{margin-left:auto;color:#3d5a6b;letter-spacing:1px}
.hudbody{flex:1;overflow:auto;padding:6px 8px;scrollbar-width:thin}
.hudbody::-webkit-scrollbar{width:5px}.hudbody::-webkit-scrollbar-thumb{background:#12414f;border-radius:9px}
.irow{display:grid;grid-template-columns:1fr auto;gap:2px 8px;align-items:center;cursor:pointer;
  padding:7px 8px;border:1px solid transparent;border-left:2px solid #1b3d4d;border-radius:3px;margin-bottom:4px;
  transition:background .16s ease,border-color .16s ease}
@media(hover:hover){.irow:hover{background:#0b2130aa;border-color:#1f6a83}}
.irow.live{background:#0a2320aa}
.irow .s{font-size:11.5px;color:#dff0ff;letter-spacing:1px}
.irow .p{font-size:11.5px;color:#9fd8ea;text-align:right}
.irow .ch{font-size:10px;text-align:right}
.irow .sp{grid-column:1/-1;height:22px;margin-top:2px}
.irow .sp svg{display:block;width:100%;height:22px;overflow:visible}
.impbar{display:flex;gap:5px;padding:2px 1px 7px}
.impc{flex:1;text-align:center;cursor:pointer;font-size:8.5px;letter-spacing:1.2px;padding:3px 0;border-radius:2px;
  border:1px solid #17323f;color:#3d5a6b;transition:color .15s ease,border-color .15s ease,background .15s ease}
.impc.on{color:var(--c);border-color:var(--c);background:color-mix(in srgb,var(--c) 12%,transparent);
  box-shadow:0 0 10px color-mix(in srgb,var(--c) 30%,transparent)}
.nrow{display:flex;gap:7px;align-items:baseline;padding:6px 8px;border-radius:3px;font-size:10.5px;margin-bottom:2px}
.nrow.w{background:#0a2030aa;border-left:2px solid #38e6ff}
.nrow .t{color:#3d5a6b;width:38px;flex:none}
.nrow .d{width:6px;height:6px;border-radius:99px;flex:none;box-shadow:0 0 7px currentColor;align-self:center}
.nrow .c{color:#9fd8ea;width:30px;flex:none;letter-spacing:.5px}
.nrow .n{color:#7d97a8;line-height:1.35}
.hudsub{display:flex;align-items:center;gap:8px;padding:7px 11px;border-top:1px solid #10333f;border-bottom:1px solid #0d2833;
  font-size:9.5px;letter-spacing:2.4px;color:#5ad1e6;text-shadow:0 0 10px #38e6ff55}
.hudsub .tf{margin-left:auto;color:#3d5a6b;letter-spacing:1px}
.sesbox,.posbox{padding:6px 8px}
.posbox{max-height:118px;overflow:auto}
.srow{display:grid;grid-template-columns:66px 1fr 34px;gap:7px;align-items:center;padding:3px 2px;font-size:10px}
.srow .sn{color:#7d97a8;letter-spacing:.6px;white-space:nowrap}
.srow.on .sn{color:#dff0ff}
.srow .bar{height:4px;border-radius:99px;background:#0d2430;position:relative;overflow:hidden}
.srow .bar i{position:absolute;inset:0;width:0;background:linear-gradient(90deg,#1b7f96,#38e6ff);box-shadow:0 0 8px #38e6ff88}
.srow .hh{color:#3d5a6b;font-size:9px;letter-spacing:.5px}
.srow.on .hh{color:#5ad1e6}
.prow{display:grid;grid-template-columns:auto 1fr auto;gap:6px;align-items:baseline;padding:5px 7px;margin-bottom:3px;
  border-radius:3px;border-left:2px solid #1b3d4d;background:#0a1a26aa;font-size:10.5px;cursor:pointer}
.prow .sd{font-size:9px;letter-spacing:1px;padding:1px 5px;border-radius:2px}
.prow .sy{color:#dff0ff;letter-spacing:1px}
.prow .vl{color:#5f7387;font-size:9.5px}
.sysbox{padding:7px 10px}
.srow2{display:flex;justify-content:space-between;gap:10px;padding:4px 0;font-size:10.5px;color:#5f7387;
  border-bottom:1px solid #0d2833}
.srow2:last-child{border-bottom:0}
.srow2 b{color:#dff0ff;font-weight:600}
.sysact{display:flex;flex-wrap:wrap;gap:6px;padding:8px 10px;border-top:1px solid #10333f}
.sysact .btn{padding:6px 9px;font-size:9.5px;letter-spacing:1px}
.hudfoot{padding:6px 10px;border-top:1px solid #10333f;font-size:9px;letter-spacing:1.6px;color:#33505f;
  display:flex;justify-content:space-between;cursor:pointer}
@media(max-width:1180px){.hudcol{display:none}}
/* CINTA DE ACTIVIDAD (arriba, centrada): lo que se está analizando y ejecutando */
#tape{position:fixed;top:58px;left:50%;transform:translateX(-50%) translateY(-10px);z-index:10;
  width:min(620px,calc(100vw - 620px));min-width:360px;max-height:172px;display:flex;flex-direction:column;
  background:linear-gradient(180deg,#061420b8,#04090fb8);border:1px solid #14414f;border-radius:4px;
  box-shadow:0 0 30px #0008,inset 0 0 40px #0a2b3a30;backdrop-filter:blur(2px);
  opacity:0;transition:opacity .6s var(--ease-out),transform .6s var(--ease-out);pointer-events:none}
#tape.in{opacity:1;transform:translateX(-50%);pointer-events:auto}
#tape::before,#tape::after{content:'';position:absolute;width:12px;height:12px;border:1px solid #38e6ff88}
#tape::before{top:-1px;left:-1px;border-right:0;border-bottom:0}
#tape::after{bottom:-1px;right:-1px;border-left:0;border-top:0}
#tape .th{display:flex;align-items:center;gap:8px;padding:6px 11px;border-bottom:1px solid #10333f;
  font-size:9.5px;letter-spacing:2.4px;color:#5ad1e6;text-shadow:0 0 10px #38e6ff55}
#tape .th .live{margin-left:auto;color:#3d5a6b;letter-spacing:1px;display:flex;align-items:center;gap:5px}
#tape .th .live i{width:5px;height:5px;border-radius:99px;background:#3d5a6b;display:block}
#tape.busy .th .live{color:#7ff6ff}
#tape.busy .th .live i{background:#38e6ff;box-shadow:0 0 8px #38e6ff;animation:hb 1s ease-in-out infinite}
#tape .tb{overflow:auto;padding:4px 6px;scrollbar-width:thin}
#tape .tb::-webkit-scrollbar{width:5px}#tape .tb::-webkit-scrollbar-thumb{background:#12414f;border-radius:9px}
.trow{display:flex;gap:8px;align-items:baseline;padding:4px 6px;border-radius:3px;font-size:10.5px;
  border-left:2px solid #1b3d4d;margin-bottom:3px;background:#08131e66;animation:tin .35s var(--ease-out)}
@keyframes tin{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}
.trow .tt{color:#3d5a6b;font-size:9.5px;width:36px;flex:none}
.trow .ta{font-size:9px;letter-spacing:1.4px;width:62px;flex:none}
.trow .ts{color:#dff0ff;letter-spacing:1px;flex:none}
.trow .tx{color:#7d97a8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(max-width:1180px){#tape{width:min(620px,calc(100vw - 40px))}}
#toast{position:fixed;left:50%;top:13px;z-index:40;max-width:min(660px,52vw);background:#08192af5;border:1px solid #1a4a5f;border-radius:10px;padding:10px 16px;color:#dffaff;font-size:12.5px;pointer-events:none;opacity:0;transform:translateX(-50%) translateY(-6px);transition:opacity .18s var(--ease-out),transform .18s var(--ease-out)}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
</style></head>
<body>
<div id="scan"></div>
<div class="corner tl"></div><div class="corner tr"></div><div class="corner bl"></div><div class="corner br"></div>
<canvas id="wave"></canvas>

<div id="boot">
  <button id="activate" title="Encender Hydra" aria-label="Encender Hydra"></button>
</div>

<div id="top">
  <span class="brand"><svg viewBox="0 0 120 120" width="20" height="20" style="vertical-align:-4px;filter:drop-shadow(0 0 6px #38e6ff)">
    <g fill="#7ff6ff"><path fill-rule="evenodd" d="M60 5 L107.6 32.5 L107.6 87.5 L60 115 L12.4 87.5 L12.4 32.5 Z M60 17.6 L96.7 38.8 L96.7 81.2 L60 102.4 L23.3 81.2 L23.3 38.8 Z"/><path d="M60 23 L65 34.5 L60 41.5 L55 34.5 Z"/><path d="M26.5 40.5 L54 55 L54 59 L26.5 49 Z"/><path d="M93.5 40.5 L66 55 L66 59 L93.5 49 Z"/><path d="M27.5 62.5 L38 67 L38 78.5 L27.5 72 Z"/><path d="M92.5 62.5 L82 67 L82 78.5 L92.5 72 Z"/><path d="M42 62 L78 62 L78 67.5 L71.5 84 L67 68.5 L63.5 74 L60 67.5 L56.5 74 L53 68.5 L48.5 84 L42 67.5 Z"/><path d="M52 87 L56.5 81.5 L60 85.5 L63.5 81.5 L68 87 L60 96.5 Z"/></g>
  </svg> HYDRA</span>
  <span id="vstatus"></span>
  <span class="spacer"></span>
</div>

<div id="sistema">
  <div class="hd"><div class="e">⚙</div><div><h2>Sistema</h2><div class="role">Voz, acciones y configuración</div></div><div class="x" onclick="closeSistema()">✕</div></div>
  <div class="sbody">
    <div class="ssec">
      <span class="chip" id="c-mode">modo —</span>
      <span class="chip" id="c-conn">conexión —</span>
      <span class="chip" id="c-bal">balance —</span>
      <span class="chip" id="c-pb">playbook —</span>
    </div>
    <div class="slbl">VOZ</div>
    <div class="ssec">
      <button class="btn ghost" id="b-mic" title="Hablar (clic, o di “Oye Hydra”)">🎙️ Hablar</button>
      <button class="btn ghost" id="b-wake" title="Palabra mágica">👂 Oye Hydra</button>
      <button class="btn ghost" id="b-mute" title="Dejar de oír el micrófono ahora">🔇 No oír</button>
      <button class="btn ghost" id="b-clap" title="Activar aplaudiendo 2 veces">👏 Aplauso</button>
      <button class="btn ghost on" id="b-speak" title="Voz de respuesta">🔊 Voz</button>
      <button class="btn ghost on" id="b-sfx" title="Sonidos de encendido, pausa y apagado" onclick="sfxToggle()">🎛️ Sonidos</button>
    </div>
    <div class="slbl">ACCIONES</div>
    <div class="ssec">
      <button class="btn" id="b-demo">▶ Demo</button>
      <button class="btn ghost" id="b-cal">📅 Calendario</button>
      <button class="btn ghost" id="b-halt">⏸ Halt</button>
      <button class="btn ghost" id="b-refresh">⟳ Actualizar</button>
    </div>
    <div class="slbl">CONEXIÓN Y CONFIGURACIÓN</div>
    <div id="sys-info"></div>
    <div class="slbl">🤖 MIS BOTS DE CTRADER (.algo)</div>
    <div id="sys-bots"></div>
    <div class="slbl">📈 INSTRUMENTOS Y ESTRATEGIAS</div>
    <div id="sys-watch"></div>
    <div class="slbl">🔑 CLAVES (API KEYS)</div>
    <div id="sys-keys"></div>
    <div class="slbl">📓 MEMORIA (OBSIDIAN)</div>
    <div id="sys-vault"></div>
    <div class="slbl">🧪 PROPUESTAS (CLAUDE DESKTOP · MCP)</div>
    <div id="sys-props"></div>
    <div class="slbl">🏁 FLOTA DE ESTRATEGIAS</div>
    <div id="sys-fleet"></div>
  </div>
</div>

<div id="stage"><canvas id="corefx"></canvas><div id="tip"></div></div>

<div id="tape">
  <div class="th"><span>ACTIVIDAD</span><span class="live"><i></i><span id="tape-st">EN ESPERA</span></span></div>
  <div class="tb" id="tape-b"><div class="empty" style="padding:6px;font-size:10.5px">…</div></div>
</div>

<div id="colL" class="hudcol">
  <div id="hudL" class="hud">
    <div class="hudhd"><span class="dot"></span>SESIONES<span class="tf" id="hud-ses-n"></span></div>
    <div class="sesbox" id="hud-ses"></div>
  </div>
  <div id="hudCal" class="hud grow">
    <div class="hudhd"><span class="dot"></span>CALENDARIO<span class="tf" id="hud-imp"></span></div>
    <div class="hudbody" id="hud-news"><div class="empty" style="padding:8px;font-size:11px">…</div></div>
    <div class="hudfoot" onclick="openCalendar()"><span id="hud-calses">SESIÓN ACTIVA</span><span>VER TODO &#9656;</span></div>
  </div>
</div>

<div id="colR" class="hudcol">
  <div id="hudS" class="hud">
    <div class="hudhd"><span class="dot"></span>ESTADO</div>
    <div class="sysbox" id="hud-sys"></div>
  </div>
  <div id="hudP" class="hud">
    <div class="hudhd"><span class="dot"></span>OPERANDO<span class="tf" id="hud-pos-n"></span></div>
    <div class="posbox" id="hud-pos"><div class="empty" style="padding:4px 2px;font-size:10.5px">…</div></div>
  </div>
  <div id="hudB" class="hud">
    <div class="hudhd"><span class="dot"></span>CEREBRO Y VOZ</div>
    <div class="sysbox" id="hud-brain"><div class="empty" style="padding:4px 2px;font-size:10.5px">…</div></div>
  </div>
  <div id="hudBots" class="hud">
    <div class="hudhd"><span class="dot"></span>BOTS<span class="tf" id="hud-bots-n"></span></div>
    <div class="posbox" id="hud-bots"><div class="empty" style="padding:4px 2px;font-size:10.5px">…</div></div>
  </div>
  <div class="spacer-v"></div>
  <div id="hudA" class="hud">
    <div class="hudhd"><span class="dot"></span>CONFIGURACION<span class="tf" id="hud-tf"></span></div>
    <div class="sysact">
      <button class="btn ghost" id="hud-halt" onclick="doHalt()">&#9208; HALT</button>
      <button class="btn ghost" onclick="openTradeContext()">&#128452; CONTEXT</button>
      <button class="btn ghost" onclick="openCalendar()">&#128197; CALENDARIO</button>
      <button class="btn ghost" id="b-sistema" title="Voz, claves, instrumentos y flota">&#9881; SISTEMA</button>
    </div>
  </div>
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
let DATA=null, selected=null, halted=false;
let booted=false;                // false = placa apagada (pantalla de inicio)
let OPENSYMS=new Set();          // pares con posición abierta (se marcan en verde)
let INSTR=[];                    // precios de /instruments
let RING3S=[];                   // el anillo exterior tal como se dibuja
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
  {const bs=$('#b-sfx'); if(bs) bs.classList.toggle('on',sfxOn);}
  if(c.voice_enabled===false)['b-mic','b-wake','b-clap','b-speak'].forEach(id=>{const e=$('#'+id);if(e)e.style.display='none';});
  ttsServer=!!c.tts_server; if(c.owner_name)SIR=c.owner_name; if(c.owner_lang)LANG=c.owner_lang;
  renderHudSys();
}
function agentByKey(k){ return DATA?DATA.agents.find(a=>a.key===k):null; }
function openAgent(k){ selected=k; renderDrawer(k); $('#drawer').classList.add('open'); const a=agentByKey(k); if(a)speak(a.name+'. '+a.role); }
function closeDrawer(){ selected=null; $('#drawer').classList.remove('open'); }
function renderDrawer(k){ const a=agentByKey(k); if(!a)return;
  const de=$('#d-e'); de.textContent=''; try{ const ic=window.hydraIcon&&window.hydraIcon(a.key,36); if(ic)de.appendChild(ic); else de.textContent=a.emoji; }catch(_){ de.textContent=a.emoji; }
  $('#d-name').textContent=a.name; $('#d-role').textContent=a.role;
  const est={active:'ACTIVO',idle:'EN ESPERA',off:'DESACTIVADO',alert:'ALERTA'};
  let h='<span class="badge '+a.state+'">'+est[a.state]+'</span><span class="badge idle">última: '+fmtTime(a.last_ts)+'</span><ul class="feed">';
  if(!a.entries.length) h+='</ul><div class="empty">Sin actividad todavía. Escribirá aquí cuando el cerebro trabaje.</div>';
  else{ a.entries.forEach(e=>{ h+='<li><span class="t">'+fmtTime(e.ts)+'</span><span class="k">'+e.kind+(e.symbol?' · '+e.symbol:'')+'</span><div class="c">'+prettify(e.content)+'</div></li>'; }); h+='</ul>'; }
  if(a.params&&a.params.length){ h+='<div class="slbl" style="margin-top:16px">PARÁMETROS</div>';
    a.params.forEach(p=>{ h+='<div class="prm"><label>'+escapeHtml(p.label)+'</label>';
      if(p.type==='bool'){ h+='<select data-p="'+p.name+'"><option value="true"'+(p.value?' selected':'')+'>Activado</option><option value="false"'+(!p.value?' selected':'')+'>Desactivado</option></select>'; }
      else if(p.options){ h+='<select data-p="'+p.name+'">'+p.options.map(o=>'<option'+(o===p.value?' selected':'')+'>'+escapeHtml(o)+'</option>').join('')+'</select>'; }
      else { h+='<input data-p="'+p.name+'" value="'+escapeHtml(String(p.value==null?'':p.value))+'">'; }
      h+='<div class="phelp">'+escapeHtml(p.help||'')+'</div></div>'; });
    h+='<button class="btn" style="margin-top:8px" onclick="saveParams(\''+a.key+'\')">💾 Guardar cambios</button>'; }
  if(a.key==='portfolio'){ h+='<div class="slbl" style="margin-top:16px">CORRELACIONES ENTRE INSTRUMENTOS</div><div id="d-corr" class="empty">Calculando…</div>'; }
  if(a.key==='tester'){ h+='<div class="slbl" style="margin-top:16px">TU ESTRATEGIA / CBOT</div>'
    +'<textarea id="t-strat" placeholder="Pega tus reglas o describe qué hace tu cBot. Ej: Compra cuando EMA20 cruza EMA50 al alza y RSI<70; SL 1xATR; TP 2xATR. Vende en la señal inversa." style="width:100%;min-height:120px;background:#08131d;color:#dffaff;border:1px solid #17495d;border-radius:8px;padding:9px;font-family:inherit;font-size:12px"></textarea>'
    +'<div class="ssec" style="margin-top:8px"><button class="btn" onclick="saveStrategy()">💾 Guardar</button>'
    +'<button class="btn ghost" onclick="runBacktest()">▶ Probar (backtest)</button>'
    +'<button class="btn ghost" onclick="scanEntry()">🎯 Buscar entrada</button></div>'
    +'<div class="phelp">El Tester aplica TUS reglas al histórico (backtest) y al mercado actual. Necesita cTrader conectado y la key de Anthropic. Los resultados aparecen arriba en su actividad.</div>'; }
  $('#d-body').innerHTML=h;
  if(a.key==='portfolio') loadCorr();
  if(a.key==='tester') loadStrategy(); }
async function loadStrategy(){ try{ const d=await (await fetch('/tester/strategy')).json(); const t=$('#t-strat'); if(t)t.value=d.strategy||''; }catch(e){} }
async function saveStrategy(){ const t=$('#t-strat'); if(!t)return; let r; try{ r=await fetch('/tester/strategy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({strategy:t.value})}); }catch(e){ toast('Error de red'); return; } toast(r.ok?'Estrategia guardada ✓':'No se pudo guardar'); }
async function runBacktest(){ await saveStrategy(); toast('Backtest en marcha…'); speak('Probando tu estrategia, '+SIR+'.'); let r; try{ r=await fetch('/tester/backtest',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); }catch(e){ toast('Error de red'); return; } const j=await r.json().catch(()=>({})); if(!j.ok){ toast(j.reason||'No se pudo iniciar el backtest'); } else { toast('Backtest corriendo — los resultados aparecen en la actividad.'); setTimeout(load,4000); } }
async function scanEntry(){ await saveStrategy(); toast('Buscando entrada…'); let r; try{ r=await fetch('/tester/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); }catch(e){ toast('Error de red'); return; } const j=await r.json().catch(()=>({})); if(!j.ok){ toast(j.reason||'No se pudo escanear'); } else { toast('Escaneo hecho — mira su actividad.'); setTimeout(load,2500); } }
async function loadCorr(){ let d; try{ d=await (await fetch('/correlations')).json(); }catch(e){ return; } const el=$('#d-corr'); if(!el) return;
  if(!d.ok){ el.innerHTML=escapeHtml(d.reason||'No disponible.'); return; }
  if(!(d.pairs||[]).length){ el.innerHTML='Sin datos suficientes todavía.'; return; }
  let h='<div class="empty" style="margin-bottom:6px">Correlación de rendimientos ('+d.timeframe+', −1 a 1). 🔴 = muy correlacionados; Portfolio bloquea apuestas redundantes si supera '+d.max+'.</div>';
  d.pairs.slice(0,20).forEach(p=>{ const ac=Math.abs(p.corr), col=ac>=d.max?'#ff5d73':(ac>0.4?'#fbbf24':'#5f7387');
    h+='<div class="cfg"><span>'+escapeHtml(p.a)+' ↔ '+escapeHtml(p.b)+'</span> <b style="color:'+col+'">'+p.corr+'</b></div>'; });
  el.innerHTML=h; }
async function saveParams(k){ const body={}; document.querySelectorAll('#d-body [data-p]').forEach(el=>{ body[el.getAttribute('data-p')]=el.value; });
  let r; try{ r=await fetch('/agent/'+k+'/params',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); }catch(e){ toast('Error de red'); return; }
  if(r.ok){ toast('Parámetros guardados ✓'); speak('Ajustes guardados.'); load(); } else { toast('No se pudo guardar'); } }
function prettify(s){ try{ return escapeHtml(JSON.stringify(JSON.parse(s),null,1)); }catch(_){ return escapeHtml(s);} }
function escapeHtml(s){ return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function banner(c){ const b=$('#banner'); let m='';
  if(!c.has_anthropic) m='🔑 Falta la key para que los agentes piensen: <code>fly secrets set ANTHROPIC_API_KEY=sk-ant-...</code>';
  else if(!c.connected&&c.oauth_ok) m='⏳ Autorizado, conectando con cTrader…';
  b.style.display=m?'block':'none'; b.innerHTML=m; }
function toast(t){ const el=$('#toast'); el.textContent=t; el.classList.add('show'); clearTimeout(el._t); el._t=setTimeout(()=>el.classList.remove('show'),3800); }

$('#b-refresh').onclick=()=>{ toast('Datos actualizados'); load(); }; $('#b-halt').onclick=doHalt; $('#b-demo').onclick=runDemo; $('#b-cal').onclick=openCalendar;
$('#b-sistema').onclick=()=>{ renderSysInfo(); renderBots(); renderWatch(); renderSecrets(); renderVault(); renderProps(); renderFleet(); $('#sistema').classList.add('open'); };
/* ------- BOTS DE CTRADER: se importan sus parametros del .algo ------- */
let BOTSEL='', BOTQ='';
async function renderBots(){ const box=$('#sys-bots'); if(!box)return;
  let d; try{ d=await (await fetch('/algo/bots')).json(); }
  catch(e){ box.innerHTML='<div class="empty">No disponible. ¿Falta reiniciar?</div>'; return; }
  const bots=d.bots||[];
  let h='<div class="phelp">Sube tu <code>.algo</code> y Hydra lee sus <b>parámetros</b>: nombres, tipos, valores por defecto y rangos. La <b>lógica</b> vive en una DLL de .NET que solo ejecuta cTrader — eso no corre aquí.</div>';
  h+='<div id="algo-dir"></div>'
    +'<div class="phelp" style="margin-top:10px">…o sube uno a mano:</div>'
    +'<div class="wadd"><input type="file" id="algo-f" accept=".algo" '
    +'style="flex:1;background:#08131d;color:#9fe6ff;border:1px solid #17495d;border-radius:8px;padding:6px 8px;font-size:11.5px">'
    +'<button class="btn ghost" onclick="algoUp()">Importar</button></div><div id="algo-out" class="phelp"></div>';
  h+='<div class="slbl" style="margin:14px 0 4px">BOTS EN LA CUENTA (por etiqueta)</div>'
    +'<div class="phelp">Esto sale de tus operaciones reales, no del bot: funciona con <b>cualquier</b> bot sin tocarlo.</div>'
    +'<button class="btn ghost" onclick="botsLive()">⟳ Ver qué opera cada bot</button><div id="bots-live"></div>';
  if(!bots.length){ box.innerHTML=h+'<div class="empty" style="margin-top:10px">Ningún .algo importado todavía (el seguimiento por etiqueta funciona igual).</div>'; return; }
  bots.forEach(b=>{ const on=BOTSEL===b.file;
    h+='<div class="wrow" style="cursor:pointer" onclick="botOpen(\''+b.file+'\')">'
      +'<span class="wsym" style="min-width:auto">'+(on?'▾ ':'▸ ')+escapeHtml(String(b.name))+'</span>'
      +'<span class="phelp" style="margin:0;flex:1">'+b.n_params+' parámetros · '+b.n_groups+' grupos · API '+escapeHtml(String(b.api_version||'?'))+'</span>'
      +'<span class="wx" title="Quitar" onclick="event.stopPropagation();botDel(\''+b.file+'\')">✕</span></div>';
    h+='<div class="phelp" style="margin:-4px 0 4px;color:'+(b.can_report?'#34d399':'#8aa')+'">'
      +(b.can_report
        ? '✅ Este bot PUEDE reportar a Hydra. En cTrader, grupo «🌐 Backend Remoto»: activa <b>'
          +escapeHtml(String((b.remote_params||{}).enableremotelogging||'EnableRemoteLogging'))
          +'</b> y pon <b>'+escapeHtml(String((b.remote_params||{}).backendurl||'BackendUrl'))
          +'</b> = <code>'+location.origin+'</code> (solo la base).'
        : '✗ Este bot NO tiene parámetros de reporte, y no se le pueden añadir sin tocar su código. '
          +'Hydra lo seguirá igual por sus operaciones reales en la cuenta (abajo, «bots en la cuenta»).')
      +'</div>';
    if((b.chart_bound||[]).length) h+='<div class="phelp" style="color:#fbbf24;margin:-4px 0 6px">'
      +'⚠ '+b.chart_bound.length+' parámetros leen dibujos que haces A MANO en el gráfico ('
      +b.chart_bound.map(escapeHtml).join(', ')+'). Eso no existe fuera de cTrader: una réplica solo puede igualar la parte automática.</div>';
    if(on) h+='<div class="ssec" style="margin:6px 0">'
      +'<button class="btn" onclick="botExplain(false)">🧠 Explícame la estrategia</button>'
      +'<button class="btn ghost" onclick="botExplain(true)">↻ Rehacer</button>'
      +'<button class="btn ghost" onclick="replicaRun()">⚖️ ¿La replica Hydra?</button>'
      +'</div><div id="bot-expl"></div><div id="bot-repl"></div>'
      +'<div id="bot-body"><div class="empty">Cargando…</div></div>';
  });
  box.innerHTML=h;
  algoDir();
  if(BOTSEL) botBody(); }
/* La carpeta de .algo: la que ya sincronizas con GitHub, tu Mac y el VPS.
   Leerla de ahi evita subir nada y recoge sola los bots que recompiles. */
async function algoDir(){ const box=$('#algo-dir'); if(!box)return;
  let d; try{ d=await (await fetch('/algo/dir')).json(); }catch(e){ return; }
  let h='<div class="phelp" style="margin-top:8px"><b>Carpeta de tus .algo</b> — la que sincronizas con GitHub y el VPS. Hydra la lee sola.</div>'
    +'<div class="wadd"><input id="algo-d" placeholder="/Users/tu/…/cAlgo/Sources/Robots" value="'
    +escapeHtml(String(d.dir||''))+'" style="text-transform:none">'
    +'<button class="btn" onclick="algoDirSet()">Guardar</button></div>';
  if((d.guesses||[]).length){ const c=d.guess_counts||{};
    h+='<div class="phelp">Detectadas en tu Mac (pulsa para usarla):<br>'
      +d.guesses.map(g=>'<code style="cursor:pointer;display:inline-block;margin:2px 4px 2px 0" '
        +'onclick="document.querySelector(\'#algo-d\').value=\''+g.replace(/'/g,"")+'\'">'
        +escapeHtml(g)+(c[g]!=null?(' ('+c[g]+' .algo)'):'')+'</code>').join(' ')+'</div>'; }
  if(d.dir) h+='<div class="phelp" style="color:'+(d.exists?'#34d399':'#ff5d73')+'">'
    +(d.exists?('✅ '+d.n_found+' archivos .algo encontrados'):'❌ esa carpeta no existe')+'</div>';
  if(d.exists) h+='<button class="btn" onclick="algoScan()">⟳ Escanear e importar todos</button><div id="algo-scan" class="phelp"></div>';
  box.innerHTML=h; }
async function algoDirSet(){ const el=$('#algo-d'); if(!el)return;
  const r=await fetch('/algo/dir',{method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({dir:el.value})});
  const d=await r.json();
  if(!d.ok){ toast(d.error||'No pude usar esa carpeta'); return; }
  toast('Carpeta guardada'); algoDir(); }
async function algoScan(){ const box=$('#algo-scan'); if(box) box.textContent='Escaneando…';
  let d; try{ d=await (await fetch('/algo/scan',{method:'POST'})).json(); }
  catch(e){ if(box)box.textContent='Error de red.'; return; }
  if(!d.ok){ if(box){box.style.color='#ff5d73';box.textContent=d.error||'';} return; }
  const n=(d.added||[]).length+(d.updated||[]).length;
  toast(n?(n+' bots importados'):'Sin cambios');
  if(n) speak(L('Importé '+n+' bots de tu carpeta.','Imported '+n+' bots from your folder.'));
  let h='<div style="color:#34d399">'+(d.added||[]).length+' nuevos · '
    +(d.updated||[]).length+' actualizados · '+d.unchanged+' sin cambios</div>';
  (d.failed||[]).forEach(f=>{ h+='<div style="color:#ff5d73">✗ '+escapeHtml(f.file)+': '+escapeHtml(f.error)+'</div>'; });
  if(box){ box.style.color=''; box.innerHTML=h; }
  renderBots(); }
async function algoUp(){ const el=$('#algo-f'), out=$('#algo-out');
  if(!el||!el.files||!el.files[0]){ if(out)out.textContent='Elige el archivo .algo primero.'; return; }
  const f=el.files[0];
  if(out){ out.style.color='#5f7387'; out.textContent='Leyendo '+f.name+'…'; }
  let d; try{ d=await (await fetch('/algo/import',{method:'POST',body:f,
        headers:{'content-type':'application/octet-stream'}})).json(); }
  catch(e){ if(out){out.style.color='#ff5d73';out.textContent='Error de red.';} return; }
  if(!d.ok){ if(out){out.style.color='#ff5d73';out.textContent=d.error||'No pude leerlo.';} return; }
  toast(d.name+': '+d.n_params+' parámetros importados');
  speak(L('Importé '+d.n_params+' parámetros de '+d.name+'.','Imported '+d.n_params+' parameters from '+d.name+'.'));
  BOTSEL=d.bot; renderBots(); }
function botOpen(f){ BOTSEL=(BOTSEL===f?'':f); BOTQ=''; renderBots(); }
async function botDel(f){ await fetch('/algo/bots/'+encodeURIComponent(f),{method:'DELETE'});
  if(BOTSEL===f)BOTSEL=''; toast('Bot quitado'); renderBots(); }
function botFind(v){ BOTQ=v; botBody(); }
async function botBody(){ const box=$('#bot-body'); if(!box||!BOTSEL)return;
  let d; try{ d=await (await fetch('/algo/bots/'+encodeURIComponent(BOTSEL)
        +'?q='+encodeURIComponent(BOTQ))).json(); }
  catch(e){ box.innerHTML='<div class="empty">Error de red.</div>'; return; }
  let h='<div class="wadd"><input placeholder="BUSCAR PARÁMETRO (p. ej. SL, fib, sesion)" '
    +'value="'+escapeHtml(BOTQ)+'" oninput="botFind(this.value)"></div>';
  const gs=d.groups||[];
  if(!gs.length){ box.innerHTML=h+'<div class="empty">Sin coincidencias.</div>'; return; }
  gs.forEach(g=>{ h+='<div class="slbl" style="margin:12px 0 4px">'+escapeHtml(g.group)+'</div>';
    g.params.forEach(p=>{ const rng=(p.min!=null&&p.max!=null&&p.max<1e300)?(' · '+p.min+'…'+p.max):'';
      h+='<div class="cfg" style="padding:5px 2px"><span style="max-width:58%">'+escapeHtml(String(p.label))
        +'<br><code style="font-size:10px">'+escapeHtml(p.name)+'</code></span>'
        +'<b style="text-align:right">'+escapeHtml(String(p.enum?Object.keys(p.enum)[Number(p.default)]??p.default:p.default))
        +'<br><span class="phelp" style="margin:0">'+escapeHtml(String(p.type))+rng+'</span></b></div>'; }); });
  box.innerHTML=h; }
async function botsLive(){ const box=$('#bots-live'); if(!box)return;
  box.innerHTML='<div class="empty">Leyendo posiciones e histórico de la cuenta…</div>';
  let d; try{ d=await (await fetch('/bots/live?days=7')).json(); }
  catch(e){ box.innerHTML='<div class="empty" style="color:#ff5d73">Error de red.</div>'; return; }
  if(!d.ok){ box.innerHTML='<div class="empty" style="color:#fbbf24">'+escapeHtml(d.error||'')+'</div>'; return; }
  const bs=d.bots||[];
  if(!bs.length){ box.innerHTML='<div class="empty">Sin operaciones en los últimos '+d.days+' días.</div>'; return; }
  let h='<div class="phelp">'+escapeHtml(d.nota||'')+'</div>';
  bs.forEach(b=>{ const col=b.net>0?'#34d399':(b.net<0?'#ff5d73':'#9fd8ea');
    h+='<div class="wrow" style="align-items:flex-start"><span class="wsym" style="min-width:auto;max-width:52%">'
      +escapeHtml(String(b.label))+'</span>'
      +'<span style="margin-left:auto;text-align:right;font-size:11px">'
      +'<b style="color:'+col+'">'+(b.net>0?'+':'')+b.net+'</b>'
      +'<span class="phelp" style="margin:0"> '+b.open+' abiertas · '+b.closed+' cerradas'
      +(b.win_pct!=null?' · '+b.win_pct+'% aciertos':'')+'</span>'
      +'<span class="phelp" style="margin:0">'+escapeHtml((b.symbols||[]).slice(0,5).join(', '))+'</span>'
      +'</span></div>'; });
  box.innerHTML=h; }
/* Explicación de la estrategia: sirve para comprobar si el sistema la entendió. */
async function botExplain(redo){ const box=$('#bot-expl'); if(!box||!BOTSEL)return;
  box.innerHTML='<div class="empty">Leyendo los parámetros y redactando… (una vez, luego queda guardado)</div>';
  let d; try{ d=await (await fetch('/algo/bots/'+encodeURIComponent(BOTSEL)+'/explain',
        {method:'POST',headers:{'content-type':'application/json'},
         body:JSON.stringify({redo:!!redo})})).json(); }
  catch(e){ box.innerHTML='<div class="empty" style="color:#ff5d73">Error de red.</div>'; return; }
  if(!d.ok){ box.innerHTML='<div class="empty" style="color:#ff5d73">'+escapeHtml(d.error||'No pude explicarla.')+'</div>'; return; }
  box.innerHTML='<div class="phelp">'+(d.cached?'Guardada de antes. Dale a «Rehacer» para pedirla de nuevo.':'Recién hecha.')
    +' Leída SOLO de los parámetros: el código va compilado.</div>'
    +'<div style="max-height:420px;overflow:auto;border:1px solid #12303f;border-radius:8px;'
    +'padding:10px 12px;background:#050b12;font-size:12px;line-height:1.55;white-space:pre-wrap;'
    +'word-break:break-word;color:#bcd6e6">'+escapeHtml(d.explanation||'')+'</div>';
  speak(L('Listo. Revisa si entendí tu estrategia.','Done. Check whether I understood your strategy.')); }
/* Medición: ¿coinciden las señales de Hydra con las decisiones reales del bot? */
async function replicaRun(){ const box=$('#bot-repl'); if(!box)return;
  box.innerHTML='<div class="empty">Comparando capturas del bot contra las estrategias…</div>';
  let d; try{ d=await (await fetch('/replica/compare',{method:'POST',
        headers:{'content-type':'application/json'},
        body:JSON.stringify({limit:200,tolerance_bars:1})})).json(); }
  catch(e){ box.innerHTML='<div class="empty" style="color:#ff5d73">Error de red.</div>'; return; }
  if(!d.ok){ box.innerHTML='<div class="empty" style="color:#fbbf24">'+escapeHtml(d.error||'No se pudo medir.')+'</div>'; return; }
  let h='<div class="phelp">Comparadas <b>'+d.compared+'</b> decisiones reales de tu bot contra las estrategias de Hydra, sobre las MISMAS velas ('+escapeHtml(String(d.timeframe))+'). Mide si Hydra habría visto la señal, <b>no</b> si habría ganado.</div>';
  if(d.aviso) h+='<div class="phelp" style="color:#fbbf24">⚠ '+escapeHtml(d.aviso)+'</div>';
  (d.leaderboard||[]).forEach(r=>{ const pc=r.agreement_pct;
    const col=pc==null?'#5f7387':(pc>=60?'#34d399':(pc>=30?'#fbbf24':'#ff5d73'));
    h+='<div class="cfg"><span>'+escapeHtml(r.strategy)+'</span><b style="color:'+col+'">'
      +(pc==null?'—':pc+'%')+'<span class="phelp" style="margin:0"> '+r.hits+' igual · '
      +r.wrong_side+' lado contrario · '+r.misses+' sin señal</span></b></div>'; });
  const sk=d.skipped||{};
  const tot=Object.values(sk).reduce((a,b)=>a+b,0);
  if(tot) h+='<div class="phelp">Saltadas '+tot+': '+Object.entries(sk).filter(e=>e[1])
    .map(e=>e[1]+' '+e[0].replace(/_/g,' ')).join(', ')+'.</div>';
  box.innerHTML=h; }
/* Diagnóstico de la conexión: recorre la cadena y se para en el eslabón roto. */
async function ctraderDiag(){ const box=$('#sys-diag'); if(!box)return;
  box.innerHTML='<div class="empty">Revisando la cadena… (puede tardar unos segundos)</div>';
  let d; try{ d=await (await fetch('/health/ctrader')).json(); }
  catch(e){ box.innerHTML='<div class="empty" style="color:#ff5d73">No pude ejecutarlo. ¿Falta reiniciar la app?</div>'; return; }
  if(!d.steps){ box.innerHTML='<div class="empty" style="color:#ff5d73">Respuesta inesperada.</div>'; return; }
  let h='<div class="phelp" style="color:'+(d.ok?'#34d399':'#fbbf24')+'">'+escapeHtml(d.resumen||'')+'</div>';
  d.steps.forEach(s=>{
    h+='<div class="cfg" style="align-items:flex-start"><span>'+(s.ok?'✅':'❌')+' '+escapeHtml(s.paso)+'</span>'
      +'<b style="text-align:right;max-width:62%;font-weight:400;color:'+(s.ok?'#a9bcd0':'#ffb4c0')+'">'
      +escapeHtml(String(s.detalle||''))+'</b></div>';
    if(!s.ok&&s.arreglo) h+='<div class="phelp" style="color:#fbbf24;margin:-2px 0 8px">↳ '+escapeHtml(s.arreglo)+'</div>';
  });
  box.innerHTML=h; }
/* ------- INSTRUMENTOS Y ESTRATEGIAS: añadir, quitar y asignar en los dos sentidos ------- */
let WATCH=null, WVIEW='sym';
async function renderWatch(){ const box=$('#sys-watch'); if(!box)return;
  try{ WATCH=await (await fetch('/watchlist')).json(); }
  catch(e){ box.innerHTML='<div class="empty">No se pudo cargar. ¿Falta redesplegar?</div>'; return; }
  const av=WATCH.available||[], rows=WATCH.symbols||[];
  let h='<div class="phelp">Elige QUÉ vigila Hydra y CON QUÉ estrategia. Sin estrategia marcada, ese instrumento prueba <b>todas</b>. Esto manda en la flota de pruebas; las entradas en vivo las sigue proponiendo el Analyst.</div>';
  h+='<div class="ssec" style="margin:10px 0">'
    +'<button class="btn '+(WVIEW==='sym'?'':'ghost')+'" style="padding:5px 10px" onclick="wView(\'sym\')">Por instrumento</button>'
    +'<button class="btn '+(WVIEW==='str'?'':'ghost')+'" style="padding:5px 10px" onclick="wView(\'str\')">Por estrategia</button></div>';
  if(WVIEW==='sym'){
    rows.forEach(r=>{ const on=r.strategies||[];
      if(r.fixed){    // referencia fija: ni se quita ni se le asignan estrategias
        h+='<div class="wrow" style="opacity:.72"><span class="wsym">'+escapeHtml(r.symbol)+'</span>'
          +'<span class="phelp" style="margin:0;flex:1">'+escapeHtml(r.note||'referencia')+'</span>'
          +'<span class="wx" title="Fijo: siempre vigilado" style="cursor:default">🔒</span></div>';
        return; }
      h+='<div class="wrow"><span class="wsym">'+escapeHtml(r.symbol)+'</span>'
        +av.map(a=>'<span class="chip2'+(on.indexOf(a.id)>=0?' on':'')+'" title="'+escapeHtml(JSON.stringify(a.params))
          +'" onclick="wTog(\''+r.symbol+'\',\''+a.id+'\')">'+escapeHtml(a.label)+'</span>').join('')
        +'<span class="wx" title="Quitar" onclick="wDel(\''+r.symbol+'\')">✕</span></div>'; });
    const list=(WATCH.broker_symbols||[]);
    h+='<div class="wadd"><input id="w-new" placeholder="AÑADIR (p. ej. EURUSD)"'
      +(list.length?' list="w-syms"':'')+' onkeydown="if(event.key===\'Enter\')wAdd()">'
      +'<button class="btn" onclick="wAdd()">＋</button></div>';
    if(list.length) h+='<datalist id="w-syms">'+list.map(x=>'<option value="'+escapeHtml(x)+'">').join('')+'</datalist>';
    else h+='<div class="phelp">Conecta cTrader para que te sugiera los nombres exactos de tu broker.</div>';
  } else {
    av.forEach(a=>{ h+='<div class="wrow" style="align-items:flex-start"><span class="wsym" style="padding-top:3px">'+escapeHtml(a.label)+'</span>'
      +'<span style="display:flex;gap:6px;flex-wrap:wrap;flex:1">'
      +rows.filter(r=>!r.fixed).map(r=>'<span class="chip2'+((r.strategies||[]).indexOf(a.id)>=0?' on':'')
        +'" onclick="wTog(\''+r.symbol+'\',\''+a.id+'\')">'+escapeHtml(r.symbol)+'</span>').join('')
      +'</span></div>'; });
    h+='<div class="phelp">Toca un instrumento para meterlo o sacarlo de esa estrategia.</div>';
  }
  box.innerHTML=h; }
function wView(v){ WVIEW=v; renderWatch(); }
async function wTog(sym,strat){ if(!WATCH)return;
  const r=(WATCH.symbols||[]).find(x=>x.symbol===sym); if(!r)return;
  const cur=(r.strategies||[]).slice(), i=cur.indexOf(strat);
  if(i>=0) cur.splice(i,1); else cur.push(strat);
  r.strategies=cur; renderWatch();                       // respuesta inmediata
  try{ await fetch('/watchlist/strategies',{method:'POST',headers:{'content-type':'application/json'},
        body:JSON.stringify({symbol:sym,strategies:cur})}); }
  catch(e){ toast('No se pudo guardar'); }
  renderWatch(); }
async function wAdd(){ const el=$('#w-new'); const v=(el&&el.value||'').trim().toUpperCase(); if(!v)return;
  const r=await fetch('/watchlist',{method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({add:v})});
  const d=await r.json();
  if(!d.ok){ toast(d.error||'No se pudo añadir'); return; }
  toast(v+' añadido'); speak(L(v+' añadido a la vigilancia.',v+' added to the watchlist.'));
  el.value=''; renderWatch(); load(); pollInstruments(); }
async function wDel(sym){ const r=await fetch('/watchlist',{method:'POST',
    headers:{'content-type':'application/json'},body:JSON.stringify({remove:sym})});
  const d=await r.json();
  if(!d.ok){ toast(d.error||'No se pudo quitar'); return; }
  toast(sym+' fuera de la vigilancia'); renderWatch(); load(); pollInstruments(); }
async function renderFleet(){ let d; try{ d=await (await fetch('/fleet')).json(); }catch(e){ $('#sys-fleet').innerHTML='<div class="empty">Falta redesplegar.</div>'; return; }
  const lb=d.leaderboard||[];
  let h='<div class="phelp">N estrategias corriendo en paralelo en <b>papel</b>. El 👑 <b>champion</b> nunca se ajusta: es el control. Si las variantes no le ganan, la «mejora» era ruido. Todo el R es <b>neto de costos</b>.</div>';
  h+='<button class="btn" onclick="fleetSeed()">➕ Crear flota</button> '
    +'<button class="btn ghost" onclick="fleetCycle()">▶ Correr ciclo</button>'
    +(lb.length?' <button class="btn ghost" onclick="fleetClear()">🗑 Borrar</button>':'')+'<div id="fl-out"></div>';
  if(!lb.length){ h+='<div class="empty">Flota vacía. Dale a «Crear flota».</div>'; $('#sys-fleet').innerHTML=h; return; }
  h+='<div style="overflow-x:auto;margin-top:8px"><table style="width:100%;border-collapse:collapse;font-size:12px">'
    +'<tr style="opacity:.6;text-align:right"><th style="text-align:left">Arm</th><th>Ops</th><th>R neto</th><th>Edge</th><th>Costo</th><th>Win%</th><th>vs 👑</th></tr>';
  lb.forEach(r=>{ const vs=(r.vs_champion==null)?'—':(r.vs_champion>=0?'+':'')+r.vs_champion.toFixed(1);
    const col=r.sum_net>=0?'#34d399':'#ff5d73';
    h+='<tr style="text-align:right;border-top:1px solid #ffffff12">'
      +'<td style="text-align:left">'+(r.is_champion?'👑 ':'')+escapeHtml(r.name)+'</td>'
      +'<td>'+r.trades+'</td><td style="color:'+col+'"><b>'+r.sum_net.toFixed(1)+'</b></td>'
      +'<td>'+r.edge_net.toFixed(3)+'</td><td style="opacity:.6">'+r.cost_drag.toFixed(3)+'</td>'
      +'<td>'+r.win_rate.toFixed(0)+'</td><td style="color:'+(r.vs_champion>0?'#34d399':'#8aa')+'">'+vs+'</td></tr>'; });
  h+='</table></div>';
  const rv=d.reviews||[];
  if(rv.length){ h+='<div class="phelp" style="margin-top:8px">Últimas revisiones:</div>';
    rv.slice(0,6).forEach(r=>{ const ok=r.verdict==='no_change';
      h+='<div class="cfg" style="align-items:flex-start"><span>'+escapeHtml(r.arm)+'</span> <b style="color:'+(ok?'#8aa':'#fbbf24')+'">'+escapeHtml(r.verdict)+' '+(r.confidence||0)+'%</b></div>'
        +'<div class="phelp" style="margin:-6px 0 6px">'+escapeHtml((r.reasoning||'').slice(0,180))+'</div>'; }); }
  $('#sys-fleet').innerHTML=h; }
async function fleetSeed(){ if(!confirm('Crear la flota? Si ya existe una, se reemplaza.')) return;
  $('#fl-out').innerHTML='<div class="empty">Creando…</div>';
  const r=await fetch('/fleet/seed',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reset:true,per_strategy:5})});
  const j=await r.json().catch(()=>({})); toast(j.ok?('Flota creada: '+j.created+' arms'):'No se pudo'); renderFleet(); }
async function fleetCycle(){ $('#fl-out').innerHTML='<div class="empty">Corriendo ciclo… (lee velas, simula y revisa)</div>';
  let j; try{ j=await (await fetch('/fleet/cycle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:40})})).json(); }catch(e){ $('#fl-out').innerHTML='<div class="empty" style="color:#ff5d73">Error de red.</div>'; return; }
  if(!j.ok){ $('#fl-out').innerHTML='<div class="empty" style="color:#fbbf24">'+escapeHtml(j.error||'falló')+'</div>'; return; }
  $('#fl-out').innerHTML='<div class="phelp">+'+j.new_trades+' operaciones · '+(j.reviews||[]).length+' revisiones</div>';
  speak(L('Ciclo de flota terminado, '+SIR+'.','Fleet cycle done, '+SIR+'.')); renderFleet(); }
async function fleetClear(){ if(!confirm('Borrar la flota y todo su historial?')) return;
  await fetch('/fleet/clear',{method:'POST'}); toast('Flota borrada'); renderFleet(); }
async function renderProps(){ let d; try{ d=await (await fetch('/proposals')).json(); }catch(e){ $('#sys-props').innerHTML='<div class="empty">Falta redesplegar.</div>'; return; }
  const m=d.metrics||{}, counts=m.counts||[];
  let h='<div class="phelp">Claude Desktop analiza Hydra por MCP y propone ajustes aquí. <b>Nada se aplica solo</b>: tú apruebas o rechazas.</div>';
  const tot=counts.reduce((a,c)=>a+c.count,0);
  h+='<div class="cfg"><span>Post-mortems</span> <b>'+tot+'</b> · umbral para hipótesis: '+(m.threshold||30)+'</div>';
  if(counts.length) h+=counts.map(c=>'<div class="cfg"><span>'+escapeHtml(c.category)+'</span> <b>'+c.count+(c.count>=(m.threshold||30)?' ✅':'')+'</b></div>').join('');
  const pend=d.pending||[];
  if(!pend.length) h+='<div class="empty">Sin propuestas pendientes.</div>';
  pend.forEach(p=>{ h+='<div class="prm"><label>Propuesta #'+p.id+'</label>'
    +'<div class="empty" style="color:#cfe8ff;white-space:pre-wrap">'+escapeHtml(p.changes)+'</div>'
    +'<div class="phelp">'+escapeHtml(p.rationale||'')+'</div>'
    +'<button class="btn" onclick="decideProp('+p.id+',true)">✓ Aprobar</button> '
    +'<button class="btn ghost" onclick="decideProp('+p.id+',false)">✕ Rechazar</button></div>'; });
  const hyp=d.hypotheses||[];
  if(hyp.length){ h+='<div class="phelp" style="margin-top:8px">Hipótesis abiertas:</div>'
    +hyp.map(x=>'<div class="cfg"><span>'+escapeHtml(x.param||x.category||'—')+'</span> <b>'+escapeHtml((x.description||'').slice(0,80))+'</b></div>').join(''); }
  $('#sys-props').innerHTML=h; }
async function decideProp(id,ok){ if(ok&&!confirm('Aplicar este cambio de parámetros a Hydra?')) return;
  let r; try{ r=await fetch('/proposals/'+id+'/decide',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approve:ok})}); }catch(e){ toast('Error de red'); return; }
  const j=await r.json().catch(()=>({}));
  if(j.ok){ toast(ok?'Aplicado ✓':'Rechazado'); speak(L(ok?'Cambio aplicado, '+SIR+'.':'Propuesta rechazada, '+SIR+'.',ok?'Change applied, '+SIR+'.':'Proposal rejected, '+SIR+'.')); renderProps(); load(); }
  else toast(j.error||'No se pudo'); }
async function renderVault(){ let d; try{ d=await (await fetch('/vault')).json(); }catch(e){ $('#sys-vault').innerHTML='<div class="empty">Falta redesplegar para activar la memoria.</div>'; return; }
  const n=(d.stats&&d.stats.notes)||0;
  let h='<div class="cfg"><span>Notas guardadas</span> <b>'+n+'</b> · <a href="/vault/export" style="color:#7ff6ff">⬇ descargar vault (.zip)</a></div>';
  h+='<div class="phelp">Hydra guarda aquí todo lo que aprende (revisiones, playbook, investigación) en Markdown con tags y [[enlaces]]. Descarga el zip y ábrelo como vault en <b>Obsidian</b> (o suéltalo dentro de tu vault).</div>';
  h+='<div class="prm"><label>🔎 Preguntar al investigador (Perplexity)</label><input id="rsq" placeholder="ej. ¿qué mueve al oro hoy?" onkeydown="if(event.key===\'Enter\')doResearch()"></div>';
  h+='<button class="btn ghost" onclick="doResearch()">Investigar</button><div id="rsout"></div>';
  const recent=(d.notes||[]).slice(0,6);
  if(recent.length){ h+='<div class="phelp" style="margin-top:8px">Recientes:</div>'+recent.map(x=>'<div class="cfg"><span>'+escapeHtml(x.folder||'nota')+'</span> <b>'+escapeHtml(x.name)+'</b></div>').join(''); }
  $('#sys-vault').innerHTML=h; }
async function doResearch(){ const el=$('#rsq'); const q=(el&&el.value||'').trim(); if(!q){ toast('Escribe una pregunta'); return; }
  $('#rsout').innerHTML='<div class="empty">Investigando…</div>';
  let r,j; try{ r=await fetch('/research',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:q})}); j=await r.json(); }catch(e){ $('#rsout').innerHTML='<div class="empty" style="color:#ff5d73">Error de red.</div>'; return; }
  if(!j.ok){ $('#rsout').innerHTML='<div class="empty" style="color:#fbbf24">'+escapeHtml(j.error||'No disponible')+'</div>'; return; }
  $('#rsout').innerHTML='<div class="empty" style="white-space:pre-wrap;color:#cfe8ff">'+escapeHtml(j.text)+'</div><div class="phelp">Guardado en tu memoria 📓</div>';
  speak(L('Listo, '+SIR+'. Guardé la investigación en tu memoria.','Done, '+SIR+'. Saved the research to your memory.')); }
function closeSistema(){ $('#sistema').classList.remove('open'); }
async function setLang(lg){ try{ await fetch('/lang',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lang:lg})}); }catch(e){} LANG=lg;
  if(recog){ try{ recog.lang=voiceLang(); if(running)recog.stop(); }catch(_){} }
  toast(L('Idioma: '+({es:'Español',mix:'Español + inglés',en:'English'}[lg]), 'Language: '+({es:'Spanish',mix:'Spanish + English',en:'English'}[lg])));
  speak(L('Listo, hablaré así.','Done, I will speak like this.')); renderSysInfo(); }
const MODELS=[
  {id:'claude-haiku-4-5-20251001',label:'Haiku',hint:'el más barato (~20-30x menos que Opus)'},
  {id:'claude-sonnet-5',label:'Sonnet',hint:'balance costo/calidad (recomendado)'},
  {id:'claude-opus-4-8',label:'Opus',hint:'el más capaz y el más caro'}];
async function setModel(id){ const m=MODELS.find(x=>x.id===id)||{label:id};
  let r; try{ r=await fetch('/model',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:id})}); }catch(e){ toast('Error de red'); return; }
  if(r.ok){ toast('Modelo IA: '+m.label+' ✓'); speak(L('Cambié el modelo a '+m.label+', '+SIR+'.','Switched the model to '+m.label+', '+SIR+'.')); load(); setTimeout(renderSysInfo,600); }
  else if(r.status===404){ toast('Falta redesplegar: git pull && fly deploy.'); }
  else { toast('No se pudo cambiar el modelo'); } }
async function renderSecrets(){ let d; try{ d=await (await fetch('/secrets')).json(); }catch(e){ $('#sys-keys').innerHTML='<div class="empty">No disponible.</div>'; return; }
  let h='';
  if(!d.master_key){ const local=/^(localhost|127\.0\.0\.1)/.test(location.host);
    h+='<div class="empty" style="text-align:left">🔒 Los campos están bloqueados porque falta la <b>llave maestra</b> que cifra tus claves.'
      +(local
        ?'<br><br>Estás en <b>local</b>. Genera una y guárdala en tu <code>.env</code>:<br>'
         +'<code style="display:block;margin:6px 0;white-space:pre-wrap">cd ~/Hydra-Trading\necho "APP_SECRET_KEY=$(python3 -c \'import secrets;print(secrets.token_urlsafe(48))\')" >> .env\nlaunchctl kickstart -k gui/$(id -u)/com.hydra.trading</code>'
         +'Recarga esta página y ya podrás escribir.<br><br><span style="opacity:.7">Alternativa: si prefieres, pon las claves directo en el <code>.env</code> (una por línea, p.ej. <code>ANTHROPIC_API_KEY=…</code>) y sáltate este panel.</span>'
        :'<br><br>En Fly:<br><code style="display:block;margin:6px 0">fly secrets set APP_SECRET_KEY=una-frase-larga-secreta</code>y redespliega.')
      +'</div>'; }
  (d.items||[]).forEach(it=>{ h+='<div class="prm"><label>'+escapeHtml(it.label)+' '+(it.set?'<span style="color:#34d399">'+escapeHtml(it.hint)+'</span>':'<span style="color:#ff5d73">falta</span>')+'</label>';
    h+='<input type="password" autocomplete="new-password" data-s="'+it.name+'" placeholder="'+(it.set?'nueva clave (vacío = sin cambio)':'pega la clave')+'"'+(d.master_key?'':' disabled')+'></div>'; });
  if(d.master_key) h+='<button class="btn" style="margin-top:6px" onclick="saveSecrets()">🔒 Guardar claves</button>';
  $('#sys-keys').innerHTML=h; }
async function saveSecrets(){ const els=document.querySelectorAll('#sys-keys [data-s]'); let n=0;
  for(const el of els){ const v=(el.value||'').trim(); if(!v)continue;
    try{ const r=await fetch('/secrets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:el.getAttribute('data-s'),value:v})}); if(r.ok)n++; el.value=''; }catch(e){} }
  toast(n?('Guardadas '+n+' clave(s) 🔒'):'Sin cambios'); renderSecrets(); }
function renderSysInfo(){ if(!DATA){ $('#sys-info').innerHTML='<div class="empty">Cargando…</div>'; return; } const c=DATA.core;
  const conn=c.connected?'<b style="color:#34d399">conectado</b>':(c.oauth_ok?'<b style="color:#fbbf24">autorizado, conectando…</b>':'<b style="color:#ff5d73">sin conexión</b>');
  let h='<div class="cfg"><span>cTrader</span> '+conn+'</div>';
  if(c.connected&&c.account_id) h+='<div class="cfg"><span>Cuenta activa</span> <b>#'+c.account_id+' · '+((c.ctrader_env||'demo').toUpperCase())+'</b></div>';
  if(c.connected&&c.balance_error) h+='<div class="empty" style="color:#fbbf24">Balance no disponible: '+escapeHtml(c.balance_error)+'</div>';
  if(!c.connected&&c.oauth_ok&&c.conn_error){
    const ssl=/CERTIFICATE_VERIFY_FAILED|SSLCertVerification/i.test(c.conn_error);
    h+='<div class="empty" style="color:#ff5d73">No conecta: '+escapeHtml(c.conn_error)+'</div>'
      +'<div class="phelp" style="color:#fbbf24">'+(ssl
        ? 'Faltan las raíces de confianza de Python (no usa el llavero de macOS). Arréglalo con:<br>'
          +'<code>cd ~/Hydra-Trading &amp;&amp; .venv/bin/pip install -U certifi</code><br>y reinicia la app.'
        : 'Revisa que el entorno (DEMO/LIVE) coincida con la cuenta.')+'</div>';
  }
  if(!c.oauth_ok) h+='<a class="btn" href="/oauth/login" style="display:inline-block;margin:10px 0;text-decoration:none">🔌 Conectar mi cuenta de cTrader</a>';
  if(c.oauth_ok) h+='<a class="btn ghost" href="/oauth/login" style="display:inline-block;margin:8px 0;text-decoration:none">🔄 Reconectar cTrader (actualizar cuentas)</a>';
  if(c.oauth_ok) h+='<div id="sys-accounts" class="empty">Cargando cuentas…</div>';
  h+='<button class="btn ghost" onclick="ctraderDiag()">🩺 Diagnóstico cTrader</button><div id="sys-diag"></div>';
  h+='<div class="cfg"><span>Modelo IA</span> <span>'+MODELS.map(m=>'<button class="btn ghost'+((c.model||'')===m.id?' on':'')+'" style="padding:5px 9px;margin-left:5px" title="'+m.hint+'" onclick="setModel(\''+m.id+'\')">'+m.label+'</button>').join('')+'</span></div>';
  h+='<div class="phelp" style="margin:-4px 0 8px">'+((MODELS.find(m=>m.id===(c.model||''))||{}).hint||'')+'. Menos capaz = más barato. El costo se reduce también subiendo <b>«analiza cada (min)»</b> del agente Analista.</div>';
  h+='<div id="sys-local"></div>';
  h+='<div class="cfg"><span>Voz neural</span> <b>'+(c.tts_server?'activa ✅':'navegador')+'</b> · <a href="/tts/health" target="_blank" style="color:#7ff6ff">diagnóstico</a></div>';
  h+='<div id="sys-voice"></div>';
  h+='<div class="cfg"><span>Te llama</span> <b>'+(c.owner_name||'Krauser')+'</b></div>';
  h+='<div class="cfg"><span>Idioma</span> <span>'+['es','mix','en'].map(lg=>'<button class="btn ghost'+((c.owner_lang||'mix')===lg?' on':'')+'" style="padding:5px 9px;margin-left:5px" onclick="setLang(\''+lg+'\')">'+({es:'ES',mix:'ES+EN',en:'EN'}[lg])+'</button>').join('')+'</span></div>';
  h+='<div class="cfg"><span>Anthropic key</span> <b>'+(c.has_anthropic?'puesta ✅':'falta ❌')+'</b></div>';
  h+='<div class="empty" style="margin-top:12px">Los ajustes se cambian con <code>fly secrets set …</code> y luego <code>fly deploy</code>.</div>';
  $('#sys-info').innerHTML=h;
  renderLocal(); renderVoice();
  if(c.oauth_ok) loadAccounts(); }
async function renderVoice(){ const el=$('#sys-voice'); if(!el) return;
  let d; try{ const r=await fetch('/voice/local'); if(!r.ok) throw 0; d=await r.json(); }
  catch(e){ el.innerHTML='<div class="phelp" style="color:#fbbf24">Selector de voz no disponible — la app corre código viejo. Reinicia:<br><code>launchctl kickstart -k gui/$(id -u)/com.hydra.trading</code></div>'; return; }
  const P=d.provider||'';
  const opt=(id,txt,tip)=>'<button class="btn ghost'+(P===id?' on':'')+'" style="padding:5px 9px;margin-right:5px" title="'+tip+'" onclick="setVoice(\''+id+'\')">'+txt+'</button>';
  let h='<div style="margin:2px 0 6px">'
    +opt('','🌐 Navegador','La voz del sistema. Gratis.')
    +opt('voicebox','🎙️ Voicebox','Voz local clonada. Gratis, sin API key.')
    +opt('elevenlabs','☁️ ElevenLabs','De pago, requiere API key.')+'</div>';
  if(!d.running) h+='<div class="phelp" style="color:#fbbf24">Voicebox no responde en '+escapeHtml(d.url||'')+'. <b>La app debe estar abierta</b> — el servidor corre dentro de ella.</div>';
  else { h+='<div class="phelp" style="color:#34d399">Voicebox activo ✅ — voz local, gratis e ilimitada.</div>';
    const pr=d.profiles||[];
    if(pr.length) h+='<div class="prm"><label>Voz</label><select onchange="setVoice(\''+P+'\',this.value)">'
      +pr.map(p=>'<option'+(p.name===d.selected?' selected':'')+'>'+escapeHtml(p.name)+'</option>').join('')+'</select>'
      +'<div class="phelp">'+pr.map(p=>escapeHtml(p.name)+' ('+escapeHtml(p.language||'?')+')').join(' · ')+'</div></div>'; }
  el.innerHTML=h; }
async function setVoice(p,prof){ let r; try{ r=await fetch('/voice/local',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:p,profile:prof||undefined})}); }catch(e){ toast('Error de red'); return; }
  if(r.ok){ ttsServer=(p!==''); toast(p==='voicebox'?'Voz local ✓ (gratis)':(p?'Voz: '+p:'Voz del navegador'));
    renderVoice(); setTimeout(()=>speak(L('Listo '+SIR+', esta es mi voz.','Ready '+SIR+', this is my voice.')),400); }
  else toast('Falta redesplegar'); }
async function renderLocal(){ const el=$('#sys-local'); if(!el) return;
  let d; try{ d=await (await fetch('/llm/local')).json(); }catch(e){ el.innerHTML=''; return; }
  const P=d.provider||'anthropic';
  const opt=(id,txt,tip)=>'<button class="btn ghost'+(P===id?' on':'')+'" style="padding:5px 9px;margin-right:5px" title="'+tip+'" onclick="setProvider(\''+id+'\')">'+txt+'</button>';
  let h='<div class="cfg"><span>Cerebro</span></div><div style="margin:2px 0 6px">'
    +opt('anthropic','☁️ Nube','Todo con Claude. Sin instalar nada.')
    +opt('hybrid','⚡ Híbrido','El volumen en local (gratis), el juicio con Claude. Recomendado.')
    +opt('ollama','💻 Local','Todo en tu Mac. Costo cero.')+'</div>';
  if(!d.running){
    if(d.installed){   // está instalado pero apagado: se enciende desde aquí
      h+='<div class="phelp" style="color:#fbbf24">Cerebro local apagado. Enciéndelo sin abrir la terminal:</div>'
        +'<button class="btn" id="ol-go" onclick="startLocal()">▶ Encender cerebro local</button>'
        +'<div id="ol-out" class="phelp"></div>'
        +'<div class="phelp">Para que arranque solo al encender el Mac:<br>'
        +'<code>bash scripts/install-ollama-service.sh</code></div>';
    } else {
      h+='<div class="phelp" style="color:#fbbf24">Ollama no responde en '+escapeHtml(d.url||'')
        +'. Bájalo en <b>ollama.com</b>, ábrelo (queda en la barra de arriba) y corre <code>ollama pull qwen3:8b</code>.</div>';
    }
  }
  else { h+='<div class="phelp" style="color:#34d399">Ollama activo ✅ — lo que corra en local es gratis e ilimitado.</div>';
    if((d.models||[]).length) h+='<div class="prm"><label>Modelo local</label><select id="olm" onchange="setProvider(\''+P+'\',this.value)">'
      +d.models.map(m=>'<option'+(m===d.selected?' selected':'')+'>'+escapeHtml(m)+'</option>').join('')+'</select></div>';
    h+='<button class="btn ghost" onclick="testLocal()">🧪 Probar modelo</button><div id="lm-test"></div>'; }
  const rt=d.routing||[];
  if(rt.length){ h+='<div class="phelp" style="margin-top:6px">Quién usa qué:</div>'
    +rt.map(r=>'<div class="cfg"><span>'+escapeHtml(r.label)+' <span style="opacity:.55">· '+escapeHtml(r.why)+'</span></span> <b style="color:'+(r.brain==='ollama'?'#34d399':'#7ff6ff')+'">'+(r.brain==='ollama'?'💻 local':'☁️ Claude')+'</b></div>').join(''); }
  el.innerHTML=h; }
async function startLocal(){ const b=$('#ol-go'), o=$('#ol-out');
  if(b){ b.disabled=true; b.textContent='Encendiendo…'; }
  if(o) o.textContent='';
  let d; try{ d=await (await fetch('/llm/local/start',{method:'POST'})).json(); }
  catch(e){ if(o){o.style.color='#ff5d73';o.textContent='Error de red.';}
            if(b){b.disabled=false;b.textContent='▶ Encender cerebro local';} return; }
  if(d.running){ toast('Cerebro local encendido ✅');
    speak(L('Cerebro local encendido, '+SIR+'.','Local brain online, '+SIR+'.'));
    renderLocal(); pollBrain(); return; }
  if(o){ o.style.color=d.ok?'#fbbf24':'#ff5d73'; o.textContent=d.message||d.error||'No pude encenderlo.'; }
  if(b){ b.disabled=false; b.textContent='▶ Reintentar'; }
  if(d.ok) setTimeout(()=>{ renderLocal(); pollBrain(); },6000); }
async function testLocal(){ const o=$('#lm-test'); if(o) o.innerHTML='<div class="empty">Probando… (la primera vez tarda: carga el modelo en memoria)</div>';
  let j; try{ j=await (await fetch('/llm/test',{method:'POST'})).json(); }catch(e){ o.innerHTML='<div class="empty" style="color:#ff5d73">Error de red.</div>'; return; }
  if(j.ok){ const g=j.good_judgement;
    o.innerHTML='<div class="phelp" style="color:#34d399">✅ '+escapeHtml(j.model)+' respondió en <b>'+j.seconds+'s</b> con JSON válido.</div>'
      +'<div class="phelp" style="color:'+(g?'#34d399':'#fbbf24')+'">'+(g?'🎯 Buen criterio':'⚠️ Criterio flojo')
      +' — dijo <b>'+escapeHtml(j.reply.verdict||'')+'</b> ('+(j.reply.confidence||0)+'%), lo correcto era <b>'+escapeHtml(j.expected)+'</b>.'
      +(g?' Vio que el edge bruto ya era negativo.':' Se dejó llevar por el 67% de salidas por SL sin mirar que el edge bruto ya era negativo — mover el stop no crea una ventaja que no existe.')+'</div>'
      +'<div class="phelp" style="opacity:.7;white-space:pre-wrap">'+escapeHtml((j.reply.reasoning||'').slice(0,260))+'</div>'; }
  else o.innerHTML='<div class="phelp" style="color:#ff5d73">❌ '+escapeHtml(j.error||'falló')+'</div>'; }
async function setProvider(p,m){ let r; try{ r=await fetch('/llm/local',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:p,ollama_model:m||undefined})}); }catch(e){ toast('Error de red'); return; }
  if(r.ok){ toast(p==='ollama'?'Cerebro local ✓ (gratis)':'Cerebro en la nube ✓'); speak(L(p==='ollama'?'Cambié al cerebro local, '+SIR+'. Ya no gasta créditos.':'Cerebro en la nube, '+SIR+'.','Switched brain, '+SIR+'.')); renderLocal(); load(); }
  else toast('Falta redesplegar'); }
async function loadAccounts(){ let d; try{ d=await (await fetch('/accounts')).json(); }catch(e){ return; }
  const el=$('#sys-accounts'); if(!el) return;
  if(!d.ok||!(d.accounts||[]).length){ el.innerHTML='No pude listar tus cuentas'+(d&&d.reason?': '+escapeHtml(d.reason):'.'); return; }
  const opts=d.accounts.map(a=>'<option value="'+a.id+'" data-env="'+(a.live?'live':'demo')+'"'+(a.id==d.current?' selected':'')+'>#'+a.id+' · '+(a.live?'LIVE ⚠️':'DEMO')+(a.login?' · login '+a.login:'')+'</option>').join('');
  el.innerHTML='<div class="prm"><label>Cuenta que usa Hydra</label><select id="acc-sel">'+opts+'</select>'
    +'<div class="phelp">Elige tu cuenta. Usa una <b>DEMO</b> para practicar; LIVE opera con dinero real.</div></div>'
    +'<button class="btn" onclick="selectAccount()">✓ Usar esta cuenta</button>'; }
async function selectAccount(){ const sel=$('#acc-sel'); if(!sel) return; const o=sel.options[sel.selectedIndex]; const id=+o.value, env=o.getAttribute('data-env');
  if(env==='live' && !confirm('⚠️ Es una cuenta REAL (LIVE): opera con dinero real. Para practicar usa una DEMO. ¿Continuar?')) return;
  toast('Cambiando de cuenta…');
  let r; try{ r=await fetch('/account/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,env:env})}); }catch(e){ toast('Error de red'); return; }
  if(r.ok){ toast('Cuenta seleccionada ✓ conectando…'); speak('Cuenta cambiada, '+SIR+'. Conectando.'); setTimeout(load,2500); setTimeout(()=>{renderSysInfo();},3000); }
  else if(r.status===404){ toast('Falta redesplegar: git pull && fly deploy (el selector aún no está en tu app).'); }
  else { let m='No se pudo cambiar'; try{ const j=await r.json(); if(j&&(j.error||j.detail)) m+=': '+(j.error||j.detail); }catch(_){} toast(m); } }
async function doHalt(){ const halt=$('#b-halt').textContent.includes('HALT');
  if(halt) sfxOff(); else sfxBoot();          // el sonido va ANTES: se siente inmediato
  await fetch(halt?'/halt':'/resume',{method:'POST'});
  toast(halt?'Sistema DETENIDO':'Sistema reanudado');
  speak(halt?'Sistema detenido, '+SIR+'.':'Sistema reanudado, '+SIR+'.'); load(); }
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
async function runDemo(){ toast('Corriendo demo…'); speak(L('Ejecutando análisis de demostración.','Running the demo analysis.'));
  let r; try{ r=await fetch('/demo',{method:'POST'}); }catch(e){ toast('Error de red'); return; }
  if(!r.ok){ const t=await r.text(); openInfo('▶ Modo demo','<p style="color:#ff5d73">No se pudo correr el demo.</p><p>'+escapeHtml(t)+'</p><p>Configura la key: <code>fly secrets set ANTHROPIC_API_KEY=sk-ant-...</code></p>'); speak('No pude correr el demo. Falta la clave de Anthropic.'); return; }
  const data=await r.json(); renderDemo(data.results); load();
  const props=data.results.filter(x=>x.proposal.action==='propose').length; speak('Análisis completo, '+SIR+'. '+props+' de '+data.results.length+' símbolos con oportunidad.'); }
function openInfo(t,h){ selected=null; $('#d-e').textContent='ℹ️'; $('#d-name').textContent=t; $('#d-role').textContent=''; $('#d-body').innerHTML=h; $('#drawer').classList.add('open'); }
async function openMarket(sym,tf){ selected=null; tf=tf||(DATA&&DATA.core&&DATA.core.timeframe)||'M15';
  const de=$('#d-e'); de.textContent=''; try{ const ic=window.marketCoin&&window.marketCoin(sym,38); if(ic)de.appendChild(ic); else de.textContent='📈'; }catch(_){ de.textContent='📈'; }
  $('#d-name').textContent=(sym==='DXY'?'DXY · '+L('Índice del dólar','Dollar Index'):sym); $('#d-role').textContent=L('Resumen técnico','Technical summary'); $('#d-body').innerHTML='<div class="empty">Cargando…</div>'; $('#drawer').classList.add('open');
  let d; try{ d=await (await fetch('/market/'+encodeURIComponent(sym)+'?tf='+encodeURIComponent(tf))).json(); }catch(e){ $('#d-body').innerHTML='<div class="empty" style="color:#ff5d73">Error de red.</div>'; return; }
  const TFS=['M5','M15','M30','H1','H4','D1'];
  let tfrow='<div class="ssec" style="margin-bottom:12px">'+TFS.map(t=>'<button class="btn ghost'+(t===(d.timeframe||tf)?' on':'')+'" style="padding:5px 10px" onclick="openMarket(\''+sym+'\',\''+t+'\')">'+t+'</button>').join('')+'</div>';
  if(!d.ok){ $('#d-body').innerHTML=tfrow+'<div class="empty">'+escapeHtml(d.reason||'No disponible')+'</div>'; return; }
  const vc=d.verdict==='compra'?'#34d399':(d.verdict==='venta'?'#ff5d73':'#fbbf24');
  const vt={compra:L('COMPRA','BUY'),venta:L('VENTA','SELL'),neutral:'NEUTRAL'}[d.verdict]||d.verdict.toUpperCase();
  let h=tfrow+'<div class="cfg"><span>Precio</span> <b>'+d.price+'</b></div>';
  h+='<div class="cfg"><span>Señal ('+d.timeframe+')</span> <b style="color:'+vc+'">'+vt+'</b></div>';
  h+='<div class="cfg"><span>'+L('Tendencia','Trend')+'</span> <b>'+(d.trend==='alcista'?L('alcista','bullish'):L('bajista','bearish'))+'</b></div>';
  h+='<div class="slbl">'+L('INDICADORES','INDICATORS')+'</div>';
  h+='<div class="cfg"><span>RSI 14</span> <b style="color:'+(d.rsi14>70?'#ff5d73':(d.rsi14<30?'#34d399':'#dffaff'))+'">'+d.rsi14+'</b></div>';
  h+='<div class="cfg"><span>EMA 20 / 50 / 200</span> <b>'+d.ema20+' · '+d.ema50+' · '+d.ema200+'</b></div>';
  h+='<div class="cfg"><span>ATR 14</span> <b>'+d.atr14+'</b></div>';
  h+='<div class="slbl">KEY LEVELS</div>';
  const rs=(d.resistances||[]).slice(0,3), sp=(d.supports||[]).slice(0,3);
  if(!rs.length&&!sp.length) h+='<div class="empty">—</div>';
  rs.forEach(r=> h+='<div class="cfg"><span>'+L('Resistencia','Resistance')+'</span> <b style="color:#ff5d73">'+r+'</b></div>');
  sp.forEach(r=> h+='<div class="cfg"><span>'+L('Soporte','Support')+'</span> <b style="color:#34d399">'+r+'</b></div>');
  if(sym==='DXY') h+='<div class="empty" style="margin-top:10px">DXY sintético, calculado de la canasta EUR, JPY, GBP, CAD, SEK, CHF.</div>';
  $('#d-body').innerHTML=h; }
/* ---------- PANTALLAS LATERALES: instrumentos (izq) y noticias (der) ---------- */
function spark(vals,col){ if(!vals||vals.length<2)return'';
  const n=vals.length, lo=Math.min.apply(null,vals), hi=Math.max.apply(null,vals), rng=(hi-lo)||1;
  const pts=vals.map((v,i)=>(i/(n-1)*100).toFixed(2)+','+(20-((v-lo)/rng)*18).toFixed(2)).join(' ');
  const id='g'+Math.random().toString(36).slice(2,7);
  return'<svg viewBox="0 0 100 22" preserveAspectRatio="none">'
    +'<defs><linearGradient id="'+id+'" x1="0" y1="0" x2="0" y2="1">'
    +'<stop offset="0" stop-color="'+col+'" stop-opacity=".28"/><stop offset="1" stop-color="'+col+'" stop-opacity="0"/></linearGradient></defs>'
    +'<polygon points="0,22 '+pts+' 100,22" fill="url(#'+id+')"/>'
    +'<polyline points="'+pts+'" fill="none" stroke="'+col+'" stroke-width="1" vector-effect="non-scaling-stroke"/></svg>'; }
async function pollInstruments(){
  let d; try{ d=await (await fetch('/instruments')).json(); }catch(e){ return; }
  const rows=d.rows||[];
  INSTR=rows;                       // los instrumentos SON el tercer anillo del reactor
  const tf=$('#hud-tf'); if(tf) tf.textContent=d.timeframe||'';
  const box=$('#hud-inst'); if(!box) return;          // el panel es opcional: el anillo manda
  if(!rows.length){ box.innerHTML='<div class="empty" style="padding:8px;font-size:11px">'
      +escapeHtml(d.reason||L('Sin datos todavía.','No data yet.'))+'</div>'; return; }
  box.innerHTML=rows.map(r=>{ const up=r.change_pct>=0, col=up?'#34d399':'#ff5d73';
    const vc=r.verdict==='compra'?'#34d399':(r.verdict==='venta'?'#ff5d73':'#5f7387');
    const live=OPENSYMS.has(String(r.symbol||'').toUpperCase());   // lo está operando ahora
    const nm=(window.mktName&&window.mktName(r.symbol))||'';
    return'<div class="irow'+(live?' live':'')+'" style="border-left-color:'+vc+'" onclick="openMarket(\''+r.symbol+'\')">'
      +'<span class="s">'+escapeHtml(r.symbol)+(nm?'<span style="color:#3d5a6b;font-size:9px;letter-spacing:1px"> '+escapeHtml(nm)+'</span>':'')
      +(live?'<span style="color:#34d399"> ●</span>':'')+'</span><span class="p">'+r.price+'</span>'
      +'<span class="ch" style="color:'+vc+';font-size:9.5px;letter-spacing:1px">'+escapeHtml(String(r.verdict||'').toUpperCase())+'</span>'
      +'<span class="ch" style="color:'+col+'">'+(up?'▲':'▼')+' '+Math.abs(r.change_pct).toFixed(2)+'%</span>'
      +'<span class="sp">'+spark(r.spark,col)+'</span></div>'; }).join(''); }
/* Filtro de impacto: se puede encender/apagar cada nivel y se recuerda. */
let IMPF={high:true,medium:true,low:false};
try{ const sv=JSON.parse(localStorage.getItem('hydra_impf')||'null'); if(sv)IMPF=sv; }catch(e){}
const IMPC={high:'#ff5d73',medium:'#fbbf24',low:'#5ad1e6',holiday:'#8aa'};
function toggleImp(k){ IMPF[k]=!IMPF[k];
  try{ localStorage.setItem('hydra_impf',JSON.stringify(IMPF)); }catch(e){}
  pollNews(); }
function impChips(){ return ['high','medium','low'].map(k=>
  '<span class="impc'+(IMPF[k]?' on':'')+'" style="--c:'+IMPC[k]+'" onclick="toggleImp(\''+k+'\')">'
  +{high:L('ALTO','HIGH'),medium:L('MEDIO','MED'),low:L('BAJO','LOW')}[k]+'</span>').join(''); }
let NEWS_RAW=null;
async function pollNews(){ const box=$('#hud-news'); if(!box)return;
  if(!NEWS_RAW){ try{ NEWS_RAW=await (await fetch('/calendar')).json(); }catch(e){ return; } }
  const d=NEWS_RAW;
  // El calendario cuelga de la sesión: SOLO las divisas de la plaza abierta ahora.
  const act=SESSIONS.filter(isOpenNow), cur=new Set();
  act.forEach(s=>(SES_CCY[s.n]||[]).forEach(c=>cur.add(c)));
  const lab=$('#hud-calses');
  if(lab) lab.textContent=act.length?act.map(s=>s.n).join(' + '):L('FUERA DE SESIÓN','OUT OF SESSION');
  const chips='<div class="impbar">'+impChips()+'</div>';
  if(!act.length){ box.innerHTML=chips+'<div class="empty" style="padding:8px;font-size:11px">'
      +L('Ninguna sesión abierta. El calendario vuelve al abrir la siguiente plaza.',
         'No session open. The calendar returns when the next one opens.')+'</div>'; return; }
  const ev=(d.events||[]).filter(e=>cur.has(String(e.currency||'').toUpperCase()))
                         .filter(e=>IMPF[String(e.impact||'low').toLowerCase()]!==false
                                    &&IMPF[String(e.impact||'low').toLowerCase()])
                         .slice(0,30);
  const hi=ev.filter(e=>String(e.impact||'').toLowerCase()==='high').length;
  const imp=$('#hud-imp'); if(imp) imp.textContent=hi?hi+' ALTO':'';
  if(!ev.length){ box.innerHTML=chips+'<div class="empty" style="padding:8px;font-size:11px">'
      +escapeHtml(d.error||L('Sin eventos de '+[...cur].join('/')+' con esos filtros.',
                             'No '+[...cur].join('/')+' events with those filters.'))+'</div>'; return; }
  let last='',h=chips;
  ev.forEach(e=>{ const dt=new Date(e.ts*1000);
    const day=dt.toLocaleDateString(LANG==='en'?'en':'es',{weekday:'short',day:'numeric',month:'short'});
    if(day!==last){ h+='<div style="color:#3d5a6b;font-size:9px;letter-spacing:2px;margin:9px 0 4px;text-transform:uppercase">'+escapeHtml(day)+'</div>'; last=day; }
    const col=IMPC[(e.impact||'low').toLowerCase()]||'#5ad1e6';
    h+='<div class="nrow'+(e.watched?' w':'')+'"><span class="t">'+dt.toLocaleTimeString('es',{hour:'2-digit',minute:'2-digit'})+'</span>'
      +'<span class="d" style="background:'+col+';color:'+col+'"></span>'
      +'<span class="c">'+escapeHtml(String(e.currency||''))+'</span>'
      +'<span class="n">'+escapeHtml(String(e.title||''))+'</span></div>'; });
  box.innerHTML=h; }
async function refreshNews(){ NEWS_RAW=null; await pollNews(); }
/* Sesiones: se calculan con la hora LOCAL de cada plaza (Intl ya aplica el horario
   de verano), así no hay que tocar nada dos veces al año. */
const SESSIONS=[{n:'SÍDNEY',tz:'Australia/Sydney',o:8,c:17},
                {n:'TOKIO',tz:'Asia/Tokyo',o:9,c:18},
                {n:'FRÁNCFORT',tz:'Europe/Berlin',o:8,c:17},
                {n:'LONDRES',tz:'Europe/London',o:8,c:17},
                {n:'N. YORK',tz:'America/New_York',o:8,c:17}];
const SES_CCY={'SÍDNEY':['AUD','NZD'],'TOKIO':['JPY','CNY'],'FRÁNCFORT':['EUR','CHF'],
               'LONDRES':['GBP','EUR'],'N. YORK':['USD','CAD','MXN']};
function isOpenNow(s){ const t=tzNow(s.tz);
  return t.wd!=='Sat'&&t.wd!=='Sun'&&t.h>=s.o&&t.h<s.c; }
function tzNow(tz){ const p=new Intl.DateTimeFormat('en-GB',{timeZone:tz,hour:'2-digit',minute:'2-digit',
    weekday:'short',hour12:false}).formatToParts(new Date()); const o={};
  p.forEach(x=>o[x.type]=x.value); return {h:+o.hour%24+(+o.minute)/60, wd:o.weekday}; }
function renderSessions(){ const box=$('#hud-ses'); if(!box)return; let open=0,h='';
  SESSIONS.forEach(s=>{ const t=tzNow(s.tz), wknd=(t.wd==='Sat'||t.wd==='Sun');
    const on=isOpenNow(s); if(on)open++;
    const p=on?Math.min(1,(t.h-s.o)/(s.c-s.o)):0;
    const hh=String(Math.floor(t.h)).padStart(2,'0')+':'+String(Math.floor((t.h%1)*60)).padStart(2,'0');
    h+='<div class="srow'+(on?' on':'')+'"><span class="sn">'+s.n+'</span>'
      +'<span class="bar"><i style="width:'+(p*100).toFixed(1)+'%"></i></span>'
      +'<span class="hh">'+(wknd?L('cerrado','closed'):hh)+'</span></div>'; });
  box.innerHTML=h;
  const n=$('#hud-ses-n');
  if(n) n.textContent=open?open+' '+L('ABIERTAS','OPEN')+(open>1?' · SOLAPE':''):L('CERRADO','CLOSED');
  const key=SESSIONS.filter(isOpenNow).map(s=>s.n).join('|');
  if(key!==SESKEY){ SESKEY=key; pollNews(); } }
let SESKEY='';
async function pollPositions(){ const box=$('#hud-pos'); if(!box)return;
  let d; try{ d=await (await fetch('/positions')).json(); }catch(e){ return; }
  const rows=Array.isArray(d)?d:[];
  OPENSYMS=new Set(rows.map(p=>String(p.symbol||'').toUpperCase()));
  const n=$('#hud-pos-n'); if(n) n.textContent=rows.length?rows.length+' '+L('ABIERTAS','OPEN'):'—';
  if(!rows.length){ box.innerHTML='<div class="empty" style="padding:4px 2px;font-size:10.5px">'
      +L('Ninguna posición abierta.','No open positions.')+'</div>'; return; }
  box.innerHTML=rows.map(p=>{ const buy=String(p.side||'').toUpperCase().indexOf('BUY')>=0;
    const col=buy?'#34d399':'#ff5d73', lots=(p.volume_units/100000);
    return'<div class="prow" style="border-left-color:'+col+'" onclick="openMarket(\''+String(p.symbol||'')+'\')">'
      +'<span class="sd" style="color:#02141b;background:'+col+'">'+(buy?'BUY':'SELL')+'</span>'
      +'<span class="sy">'+escapeHtml(String(p.symbol||'—'))+'</span>'
      +'<span class="vl">'+(lots>=0.01?lots.toFixed(2)+' lot':p.volume_units+' u')+' · '+ctxAgo(p.open_ts)+'</span>'
      +'</div>'; }).join(''); }
/* CINTA DE ACTIVIDAD: qué está analizando y qué está ejecutando, en vivo.
   Traduce cada entrada del diario a una línea corta y legible. */
const TAPE_AG={analyst:['ANALIZA','#fbbf24'],risk_manager:['RIESGO','#ff9f6b'],
  executor:['EJECUTA','#a78bfa'],overnight:['VIGILA','#5ad1e6'],portfolio:['CARTERA','#c084fc'],
  sentinel:['NOTICIA','#38bdf8'],auditor:['AUDITA','#fb923c'],reviewer:['REVISA','#60a5fa'],
  architect:['EVOLUC.','#a3e635'],validator:['VALIDA','#22d3ee'],watchdog:['SALUD','#f87171'],
  tester:['PRUEBA','#facc15']};
function tapeText(e){ let c=e.content;
  if(typeof c==='string'){ try{ c=JSON.parse(c); }catch(_){ return String(c).slice(0,110); } }
  if(!c||typeof c!=='object') return String(e.kind||'').replace(/_/g,' ');
  const dir=d=>d==='buy'?L('COMPRA','BUY'):(d==='sell'?L('VENTA','SELL'):String(d||'').toUpperCase());
  if(e.agent==='analyst'){
    if(c.action!=='propose') return L('sin oportunidad','no setup')+(c.thesis?' · '+c.thesis:'');
    return L('propone ','proposes ')+dir(c.direction)+' · conf '+(c.confidence!=null?c.confidence:'?')
      +(c.stop_loss?' · SL '+c.stop_loss:'')+(c.take_profit?' · TP '+c.take_profit:''); }
  if(e.agent==='risk_manager'){ const p=c.proposal||{};
    return (c.approved?L('aprobado','approved'):L('VETADO','VETOED'))
      +(c.volume_units?' · '+(c.volume_units/100000).toFixed(2)+' lot':'')
      +(c.reason?' · '+c.reason:'')+(p.direction?' ('+dir(p.direction)+')':''); }
  if(e.agent==='executor'){ const st={order_placed:L('ORDEN ENVIADA','ORDER SENT'),
      order_simulated:L('simulada','simulated'),order_error:'ERROR'}[e.kind]||e.kind;
    return st+(c.side?' '+dir(c.side):'')+(c.volume_units?' · '+(c.volume_units/100000).toFixed(2)+' lot':'')
      +(c.error?' · '+String(c.error).slice(0,60):''); }
  if(e.agent==='portfolio') return L('VETO cartera','portfolio VETO')+(c.reason?' · '+c.reason:'');
  if(e.agent==='sentinel'&&e.kind==='blackout')
    return L('bloqueado por ','blocked by ')+(c.currency||'')+' '+(c.title||'');
  if(e.agent==='overnight'){ if(c.action) return String(c.action).replace(/_/g,' ')+(c.reason?' · '+c.reason:'');
    if(Array.isArray(c.actions)) return c.actions.length+L(' posiciones revisadas',' positions reviewed'); }
  return (c.reason||c.summary||c.thesis||String(e.kind||'').replace(/_/g,' ')); }
let TAPE_SEEN=0;
async function pollTape(){ const box=$('#tape-b'); if(!box)return;
  let j; try{ j=await (await fetch('/journal?limit=40')).json(); }catch(e){ return; }
  const rows=(Array.isArray(j)?j:[]).filter(e=>TAPE_AG[e.agent]).slice(0,14);
  const newest=rows.length?rows[0].ts:0;
  const busy=newest&&(Date.now()/1000-newest)<120;      // algo se movió hace menos de 2 min
  const tp=$('#tape'); if(tp) tp.classList.toggle('busy',!!busy);
  const st=$('#tape-st');
  if(st) st.textContent=busy?L('EN VIVO','LIVE'):(newest?L('ÚLTIMO ','LAST ')+ctxAgo(newest):L('EN ESPERA','IDLE'));
  if(!rows.length){ box.innerHTML='<div class="empty" style="padding:6px;font-size:10.5px">'
      +L('Sin actividad todavía. Aquí aparecerá cada análisis y cada orden.',
         'No activity yet. Every analysis and order shows up here.')+'</div>'; return; }
  box.innerHTML=rows.map(e=>{ const m=TAPE_AG[e.agent]||['—','#5f7387'];
    const dt=new Date((e.ts||0)*1000);
    return '<div class="trow" style="border-left-color:'+m[1]+'">'
      +'<span class="tt">'+dt.toLocaleTimeString('es',{hour:'2-digit',minute:'2-digit'})+'</span>'
      +'<span class="ta" style="color:'+m[1]+'">'+m[0]+'</span>'
      +'<span class="ts">'+escapeHtml(String(e.symbol||'—'))+'</span>'
      +'<span class="tx">'+escapeHtml(tapeText(e))+'</span></div>'; }).join('');
  TAPE_SEEN=newest; }
/* Nombre corto del agente para que quepa dentro del segmento del anillo. */
function shortName(n){ const w=String(n||'').trim().split(/\s+/); return (w[0]||'').toUpperCase().slice(0,10); }
function hudStart(){ document.querySelectorAll('.hudcol .hud').forEach((e,i)=>setTimeout(()=>e.classList.add('in'),180+i*110));
  // las pistas se rutean al borde de cada ventana: hay que esperar a que
  // terminen de entrar para medirlas donde de verdad se quedan.
  [900,1800].forEach(t=>setTimeout(()=>window.pcbRewire&&window.pcbRewire(),t));
  setTimeout(()=>{const t=$('#tape');if(t)t.classList.add('in');},140);
  renderSessions(); pollPositions(); pollInstruments(); pollNews(); renderHudSys(); pollBrain(); pollTape(); pollBots();
  setInterval(renderSessions,30000); setInterval(pollPositions,20000);
  setInterval(pollInstruments,30000); setInterval(refreshNews,1800000);
  setInterval(pollBrain,60000); setInterval(pollTape,6000);
  setInterval(pollBots,20000); }
/* Ventana BOTS: solo los que están HACIENDO algo — operando o analizando.
   "Analiza" sale de trade_context (el bot mira aunque no abra), "opera" de las
   posiciones abiertas. El que no reporta y no tiene posiciones, no aparece. */
async function pollBots(){ const box=$('#hud-bots'); if(!box)return;
  let d; try{ d=await (await fetch('/bots/active?minutes=45')).json(); }catch(e){ return; }
  const bs=(d.bots||[]);
  const n=$('#hud-bots-n');
  if(n) n.textContent=bs.length?(bs.filter(b=>b.open).length+' OPERAN'):'EN REPOSO';
  if(!bs.length){ box.innerHTML='<div class="empty" style="padding:4px 2px;font-size:10.5px">'
      +L('Ningún bot activo. Aparecen al abrir posición o al reportar análisis.',
         'No active bots. They appear when they open a position or report analysis.')+'</div>'; return; }
  box.innerHTML=bs.map(b=>{ const op=b.open>0, col=op?'#34d399':'#5ad1e6';
    return '<div class="prow" style="border-left-color:'+col+'">'
      +'<span class="sd" style="color:#02141b;background:'+col+'">'+(op?'OPERA':'ANALIZA')+'</span>'
      +'<span class="sy" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
      +escapeHtml(String(b.label))+'</span>'
      +'<span class="vl">'+(op?(b.open+(b.open>1?' pos':' pos')):(b.seen+' señales'))
      +(b.alerted?' · '+b.alerted+' ok':'')+' · '+ctxAgo(b.last_ts)+'</span>'
      +'</div>'
      +((b.symbols||[]).length?'<div class="phelp" style="margin:-2px 0 4px 6px">'
        +escapeHtml(b.symbols.slice(0,6).join(', '))+'</div>':''); }).join(''); }
/* Pantalla CEREBRO Y VOZ: qué modelo piensa y qué voz habla, sin abrir nada. */
async function pollBrain(){ const box=$('#hud-brain'); if(!box)return;
  const row=(k,v,col)=>'<div class="srow2"><span>'+k+'</span><b'+(col?' style="color:'+col+'"':'')+'>'+escapeHtml(String(v))+'</b></div>';
  let m={},lo={},vo={};
  try{ m=await (await fetch('/model')).json(); }catch(e){}
  try{ lo=await (await fetch('/llm/local')).json(); }catch(e){}
  try{ vo=await (await fetch('/voice/local')).json(); }catch(e){}
  const pv=m.provider||lo.provider||'';
  const prov={anthropic:'Claude (nube)',ollama:'Ollama (local)',hybrid:'Híbrido'}[pv]||(pv||'—');
  const short=String(m.model||'').replace('claude-','').replace(/-\d{8}$/,'');
  let h=row(L('Cerebro','Brain'),prov,'#7ff6ff')+row('Claude',short||'—');
  if(pv!=='anthropic')
    h+=row('Ollama',(lo.selected||m.ollama_model||'—')+(lo.running?'':' ⚠'),lo.running?'#34d399':'#fbbf24');
    if(!lo.running&&lo.installed)
      h+='<div class="sysact" style="border:0;padding:6px 0 0"><button class="btn ghost" '
        +'onclick="startLocal()">▶ ENCENDER CEREBRO</button></div>';
  const vp=vo.provider||'';
  h+=row(L('Voz','Voice'),vp==='voicebox'?'Voicebox':(vp||L('navegador','browser')),
         vp==='voicebox'?(vo.running?'#34d399':'#ff5d73'):'#5f7387');
  if(vp==='voicebox') h+=row(L('Perfil','Profile'),vo.selected||'—');
  const rt=(lo.routing||[]).filter(r=>r.brain==='ollama').length;
  if(rt) h+=row(L('En local','Local'),rt+' '+L('agentes','agents'));
  box.innerHTML=h; }
/* Ventana inferior derecha: el estado del sistema de un vistazo + entrada a la configuración. */
function renderHudSys(){ const box=$('#hud-sys'); if(!box||!DATA)return; const c=DATA.core||{};
  const row=(k,v,col)=>'<div class="srow2"><span>'+k+'</span><b'+(col?' style="color:'+col+'"':'')+'>'+v+'</b></div>';
  const conn=c.connected?['viva','#34d399']:(c.oauth_ok?['esperando','#fbbf24']:['sin cTrader','#ff5d73']);
  box.innerHTML=row(L('Modo','Mode'),c.dry_run?'PAPEL':'REAL',c.dry_run?'#fbbf24':'#34d399')
    +row(L('Conexión','Link'),conn[0],conn[1])
    +row('Balance',c.balance!=null?c.balance:'—')
    +row('Playbook','v'+(c.playbook_version||'—'))
    +row(L('Agentes','Agents'),(DATA.agents||[]).length)
    +row(L('Contexto','Context'),CTXCOUNT>0?CTXCOUNT:'0','#b096ff')
    +row(L('Estado','State'),c.halted?L('DETENIDO','HALTED'):L('en línea','online'),c.halted?'#ff5d73':'#34d399');
  const b=$('#hud-halt'); if(b) b.textContent=c.halted?'▶ REANUDAR':'⏸ HALT'; }
let CTXCOUNT=0;

/* ---------- TRADE CONTEXT: memoria inmutable de como se veia el mundo al decidir ---------- */
let CTXF={symbol:'',outcome:''};
function ctxColor(o){ o=String(o||''); if(o.indexOf('blocked')===0)return'#ff5d73';
  if(o==='low_score'||o==='rejected')return'#fbbf24'; if(o==='alerted'||o==='taken')return'#34d399'; return'#9d8cff'; }
/* El bot es C#: sus confluencias pueden venir como {Label:…}, {label:…} o texto suelto. */
function sigLabel(s){ if(s==null)return'?'; if(typeof s!=='object')return String(s);
  for(const k of ['Label','label','Name','name','Type','type']) if(s[k])return String(s[k]);
  const v=Object.values(s).find(x=>typeof x==='string'); return v||JSON.stringify(s).slice(0,28); }
function ctxAgo(ts){ if(!ts)return''; const s=Math.max(0,Date.now()/1000-ts);
  if(s<90)return Math.round(s)+'s'; if(s<5400)return Math.round(s/60)+'m';
  if(s<172800)return Math.round(s/3600)+'h'; return Math.round(s/86400)+'d'; }
async function openTradeContext(sym,out){ selected=null;
  if(sym!==undefined) CTXF.symbol=sym; if(out!==undefined) CTXF.outcome=out;
  $('#d-e').textContent='🗄'; $('#d-name').textContent='TRADE CONTEXT';
  $('#d-role').textContent=L('Memoria inmutable · append-only','Immutable memory · append-only');
  $('#d-body').innerHTML='<div class="empty">Cargando…</div>'; $('#drawer').classList.add('open');
  let d; try{ d=await (await fetch('/trade-context?limit=40&symbol='+encodeURIComponent(CTXF.symbol)+'&outcome='+encodeURIComponent(CTXF.outcome))).json(); }
  catch(e){ $('#d-body').innerHTML='<div class="empty" style="color:#ff5d73">Error de red.</div>'; return; }
  const st=d.stats||{}, rows=d.rows||[];
  let h='<p class="role">'+L('Cómo se veía el mercado en el instante exacto en que el bot decidió. No se puede modificar ni borrar: cada fila queda tal cual llegó.','How the market looked at the exact instant the bot decided. It cannot be modified or deleted: every row stays exactly as it arrived.')+'</p>';
  h+='<div class="cfg"><span>'+L('Capturas','Captures')+'</span> <b style="color:#b096ff">'+(st.total||0)+'</b></div>';
  if(st.first_ts) h+='<div class="cfg"><span>'+L('Ventana','Window')+'</span> <b>'+ctxAgo(st.first_ts)+' → '+ctxAgo(st.last_ts)+'</b></div>';
  if(!st.total){ h+='<div class="slbl">'+L('AÚN NO LLEGA NADA','NOTHING YET')+'</div><div class="empty" style="text-align:left;line-height:1.6">'
      +L('Apunta el bot a este backend y empieza a guardar:','Point the bot at this backend and it starts saving:')
      +'<br><code>BackendUrl = '+location.origin+'/ingest/trade-context</code><br><br>'
      +L('Acepta el JSON tal como lo mande — no hace falta que el formato coincida.','It accepts whatever JSON the bot sends — the format does not need to match.')+'</div>';
    $('#d-body').innerHTML=h; return; }
  const bo=st.by_outcome||[];
  if(bo.length){ h+='<div class="slbl">'+L('POR DESENLACE','BY OUTCOME')+'</div>';
    bo.forEach(o=>{ const on=CTXF.outcome&&String(o.outcome||'').indexOf(CTXF.outcome)===0;
      h+='<div class="cfg" style="cursor:pointer;'+(on?'background:#12203a55':'')+'" onclick="openTradeContext(undefined,\''+(on?'':String(o.outcome||''))+'\')"><span style="color:'+ctxColor(o.outcome)+'">'
        +escapeHtml(String(o.outcome||'?'))+'</span> <b>'+o.n+(o.avg_score?' · score '+o.avg_score:'')+'</b></div>'; }); }
  const bs=st.by_symbol||[];
  if(bs.length>1){ h+='<div class="slbl">'+L('POR MERCADO','BY MARKET')+'</div><div class="ssec">'
      +bs.map(s=>'<button class="btn ghost'+(CTXF.symbol===s.symbol?' on':'')+'" style="padding:5px 10px" onclick="openTradeContext(\''+(CTXF.symbol===s.symbol?'':String(s.symbol||''))+'\')">'
        +escapeHtml(String(s.symbol||'?'))+' '+s.n+'</button>').join('')+'</div>'; }
  h+='<div class="slbl">'+L('ÚLTIMAS CAPTURAS','LATEST CAPTURES')+'</div>';
  if(!rows.length) h+='<div class="empty">'+L('Nada con ese filtro.','Nothing with that filter.')+'</div>';
  rows.forEach(r=>{ const col=ctxColor(r.outcome);
    let sig=[]; try{ sig=JSON.parse(r.signals_json||'[]')||[]; }catch(_){}
    const det=[r.zone_price&&L('zona ','zone ')+r.zone_price,
               r.zone_width_pips&&r.zone_width_pips+' pips',
               r.n_confluences&&r.n_confluences+' '+L('confluencias','confluences'),
               r.dist_pips&&'dist '+r.dist_pips,
               r.spread_pips&&'spread '+r.spread_pips].filter(Boolean).join(' · ');
    h+='<div id="ctx'+r.id+'" style="border:1px solid #1a2440;border-left:2px solid '+col+';border-radius:8px;padding:9px 11px;margin:8px 0;background:#0a1020aa">'
      +'<div style="display:flex;gap:8px;align-items:baseline"><b style="color:#dff0ff">'+escapeHtml(String(r.symbol||'—'))+'</b>'
      +'<span style="color:#5f7387;font-size:11px">'+escapeHtml(String(r.timeframe||''))+' '+escapeHtml(String(r.bias||''))+'</span>'
      +(r.score!=null?'<span style="color:#b096ff;font-size:11px">score '+r.score+'</span>':'')
      +'<span style="margin-left:auto;color:'+col+';font-size:11px">'+escapeHtml(String(r.outcome||''))+'</span>'
      +'<span style="color:#5f7387;font-size:11px">'+ctxAgo(r.ts)+'</span></div>'
      +(det?'<div style="color:#8aa;font-size:11px;margin-top:4px">'+escapeHtml(det)+'</div>':'')
      +(sig.length?'<div style="color:#6f8aa5;font-size:10.5px;margin-top:4px">'+escapeHtml(sig.slice(0,6).map(sigLabel).join(' · '))+(sig.length>6?' +'+(sig.length-6):'')+'</div>':'')
      +'<div style="margin-top:6px"><span style="cursor:pointer;color:#5ad1e6;font-size:11px" onclick="ctxRaw('+r.id+')">'+L('ver todo lo guardado ▾','see everything stored ▾')+'</span></div></div>'; });
  $('#d-body').innerHTML=h; }
async function ctxRaw(id){ const box=$('#ctx'+id); if(!box)return;
  if(box.querySelector('pre')){ box.querySelector('pre').remove(); return; }
  let d; try{ d=await (await fetch('/trade-context/'+id)).json(); }catch(e){ toast('Error de red'); return; }
  const pre=document.createElement('pre');
  pre.style.cssText='margin:8px 0 0;padding:8px;background:#050810;border:1px solid #12203a;border-radius:6px;color:#9ec6dd;font-size:10.5px;line-height:1.45;max-height:280px;overflow:auto;white-space:pre-wrap;word-break:break-word';
  pre.textContent=JSON.stringify(d.raw!==undefined?d.raw:d,null,2); box.appendChild(pre); }
function renderDemo(results){ let h='<p class="role">Datos sintéticos. Así lee el mercado el Analyst.</p>';
  results.forEach(r=>{ const p=r.proposal,m=r.market; const dir=p.action==='propose'?(p.direction==='buy'?'🟢 COMPRA':'🔴 VENTA'):'⚪ SIN OPERACIÓN';
    h+='<li style="list-style:none;border:1px solid #12303f;border-radius:10px;padding:12px;margin:10px 0;background:#08131e88"><b style="color:#7ff6ff">'+r.symbol+'</b> — '+dir+' <span style="color:#5f7387">(confianza '+(p.confidence||0)+')</span>';
    if(p.thesis)h+='<div class="c" style="margin-top:6px;color:#a9bcd0">'+escapeHtml(p.thesis)+'</div>';
    if(p.action==='propose')h+='<div style="color:#8aa;font-size:11px;margin-top:6px">entrada≈ '+p.last_close+' · SL '+p.stop_loss+' · TP '+p.take_profit+'</div>';
    if(r.risk_preview){ const rp=r.risk_preview; h+='<div style="margin-top:8px;font-size:11.5px;color:'+(rp.passes_deterministic?'#34d399':'#ff5d73')+'">'+(rp.passes_deterministic?'✅ pasa filtros del Risk Manager':'❌ sería vetada')+' (R:R '+rp.risk_reward+')</div>'; } h+='</li>'; });
  openInfo('▶ Resultado del demo',h); }

/* ===================== VOZ ===================== */
/* ===================== SONIDOS DE MÁQUINA =====================
   Sintetizados con Web Audio: nada de archivos, nada que descargar, y funciona
   sin conexión. El contexto de audio se crea en el primer gesto del usuario —
   los navegadores no dejan sonar antes, y el clic para encender ES ese gesto. */
let sfxOn=true, actx=null;
try{ const sv=localStorage.getItem('hydra_sfx'); if(sv!==null) sfxOn=sv==='1'; }catch(e){}
function ac(){ if(!sfxOn) return null;
  try{ if(!actx) actx=new (window.AudioContext||window.webkitAudioContext)();
       if(actx.state==='suspended') actx.resume();
       return actx; }catch(e){ return null; } }
/* un oscilador con envolvente y barrido de tono/filtro */
function tone(o){ const c=ac(); if(!c) return;
  const t0=c.currentTime+(o.at||0), dur=o.dur||0.4;
  const osc=c.createOscillator(), g=c.createGain(), f=c.createBiquadFilter();
  osc.type=o.type||'sine';
  osc.frequency.setValueAtTime(o.f0, t0);
  if(o.f1) osc.frequency.exponentialRampToValueAtTime(Math.max(1,o.f1), t0+dur);
  f.type='lowpass';
  f.frequency.setValueAtTime(o.c0||8000, t0);
  if(o.c1) f.frequency.exponentialRampToValueAtTime(Math.max(60,o.c1), t0+dur);
  const v=o.vol||0.2;
  g.gain.setValueAtTime(0.0001, t0);
  g.gain.exponentialRampToValueAtTime(v, t0+(o.atk||0.02));
  g.gain.exponentialRampToValueAtTime(0.0001, t0+dur);
  osc.connect(f); f.connect(g); g.connect(c.destination);
  osc.start(t0); osc.stop(t0+dur+0.05); }
/* ruido filtrado: el "aire" del arranque y del apagado */
function whoosh(o){ const c=ac(); if(!c) return;
  const dur=o.dur||0.8, n=Math.floor(c.sampleRate*dur);
  const buf=c.createBuffer(1,n,c.sampleRate), d=buf.getChannelData(0);
  for(let i=0;i<n;i++) d[i]=(Math.random()*2-1)*(1-i/n);
  const src=c.createBufferSource(); src.buffer=buf;
  const f=c.createBiquadFilter(), g=c.createGain();
  const t0=c.currentTime+(o.at||0);
  f.type='bandpass'; f.Q.value=1.2;
  f.frequency.setValueAtTime(o.c0||300, t0);
  f.frequency.exponentialRampToValueAtTime(Math.max(60,o.c1||3000), t0+dur);
  g.gain.setValueAtTime(o.vol||0.12, t0);
  g.gain.exponentialRampToValueAtTime(0.0001, t0+dur);
  src.connect(f); f.connect(g); g.connect(c.destination);
  src.start(t0); }
/* ENCENDIDO: golpe grave, el reactor subiendo de vueltas y un repique claro */
function sfxBoot(){ if(!ac())return;
  tone({f0:42,f1:70,dur:0.9,type:'sine',vol:0.32,atk:0.01});
  whoosh({dur:1.3,c0:180,c1:5200,vol:0.10});
  tone({f0:120,f1:660,dur:1.1,type:'sawtooth',vol:0.10,c0:400,c1:6000,atk:0.25});
  tone({at:0.95,f0:880,dur:0.5,type:'sine',vol:0.16,atk:0.01});
  tone({at:1.02,f0:1320,dur:0.6,type:'sine',vol:0.10,atk:0.01}); }
/* PAUSA: dos notas que bajan y el filtro cerrándose. Sigue vivo, pero quieto. */
function sfxPause(){ if(!ac())return;
  tone({f0:520,dur:0.20,type:'square',vol:0.13,c0:2600,c1:900});
  tone({at:0.16,f0:330,dur:0.34,type:'square',vol:0.13,c0:1800,c1:500});
  whoosh({at:0.1,dur:0.5,c0:1800,c1:200,vol:0.06}); }
/* APAGADO: pierde vueltas hasta morir, como al desenchufar la máquina */
function sfxOff(){ if(!ac())return;
  tone({f0:520,f1:38,dur:1.6,type:'sawtooth',vol:0.20,c0:4000,c1:120,atk:0.02});
  tone({at:0.05,f0:260,f1:30,dur:1.7,type:'sine',vol:0.22,atk:0.02});
  whoosh({dur:1.5,c0:2600,c1:90,vol:0.09}); }
function sfxToggle(){ sfxOn=!sfxOn;
  try{ localStorage.setItem('hydra_sfx',sfxOn?'1':'0'); }catch(e){}
  const b=$('#b-sfx'); if(b) b.classList.toggle('on',sfxOn);
  toast(sfxOn?'Sonidos activados':'Sonidos silenciados');
  if(sfxOn) sfxPause(); }
let esVoices=[], esVoice=null, speakOn=true, ttsServer=false, ttsAudio=null, SIR='Krauser', LANG='mix';
function L(es,en){ return LANG==='en'?en:es; }   // 'mix' usa base español
function voiceLang(){ return LANG==='en'?'en-US':'es-ES'; }
let speaking=false, listeningActive=false, wakeUntil=0;
const MALE_PRIORITY=['jorge','juan','diego','carlos','enrique','miguel','pablo','alvaro','google español de estados unidos','google español'];
function loadVoices(){ if(!('speechSynthesis'in window))return; esVoices=speechSynthesis.getVoices().filter(v=>/es(-|_)/i.test(v.lang));
  if(!esVoice){ for(const nm of MALE_PRIORITY){ const v=esVoices.find(v=>v.name.toLowerCase().includes(nm)); if(v){esVoice=v;break;} } if(!esVoice)esVoice=esVoices[0]||null; } }
if('speechSynthesis'in window){ loadVoices(); speechSynthesis.onvoiceschanged=loadVoices; }
$('#b-speak').onclick=()=>{ speakOn=!speakOn; $('#b-speak').classList.toggle('on',speakOn); toast(speakOn?'Voz activada':'Voz silenciada'); if(speakOn)speak('Voz activada.'); };
function speak(t){ if(!speakOn)return; if(ttsServer){ serverSpeak(t); return; } browserSpeak(t); }
let ttsWarned=false;
let ttsBusy=false;
async function serverSpeak(t){
  // Voicebox reproduce por su cuenta y no se puede interrumpir: si dejamos que
  // se encimen varias frases, se oyen voces superpuestas. Descarta mientras habla.
  if(ttsBusy) return;
  ttsBusy=true;
  try{ speaking=true; if(ttsAudio)ttsAudio.pause();
    const r=await fetch('/tts',{method:'POST',headers:{'Content-Type':'text/plain'},body:t});
    if(!r.ok){ const why=await r.text().catch(()=>''); if(!ttsWarned){ ttsWarned=true; toast('Voz neural falló → uso la del navegador. '+(why||'').slice(0,90)); } throw 0; }
    ttsWarned=false;
    // 204 = Voicebox ya lo dijo por las bocinas del Mac; no repetir con el navegador
    if(r.status===204){ speaking=false; return; }
    const url=URL.createObjectURL(await r.blob()); ttsAudio=new Audio(url);
    ttsAudio.onended=()=>{speaking=false;URL.revokeObjectURL(url);}; ttsAudio.onerror=()=>{speaking=false;browserSpeak(t);}; await ttsAudio.play();
  }catch(_){ speaking=false; browserSpeak(t); }
  finally{ ttsBusy=false; } }
function browserSpeak(t){ if(!('speechSynthesis'in window))return; try{ speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(t); u.lang=voiceLang(); u.rate=1.08; u.pitch=0.85;
  const vs=speechSynthesis.getVoices(), want=voiceLang().slice(0,2);
  const v=(LANG!=='en'&&esVoice)?esVoice:vs.find(v=>v.lang&&v.lang.slice(0,2)===want); if(v)u.voice=v;
  u.onstart=()=>{speaking=true;}; u.onend=()=>{speaking=false;}; u.onerror=()=>{speaking=false;}; speechSynthesis.speak(u); }catch(_){}}

const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
let recog=null,running=false,wakeMode=false,awaiting=false,awaitTimer=null,micDenied=false,micMuted=false;
const WAKE=['oye hydra','hola hydra','hey hydra','oye idra','oye hidra','hydra','hidra','jarvis'];
function setV(t){ const el=$('#vstatus'); if(!el)return; el.innerHTML=t||''; el.style.display=t?'inline-block':'none'; if(el._t)clearTimeout(el._t); if(t)el._t=setTimeout(()=>{el.style.display='none';},6000); }
function coreHear(on){ listeningActive=on; $('#b-mic').classList.toggle('mic-on',on); }
function wakeFlash(){ wakeUntil=performance.now()+700; }
if(!SR){ setV('Voz no soportada — usa Chrome.'); }
else{ recog=new SR(); recog.lang=voiceLang(); recog.interimResults=true; recog.continuous=true;
  recog.onresult=e=>{ let interim=''; for(let i=e.resultIndex;i<e.results.length;i++){ const r=e.results[i]; if(r.isFinal) handlePhrase(norm(r[0].transcript)); else interim+=r[0].transcript; } if(interim)setV('“'+interim+'”'); };
  recog.onerror=e=>{ if(e.error==='not-allowed'){ micDenied=true; wakeMode=false; $('#b-wake').classList.remove('on'); setV(''); toast('Micrófono bloqueado. Actívalo en Ajustes de Safari → Sitios web → Micrófono → Permitir.'); } };
  recog.onend=()=>{ running=false; coreHear(false); if((wakeMode||awaiting)&&!micDenied){ setTimeout(startRecog,300);} else setV(''); };
}
function startRecog(){ if(!recog||running||micDenied||micMuted)return; try{ recog.lang=voiceLang(); recog.start(); running=true; coreHear(true);}catch(_){}}
function handlePhrase(t){ if(awaiting){ clearTimeout(awaitTimer); awaiting=false; wakeFlash(); runCmd(t); return; }
  const w=WAKE.find(w=>t.includes(w)); if(!w)return; wakeFlash(); const rest=t.slice(t.indexOf(w)+w.length).trim();
  if(rest.length>2){ runCmd(rest); } else { speak(L('A la orden, '+SIR+'.','At your command, '+SIR+'.')); setV('<b>Le escucho…</b>'); awaiting=true; awaitTimer=setTimeout(()=>{awaiting=false;setV('Di <b>“Oye Hydra…”</b>');},9000); } }
$('#b-mic').onclick=()=>{ if(!SR){toast('Usa Chrome para la voz');return;} micDenied=false; micMuted=false; $('#b-mute').classList.remove('on'); awaiting=true; setV('<b>Le escucho…</b>'); speak(L('Dígame, '+SIR+'.','Yes, '+SIR+'?')); if(!running)startRecog(); };
$('#b-wake').onclick=()=>{ wakeMode=!wakeMode; $('#b-wake').classList.toggle('on',wakeMode); if(wakeMode){ micDenied=false; micMuted=false; $('#b-mute').classList.remove('on'); try{localStorage.setItem('hydraWake','1');}catch(_){} toast('Escuchando “Oye Hydra”'); startRecog(); } else { try{localStorage.removeItem('hydraWake');}catch(_){} toast('Palabra mágica apagada'); if(recog&&running)recog.stop(); } };
$('#b-mute').onclick=()=>{ micMuted=!micMuted; $('#b-mute').classList.toggle('on',micMuted);
  if(micMuted){ wakeMode=false; awaiting=false; $('#b-wake').classList.remove('on'); try{localStorage.removeItem('hydraWake');}catch(_){} if(recog&&running)recog.stop(); if(typeof clapOn!=='undefined'&&clapOn)stopClap(); setV(''); toast('Micrófono silenciado 🔇'); speak('Dejo de escuchar, '+SIR+'.'); }
  else { toast('Micrófono disponible. Toca 👂 Oye Hydra para escuchar.'); } };

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
function onClap(){ wakeFlash(); speak(L('A la orden, '+SIR+'.','At your command, '+SIR+'.')); setV('<b>Le escucho…</b>'); awaiting=true; if(!running)startRecog(); clearTimeout(awaitTimer); awaitTimer=setTimeout(()=>{awaiting=false;},9000); }

const AGENT_WORDS=[{k:'analyst',w:['analista','analisis']},{k:'risk_manager',w:['riesgo','gestor']},{k:'executor',w:['ejecutor','ordenes']},{k:'overnight',w:['nocturno','noche']},{k:'reviewer',w:['revisor','revision']},{k:'architect',w:['arquitecto','playbook']},{k:'sentinel',w:['sentinel','noticias','calendario','centinela']},{k:'watchdog',w:['watchdog','vigilante','salud']},{k:'auditor',w:['auditor','auditoria']},{k:'validator',w:['validador','backtest']},{k:'portfolio',w:['portafolio','cartera','correlacion']}];
function runCmd(t){
  if(/(demo|prueba|analiza|corre)/.test(t)){ runDemo(); return; }
  if(/(deten|para|alto|halt|pausa)/.test(t)){ if($('#b-halt').textContent.includes('HALT'))doHalt(); else speak('Ya está detenido, '+SIR+'.'); return; }
  if(/(reanuda|continua|resume|activa el sistema)/.test(t)){ if($('#b-halt').textContent.includes('RESUME'))doHalt(); else speak('Ya está activo, '+SIR+'.'); return; }
  if(/(estado|reporte|situacion|resumen|status|como vas)/.test(t)){ speakStatus(); return; }
  if(/(calendario|noticias)/.test(t)){ openCalendar(); speak('Abriendo el calendario.'); return; }
  if(/(actualiza|refresca|recarga)/.test(t)){ load(); speak('Datos actualizados, '+SIR+'.'); return; }
  if(/(cierra|cerrar|oculta)/.test(t)){ closeDrawer(); return; }
  if(/(hola|buenas|quien eres|presenta)/.test(t)){ speak(L('Soy Hydra, a su servicio. Puedo correr el demo, darle el estado, o mostrarle cualquier agente.','I am Hydra, at your service. I can run the demo, give you the status, or show you any agent.')); return; }
  for(const a of AGENT_WORDS){ if(a.w.some(w=>t.includes(w))){ openAgent(a.k); return; } }
  speak(L('No le entendí, '+SIR+'. Pruebe: corre el demo, dame el estado, o abre el analista.','I did not catch that, '+SIR+'. Try: run the demo, give me the status, or open the analyst.'));
}
function speakStatus(){ if(!DATA){ speak('Aún cargando.'); return; } const c=DATA.core; const act=DATA.agents.filter(a=>a.state==='active').length;
  const conn=c.connected?'conectado a cTrader':(c.oauth_ok?'esperando conexión':'sin cuenta conectada');
  speak('Modo '+(c.dry_run?'papel':'real')+', '+conn+'. Balance '+(c.balance!=null?c.balance:'desconocido')+'. '+act+' de '+DATA.agents.length+' agentes activos, '+SIR+'.'); }

$('#activate').onclick=()=>{ booted=true; sfxBoot(); $('#boot').classList.add('hide'); setTimeout(()=>$('#boot').style.display='none',700);
  hudStart(); loadVoices(); speak(L('Sistemas en línea, '+SIR+'. Toca Oye Hydra cuando quieras activar el micrófono.','Systems online, '+SIR+'. Tap Oye Hydra to enable the mic.'));
  if(SR) setV('Toca 👂 Oye Hydra para activar la voz');
  if(!ttsServer) setTimeout(()=>toast('💡 Voz neural apagada (suena genérica). Actívala: fly secrets set TTS_PROVIDER=elevenlabs TTS_API_KEY=… ELEVENLABS_VOICE_ID=…'),2500); };

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
  let pcbDirty=true;                 // la placa se re-rutea al cambiar el tamaño
  let W=0,H=0,CX=0,CY=0,S=0,Rh=0,Rlab=0,Rctx=0, mx=-9999,my=-9999, hoverKey=null, hoverC=false, hoverI=-1, dirty=true;
  const dpr=Math.min(window.devicePixelRatio||1,1.5);
  function rs(){ W=cv.clientWidth||innerWidth; H=cv.clientHeight||innerHeight; cv.width=W*dpr; cv.height=H*dpr; g.setTransform(dpr,0,0,dpr,0,0); CX=W/2; CY=H*0.53;
    const side=W>1180?296:16;                       // deja aire para las pantallas laterales
    S=Math.max(260,Math.min(W-side*2,H)); Rh=S*0.25; Rlab=S*0.44; Rctx=S*0.385; dirty=true; pcbDirty=true; }
  rs(); addEventListener('resize',rs);
  function stateOf(k){ const a=agentByKey(k); return a?a.state:'idle'; }
  function entriesOf(k){ const a=agentByKey(k); return a&&a.entries?a.entries.length:0; }
  const PAL=['#ffd24a','#ff7a59','#c07cff','#4ad1c8','#5aa0ff','#9be36b','#7ff6ff','#ff5d73','#ff9f43','#6ee7ff','#e879f9'];
  function hx2(h){ h=(h||'').replace('#',''); if(h.length===3)h=h.split('').map(c=>c+c).join(''); const n=parseInt(h,16); if(isNaN(n))return '127,246,255'; return (n>>16&255)+','+(n>>8&255)+','+(n&255); }
  function rng(a){ return function(){ a|=0; a=a+0x6D2B79F5|0; let t=Math.imul(a^a>>>15,1|a); t=t+Math.imul(t^t>>>7,61|t)^t; return ((t^t>>>14)>>>0)/4294967296; }; }
  // árbol de ramas que crece hacia afuera desde el agente (sus tareas/funciones)
  // árbol en coordenadas LOCALES (agente en 0,0; crece hacia +x = radial). Al dibujar se rota con el agente.
  function makeTree(seed,extra){
    const r=rng(seed), segs=[], leaves=[], B=3+((r()*3)|0);
    for(let b=0;b<B;b++){ const a1=(b-(B-1)/2)*(1.6/B)+(r()-0.5)*0.15, L1=S*0.075+r()*S*0.04;
      const x1=Math.cos(a1)*L1, y1=Math.sin(a1)*L1; segs.push([0,0,x1,y1]); leaves.push([x1,y1,1.9,r()*6.28]);
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
    ['validator','analyst'],['watchdog','executor'],['watchdog','sentinel'],
    ['tester','analyst'],['tester','executor'],
    // el contexto de decision alimenta la revision diaria, y de ahi la
    // evolucion del playbook. Solo esos dos: el Analyst NO lo lee.
    ['__ctx','reviewer'],['__ctx','architect']];
  // símbolo vectorial propio de cada agente (dibujado, no un emoji genérico)
  function glyph(k,x,y,s,rgb,al,G){ G=G||g; G.save(); G.translate(x,y); G.strokeStyle='rgba('+rgb+','+al+')'; G.fillStyle='rgba('+rgb+','+al+')'; G.lineWidth=1.7; G.lineJoin='round'; G.lineCap='round';
    switch(k){
      case 'analyst': G.beginPath(); G.moveTo(-s,s*0.5); G.lineTo(-s*0.3,-s*0.15); G.lineTo(s*0.15,s*0.25); G.lineTo(s,-s*0.6); G.stroke(); G.beginPath(); G.moveTo(s*0.5,-s*0.6); G.lineTo(s,-s*0.6); G.lineTo(s,-s*0.12); G.stroke(); break;
      case 'risk_manager': G.beginPath(); G.moveTo(0,-s); G.lineTo(s*0.8,-s*0.55); G.lineTo(s*0.8,s*0.15); G.quadraticCurveTo(s*0.8,s*0.75,0,s); G.quadraticCurveTo(-s*0.8,s*0.75,-s*0.8,s*0.15); G.lineTo(-s*0.8,-s*0.55); G.closePath(); G.stroke(); break;
      case 'executor': G.beginPath(); G.moveTo(s*0.15,-s); G.lineTo(-s*0.55,s*0.1); G.lineTo(-s*0.05,s*0.1); G.lineTo(-s*0.15,s); G.lineTo(s*0.55,-s*0.1); G.lineTo(s*0.05,-s*0.1); G.closePath(); G.stroke(); break;
      case 'overnight': G.beginPath(); G.arc(0,0,s,Math.PI*0.42,Math.PI*1.58,false); G.arc(s*0.45,0,s*0.82,Math.PI*1.35,Math.PI*0.65,true); G.closePath(); G.stroke(); break;
      case 'reviewer': G.beginPath(); G.arc(0,0,s,0,6.283); G.stroke(); G.beginPath(); G.moveTo(-s*0.42,s*0.02); G.lineTo(-s*0.08,s*0.4); G.lineTo(s*0.48,-s*0.4); G.stroke(); break;
      case 'architect': G.beginPath(); G.moveTo(0,-s); G.lineTo(-s*0.62,s*0.75); G.moveTo(0,-s); G.lineTo(s*0.62,s*0.75); G.moveTo(-s*0.32,s*0.05); G.lineTo(s*0.32,s*0.05); G.stroke(); G.beginPath(); G.arc(0,-s,s*0.13,0,6.283); G.stroke(); break;
      case 'sentinel': G.beginPath(); G.moveTo(-s,0); G.quadraticCurveTo(0,-s*0.75,s,0); G.quadraticCurveTo(0,s*0.75,-s,0); G.closePath(); G.stroke(); G.beginPath(); G.arc(0,0,s*0.28,0,6.283); G.stroke(); break;
      case 'watchdog': G.beginPath(); G.moveTo(-s,0); G.lineTo(-s*0.4,0); G.lineTo(-s*0.15,-s*0.7); G.lineTo(s*0.1,s*0.7); G.lineTo(s*0.35,0); G.lineTo(s,0); G.stroke(); break;
      case 'auditor': G.beginPath(); G.moveTo(0,-s*0.9); G.lineTo(0,s*0.55); G.moveTo(-s*0.75,-s*0.5); G.lineTo(s*0.75,-s*0.5); G.moveTo(-s*0.55,s*0.7); G.lineTo(s*0.55,s*0.7); G.stroke(); G.beginPath(); G.arc(-s*0.75,-s*0.12,s*0.3,0,Math.PI); G.stroke(); G.beginPath(); G.arc(s*0.75,-s*0.12,s*0.3,0,Math.PI); G.stroke(); break;
      case 'validator': G.beginPath(); G.moveTo(-s*0.4,-s*0.75); G.lineTo(-s*0.4,-s*0.05); G.lineTo(-s*0.8,s*0.8); G.lineTo(s*0.8,s*0.8); G.lineTo(s*0.4,-s*0.05); G.lineTo(s*0.4,-s*0.75); G.stroke(); G.beginPath(); G.moveTo(-s*0.6,-s*0.75); G.lineTo(s*0.6,-s*0.75); G.stroke(); break;
      case 'portfolio': G.beginPath(); G.arc(0,0,s,0,6.283); G.stroke(); G.beginPath(); G.moveTo(0,0); G.lineTo(0,-s); G.moveTo(0,0); G.lineTo(s*0.85,s*0.5); G.stroke(); break;
      case 'tester': G.beginPath(); for(let t=-1;t<=1.001;t+=0.1){ const x=Math.sin(t*Math.PI*1.4)*s*0.55; t<=-1?G.moveTo(x,t*s):G.lineTo(x,t*s); } G.stroke();
        G.beginPath(); for(let t=-1;t<=1.001;t+=0.1){ const x=-Math.sin(t*Math.PI*1.4)*s*0.55; t<=-1?G.moveTo(x,t*s):G.lineTo(x,t*s); } G.stroke();
        G.beginPath(); for(let t=-0.7;t<=0.71;t+=0.35){ const x=Math.sin(t*Math.PI*1.4)*s*0.55; G.moveTo(x,t*s); G.lineTo(-x,t*s); } G.stroke(); break;
      default: G.beginPath(); G.arc(0,0,s*0.6,0,6.283); G.stroke();
    }
    G.restore(); }
  // helper para usar el MISMO símbolo del agente en el panel (en vez del emoji viejo)
  window.hydraIcon=function(key,size){ const dpr=Math.min(window.devicePixelRatio||1,2);
    const cv2=document.createElement('canvas'); cv2.width=cv2.height=size*dpr; cv2.style.width=cv2.style.height=size+'px';
    const ct=cv2.getContext('2d'); ct.setTransform(dpr,0,0,dpr,0,0);
    const a=byKey[key], rgb=a?a.rgb:'127,246,255';
    glyph(key,size/2,size/2,size*0.30,rgb,1,ct); return cv2; };
  // ícono del agente como dataURL (para el tooltip) — cacheado
  const _iconCache={};
  window.hydraIconURL=function(key){ if(_iconCache[key])return _iconCache[key]; try{ const c=window.hydraIcon(key,26); _iconCache[key]=c.toDataURL(); return _iconCache[key]; }catch(e){ return ''; } };
  // MONEDAS metálicas de cada instrumento (para el panel al hacer clic)
  const COIN={
    GOLD:{c:'196,148,20',c2:'255,226,132',dk:'74,50,8',sym:'ingots'},
    SILVER:{c:'150,160,172',c2:'240,244,250',dk:'58,64,72',sym:'ingot'},
    PLATINUM:{c:'176,182,190',c2:'242,246,250',dk:'70,74,80',sym:'pt'},
    OIL:{c:'52,46,40',c2:'150,110,60',dk:'18,14,10',sym:'drop'},
    BRENT:{c:'44,46,52',c2:'120,96,64',dk:'16,16,20',sym:'barrel'},
    'S&P 500':{c:'36,120,66',c2:'132,222,152',dk:'8,42,20',sym:'spider'},
    NASDAQ:{c:'34,116,176',c2:'132,216,255',dk:'8,38,62',sym:'chip'},
    DOW:{c:'74,90,168',c2:'156,176,255',dk:'22,28,66',sym:'bull'},
    DXY:{c:'36,138,90',c2:'134,232,178',dk:'8,46,28',sym:'dollar'},
    DAX:{c:'150,40,44',c2:'255,150,150',dk:'50,10,12',sym:'ticker'},
    FTSE:{c:'40,60,140',c2:'150,170,255',dk:'12,20,54',sym:'ticker'},
    NIKKEI:{c:'170,40,60',c2:'255,150,170',dk:'56,12,20',sym:'ticker'} };
  // nombre "de calle" de cada símbolo (para la moneda del cajón y el panel)
  const MKT_NAMES={XAUUSD:'GOLD',XAGUSD:'SILVER',XPTUSD:'PLATINUM',XTIUSD:'OIL',USOIL:'OIL',WTI:'OIL',
    XBRUSD:'BRENT',UKOIL:'BRENT',US100:'NASDAQ',USTEC:'NASDAQ',NAS100:'NASDAQ',US30:'DOW',
    US500:'S&P 500',SPX500:'S&P 500',DE40:'DAX',GER40:'DAX',UK100:'FTSE',JPN225:'NIKKEI',JP225:'NIKKEI'};
  window.mktName=s=>MKT_NAMES[(s||'').toUpperCase()]||'';
  function coinMeta(sym){ const nm=(sym==='DXY')?'DXY':(MKT_NAMES[(sym||'').toUpperCase()]||(sym||'').toUpperCase());
    return COIN[nm]||{c:'110,132,156',c2:'205,222,240',dk:'18,28,44',sym:'ticker',t:nm}; }
  function coinSym(ct,kind,s,txt){ ct.lineWidth=Math.max(1.4,s*0.14);
    switch(kind){
      case 'ingots': for(let k=0;k<3;k++){ const oy=(k-1)*s*0.44; ct.beginPath(); ct.moveTo(-s*0.62,oy+s*0.13); ct.lineTo(s*0.48,oy+s*0.13); ct.lineTo(s*0.64,oy-s*0.13); ct.lineTo(-s*0.46,oy-s*0.13); ct.closePath(); ct.fill(); } break;
      case 'ingot': ct.beginPath(); ct.moveTo(-s*0.62,s*0.22); ct.lineTo(s*0.5,s*0.22); ct.lineTo(s*0.7,-s*0.2); ct.lineTo(-s*0.42,-s*0.2); ct.closePath(); ct.fill(); break;
      case 'drop': ct.beginPath(); ct.moveTo(0,-s*0.85); ct.bezierCurveTo(s*0.75,-s*0.1,s*0.58,s*0.75,0,s*0.75); ct.bezierCurveTo(-s*0.58,s*0.75,-s*0.75,-s*0.1,0,-s*0.85); ct.closePath(); ct.fill(); break;
      case 'barrel': ct.beginPath(); ct.moveTo(-s*0.5,-s*0.7); ct.lineTo(s*0.5,-s*0.7); ct.lineTo(s*0.5,s*0.7); ct.lineTo(-s*0.5,s*0.7); ct.closePath(); ct.stroke(); ct.beginPath(); ct.moveTo(-s*0.5,-s*0.25); ct.lineTo(s*0.5,-s*0.25); ct.moveTo(-s*0.5,s*0.25); ct.lineTo(s*0.5,s*0.25); ct.stroke(); break;
      case 'chip': ct.beginPath(); ct.rect(-s*0.5,-s*0.5,s,s); ct.stroke(); for(let k=-1;k<=1;k++){ ct.beginPath(); ct.moveTo(-s*0.72,k*s*0.34); ct.lineTo(-s*0.5,k*s*0.34); ct.moveTo(s*0.5,k*s*0.34); ct.lineTo(s*0.72,k*s*0.34); ct.moveTo(k*s*0.34,-s*0.72); ct.lineTo(k*s*0.34,-s*0.5); ct.moveTo(k*s*0.34,s*0.5); ct.lineTo(k*s*0.34,s*0.72); ct.stroke(); } ct.beginPath(); ct.arc(0,0,s*0.16,0,7); ct.fill(); break;
      case 'spider': ct.beginPath(); ct.ellipse(0,s*0.18,s*0.26,s*0.34,0,0,7); ct.fill(); ct.beginPath(); ct.arc(0,-s*0.26,s*0.19,0,7); ct.fill(); for(const sg of [-1,1]){ for(let k=0;k<4;k++){ ct.beginPath(); ct.moveTo(sg*s*0.14,s*0.05); ct.quadraticCurveTo(sg*s*0.62,-s*0.15+k*s*0.22,sg*s*0.82,s*0.1+k*s*0.2); ct.stroke(); } } break;
      case 'bull': ct.beginPath(); ct.moveTo(-s*0.72,-s*0.45); ct.quadraticCurveTo(-s*0.45,-s*0.8,-s*0.22,-s*0.42); ct.moveTo(s*0.72,-s*0.45); ct.quadraticCurveTo(s*0.45,-s*0.8,s*0.22,-s*0.42); ct.stroke(); ct.beginPath(); ct.moveTo(-s*0.36,-s*0.35); ct.lineTo(-s*0.3,s*0.42); ct.quadraticCurveTo(0,s*0.78,s*0.3,s*0.42); ct.lineTo(s*0.36,-s*0.35); ct.closePath(); ct.stroke(); break;
      case 'dollar': ct.font='700 '+(s*1.6)+'px system-ui,sans-serif'; ct.textAlign='center'; ct.textBaseline='middle'; ct.fillText('$',0,s*0.06); break;
      case 'pt': ct.font='700 '+(s*1.15)+'px system-ui,sans-serif'; ct.textAlign='center'; ct.textBaseline='middle'; ct.fillText('Pt',0,s*0.06); break;
      default: ct.font='700 '+(s*0.72)+'px system-ui,sans-serif'; ct.textAlign='center'; ct.textBaseline='middle'; ct.fillText((txt||'?').slice(0,4),0,s*0.05); }
  }
  window.marketCoin=function(sym,size){ const dpr=Math.min(window.devicePixelRatio||1,2);
    const cv2=document.createElement('canvas'); cv2.width=cv2.height=size*dpr; cv2.style.width=cv2.style.height=size+'px';
    const ct=cv2.getContext('2d'); ct.setTransform(dpr,0,0,dpr,0,0);
    const m=coinMeta(sym), R=size*0.44, cx=size/2, cy=size/2;
    const gr=ct.createRadialGradient(cx-R*0.35,cy-R*0.35,R*0.1,cx,cy,R); gr.addColorStop(0,'rgba('+m.c2+',1)'); gr.addColorStop(1,'rgba('+m.c+',1)');
    ct.fillStyle=gr; ct.beginPath(); ct.arc(cx,cy,R,0,7); ct.fill();
    ct.strokeStyle='rgba('+m.c2+',0.85)'; ct.lineWidth=R*0.1; ct.beginPath(); ct.arc(cx,cy,R*0.82,0,7); ct.stroke();
    ct.save(); ct.translate(cx,cy); ct.fillStyle='rgba('+m.dk+',0.92)'; ct.strokeStyle='rgba('+m.dk+',0.92)'; ct.lineJoin='round'; ct.lineCap='round';
    coinSym(ct,m.sym,R*0.5,m.t); ct.restore(); return cv2; };
  // LA MARCA (vibora robotica en hexagono) dibujada en el lienzo, pieza a pieza,
  // para poder encender los ojos y la boca por separado. Coordenadas 0..120.
  const MK_FRAME=new Path2D('M60 5 L107.6 32.5 L107.6 87.5 L60 115 L12.4 87.5 L12.4 32.5 Z M60 17.6 L96.7 38.8 L96.7 81.2 L60 102.4 L23.3 81.2 L23.3 38.8 Z');
  const MK_SENSOR=new Path2D('M60 23 L65 34.5 L60 41.5 L55 34.5 Z');
  const MK_EYES=[new Path2D('M26.5 40.5 L54 55 L54 59 L26.5 49 Z'),
                 new Path2D('M93.5 40.5 L66 55 L66 59 L93.5 49 Z')];
  const MK_PLATES=[new Path2D('M27.5 62.5 L38 67 L38 78.5 L27.5 72 Z'),
                   new Path2D('M92.5 62.5 L82 67 L82 78.5 L92.5 72 Z')];
  const MK_MOUTH=[new Path2D('M42 62 L78 62 L78 67.5 L71.5 84 L67 68.5 L63.5 74 L60 67.5 L56.5 74 L53 68.5 L48.5 84 L42 67.5 Z'),
                  new Path2D('M52 87 L56.5 81.5 L60 85.5 L63.5 81.5 L68 87 L60 96.5 Z')];
  /* r = radio en pantalla; eye = color rgb de los ojos; blink 0..1 = latido de los ojos */
  function drawMark(cx,cy,r,body,eye,blink,al){
    const k=r*2/110;
    g.save(); g.translate(cx,cy); g.scale(k,k); g.translate(-60,-60);
    g.fillStyle='rgba('+body+','+(0.85*al)+')'; g.fill(MK_FRAME,'evenodd');
    g.fillStyle='rgba('+body+','+(0.7*al)+')';
    g.fill(MK_SENSOR); MK_PLATES.forEach(q=>g.fill(q));
    // BOCA: parte del cuerpo, sin luz propia (el latido vive en los ojos)
    g.fillStyle='rgba('+body+','+(0.78*al)+')'; MK_MOUTH.forEach(q=>g.fill(q));
    // OJOS: aquí late la luz. Color por estado — verde en marcha, amarillo al
    // señalar, rojo en pausa — y el brillo sube y baja con `blink`.
    // Una sola pasada: repetir la forma en modo aditivo satura a blanco y se
    // pierde el color. El latido va en el alfa y en el halo, no en capas.
    g.shadowColor='rgba('+eye+',1)'; g.shadowBlur=(8+26*blink)/k;
    g.fillStyle='rgba('+eye+','+(0.6+0.4*blink)*al+')'; MK_EYES.forEach(q=>g.fill(q));
    g.shadowBlur=0; g.restore();
  }
  /* ==================== FONDO: PLACA / CPU ====================
     El reactor deja de flotar en el espacio: ahora vive sobre el die de un chip
     y de sus pines salen pistas que llegan a las ventanas laterales. Las pistas
     no se inventan: se rutan hacia el borde interior REAL de cada panel, medido
     del DOM, para que se lea que la app está cableada a sus opciones. */
  const PCB={ traces:[], etch:[], die:null };
  // esquina achaflanada: las pistas de una placa nunca giran a 90° secos
  function chamfer(pts, c){
    if(pts.length<3) return pts.slice();
    const out=[pts[0]];
    for(let i=1;i<pts.length-1;i++){
      const p=pts[i-1], q=pts[i], r=pts[i+1];
      const d1=Math.hypot(q.x-p.x,q.y-p.y), d2=Math.hypot(r.x-q.x,r.y-q.y);
      const c1=Math.min(c,d1*0.45), c2=Math.min(c,d2*0.45);
      out.push({x:q.x+(p.x-q.x)/(d1||1)*c1, y:q.y+(p.y-q.y)/(d1||1)*c1});
      out.push({x:q.x+(r.x-q.x)/(d2||1)*c2, y:q.y+(r.y-q.y)/(d2||1)*c2});
    }
    out.push(pts[pts.length-1]);
    return out;
  }
  function panelAnchors(){
    // borde interior de cada ventana del HUD: ahí es donde debe morder la pista
    const out=[];
    document.querySelectorAll('.hudcol .hud').forEach(el=>{
      const r=el.getBoundingClientRect();
      if(r.width<40) return;                       // oculta en pantalla estrecha
      const left=r.left<W/2;
      out.push({x:left?r.right:r.left, y:r.top+Math.min(26,r.height*0.3), left, panel:true});
    });
    return out;
  }
  function buildPCB(){
    // El die vive dentro del anillo de modulos: su diagonal no debe cruzarlo.
    // Rh es el radio del anillo, asi que el medio lado se limita a Rh*0.55/√2·√2.
    const half=Math.max(64,Math.min(Rh*0.46,Math.min(W,H)*0.14));
    // ya no se dibuja ninguna pastilla: 'die' solo marca de donde salen las
    // pistas hacia las ventanas. En el centro manda la cara.
    PCB.die={x:CX-half, y:CY-half, s:half*2};
    PCB.traces=[]; PCB.etch=[];
    const anchors=panelAnchors();
    // si no hay paneles (móvil), se cablea al borde de la pantalla
    const edge=[];
    if(!anchors.length){
      for(let i=0;i<4;i++){ edge.push({x:-20, y:H*(0.2+i*0.2), left:true});
                            edge.push({x:W+20, y:H*(0.2+i*0.2), left:false}); }
    }
    const targets=anchors.concat(edge);
    targets.forEach((t,i)=>{
      const sideX=t.left?PCB.die.x:PCB.die.x+PCB.die.s;
      // el pin de salida se reparte por el lado del die, no todos del mismo punto
      const py=PCB.die.y+PCB.die.s*(0.18+0.64*((i%5)+0.5)/5);
      const midX=t.left ? sideX-(sideX-t.x)*(0.42+0.12*(i%3))
                        : sideX+(t.x-sideX)*(0.42+0.12*(i%3));
      const pts=[{x:sideX,y:py},{x:midX,y:py},{x:midX,y:t.y},{x:t.x,y:t.y}];
      PCB.traces.push({pts:chamfer(pts,10), left:t.left, panel:!!t.panel,
                       ph:i*0.37, sp:0.00013+0.00005*(i%4)});
    });
    // pistas verticales de relleno: dan densidad de placa arriba y abajo
    for(let i=0;i<8;i++){
      const up=i%2===0, px=PCB.die.x+PCB.die.s*(0.14+0.72*((i>>1)+0.5)/4);
      const endY=up?-20:H+20, midY=up?PCB.die.y-40-i*14:PCB.die.y+PCB.die.s+40+i*14;
      const outX=px+(i%4<2?-1:1)*(30+i*9);
      const pts=[{x:px,y:up?PCB.die.y:PCB.die.y+PCB.die.s},{x:px,y:midY},
                 {x:outX,y:midY},{x:outX,y:endY}];
      PCB.traces.push({pts:chamfer(pts,9), left:i%4<2, panel:false,
                       ph:i*0.61, sp:0.00010+0.00004*(i%3)});
    }
    // grabado de fondo: segmentos cortos, deterministas (misma placa cada vez)
    let seed=1337;
    const rnd=()=>((seed=(seed*1103515245+12345)&0x7fffffff)/0x7fffffff);
    for(let i=0;i<340;i++){
      const x=rnd()*W, y=rnd()*H, ln=10+rnd()*58, hor=rnd()<0.5;
      PCB.etch.push({x,y,ln,hor,a:0.05+rnd()*0.13});
    }
    pcbDirty=false;
  }
  /* Un componente soldado: caja alineada a la placa (no girada), con pines en el
     lado que mira al chip y una pista que llega hasta ahi. */
  function compBox(c,w,h){ return {x:c.x-w/2,y:c.y-h/2,w,h}; }
  function compEntry(b){
    // por donde entra la pista: el lado de la caja que mira al centro
    const dx=CX-(b.x+b.w/2), dy=CY-(b.y+b.h/2);
    if(Math.abs(dx)*b.h>Math.abs(dy)*b.w)
      return {x:dx>0?b.x+b.w:b.x, y:b.y+b.h/2, side:dx>0?'r':'l'};
    return {x:b.x+b.w/2, y:dy>0?b.y+b.h:b.y, side:dy>0?'b':'t'};
  }
  function wireTo(entry,rcore,ph,sp,col){
    /* Ruteo de placa: un tocón radial corto para salir del núcleo (como el fan-out
       de un BGA) y a partir de ahí SOLO tramos ortogonales hasta el borde de la
       caja. Antes la primera pata era una diagonal larga y el conjunto parecía un
       abanico de radios, no cobre. */
    const a=Math.atan2(entry.y-CY,entry.x-CX);
    const p0={x:CX+Math.cos(a)*rcore, y:CY+Math.sin(a)*rcore};
    const stub=Math.max(18,rcore*0.30);
    const p1={x:p0.x+Math.cos(a)*stub, y:p0.y+Math.sin(a)*stub};
    const e={x:entry.x,y:entry.y};
    let pts;
    if(entry.side==='l'||entry.side==='r'){          // se entra en horizontal
      const midX=p1.x+(e.x-p1.x)*0.55;
      pts=[p0,p1,{x:midX,y:p1.y},{x:midX,y:e.y},e];
    } else {                                          // se entra en vertical
      const midY=p1.y+(e.y-p1.y)*0.55;
      pts=[p0,p1,{x:p1.x,y:midY},{x:e.x,y:midY},e];
    }
    return {pts:chamfer(pts,7), col, ph, sp, comp:true};
  }
  function drawComp(b,rgb,al,lit,fillA){
    g.globalCompositeOperation='source-over';
    g.fillStyle='rgba(6,11,18,'+(fillA===undefined?0.94:fillA)+')';
    if(g.roundRect){ g.beginPath(); g.roundRect(b.x,b.y,b.w,b.h,3); g.fill(); }
    else g.fillRect(b.x,b.y,b.w,b.h);
    g.globalCompositeOperation='lighter';
    const ig=g.createLinearGradient(b.x,b.y,b.x,b.y+b.h);
    ig.addColorStop(0,'rgba('+rgb+','+(0.16*al)+')'); ig.addColorStop(1,'rgba('+rgb+',0)');
    g.fillStyle=ig;
    if(g.roundRect){ g.beginPath(); g.roundRect(b.x,b.y,b.w,b.h,3); g.fill(); }
    else g.fillRect(b.x,b.y,b.w,b.h);
    if(lit){ g.shadowColor='rgba('+rgb+',1)'; g.shadowBlur=lit; }
    g.lineWidth=lit?2:1.3; g.strokeStyle='rgba('+rgb+','+((lit?1:0.82)*al)+')';
    if(g.roundRect){ g.beginPath(); g.roundRect(b.x,b.y,b.w,b.h,3); g.stroke(); }
    else g.strokeRect(b.x,b.y,b.w,b.h);
    g.shadowBlur=0;
  }
  function compPins(b,entry,rgb,al){
    g.strokeStyle='rgba('+rgb+','+(0.4*al)+')'; g.lineWidth=1.3; g.beginPath();
    const hor=(entry.side==='l'||entry.side==='r'), n=3;
    for(let i=1;i<=n;i++){ const f=i/(n+1);
      if(hor){ const y=b.y+b.h*f, x=entry.side==='l'?b.x:b.x+b.w, d=entry.side==='l'?-6:6;
        g.moveTo(x,y); g.lineTo(x+d,y); }
      else { const x=b.x+b.w*f, y=entry.side==='t'?b.y:b.y+b.h, d=entry.side==='t'?-6:6;
        g.moveTo(x,y); g.lineTo(x,y+d); } }
    g.stroke();
  }
  function drawPCB(now){
    if(pcbDirty) buildPCB();
    const d=PCB.die;
    // 1) grabado tenue: textura de cobre bajo todo lo demás
    g.strokeStyle='rgba(90,150,190,0.5)'; g.lineWidth=1;
    for(const e of PCB.etch){ g.globalAlpha=e.a; g.beginPath(); g.moveTo(e.x,e.y);
      g.lineTo(e.hor?e.x+e.ln:e.x, e.hor?e.y:e.y+e.ln); g.stroke(); }
    g.globalAlpha=1;
    // 2) pistas: cobre apagado + un pulso de datos que viaja del chip a la ventana.
    //    Las de dentro del die van DESPUES de rellenarlo, o el relleno las tapa.
    for(const t of PCB.traces) drawTrace(t,now);
  }
  function drawTrace(t,now){
      const col=t.left?'90,190,255':'170,120,255';        // azul a un lado, violeta al otro
      g.strokeStyle='rgba('+col+','+(t.panel?0.28:(t.comp?0.30:0.16))+')';
      g.lineWidth=(t.panel||t.comp)?1.4:1;
      g.beginPath(); g.moveTo(t.pts[0].x,t.pts[0].y);
      for(let i=1;i<t.pts.length;i++) g.lineTo(t.pts[i].x,t.pts[i].y);
      g.stroke();
      // longitudes acumuladas para poder recorrer la pista a velocidad constante
      if(!t.len){ t.seg=[]; t.len=0;
        for(let i=1;i<t.pts.length;i++){ const l=Math.hypot(t.pts[i].x-t.pts[i-1].x,t.pts[i].y-t.pts[i-1].y);
          t.seg.push(l); t.len+=l; } }
      const u=((now*t.sp+t.ph)%1);
      let want=u*t.len, k=0;
      while(k<t.seg.length&&want>t.seg[k]){ want-=t.seg[k]; k++; }
      if(k>=t.seg.length) return;      // el pulso ya salió del último tramo
      const p=t.pts[k], q=t.pts[k+1], f=t.seg[k]?want/t.seg[k]:0;
      const hx=p.x+(q.x-p.x)*f, hy=p.y+(q.y-p.y)*f;
      const tl=Math.min(t.seg[k]*f, 26), ux=(q.x-p.x)/(t.seg[k]||1), uy=(q.y-p.y)/(t.seg[k]||1);
      const gr=g.createLinearGradient(hx,hy,hx-ux*tl,hy-uy*tl);
      gr.addColorStop(0,'rgba('+col+',0.9)'); gr.addColorStop(1,'rgba('+col+',0)');
      g.strokeStyle=gr; g.lineWidth=t.panel?2:1.5;
      g.beginPath(); g.moveTo(hx,hy); g.lineTo(hx-ux*tl,hy-uy*tl); g.stroke();
      // al llegar a la ventana, la almohadilla destella
      if(t.panel){ const e=t.pts[t.pts.length-1], near=Math.max(0,1-(1-u)*14);
        g.fillStyle='rgba('+col+','+(0.25+0.7*near)+')';
        g.beginPath(); g.arc(e.x,e.y,2+2.6*near,0,7); g.fill();
        if(near>0.05){ g.strokeStyle='rgba('+col+','+(0.5*near)+')'; g.lineWidth=1;
          g.beginPath(); g.arc(e.x,e.y,4+7*(1-near),0,7); g.stroke(); } }
  }
  // TRADE CONTEXT: orbe de memoria. Gira fuera del orbe, en un plano inclinado,
  // en sentido contrario a los agentes (por eso a veces pasa por detrás).
  const CTXO={sx:0,sy:0,depth:0.5,n:-1,pulse:-1e9,tilt:0.46};
  /* El componente de memoria tiene que SOBREVIVIR entre cuadros: su caja de
     colisión se guarda al dibujarlo y se consulta en el cuadro siguiente. Si se
     recreara cada frame, el cursor nunca lo encontraría (y no hacía nada). */
  const CTXMOD={key:'__ctx',name:'CONTEXT',rgb:'176,150,255',ctx:true,
                role:'Memoria de decisiones',x:0,y:0,ang:0};
  async function pollCtx(){ try{ const d=await (await fetch('/trade-context?limit=1')).json();
      const t=(d.stats&&d.stats.total)|0; if(CTXO.n>=0&&t>CTXO.n) CTXO.pulse=performance.now(); CTXO.n=t;
      CTXCOUNT=t; renderHudSys();
    }catch(e){} }
  pollCtx(); setInterval(pollCtx,12000);
  window.ctxCaptured=()=>{ CTXO.pulse=performance.now(); pollCtx(); };
  window.ctxAt=()=>[CTXO.sx,CTXO.sy];      // donde va el modulo ahora mismo
  window.pcbRewire=()=>{ pcbDirty=true; };   // re-rutea a las ventanas
  let A=[], byKey={}, curOpen=null, openAt=0;
  function build(){
    const ags=DATA?DATA.agents:[], N=(ags.length||1)+1;   // +1: el modulo trade_context
    A=ags.map((a,i)=>{ const baseAng=-Math.PI/2 + i/N*Math.PI*2;
      const extra=Math.min(2,(entriesOf(a.key)/4)|0);
      const t=makeTree((i+1)*131+7,extra), sg=t.segs;
      // grafo del árbol (coords locales): raíces salen de (0,0); hijos encadenan por sus extremos
      const roots=[], next=sg.map(()=>[]);
      sg.forEach((s,si)=>{ if(Math.abs(s[0])<0.5&&Math.abs(s[1])<0.5) roots.push(si);
        sg.forEach((s2,sj)=>{ if(si!==sj&&Math.abs(s2[0]-s[2])<0.5&&Math.abs(s2[1]-s[3])<0.5) next[si].push(sj); }); });
      const sparks=[], ns=Math.max(3,Math.round(sg.length*0.55));
      for(let s=0;s<ns;s++){ const seg=roots.length?roots[(Math.random()*roots.length)|0]:0; sparks.push({seg,t:Math.random(),sp:0.012+Math.random()*0.020}); }
      return {key:a.key,name:a.name,emoji:a.emoji,role:a.role,baseAng,x:CX,y:CY,ang:baseAng,lx:CX,ly:CY,lalign:'center',rgb:hx2(PAL[i%PAL.length]),segs:sg,leaves:t.leaves,roots,next,sparks}; });
    byKey={}; A.forEach(a=>byKey[a.key]=a);
    CTXO.baseAng=-Math.PI/2 + (ags.length||1)/N*Math.PI*2;   // ultima plaza del anillo
    dirty=false;
  }
  function qpt(a,c,b,t){ const u=1-t; return [u*u*a[0]+2*u*t*c[0]+t*t*b[0], u*u*a[1]+2*u*t*c[1]+t*t*b[1]]; }
  cv.addEventListener('mousemove',e=>{ const r=cv.getBoundingClientRect(); mx=e.clientX-r.left; my=e.clientY-r.top; });
  cv.addEventListener('mouseleave',()=>{ mx=my=-9999; });
  function openHydra(){ const names=(DATA?DATA.agents:[]).map(a=>a.emoji+' '+a.name).join(' · ');
    openInfo('🐉 HYDRA · orquestador','<p class="role">El núcleo que coordina a todos los agentes: recibe sus señales, decide y ejecuta como un solo cerebro.</p><div class="empty">Controla a: '+names+'</div>');
    speak('Hydra en línea, '+SIR+'. Coordino a los '+(DATA?DATA.agents.length:0)+' agentes.'); }
  cv.addEventListener('click',()=>{ if(!booted){ $('#activate').click(); return; }
    if(hoverI>=0&&RING3S[hoverI]) openMarket(RING3S[hoverI].symbol); else if(hoverC) openTradeContext(); else if(hoverKey==='__hydra') openHydra(); else if(hoverKey) openAgent(hoverKey); else { speakStatus(); toast('HYDRA · '+(DATA?DATA.agents.length:0)+' agentes'); } });
  function frame(now){
    if(!DATA){ requestAnimationFrame(frame); return; }
    if(dirty||A.length!==(DATA.agents||[]).length) build();
    // órbita lenta: los agentes giran alrededor de Hydra (que queda al centro)
    // COMPONENTES FIJOS: van soldados a la placa. La elipse (más ancha que alta)
    // aprovecha el hueco entre la cinta de arriba y el aviso de abajo, y deja los
    // laterales para las ventanas.
    const NA=A.length+1, arx=S*0.34, ary=S*0.195;
    for(let i=0;i<A.length;i++){ const a=A[i];
      a.ang=-Math.PI/2+(i+0.5)*Math.PI*2/NA;       // FIJO: sin el término del giro
      a.x=CX+Math.cos(a.ang)*arx; a.y=CY+Math.sin(a.ang)*ary; }
    CTXMOD.ang=-Math.PI/2+(A.length+0.5)*Math.PI*2/NA;
    CTXMOD.x=CX+Math.cos(CTXMOD.ang)*arx; CTXMOD.y=CY+Math.sin(CTXMOD.ang)*ary;
    CTXO.sx=CTXMOD.x; CTXO.sy=CTXMOD.y; CTXO.ang=CTXMOD.ang;
    byKey['__ctx']=CTXMOD;                       // para que LINKS lo encuentre
    const RING=A.concat([CTXMOD]);
    // Los componentes son cajas fijas: el cursor se prueba contra la caja de cada
    // uno (las cajas se guardan al dibujarlas en el cuadro anterior).
    hoverKey=null; hoverC=false;
    const inBox=(b)=>b&&mx>=b.x-3&&mx<=b.x+b.w+3&&my>=b.y-3&&my<=b.y+b.h+3;
    for(const a of RING){ if(inBox(a.box)){ hoverKey=a.key; break; } }
    if(hoverKey==='__ctx'){ hoverC=true; hoverKey=null; }
    { const hr=Math.max(22,S*0.055)*1.55, dx=CX-mx,dy=CY-my;              // la cara del centro
      if(!hoverKey&&!hoverC&&dx*dx+dy*dy<hr*hr) hoverKey='__hydra'; }
    // TERCER ANILLO: un segmento por instrumento, girando al revés que los módulos
    // El anillo exterior existe siempre: se construye con los símbolos VIGILADOS
    // y se va rellenando con precios cuando /instruments responde.
    const WATCH=(DATA&&DATA.core&&DATA.core.symbols)||[];
    const byS={}; INSTR.forEach(r=>{ byS[String(r.symbol||'').toUpperCase()]=r; });
    const order=WATCH.map(x=>String(x).toUpperCase());
    INSTR.forEach(r=>{ const k=String(r.symbol||'').toUpperCase(); if(order.indexOf(k)<0) order.push(k); });
    // fijos (DXY): referencia que siempre cierra el anillo, aunque no haya datos
    ((DATA&&DATA.core&&DATA.core.pinned)||['DXY']).forEach(k=>{
      k=String(k).toUpperCase(); if(order.indexOf(k)<0) order.push(k); });
    // Se reusa la lista del cuadro anterior si los símbolos no cambiaron, para no
    // perder las posiciones ni la caché de las pistas en cada frame.
    const key3=order.join(',');
    let RING3;
    if(RING3S.length&&RING3S._key===key3){ RING3=RING3S;
      RING3.forEach((r,i)=>{ const fresh=byS[String(r.symbol||'').toUpperCase()];
        if(fresh) Object.assign(r,{price:fresh.price,change_pct:fresh.change_pct,
                                   verdict:fresh.verdict,trend:fresh.trend,spark:fresh.spark}); }); }
    else { RING3=order.map(k=>Object.assign({},byS[k]||{},{symbol:k}));
           RING3._key=key3; RING3S=RING3; }
    const NI=RING3.length;
    // elipse exterior, más ancha que alta: cabe entre la cinta y el aviso de abajo
    const irx=S*0.475, iry=S*0.285;
    for(let i=0;i<NI;i++){ const an=-Math.PI/2+(i+0.5)*Math.PI*2/(NI||1);
      RING3[i].x=CX+Math.cos(an)*irx; RING3[i].y=CY+Math.sin(an)*iry; }
    hoverI=-1;
    for(let i=0;i<NI;i++){ if(inBox(RING3[i].box)){ hoverI=i; hoverKey=null; hoverC=false; break; } }

    cv.style.cursor=(hoverKey||hoverC||!booted)?'pointer':'default';
    const sel=(typeof selected!=='undefined')?selected:null;         // agente abierto (por click)
    if(sel!==curOpen){ curOpen=sel; openAt=now; }
    const grow=sel?Math.min(1,(now-openAt)/450):0;
    const flash=now<wakeUntil?1:0, Rorb=Rh;
    g.globalCompositeOperation='source-over'; g.fillStyle='#03050b'; g.fillRect(0,0,W,H);
    g.globalCompositeOperation='lighter'; g.shadowBlur=0;
    // FONDO: la placa. Dos halos de color muy tenues (azul / violeta, como la
    // foto de referencia) y encima el cobre, las pistas y el die.
    const nb1=g.createRadialGradient(W*0.18,H*0.72,0,W*0.18,H*0.72,W*0.55);
    nb1.addColorStop(0,'rgba(30,90,150,0.10)'); nb1.addColorStop(1,'rgba(0,0,0,0)');
    g.fillStyle=nb1; g.fillRect(0,0,W,H);
    const nb2=g.createRadialGradient(W*0.84,H*0.24,0,W*0.84,H*0.24,W*0.5);
    nb2.addColorStop(0,'rgba(95,45,150,0.10)'); nb2.addColorStop(1,'rgba(0,0,0,0)');
    g.fillStyle=nb2; g.fillRect(0,0,W,H);
    drawPCB(now);
    // volumen del orbe (glow interno)
    const vg=g.createRadialGradient(CX,CY,Rorb*0.08,CX,CY,Rorb); vg.addColorStop(0,halted?'rgba(255,110,130,0.07)':'rgba(90,185,225,0.08)'); vg.addColorStop(0.7,'rgba(40,95,125,0.05)'); vg.addColorStop(1,'rgba(0,0,0,0)');
    g.fillStyle=vg; g.beginPath(); g.arc(CX,CY,Rorb,0,7); g.fill();
    // conexiones de HYDRA (centro) → agentes. Base tenue + resaltado del agente señalado/abierto
    const hyHover=hoverKey==='__hydra';
    const hk=hoverC?'__ctx':hoverKey;      // el modulo de memoria cuenta como nodo
    /* Sin líneas nuevas cruzando la placa: para enseñar QUÉ está conectado CON QUÉ
       se encienden en BLANCO las pistas que ya existen — la del componente
       señalado, y las de aquellos con los que trabaja (LINKS). */
    let lit=null, focus=[sel,hk].filter(Boolean);
    if(hyHover) lit=RING.map(a=>a.key);              // el núcleo enciende todas
    else if(focus.length){ lit=focus.slice();
      focus.forEach(k=>LINKS.forEach(L=>{
        if(L[0]===k&&lit.indexOf(L[1])<0) lit.push(L[1]);
        if(L[1]===k&&lit.indexOf(L[0])<0) lit.push(L[0]); })); }
    if(lit) for(const a of RING){ const i=lit.indexOf(a.key);
      if(i<0||!a.wire) continue;
      const own=focus.indexOf(a.key)>=0;             // el señalado, más brillante
      const w=a.wire;
      g.shadowColor='rgba(255,255,255,1)'; g.shadowBlur=own?10:5;
      g.strokeStyle='rgba(255,255,255,'+(own?0.95:0.55)+')'; g.lineWidth=own?2.2:1.6;
      g.beginPath(); g.moveTo(w.pts[0].x,w.pts[0].y);
      for(let j=1;j<w.pts.length;j++) g.lineTo(w.pts[j].x,w.pts[j].y);
      g.stroke(); g.shadowBlur=0; }
    // MÓDULOS: componentes soldados a la placa. Caja alineada, pines hacia el chip
    // y una pista que llega hasta ellos, igual que las ventanas.
    const CW=Math.max(62,Math.min(96,S*0.115)), CH=Math.max(24,Math.min(34,S*0.040));
    const RCORE=Math.max(22,S*0.055)*1.75;         // borde del circulo que gira
    for(let ai=0;ai<RING.length;ai++){ const a=RING[ai], isctx=!!a.ctx;
      const st=isctx?'idle':stateOf(a.key), h=isctx?hoverC:(a.key===hoverKey);
      const o=!isctx&&a.key===sel, on=st==='active'||st==='alert';
      const dim=((hoverKey||hoverC)&&!h&&!o), al=dim?0.45:1;
      const load=isctx?Math.min(1,CTXO.n/40):Math.min(1,entriesOf(a.key)/8);
      const gw=o?CW*(1+grow*0.22):CW, gh=o?CH*(1+grow*0.16):CH;
      const b2=compBox(a,gw,gh); a.box=b2;
      const entry=compEntry(b2);
      // pista al chip: se cachea mientras no cambie la geometria
      if(!a.wire||a.wireK!==(gw+','+gh+','+CX+','+CY))
        { a.wire=wireTo(entry,RCORE,ai*0.41,0.00016+0.00004*(ai%3),
                        isctx?'176,150,255':a.rgb); a.wireK=gw+','+gh+','+CX+','+CY; }
      drawTrace(a.wire,now);
      compPins(b2,entry,a.rgb,al);
      drawComp(b2,a.rgb,al,(on||h||o)?(o?14+grow*16:(h?18:9)):0);
      // contenido HORIZONTAL: en una placa la serigrafía no va girada
      const gr2=Math.min(8,gh*0.30), gx=b2.x+gh*0.52;
      if(isctx){ g.strokeStyle='rgba('+a.rgb+','+(dim?0.5:0.98)+')'; g.lineWidth=1.2;
        for(let k=-1;k<=1;k++){ g.beginPath();
          g.ellipse(gx,a.y+k*gr2*0.5,gr2*0.62,gr2*0.24,0,0,7); g.stroke(); } }
      else glyph(a.key,gx,a.y,gr2,a.rgb,dim?0.5:0.98);
      g.font='700 '+Math.max(7.5,Math.min(9.5,gh*0.30))+'px system-ui,sans-serif';
      g.textAlign='left'; g.textBaseline='middle';
      g.fillStyle='rgba('+a.rgb+','+((h||o)?1:0.78)*al+')';
      g.fillText(isctx?('CTX'+(CTXO.n>0?' '+CTXO.n:'')):shortName(a.name),
                 gx+gr2+5, a.y-(load>0.02?2:0));
      // barra de actividad: una traza fina bajo la serigrafía
      if(load>0.02){ g.strokeStyle='rgba('+a.rgb+','+(0.8*al)+')'; g.lineWidth=1.6;
        const x0=gx+gr2+5, x1=b2.x+b2.w-5;
        g.beginPath(); g.moveTo(x0,a.y+gh*0.26); g.lineTo(x0+(x1-x0)*load,a.y+gh*0.26); g.stroke(); }
      if(isctx){ const pt=(now-CTXO.pulse)/1400;      // captura nueva
        if(pt>=0&&pt<1){ g.strokeStyle='rgba(200,180,255,'+(0.6*(1-pt))+')'; g.lineWidth=1.6;
          g.beginPath(); g.rect(b2.x-pt*14,b2.y-pt*10,b2.w+pt*28,b2.h+pt*20); g.stroke(); } }
      if(st==='alert'){ g.strokeStyle='rgba(255,93,115,'+(0.45+0.45*Math.sin(now*0.006))+')';
        g.lineWidth=1.6; g.strokeRect(b2.x-4,b2.y-4,b2.w+8,b2.h+8); } }
    // INSTRUMENTOS: también componentes, en la elipse de fuera y sin girar.
    const IW=Math.max(56,Math.min(88,S*0.105)), IH=Math.max(20,Math.min(28,S*0.033));
    for(let i=0;i<NI;i++){ const r=RING3[i], sym=String(r.symbol||'').toUpperCase();
      const hi=hoverI===i, live=OPENSYMS.has(sym);
      const col=live?'52,211,153':(r.verdict==='compra'?'52,211,153':(r.verdict==='venta'?'255,93,115':(r.verdict?'110,150,175':'80,110,132')));
      const bb=compBox(r,hi?IW*1.06:IW,hi?IH*1.06:IH); r.box=bb;
      const entry=compEntry(bb);
      if(!r.wire||r.wireK!==(IW+','+CX+','+CY))
        { r.wire=wireTo(entry,RCORE,i*0.53+2.1,0.00012+0.00004*(i%3),col); r.wireK=IW+','+CX+','+CY; }
      r.wire.col=col; drawTrace(r.wire,now);
      compPins(bb,entry,col,1);
      drawComp(bb,col,1,hi?16:(live?9:0),0.92);
      if(live){ const bp=0.5+0.5*Math.sin(now*0.004);   // posición abierta
        g.strokeStyle='rgba(52,211,153,'+(0.3+0.5*bp)+')'; g.lineWidth=1.4;
        g.strokeRect(bb.x-3,bb.y-3,bb.w+6,bb.h+6); }
      g.textAlign='center'; g.textBaseline='middle';
      g.font='700 '+Math.max(7.5,Math.min(9.5,IH*0.36))+'px system-ui,sans-serif';
      g.fillStyle='rgba('+col+','+(hi?1:0.9)+')';
      g.fillText(((window.mktName&&window.mktName(sym))||sym).slice(0,10), r.x, r.y-IH*0.17);
      g.font=Math.max(6.5,Math.min(8.5,IH*0.30))+'px system-ui,sans-serif';
      g.fillStyle='rgba('+col+',0.62)';
      g.fillText(r.change_pct==null?'· · ·':((r.change_pct>=0?'+':'')+r.change_pct.toFixed(2)+'%'),
                 r.x, r.y+IH*0.26); }
    if(hoverI>=0) cv.style.cursor='pointer';
    // REACTOR HYDRA: anillos concéntricos girando en sentidos opuestos y, en el
    // centro, la marca: ojos verdes en marcha, amarillos al señalar, rojos en pausa,
    // y la luz de la boca latiendo.
    const hyR=(hyHover?1.14:1)*Math.max(22,S*0.055), hp=0.5+0.5*Math.sin(now*0.003);
    const hyc=halted?'255,93,115':'127,246,255', em=halted?'255,150,165':'205,246,255';
    g.save(); g.translate(CX,CY); g.lineJoin='round';
    // resplandor del núcleo (lo que hace que se lea como reactor y no como círculo)
    const cg=g.createRadialGradient(0,0,0,0,0,hyR*1.9);
    cg.addColorStop(0,'rgba('+em+','+(0.30+0.10*hp+flash*0.2)+')');
    cg.addColorStop(0.45,'rgba('+hyc+',0.10)'); cg.addColorStop(1,'rgba(0,0,0,0)');
    g.fillStyle=cg; g.beginPath(); g.arc(0,0,hyR*1.9,0,7); g.fill();
    // anillo exterior de marcas: 48 ticks, gira despacio hacia la derecha
    g.save(); g.rotate(now*0.00009);
    g.strokeStyle='rgba('+hyc+',0.42)'; g.lineWidth=1; g.beginPath();
    for(let k=0;k<48;k++){ const an=k*Math.PI/24, lg=(k%6===0)?hyR*0.20:hyR*0.09;
      g.moveTo(Math.cos(an)*hyR*1.62,Math.sin(an)*hyR*1.62);
      g.lineTo(Math.cos(an)*(hyR*1.62+lg),Math.sin(an)*(hyR*1.62+lg)); }
    g.stroke(); g.restore();
    // anillo segmentado: 6 arcos gruesos girando al revés (la "carcasa" del reactor)
    g.save(); g.rotate(-now*0.00016);
    g.strokeStyle='rgba('+hyc+','+(0.55+0.25*hp)+')'; g.lineWidth=Math.max(2,hyR*0.09); g.lineCap='butt';
    for(let k=0;k<6;k++){ const a0=k*Math.PI/3+0.16; g.beginPath(); g.arc(0,0,hyR*1.34,a0,a0+Math.PI/3-0.32); g.stroke(); }
    g.restore();
    // anillo interior fino: el marco donde vive la cabeza
    g.strokeStyle='rgba('+hyc+',0.75)'; g.lineWidth=1.6; g.beginPath(); g.arc(0,0,hyR,0,7); g.stroke();
    // LA CABEZA: los ojos laten y su color dice el estado
    // Colores puros: el lienzo va en modo 'lighter' y cualquier mezcla tira a
    // blanco, asi que se parte de un canal dominante y los otros muy bajos.
    const eyeCol=halted?'255,16,40':(hyHover?'255,196,0':'0,255,102');
    const blink=0.35+0.65*Math.pow(0.5+0.5*Math.sin(now*0.0042),2);   // latido, no parpadeo plano
    g.restore();
    drawMark(CX,CY,hyR*0.92,em,eyeCol,blink,1);
    g.save(); g.translate(CX,CY);
    if(booted){
      g.font='700 10px system-ui,sans-serif'; g.textAlign='center'; g.textBaseline='middle';
      g.fillStyle='rgba('+em+',0.95)'; g.fillText('HYDRA',0,hyR*1.62+22);
      g.font='8px system-ui,sans-serif'; g.fillStyle='rgba('+hyc+',0.5)';
      g.fillText(halted?'DETENIDO':'REACTOR EN LÍNEA',0,hyR*1.62+34);
    }
    g.restore();
    // ---- PLACA APAGADA (pantalla de inicio) ----
    // Se dibuja todo y luego se atenúa: así el icono ya está en su sitio final y
    // al encender no hay ningún salto, solo se ilumina.
    if(!booted){
      g.globalCompositeOperation='source-over';
      g.fillStyle='rgba(3,5,11,0.80)'; g.fillRect(0,0,W,H);
      g.globalCompositeOperation='lighter';
      const hr2=Math.max(22,S*0.055), warm=hyHover;
      const st2=0.4+0.6*Math.pow(0.5+0.5*Math.sin(now*0.0022),2);   // rojo en espera
      g.strokeStyle=warm?'rgba(255,196,0,0.5)':'rgba(120,150,175,0.22)'; g.lineWidth=1.4;
      g.beginPath(); g.arc(CX,CY,hr2*1.34,0,7); g.stroke();
      drawMark(CX,CY,hr2*0.92, warm?'150,225,255':'96,116,136',
               warm?'255,196,0':'255,16,40', warm?1:st2, 1);
      g.font='700 12px system-ui,sans-serif'; g.textAlign='center'; g.textBaseline='middle';
      g.fillStyle=warm?'rgba(223,250,255,0.95)':'rgba(150,170,190,0.5)';
      try{ g.letterSpacing='9px'; }catch(e){}     // no está en todos los navegadores
      g.fillText('HYDRA',CX,CY+hr2*1.34+27);
      try{ g.letterSpacing='0px'; }catch(e){}     // no dejarlo pegado al resto del texto
      g.font='8px system-ui,sans-serif';
      g.fillStyle=warm?'rgba(255,196,0,0.7)':'rgba(255,60,80,0.55)';
      g.fillText(warm?L('PULSA PARA ENCENDER','CLICK TO POWER ON'):L('APAGADO','OFF'),
                 CX,CY+hr2*1.34+42);
    }
    // etiquetas (nombres): SOLO del agente señalado o abierto (pantalla más limpia)
    g.font='11px system-ui,sans-serif'; g.textBaseline='middle';
    for(const a of A){ if(a.key!==hoverKey&&a.key!==sel) continue; g.textAlign=a.lalign; g.fillStyle='rgba(220,240,250,0.96)'; g.fillText(a.name.toUpperCase(),a.lx,a.ly); }
    // tooltip al pasar el cursor: rol + con quién colabora + pista de click
    const tip=$('#tip');
    if(!booted){ tip.classList.remove('show'); requestAnimationFrame(frame); return; }
    if(hoverI>=0&&RING3S[hoverI]){ const r=RING3S[hoverI], sym=String(r.symbol||'');
      const bb=r.box||{x:r.x,y:r.y,w:0,h:0};
      tip.style.left=(bb.x+bb.w+12)+'px'; tip.style.top=(bb.y+bb.h/2)+'px';
      const nm=(window.mktName&&window.mktName(sym))||'';
      tip.innerHTML='📈 <b>'+escapeHtml(sym)+'</b>'+(nm?' · '+escapeHtml(nm):'')
        +'<br><span>'+(r.price==null?L('esperando datos del broker','waiting for broker data')
          :r.price+' · '+(r.change_pct>=0?'+':'')+r.change_pct.toFixed(2)+'% · '+escapeHtml(String(r.verdict||'')))+'</span>'
        +(OPENSYMS.has(sym.toUpperCase())?'<br><span style="color:#34d399">'+L('con posición abierta','position open')+'</span>':'')
        +'<br><span style="opacity:.7">'+L('clic para ver precio y técnicos','click for price & technicals')+'</span>';
      tip.classList.add('show'); }
    else if(hoverC){ tip.style.left=(CTXO.sx+22)+'px'; tip.style.top=CTXO.sy+'px';
      tip.innerHTML='🗄 <b>TRADE CONTEXT</b> · '+L('memoria','memory')+'<br><span>'
        +(CTXO.n>0?CTXO.n+' '+L('capturas guardadas','captures stored'):L('esperando la primera captura','waiting for the first capture'))
        +'</span><br><span>↔ Reviewer, Architect</span>'
        +'<br><span style="opacity:.7">'+L('clic para ver todo lo que guarda','click to see everything it stores')+'</span>';
      tip.classList.add('show'); }
    else if(hoverKey==='__hydra'){ tip.style.left=(CX+30)+'px'; tip.style.top=CY+'px';
      tip.innerHTML='🐉 <b>HYDRA</b> · orquestador<br><span>Coordina a todos los agentes como un solo cerebro.</span><br><span style="opacity:.7">clic para ver el conjunto</span>';
      tip.classList.add('show'); }
    else if(hoverKey){ const a=byKey[hoverKey];
      const nb=LINKS.filter(L=>L[0]===hoverKey||L[1]===hoverKey).map(L=>L[0]===hoverKey?L[1]:L[0]).map(k=>byKey[k]?byKey[k].name:k);
      tip.style.left=(a.x+24)+'px'; tip.style.top=a.y+'px';
      const icu=window.hydraIconURL?window.hydraIconURL(a.key):''; const ico=icu?'<img src="'+icu+'" style="width:16px;height:16px;vertical-align:-3px;margin-right:3px">':a.emoji;
      tip.innerHTML=ico+' <b>'+a.name+'</b> · '+stateOf(a.key)+'<br><span>'+a.role+'</span>'+(nb.length?'<br><span>↔ '+nb.join(', ')+'</span>':'')+'<br><span style="opacity:.7">'+L('clic para ver sus tareas','click to see its tasks')+'</span>';
      tip.classList.add('show'); }
    else tip.classList.remove('show');
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();

addEventListener('resize',()=>{});
load(); setInterval(load,5000);
</script>
</body></html>
"""
