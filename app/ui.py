"""Interfaz JARVIS: red neuronal de partículas viva (estilo del video de referencia).

Sin nodos fijos ni líneas sólidas: filamentos que convergen en puntos-agente ocultos.
Al acercar el mouse se revela qué agente es. Voz neural (servidor) + palabra mágica.
"""

BRAIN_HTML = r"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>HYDRA · núcleo</title>
<link rel="icon" type="image/png" href="/static/favicon.png">
<link rel="apple-touch-icon" href="/static/icon-180.png">
<link rel="manifest" href="/manifest.webmanifest">
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
#boot{position:fixed;inset:0;z-index:60;background:radial-gradient(900px 700px at 50% 45%,#08202f,#03060c 70%);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:22px;transition:opacity .7s}
#boot.hide{opacity:0;pointer-events:none}
#boot .bt{font-weight:800;letter-spacing:10px;font-size:44px;color:#dffaff;text-shadow:0 0 30px #38e6ff}
#boot .bs{color:#7fd9ee;letter-spacing:3px;font-size:12px}
#boot .bcore{width:120px;height:120px;border-radius:50%;position:relative;display:flex;align-items:center;justify-content:center;animation:bp 1.6s ease-in-out infinite}
#boot .bcore svg{filter:drop-shadow(0 0 10px #38e6ff) drop-shadow(0 0 26px #22d3ee66)}
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
  <div class="bcore">
    <svg viewBox="0 0 120 120" width="120" height="120">
      <g fill="#7ff6ff"><path fill-rule="evenodd" d="M60 5 L107.6 32.5 L107.6 87.5 L60 115 L12.4 87.5 L12.4 32.5 Z M60 17.6 L96.7 38.8 L96.7 81.2 L60 102.4 L23.3 81.2 L23.3 38.8 Z"/><path d="M60 27 L65 37.5 L60 44 L55 37.5 Z"/><path d="M30 43 L53.5 51.5 L53.5 60.5 L30 53.5 Z"/><path d="M90 43 L66.5 51.5 L66.5 60.5 L90 53.5 Z"/><path d="M29 61.5 L39.5 65.5 L39.5 78 L29 71.5 Z"/><path d="M91 61.5 L80.5 65.5 L80.5 78 L91 71.5 Z"/><path d="M45 65 L75 65 L71.5 71.5 L48.5 71.5 Z"/><path d="M49 75.5 L71 75.5 L68 82 L52 82 Z"/><path d="M53.5 86 L66.5 86 L60 95.5 Z"/></g>
    </svg>
    <div class="bring"></div>
  </div>
  <div class="bt">HYDRA</div><div class="bs">RED NEURONAL · 11 AGENTES</div>
  <button id="activate">⏻ ACTIVAR SISTEMA</button>
  <div class="bs" style="opacity:.6">pulsa para encender el sistema</div>
</div>

<div id="top">
  <span class="brand"><svg viewBox="0 0 120 120" width="20" height="20" style="vertical-align:-4px;filter:drop-shadow(0 0 6px #38e6ff)">
    <g fill="#7ff6ff"><path fill-rule="evenodd" d="M60 5 L107.6 32.5 L107.6 87.5 L60 115 L12.4 87.5 L12.4 32.5 Z M60 17.6 L96.7 38.8 L96.7 81.2 L60 102.4 L23.3 81.2 L23.3 38.8 Z"/><path d="M60 27 L65 37.5 L60 44 L55 37.5 Z"/><path d="M30 43 L53.5 51.5 L53.5 60.5 L30 53.5 Z"/><path d="M90 43 L66.5 51.5 L66.5 60.5 L90 53.5 Z"/><path d="M29 61.5 L39.5 65.5 L39.5 78 L29 71.5 Z"/><path d="M91 61.5 L80.5 65.5 L80.5 78 L91 71.5 Z"/><path d="M45 65 L75 65 L71.5 71.5 L48.5 71.5 Z"/><path d="M49 75.5 L71 75.5 L68 82 L52 82 Z"/><path d="M53.5 86 L66.5 86 L60 95.5 Z"/></g>
  </svg> HYDRA</span>
  <span id="vstatus"></span>
  <span class="spacer"></span>
  <button class="btn ghost" id="b-sistema" title="Sistema: voz, acciones y configuración">⚙ SISTEMA</button>
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
  <div class="spacer-v"></div>
  <div id="hudA" class="hud">
    <div class="hudhd"><span class="dot"></span>CONFIGURACION<span class="tf" id="hud-tf"></span></div>
    <div class="sysact">
      <button class="btn ghost" id="hud-halt" onclick="doHalt()">&#9208; HALT</button>
      <button class="btn ghost" onclick="openTradeContext()">&#128452; CONTEXT</button>
      <button class="btn ghost" onclick="$('#b-sistema').click()">&#9881; TODO</button>
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
$('#b-sistema').onclick=()=>{ renderSysInfo(); renderWatch(); renderSecrets(); renderVault(); renderProps(); renderFleet(); $('#sistema').classList.add('open'); };
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
      +rows.map(r=>'<span class="chip2'+((r.strategies||[]).indexOf(a.id)>=0?' on':'')
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
  if(!c.connected&&c.oauth_ok&&c.conn_error) h+='<div class="empty" style="color:#ff5d73">No conecta: '+escapeHtml(c.conn_error)+' — revisa que el entorno (DEMO/LIVE) coincida con la cuenta.</div>';
  if(!c.oauth_ok) h+='<a class="btn" href="/oauth/login" style="display:inline-block;margin:10px 0;text-decoration:none">🔌 Conectar mi cuenta de cTrader</a>';
  if(c.oauth_ok) h+='<a class="btn ghost" href="/oauth/login" style="display:inline-block;margin:8px 0;text-decoration:none">🔄 Reconectar cTrader (actualizar cuentas)</a>';
  if(c.oauth_ok) h+='<div id="sys-accounts" class="empty">Cargando cuentas…</div>';
  h+='<div class="cfg"><span>Modo</span> <b>'+(c.dry_run?'PAPEL (demo)':'REAL')+'</b></div>';
  h+='<div class="cfg"><span>Símbolos</span> <b>'+((c.symbols||[]).join(', ')||'—')+'</b></div>';
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
  if(!d.running) h+='<div class="phelp" style="color:#fbbf24">Ollama no responde en '+escapeHtml(d.url||'')+'. Bájalo en <b>ollama.com</b>, ábrelo (queda en la barra de arriba) y corre <code>ollama pull qwen3:8b</code>.</div>';
  else { h+='<div class="phelp" style="color:#34d399">Ollama activo ✅ — lo que corra en local es gratis e ilimitado.</div>';
    if((d.models||[]).length) h+='<div class="prm"><label>Modelo local</label><select id="olm" onchange="setProvider(\''+P+'\',this.value)">'
      +d.models.map(m=>'<option'+(m===d.selected?' selected':'')+'>'+escapeHtml(m)+'</option>').join('')+'</select></div>';
    h+='<button class="btn ghost" onclick="testLocal()">🧪 Probar modelo</button><div id="lm-test"></div>'; }
  const rt=d.routing||[];
  if(rt.length){ h+='<div class="phelp" style="margin-top:6px">Quién usa qué:</div>'
    +rt.map(r=>'<div class="cfg"><span>'+escapeHtml(r.label)+' <span style="opacity:.55">· '+escapeHtml(r.why)+'</span></span> <b style="color:'+(r.brain==='ollama'?'#34d399':'#7ff6ff')+'">'+(r.brain==='ollama'?'💻 local':'☁️ Claude')+'</b></div>').join(''); }
  el.innerHTML=h; }
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
async function doHalt(){ const halt=$('#b-halt').textContent.includes('HALT'); await fetch(halt?'/halt':'/resume',{method:'POST'}); toast(halt?'Sistema DETENIDO':'Sistema reanudado'); speak(halt?'Sistema detenido, '+SIR+'.':'Sistema reanudado, '+SIR+'.'); load(); }
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
  setTimeout(()=>{const t=$('#tape');if(t)t.classList.add('in');},140);
  renderSessions(); pollPositions(); pollInstruments(); pollNews(); renderHudSys(); pollBrain(); pollTape();
  setInterval(renderSessions,30000); setInterval(pollPositions,20000);
  setInterval(pollInstruments,30000); setInterval(refreshNews,300000);
  setInterval(pollBrain,60000); setInterval(pollTape,6000); }
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

$('#activate').onclick=()=>{ $('#boot').classList.add('hide'); setTimeout(()=>$('#boot').style.display='none',700);
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
  let W=0,H=0,CX=0,CY=0,S=0,Rh=0,Rlab=0,Rctx=0, mx=-9999,my=-9999, hoverKey=null, hoverC=false, hoverI=-1, dirty=true;
  const dpr=Math.min(window.devicePixelRatio||1,1.5);
  function rs(){ W=cv.clientWidth||innerWidth; H=cv.clientHeight||innerHeight; cv.width=W*dpr; cv.height=H*dpr; g.setTransform(dpr,0,0,dpr,0,0); CX=W/2; CY=H*0.53;
    const side=W>1180?296:16;                       // deja aire para las pantallas laterales
    S=Math.max(260,Math.min(W-side*2,H)); Rh=S*0.25; Rlab=S*0.44; Rctx=S*0.385; dirty=true; }
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
    ['tester','analyst'],['tester','executor']];
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
  // LA MARCA (cabeza de robot en hexágono) dibujada en el lienzo, pieza a pieza,
  // para poder encender los ojos y la boca por separado. Coordenadas 0..120.
  const MK_FRAME=new Path2D('M60 5 L107.6 32.5 L107.6 87.5 L60 115 L12.4 87.5 L12.4 32.5 Z '
    +'M60 17.6 L96.7 38.8 L96.7 81.2 L60 102.4 L23.3 81.2 L23.3 38.8 Z');
  const MK_SENSOR=new Path2D('M60 27 L65 37.5 L60 44 L55 37.5 Z');
  const MK_EYES=[new Path2D('M30 43 L53.5 51.5 L53.5 60.5 L30 53.5 Z'),
                 new Path2D('M90 43 L66.5 51.5 L66.5 60.5 L90 53.5 Z')];
  const MK_PLATES=[new Path2D('M29 61.5 L39.5 65.5 L39.5 78 L29 71.5 Z'),
                   new Path2D('M91 61.5 L80.5 65.5 L80.5 78 L91 71.5 Z')];
  const MK_MOUTH=[new Path2D('M45 65 L75 65 L71.5 71.5 L48.5 71.5 Z'),
                  new Path2D('M49 75.5 L71 75.5 L68 82 L52 82 Z'),
                  new Path2D('M53.5 86 L66.5 86 L60 95.5 Z')];
  /* r = radio en pantalla; eye = color rgb de los ojos; blink 0..1 = luz de la boca */
  function drawMark(cx,cy,r,body,eye,blink,al){
    const k=r*2/110;
    g.save(); g.translate(cx,cy); g.scale(k,k); g.translate(-60,-60);
    g.fillStyle='rgba('+body+','+(0.85*al)+')'; g.fill(MK_FRAME,'evenodd');
    g.fillStyle='rgba('+body+','+(0.7*al)+')';
    g.fill(MK_SENSOR); MK_PLATES.forEach(q=>g.fill(q));
    // OJOS: verde en marcha, amarillo al señalar, rojo en pausa
    g.shadowColor='rgba('+eye+',1)'; g.shadowBlur=16/k;
    g.fillStyle='rgba('+eye+','+al+')'; MK_EYES.forEach(q=>g.fill(q));
    g.shadowBlur=0;
    // BOCA: la luz que parpadea, más viva en las barras de arriba
    MK_MOUTH.forEach((q,i)=>{ const b=blink*(1-i*0.22);
      g.shadowColor='rgba(255,255,255,1)'; g.shadowBlur=(4+10*b)/k;
      g.fillStyle='rgba(255,255,255,'+(0.25+0.7*b)*al+')'; g.fill(q); });
    g.shadowBlur=0; g.restore();
  }
  // fondo de universo: campo de estrellas (posiciones normalizadas 0..1)
  const STARS=[]; for(let i=0;i<170;i++) STARS.push({x:Math.random(),y:Math.random(),r:0.3+Math.random()*1.5,ph:Math.random()*6.28,br:0.18+Math.random()*0.55,gold:Math.random()<0.1});
  // estrellas fugaces: aparecen de repente dentro del cielo, con estela afilada
  let SHOOT=[], shootNext=1800, shootLast=0;
  function spawnShoot(){ const fromLeft=Math.random()<0.5;
    const sp=0.00058+Math.random()*0.0004;                             // normalizado por ms (más suave)
    const ang=(0.14+Math.random()*0.20)*Math.PI;                       // 25°..61° hacia abajo
    SHOOT.push({x:(fromLeft?0.05:0.95)+ (fromLeft?1:-1)*Math.random()*0.35,  // aparece dentro del cielo
      y:0.06+Math.random()*0.34,
      vx:(fromLeft?1:-1)*Math.cos(ang)*sp, vy:Math.sin(ang)*sp,
      life:0, max:900+Math.random()*700, tailms:140+Math.random()*120,
      gold:Math.random()<0.25}); }
  // TRADE CONTEXT: orbe de memoria. Gira fuera del orbe, en un plano inclinado,
  // en sentido contrario a los agentes (por eso a veces pasa por detrás).
  const CTXO={sx:0,sy:0,depth:0.5,n:-1,pulse:-1e9,tilt:0.46};
  async function pollCtx(){ try{ const d=await (await fetch('/trade-context?limit=1')).json();
      const t=(d.stats&&d.stats.total)|0; if(CTXO.n>=0&&t>CTXO.n) CTXO.pulse=performance.now(); CTXO.n=t;
      CTXCOUNT=t; renderHudSys();
    }catch(e){} }
  pollCtx(); setInterval(pollCtx,12000);
  window.ctxCaptured=()=>{ CTXO.pulse=performance.now(); pollCtx(); };
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
  cv.addEventListener('click',()=>{ if(hoverI>=0&&RING3S[hoverI]) openMarket(RING3S[hoverI].symbol); else if(hoverC) openTradeContext(); else if(hoverKey==='__hydra') openHydra(); else if(hoverKey) openAgent(hoverKey); else { speakStatus(); toast('HYDRA · '+(DATA?DATA.agents.length:0)+' agentes'); } });
  function frame(now){
    if(!DATA){ requestAnimationFrame(frame); return; }
    if(dirty||A.length!==(DATA.agents||[]).length) build();
    // órbita lenta: los agentes giran alrededor de Hydra (que queda al centro)
    const orb=now*0.00006;
    for(const a of A){ a.ang=a.baseAng+orb; const c=Math.cos(a.ang), s=Math.sin(a.ang);
      a.x=CX+c*Rh; a.y=CY+s*Rh; a.lx=a.x+c*24; a.ly=a.y+s*24;
      a.lalign=c>0.35?'left':(c<-0.35?'right':'center'); }
    CTXO.ang=CTXO.baseAng+orb; CTXO.sx=CX+Math.cos(CTXO.ang)*Rh; CTXO.sy=CY+Math.sin(CTXO.ang)*Rh;
    // RING = los agentes + el modulo de memoria, todos plazas del mismo anillo
    const RING=A.concat([{key:'__ctx',name:'CONTEXT',rgb:'176,150,255',ang:CTXO.ang,ctx:true}]);
    // ANILLO DE MÓDULOS: una banda que gira alrededor del reactor, partida en
    // segmentos separados (uno por agente). Todo el cálculo es en polares.
    const NSEG=Math.max(RING.length,1), SEG=Math.PI*2/NSEG;
    const BAND=Math.max(22,Math.min(46,S*0.062)), GAP=Math.min(SEG*0.28,0.18);
    const RI=Rh-BAND/2, RO=Rh+BAND/2, SPAN=SEG-GAP;
    hoverKey=null; hoverC=false; let hd=1e9;
    { const mr=Math.hypot(mx-CX,my-CY), ma=Math.atan2(my-CY,mx-CX);
      if(mr>RI-4&&mr<RO+4) for(const a of RING){
        let da=ma-a.ang; da=Math.atan2(Math.sin(da),Math.cos(da));      // diferencia angular corta
        if(Math.abs(da)<SPAN/2&&Math.abs(da)<hd){ hd=Math.abs(da); hoverKey=a.key; } } }
    if(hoverKey==='__ctx'){ hoverC=true; hoverKey=null; }
    { const hr=Math.max(22,S*0.055)*1.35, dx=CX-mx,dy=CY-my;                                // reactor Hydra
      if(!hoverKey&&dx*dx+dy*dy<hr*hr) hoverKey='__hydra'; }
    // TERCER ANILLO: un segmento por instrumento, girando al revés que los módulos
    // El anillo exterior existe siempre: se construye con los símbolos VIGILADOS
    // y se va rellenando con precios cuando /instruments responde.
    const WATCH=(DATA&&DATA.core&&DATA.core.symbols)||[];
    const byS={}; INSTR.forEach(r=>{ byS[String(r.symbol||'').toUpperCase()]=r; });
    const order=WATCH.map(x=>String(x).toUpperCase());
    INSTR.forEach(r=>{ const k=String(r.symbol||'').toUpperCase(); if(order.indexOf(k)<0) order.push(k); });
    const RING3=order.map(k=>byS[k]||{symbol:k}); RING3S=RING3;
    const NI=RING3.length, BAND3=Math.max(15,BAND*0.56);
    const R3=RO+12+BAND3/2, RI3=R3-BAND3/2, RO3=R3+BAND3/2;
    const SEG3=NI?Math.PI*2/NI:0, GAP3=Math.min(SEG3*0.22,0.14), SPAN3=SEG3-GAP3;
    const ROT3=-now*0.000048;
    hoverI=-1;
    if(NI){ const mr=Math.hypot(mx-CX,my-CY), ma=Math.atan2(my-CY,mx-CX);
      if(mr>RI3-3&&mr<RO3+3) for(let i=0;i<NI;i++){
        let da=ma-(ROT3-Math.PI/2+i*SEG3); da=Math.atan2(Math.sin(da),Math.cos(da));
        if(Math.abs(da)<SPAN3/2){ hoverI=i; hoverKey=null; break; } } }

    cv.style.cursor=(hoverKey||hoverC)?'pointer':'default';
    const sel=(typeof selected!=='undefined')?selected:null;         // agente abierto (por click)
    if(sel!==curOpen){ curOpen=sel; openAt=now; }
    const grow=sel?Math.min(1,(now-openAt)/450):0;
    const flash=now<wakeUntil?1:0, Rorb=Rh;
    g.globalCompositeOperation='source-over'; g.fillStyle='#03050b'; g.fillRect(0,0,W,H);
    g.globalCompositeOperation='lighter'; g.shadowBlur=0;
    // FONDO UNIVERSO: nebulosas tenues + campo de estrellas
    const nb1=g.createRadialGradient(W*0.24,H*0.30,0,W*0.24,H*0.30,W*0.55); nb1.addColorStop(0,'rgba(70,45,120,0.08)'); nb1.addColorStop(1,'rgba(0,0,0,0)');
    g.fillStyle=nb1; g.fillRect(0,0,W,H);
    const nb2=g.createRadialGradient(W*0.80,H*0.72,0,W*0.80,H*0.72,W*0.5); nb2.addColorStop(0,'rgba(20,70,110,0.07)'); nb2.addColorStop(1,'rgba(0,0,0,0)');
    g.fillStyle=nb2; g.fillRect(0,0,W,H);
    for(const st of STARS){ const tw=0.6+0.4*Math.sin(now*0.001+st.ph), al=st.br*tw;
      g.fillStyle='rgba('+(st.gold?'255,224,170':'185,212,255')+','+al+')'; g.beginPath(); g.arc(st.x*W,st.y*H,st.r,0,7); g.fill(); }
    // ESTRELLAS FUGACES: encienden rápido, se apagan lento, con estela afilada
    const sdt=Math.min(60,now-(shootLast||now)); shootLast=now;
    if(now>shootNext){ spawnShoot(); if(Math.random()<0.15) spawnShoot();
      shootNext=now+3200+Math.random()*7000; }
    for(let i=SHOOT.length-1;i>=0;i--){ const m=SHOOT[i]; m.life+=sdt; m.x+=m.vx*sdt; m.y+=m.vy*sdt;
      if(m.life>m.max||m.x<-0.2||m.x>1.2||m.y>1.2){ SHOOT.splice(i,1); continue; }
      const p=m.life/m.max;
      const ignite=Math.min(1,p/0.08);                                  // encendido casi instantáneo
      const burn=1-Math.max(0,(p-0.30)/0.70);                           // apagado largo
      const fade=ignite*burn*burn; if(fade<=0.01) continue;
      const hx=m.x*W, hy=m.y*H;
      const vpx=m.vx*W, vpy=m.vy*H, vmag=Math.hypot(vpx,vpy)||1;
      const ux=vpx/vmag, uy=vpy/vmag;                                   // dirección de avance
      const tl=vmag*m.tailms;                                           // largo de la estela (px)
      const tx=hx-ux*tl, ty=hy-uy*tl;                                   // punta de la cola
      const px=-uy, py=ux, hw=1.5*fade;                                 // perpendicular (ancho en la cabeza)
      const col=m.gold?'255,214,140':'198,226,255';
      const gr=g.createLinearGradient(hx,hy,tx,ty);
      gr.addColorStop(0,'rgba('+col+','+(0.85*fade)+')'); gr.addColorStop(0.4,'rgba('+col+','+(0.25*fade)+')'); gr.addColorStop(1,'rgba('+col+',0)');
      g.fillStyle=gr; g.beginPath();                                    // estela afilada (aguja): ancha en cabeza, punta en cola
      g.moveTo(hx+px*hw,hy+py*hw); g.lineTo(hx-px*hw,hy-py*hw); g.lineTo(tx,ty); g.closePath(); g.fill();
      const hg=g.createRadialGradient(hx,hy,0,hx,hy,3.4*fade+1);        // cabeza brillante
      hg.addColorStop(0,'rgba(255,255,255,'+fade+')'); hg.addColorStop(0.5,'rgba('+col+','+(0.7*fade)+')'); hg.addColorStop(1,'rgba('+col+',0)');
      g.fillStyle=hg; g.beginPath(); g.arc(hx,hy,3.4*fade+1,0,7); g.fill(); }
    // volumen del orbe (glow interno)
    const vg=g.createRadialGradient(CX,CY,Rorb*0.08,CX,CY,Rorb); vg.addColorStop(0,halted?'rgba(255,110,130,0.12)':'rgba(90,185,225,0.13)'); vg.addColorStop(0.7,'rgba(40,95,125,0.05)'); vg.addColorStop(1,'rgba(0,0,0,0)');
    g.fillStyle=vg; g.beginPath(); g.arc(CX,CY,Rorb,0,7); g.fill();
    // conexiones de HYDRA (centro) → agentes. Base tenue + resaltado del agente señalado/abierto
    const hyHover=hoverKey==='__hydra';
    g.lineWidth=1; g.strokeStyle='rgba(90,150,180,0.12)'; g.beginPath();
    for(const a of A){ g.moveTo(CX,CY); g.lineTo(a.x,a.y); } g.stroke();
    // se ilumina el radio a Hydra del agente abierto (sel) o señalado; o TODOS si señalas el núcleo
    const litHydra=hyHover?A.map(a=>a.key):[sel,hoverKey].filter(Boolean);
    if(litHydra.length){ g.lineWidth=1.7; g.strokeStyle='rgba(127,246,255,0.8)'; g.beginPath();
      for(const a of A){ if(litHydra.indexOf(a.key)>=0){ g.moveTo(CX,CY); g.lineTo(a.x,a.y); } } g.stroke();
      const t=(now*0.0007)%1; g.fillStyle='rgba(190,250,255,0.95)';
      for(const a of A){ if(litHydra.indexOf(a.key)>=0){ g.beginPath(); g.arc(CX+(a.x-CX)*t,CY+(a.y-CY)*t,2.2,0,7); g.fill(); } } }
    // conexiones entre agentes (curvas); se iluminan al pasar el cursor o si el agente está abierto
    for(const L of LINKS){ const a=byKey[L[0]], b=byKey[L[1]]; if(!a||!b) continue;
      const hot=(hoverKey&&(L[0]===hoverKey||L[1]===hoverKey))||(sel&&(L[0]===sel||L[1]===sel));
      const cx=(a.x+b.x)/2+(CX-(a.x+b.x)/2)*0.42, cy=(a.y+b.y)/2+(CY-(a.y+b.y)/2)*0.42;
      g.strokeStyle=hot?'rgba(127,246,255,0.85)':'rgba(90,150,180,0.13)'; g.lineWidth=hot?1.7:1;
      g.beginPath(); g.moveTo(a.x,a.y); g.quadraticCurveTo(cx,cy,b.x,b.y); g.stroke();
      if(hot){ const p=qpt([a.x,a.y],[cx,cy],[b.x,b.y],(now*0.0006)%1); g.fillStyle='rgba(190,250,255,1)'; g.beginPath(); g.arc(p[0],p[1],2.2,0,7); g.fill(); } }
    // MÓDULOS: segmentos de un mismo anillo que gira sin parar alrededor del reactor.
    // Separados entre sí (GAP) para que se lean como piezas independientes.
    for(let ai=0;ai<RING.length;ai++){ const a=RING[ai], isctx=!!a.ctx;
      const st=isctx?'idle':stateOf(a.key), h=isctx?hoverC:(a.key===hoverKey);
      const o=!isctx&&a.key===sel, on=st==='active'||st==='alert';
      const dim=((hoverKey||hoverC)&&!h&&!o), al=dim?0.42:1;
      const load=isctx?Math.min(1,CTXO.n/40):Math.min(1,entriesOf(a.key)/8);
      const push=o?grow*10:(h?4:0);                       // el abierto sale del anillo
      const ri=RI-push*0.35, ro=RO+push, a0=a.ang-SPAN/2, a1=a.ang+SPAN/2;
      const seg=()=>{ g.beginPath(); g.arc(CX,CY,ro,a0,a1); g.arc(CX,CY,ri,a1,a0,true); g.closePath(); };
      // 1) placa: se rellena opaca para que el anillo tape el fondo, como una pieza real
      g.globalCompositeOperation='source-over';
      const pg=g.createRadialGradient(CX,CY,ri,CX,CY,ro);
      pg.addColorStop(0,'rgba(6,14,22,0.95)'); pg.addColorStop(1,'rgba(4,9,15,0.98)');
      g.fillStyle=pg; seg(); g.fill();
      g.globalCompositeOperation='lighter';
      // 2) brillo interior propio del agente
      const ig=g.createRadialGradient(CX,CY,ri,CX,CY,ro);
      ig.addColorStop(0,'rgba('+a.rgb+','+(0.20*al)+')'); ig.addColorStop(1,'rgba('+a.rgb+',0)');
      g.fillStyle=ig; seg(); g.fill();
      // 3) marco del segmento
      if(on||h||o){ g.shadowColor='rgba('+a.rgb+',1)'; g.shadowBlur=o?(14+grow*20):(h?20:10); } else g.shadowBlur=0;
      g.lineJoin='round'; g.lineWidth=(h||o)?2.2:1.4;
      g.strokeStyle='rgba('+a.rgb+','+((h||o)?1:0.8)*al+')'; seg(); g.stroke(); g.shadowBlur=0;
      // 4) barra de actividad pegada al borde interior
      if(load>0.02){ g.strokeStyle='rgba('+a.rgb+','+(0.85*al)+')'; g.lineWidth=2.4; g.lineCap='round';
        g.beginPath(); g.arc(CX,CY,ri+3,a0+0.02,a0+0.02+SPAN*load*0.96); g.stroke(); g.lineCap='butt'; }
      // pulso al llegar una captura nueva al modulo de memoria
      if(isctx){ const pt=(now-CTXO.pulse)/1400;
        if(pt>=0&&pt<1){ g.strokeStyle='rgba(200,180,255,'+(0.6*(1-pt))+')'; g.lineWidth=1.8;
          g.beginPath(); g.arc(CX,CY,ro+2+pt*22,a0,a1); g.stroke(); } }
      // 5) marcas radiales en el borde exterior (detalle de instrumento)
      g.strokeStyle='rgba('+a.rgb+','+(0.30*al)+')'; g.lineWidth=1; g.beginPath();
      for(let k=1;k<5;k++){ const an=a0+SPAN*k/5;
        g.moveTo(CX+Math.cos(an)*(ro+2),CY+Math.sin(an)*(ro+2));
        g.lineTo(CX+Math.cos(an)*(ro+2+(k===2||k===3?6:3)),CY+Math.sin(an)*(ro+2+(k===2||k===3?6:3))); }
      g.stroke();
      if(st==='alert'){ g.strokeStyle='rgba(255,93,115,'+(0.45+0.45*Math.sin(now*0.006))+')'; g.lineWidth=1.8;
        g.beginPath(); g.arc(CX,CY,ro+4,a0,a1); g.stroke(); }
      // 6) contenido: icono + nombre, tangentes al anillo y nunca del revés
      const cx2=CX+Math.cos(a.ang)*(ri+ro)/2, cy2=CY+Math.sin(a.ang)*(ri+ro)/2;
      g.save(); g.translate(cx2,cy2); g.rotate(a.ang+Math.PI/2+(Math.sin(a.ang)>0?Math.PI:0));
      const gr2=Math.min(9,BAND*0.26);
      if(isctx){ g.strokeStyle='rgba('+a.rgb+','+(dim?0.5:0.98)+')'; g.lineWidth=1.2;   // archivo: capas apiladas
        for(let k=-1;k<=1;k++){ g.beginPath(); g.ellipse(0,-BAND*0.16+k*gr2*0.42,gr2*0.62,gr2*0.24,0,0,7); g.stroke(); } }
      else glyph(a.key,0,-BAND*0.16,gr2,a.rgb,dim?0.5:0.98);
      g.font='700 '+Math.max(7,Math.min(9,BAND*0.22))+'px system-ui,sans-serif';
      g.textAlign='center'; g.textBaseline='top';
      g.fillStyle='rgba('+a.rgb+','+((h||o)?1:0.72)*al+')';
      g.fillText(isctx?('CONTEXT'+(CTXO.n>0?' '+CTXO.n:'')):shortName(a.name),0,BAND*0.06);
      g.restore(); }
    // TERCER ANILLO: instrumentos. Mismo lenguaje que los módulos, más fino y al revés.
    for(let i=0;i<NI;i++){ const r=RING3[i], sym=String(r.symbol||'').toUpperCase();
      const mid=ROT3-Math.PI/2+i*SEG3, b0=mid-SPAN3/2, b1=mid+SPAN3/2;
      const hi=hoverI===i, live=OPENSYMS.has(sym);
      const col=live?'52,211,153':(r.verdict==='compra'?'52,211,153':(r.verdict==='venta'?'255,93,115':(r.verdict?'110,150,175':'80,110,132')));
      const push=hi?3:0, ri=RI3, ro=RO3+push;
      const seg=()=>{ g.beginPath(); g.arc(CX,CY,ro,b0,b1); g.arc(CX,CY,ri,b1,b0,true); g.closePath(); };
      g.globalCompositeOperation='source-over';
      g.fillStyle='rgba(5,11,18,0.94)'; seg(); g.fill();
      g.globalCompositeOperation='lighter';
      const ig=g.createRadialGradient(CX,CY,ri,CX,CY,ro);
      ig.addColorStop(0,'rgba('+col+',0)'); ig.addColorStop(1,'rgba('+col+','+(hi?0.24:0.13)+')');
      g.fillStyle=ig; seg(); g.fill();
      if(hi||live){ g.shadowColor='rgba('+col+',1)'; g.shadowBlur=hi?16:8; }
      g.lineJoin='round'; g.lineWidth=hi?1.9:1.2; g.strokeStyle='rgba('+col+','+(hi?1:0.7)+')';
      seg(); g.stroke(); g.shadowBlur=0;
      // marca verde parpadeante si hay posición abierta en ese par
      if(live){ const bp=0.5+0.5*Math.sin(now*0.004);
        g.strokeStyle='rgba(52,211,153,'+(0.35+0.45*bp)+')'; g.lineWidth=2.2;
        g.beginPath(); g.arc(CX,CY,ri+1.6,b0+0.02,b1-0.02); g.stroke(); }
      const cx3=CX+Math.cos(mid)*R3, cy3=CY+Math.sin(mid)*R3;
      g.save(); g.translate(cx3,cy3); g.rotate(mid+Math.PI/2+(Math.sin(mid)>0?Math.PI:0));
      g.font='700 '+Math.max(7,Math.min(9,BAND3*0.34))+'px system-ui,sans-serif';
      g.textAlign='center'; g.textBaseline='middle';
      g.fillStyle='rgba('+col+','+(hi?1:0.85)+')';
      g.fillText(((window.mktName&&window.mktName(sym))||sym).slice(0,9),0,-BAND3*0.16);
      g.font=Math.max(6.5,Math.min(8,BAND3*0.28))+'px system-ui,sans-serif';
      g.fillStyle='rgba('+col+',0.6)';
      g.fillText(r.change_pct==null?'· · ·':((r.change_pct>=0?'+':'')+r.change_pct.toFixed(2)+'%'),0,BAND3*0.28);
      g.restore(); }
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
    // LA CABEZA: ojos por estado y la boca parpadeando
    const eyeCol=halted?'255,93,115':(hyHover?'255,214,90':'52,211,153');
    const blink=0.35+0.65*Math.pow(0.5+0.5*Math.sin(now*0.0042),2);   // latido, no parpadeo plano
    g.restore();
    drawMark(CX,CY,hyR*0.92,em,eyeCol,blink,1);
    g.save(); g.translate(CX,CY);
    g.font='700 10px system-ui,sans-serif'; g.textAlign='center'; g.textBaseline='middle';
    g.fillStyle='rgba('+em+',0.95)'; g.fillText('HYDRA',0,hyR*1.62+22);
    g.font='8px system-ui,sans-serif'; g.fillStyle='rgba('+hyc+',0.5)';
    g.fillText(halted?'DETENIDO':'REACTOR EN LÍNEA',0,hyR*1.62+34);
    g.restore();
    // etiquetas (nombres): SOLO del agente señalado o abierto (pantalla más limpia)
    g.font='11px system-ui,sans-serif'; g.textBaseline='middle';
    for(const a of A){ if(a.key!==hoverKey&&a.key!==sel) continue; g.textAlign=a.lalign; g.fillStyle='rgba(220,240,250,0.96)'; g.fillText(a.name.toUpperCase(),a.lx,a.ly); }
    // tooltip al pasar el cursor: rol + con quién colabora + pista de click
    const tip=$('#tip');
    if(hoverI>=0&&RING3S[hoverI]){ const r=RING3S[hoverI], sym=String(r.symbol||'');
      const mid=ROT3-Math.PI/2+hoverI*SEG3;
      tip.style.left=(CX+Math.cos(mid)*(RO3+14))+'px'; tip.style.top=(CY+Math.sin(mid)*(RO3+14))+'px';
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
        +'</span><br><span style="opacity:.7">'+L('clic para ver todo lo que guarda','click to see everything it stores')+'</span>';
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
