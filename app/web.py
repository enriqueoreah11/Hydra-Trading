"""FastAPI dashboard: estado, OAuth de cTrader, diario, playbook y kill switch."""
from __future__ import annotations

import asyncio
import datetime as dt
import html
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import agent_params
from . import secrets_store
from . import tts as tts_mod
from .broker import Broker
from .config import settings
from .oauth import TokenStore, build_auth_url
from .store import Store


def create_app(store: Store, tokens: TokenStore, broker: Broker, brain=None) -> FastAPI:
    app = FastAPI(title="hydra-trading")
    _static = Path(__file__).parent / "static"
    if _static.is_dir():
        app.mount("/static", StaticFiles(directory=str(_static)), name="static")

    @app.get("/manifest.webmanifest")
    async def manifest():
        return JSONResponse({
            "name": "HYDRA Trading", "short_name": "HYDRA", "start_url": "/",
            "display": "standalone", "background_color": "#04070e", "theme_color": "#04070e",
            "icons": [
                {"src": "/static/icon-180.png", "sizes": "180x180", "type": "image/png"},
                {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png",
                 "purpose": "any maskable"},
            ],
        })
    # aplica los parámetros y claves que el usuario haya ajustado desde la UI (persisten en el volumen)
    agent_params.load_overrides(settings.data_path / "overrides.json")
    secrets_store.load()
    _brain_state = {"task": None}
    _bal_cache = {"value": None}   # último balance conocido (para que /status no se cuelgue)

    def _apply_account(aid: int, env: str) -> None:
        settings.ctrader_account_id = int(aid)
        settings.ctrader_env = env if env in ("demo", "live") else "demo"
        broker.account_id = int(aid)
        broker.client.account_id = int(aid)
        broker.client.ws_url = settings.ws_url

    # aplica la cuenta elegida desde la UI (si existe), antes de que el cliente arranque
    try:
        _acc = json.loads((settings.data_path / "account.json").read_text())
        if _acc.get("account_id"):
            _apply_account(int(_acc["account_id"]), _acc.get("env", "demo"))
    except Exception:  # noqa: BLE001
        pass
    # idioma elegido desde la UI
    try:
        _lg = (settings.data_path / "lang.txt").read_text().strip()
        if _lg in ("es", "en", "mix"):
            settings.owner_lang = _lg
    except Exception:  # noqa: BLE001
        pass

    @app.on_event("startup")
    async def _start_brain():
        # NUNCA debe tumbar el arranque de la web: cualquier fallo aquí se ignora.
        try:
            if brain is not None and settings.ctrader_account_id and (
                    _brain_state["task"] is None or _brain_state["task"].done()):
                _brain_state["task"] = asyncio.create_task(brain.run_forever(), name="brain")
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger("web").warning("no se pudo arrancar el cerebro al inicio", exc_info=True)

    def _check_token(token: str | None) -> None:
        if settings.dashboard_token and token != settings.dashboard_token:
            raise HTTPException(403, "bad or missing ?token=")

    # ------------------------------------------------------------------ oauth

    @app.get("/oauth/login")
    async def oauth_login():
        if not settings.ctrader_client_id:
            raise HTTPException(500, "CTRADER_CLIENT_ID not configured")
        return RedirectResponse(build_auth_url(settings.ctrader_client_id,
                                               settings.ctrader_redirect_uri))

    @app.get("/oauth/callback")
    async def oauth_callback(code: str = ""):
        if not code:
            raise HTTPException(400, "missing ?code=")
        await tokens.exchange_code(code)
        store.log("system", "oauth", "tokens obtained/renewed via OAuth")
        accounts: list[dict] = []
        try:
            token = await tokens.get_access_token()
            # abre la conexión (auth de app, no requiere account_id) para poder listar cuentas, con timeout
            await broker.client.start()
            await broker.client.wait_connected(timeout=12)
            accounts = await asyncio.wait_for(broker.list_accounts(token), timeout=12)
        except Exception:  # noqa: BLE001 - listing accounts is best-effort here
            pass
        rows = "".join(
            f"<li><code>ctidTraderAccountId={a.get('ctidTraderAccountId')}</code> "
            f"(live={a.get('isLive')}, login={a.get('traderLogin')})</li>"
            for a in accounts)
        return HTMLResponse(
            "<h2>✅ cTrader conectado</h2>"
            "<p>Tokens guardados. Cuentas autorizadas:</p>"
            f"<ul>{rows or '<li>(reinicia el servicio para listar cuentas)</li>'}</ul>"
            "<p>Pon el <code>ctidTraderAccountId</code> elegido en la variable "
            "<code>CTRADER_ACCOUNT_ID</code> y reinicia el servicio.</p>"
            "<a href='/'>← dashboard</a>")

    @app.post("/lang")
    async def set_lang(request: Request):
        try:
            lg = (await request.json()).get("lang", "mix")
        except Exception:  # noqa: BLE001
            lg = "mix"
        if lg not in ("es", "en", "mix"):
            lg = "mix"
        settings.owner_lang = lg
        (settings.data_path / "lang.txt").write_text(lg)
        return {"ok": True, "lang": lg}

    @app.post("/account/select")
    async def account_select(request: Request):
        """Elige la cuenta de cTrader desde la UI: la aplica, persiste y reconecta."""
        try:
            body = await request.json()
            aid = int(body.get("id", 0) or 0)
        except Exception:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": "datos inválidos"}, status_code=400)
        env = body.get("env", "demo")
        if aid <= 0:
            return JSONResponse({"ok": False, "error": "id de cuenta inválido"}, status_code=400)
        try:
            _apply_account(aid, env)
            (settings.data_path / "account.json").write_text(json.dumps({"account_id": aid, "env": env}))
            store.log("system", "account", f"cuenta seleccionada {aid} ({env})")
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": f"al aplicar: {exc}"[:160]}, status_code=500)
        try:
            await broker.client.reconnect()
            await broker.client.wait_connected(timeout=12)
        except Exception:  # noqa: BLE001 - la cuenta ya quedó guardada; la conexión puede tardar
            pass
        if brain is not None and (_brain_state["task"] is None or _brain_state["task"].done()):
            _brain_state["task"] = asyncio.create_task(brain.run_forever(), name="brain")
        return {"ok": True, "account_id": aid, "env": env,
                "connected": broker.client.account_authorized,
                "conn_error": getattr(broker.client, "last_error", "")}

    _tester_state = {"running": False}

    @app.get("/tester/strategy")
    async def tester_get():
        try:
            txt = (settings.data_path / "tester_strategy.txt").read_text()
        except Exception:  # noqa: BLE001
            txt = ""
        return {"strategy": txt}

    @app.post("/tester/strategy")
    async def tester_save(request: Request):
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            return JSONResponse({"ok": False}, status_code=400)
        txt = str(body.get("strategy", ""))[:20000]
        (settings.data_path / "tester_strategy.txt").write_text(txt)
        return {"ok": True, "len": len(txt)}

    def _strategy() -> str:
        try:
            return (settings.data_path / "tester_strategy.txt").read_text().strip()
        except Exception:  # noqa: BLE001
            return ""

    def _tester_precheck():
        if not _strategy():
            return "Primero guarda tu estrategia."
        if not settings.anthropic_api_key:
            return "Falta ANTHROPIC_API_KEY para que el Tester piense."
        if not broker.client.account_authorized:
            return "Conecta cTrader para tener datos de mercado."
        return None

    @app.post("/tester/backtest")
    async def tester_backtest(request: Request):
        err = _tester_precheck()
        if err:
            return {"ok": False, "reason": err}
        if _tester_state["running"]:
            return {"ok": False, "reason": "Ya hay una prueba corriendo."}
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        syms = [body["symbol"].upper()] if body.get("symbol") else settings.symbol_list[:3]
        strat = _strategy()

        async def _run():
            from .agents import tester
            _tester_state["running"] = True
            store.log("tester", "backtest", f"Iniciando backtest de tu estrategia en {', '.join(syms)}…")
            try:
                for s in syms:
                    try:
                        candles = await asyncio.wait_for(
                            broker.candles(s, settings.timeframe, settings.backtest_bars), timeout=20)
                        r = await tester.backtest(strat, s, settings.timeframe, candles,
                                                  samples=settings.backtest_samples,
                                                  horizon=settings.backtest_horizon_bars)
                    except Exception as exc:  # noqa: BLE001
                        r = {"symbol": s, "ok": False, "reason": str(exc)[:120]}
                    if r.get("ok"):
                        store.log("tester", "result",
                                  f"{s}: {r['trades']} operaciones · {r['win_rate']}% aciertos "
                                  f"({r['wins']}W/{r['losses']}L, {r['open']} sin resolver)")
                    else:
                        store.log("tester", "result", f"{s}: {r.get('reason', 'sin resultado')}")
                store.log("tester", "backtest", "Backtest terminado.")
            finally:
                _tester_state["running"] = False

        asyncio.create_task(_run())
        return {"ok": True, "started": True}

    @app.post("/tester/scan")
    async def tester_scan(request: Request):
        err = _tester_precheck()
        if err:
            return {"ok": False, "reason": err}
        from .agents import tester
        from . import indicators
        strat = _strategy()
        found = 0
        for s in settings.symbol_list[:6]:
            try:
                candles = await asyncio.wait_for(
                    broker.candles(s, settings.timeframe, 200), timeout=15)
                if len(candles) < 60:
                    continue
                d = await tester.decide(strat, s, settings.timeframe, indicators.snapshot(candles))
                if d.get("enter") and d.get("direction") in ("buy", "sell"):
                    found += 1
                    store.log("tester", "signal",
                              f"{s}: {d['direction'].upper()} entry {d.get('entry')} "
                              f"SL {d.get('stop_loss')} TP {d.get('take_profit')} — {d.get('reason', '')[:160]}")
            except Exception as exc:  # noqa: BLE001
                store.log("tester", "signal", f"{s}: error {str(exc)[:100]}")
        store.log("tester", "scan", f"Escaneo terminado: {found} entrada(s) según tu estrategia.")
        return {"ok": True, "found": found}

    async def _dxy_snapshot(tf: str):
        """DXY sintético: se calcula de la canasta de divisas (no existe como símbolo en cTrader)."""
        from .broker import Candle
        from . import indicators
        weights = {"EURUSD": -0.576, "USDJPY": 0.136, "GBPUSD": -0.119,
                   "USDCAD": 0.091, "USDSEK": 0.042, "USDCHF": 0.036}
        series: dict[str, list] = {}
        diag: dict[str, str] = {}
        for p in weights:
            try:
                cs = await asyncio.wait_for(broker.candles(p, tf, 220), timeout=12)
                series[p] = [c.close for c in cs]
                diag[p] = f"{len(series[p])} velas"
            except Exception as exc:  # noqa: BLE001
                series[p] = []
                diag[p] = str(exc)[:60]
        # HÍBRIDO: usa los pares que SÍ existen; si falta uno (p.ej. CHF 3.6%) se omite.
        avail = [p for p in weights if len(series.get(p, [])) >= 60]
        if "EURUSD" not in avail or len(avail) < 3:
            miss = [f"{p} ({diag.get(p, '?')})" for p in weights if p not in avail]
            return {"__error__": "Faltan pares clave: " + "; ".join(miss)}
        L = min(len(series[p]) for p in avail)
        closes = []
        for i in range(L):
            val = 50.14348112
            for p in avail:
                v = series[p]
                val *= v[len(v) - L + i] ** weights[p]
            closes.append(val)
        cndls, prev = [], closes[0]
        for c in closes:
            cndls.append(Candle(ts=0, open=prev, high=max(prev, c), low=min(prev, c), close=c, volume=0))
            prev = c
        return indicators.snapshot(cndls)

    def _summarize(s: dict) -> dict:
        price = s["last_close"]; e20, e50, e200 = s["ema20"], s["ema50"], s["ema200"]
        rsi, atr = s["rsi14"], s["atr14"]; lv = s.get("levels", {})
        bulls = sum([price > e200, e20 > e50, rsi > 50, price > e20])
        bears = sum([price < e200, e20 < e50, rsi < 50, price < e20])
        verdict = "compra" if bulls >= 3 else ("venta" if bears >= 3 else "neutral")
        return {"price": round(price, 5), "ema20": e20, "ema50": e50, "ema200": e200,
                "rsi14": rsi, "atr14": atr, "trend": "alcista" if price > e200 else "bajista",
                "verdict": verdict, "supports": lv.get("supports", []),
                "resistances": lv.get("resistances", [])}

    @app.get("/symbols")
    async def symbols_list(q: str = ""):
        """Lista los símbolos del broker (para saber cómo se llaman los pares)."""
        if not broker.client.account_authorized:
            return {"ok": False, "reason": "Conecta cTrader."}
        try:
            await broker.symbol_id(settings.symbol_list[0] if settings.symbol_list else "EURUSD")
        except Exception:  # noqa: BLE001 - solo para forzar la carga de símbolos
            pass
        names = broker.symbol_names()
        if q:
            names = [n for n in names if q.upper() in n]
        return {"ok": True, "count": len(names), "symbols": names[:400]}

    _TFS = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}

    @app.get("/market/{symbol}")
    async def market_tech(symbol: str, tf: str = Query("")):
        """Resumen técnico de un instrumento en la temporalidad tf."""
        symbol = symbol.upper()
        timeframe = tf.upper() if tf.upper() in _TFS else settings.timeframe
        if not broker.client.account_authorized:
            return {"ok": False, "reason": "Conecta cTrader para ver los datos."}
        from . import indicators
        try:
            if symbol == "DXY":
                snap = await _dxy_snapshot(timeframe)
                if not snap:
                    return {"ok": False, "reason": "No pude calcular el DXY."}
                if snap.get("__error__"):
                    return {"ok": False, "reason": snap["__error__"]}
            else:
                candles = await asyncio.wait_for(broker.candles(symbol, timeframe, 250), timeout=15)
                if len(candles) < 60:
                    return {"ok": False, "reason": "Pocos datos para este símbolo."}
                snap = indicators.snapshot(candles)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "reason": str(exc)[:140]}
        return {"ok": True, "symbol": symbol, "timeframe": timeframe, **_summarize(snap)}

    @app.get("/correlations")
    async def correlations():
        """Matriz de correlación de rendimientos entre los instrumentos vigilados."""
        import math
        if not broker.client.account_authorized:
            return {"ok": False, "reason": "Conecta cTrader para calcular correlaciones con datos reales."}
        closes: dict[str, list[float]] = {}
        for s in settings.symbol_list:
            try:
                cs = await broker.candles(s, settings.timeframe, 150)
                closes[s] = [c.close for c in cs]
            except Exception:  # noqa: BLE001
                pass

        def rets(v):
            return [(v[i] - v[i - 1]) / v[i - 1] for i in range(1, len(v)) if v[i - 1]]

        R = {s: rets(v) for s, v in closes.items() if len(v) > 5}
        keys = list(R)
        pairs = []
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                n = min(len(R[keys[i]]), len(R[keys[j]]))
                if n < 8:
                    continue
                a, b = R[keys[i]][-n:], R[keys[j]][-n:]
                ma, mb = sum(a) / n, sum(b) / n
                cov = sum((a[k] - ma) * (b[k] - mb) for k in range(n))
                va = sum((x - ma) ** 2 for x in a)
                vb = sum((x - mb) ** 2 for x in b)
                if va <= 0 or vb <= 0:
                    continue
                pairs.append({"a": keys[i], "b": keys[j], "corr": round(cov / math.sqrt(va * vb), 2)})
        pairs.sort(key=lambda p: -abs(p["corr"]))
        return {"ok": True, "pairs": pairs, "max": settings.max_correlation, "timeframe": settings.timeframe}

    @app.get("/accounts")
    async def accounts_list():
        """Lista las cuentas autorizadas (ctidTraderAccountId) para saber cuál poner en CTRADER_ACCOUNT_ID."""
        if not tokens.has_tokens:
            return {"ok": False, "reason": "sin OAuth — conecta cTrader primero"}
        try:
            token = await tokens.get_access_token()
            await broker.client.start()
            await broker.client.wait_connected(timeout=12)
            accs = await asyncio.wait_for(broker.list_accounts(token), timeout=12)
            return {"ok": True, "current": settings.ctrader_account_id, "env": settings.ctrader_env,
                    "accounts": [{"id": a.get("ctidTraderAccountId"), "live": a.get("isLive"),
                                  "login": a.get("traderLogin")} for a in accs]}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "reason": str(exc)[:200]}

    # -------------------------------------------------------------- controls

    @app.post("/halt")
    async def halt(token: str | None = Query(None), reason: str = "manual"):
        _check_token(token)
        store.set_halted(True, reason)
        return {"halted": True}

    @app.post("/resume")
    async def resume(token: str | None = Query(None)):
        _check_token(token)
        store.set_halted(False, "manual resume")
        return {"halted": False}

    # -------------------------------------------------------------------- demo

    @app.post("/demo")
    async def demo(token: str | None = Query(None)):
        """Corre un ciclo de analisis con datos SINTETICOS (sin cTrader)."""
        _check_token(token)
        from . import demo as demo_mod
        try:
            results = await demo_mod.run_demo(store)
            return {"ran": True, "results": results}
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, str(e))

    @app.post("/tts")
    async def tts_endpoint(request: Request):
        """Devuelve audio MP3 con voz neural (si hay proveedor configurado)."""
        from . import tts as tts_mod
        text = (await request.body()).decode("utf-8", "ignore")
        audio = await tts_mod.synth(text)
        if not audio:
            # devolvemos el motivo real para poder diagnosticar (la UI lo muestra)
            raise HTTPException(503, tts_mod.last_error() or "TTS neural no configurado")
        return Response(content=audio, media_type="audio/mpeg")

    @app.post("/agent/{key}/params")
    async def set_agent_params(key: str, request: Request):
        """Guarda y aplica en caliente los parámetros de un agente (persisten en el volumen)."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "JSON inválido")
        applied = agent_params.apply_and_save(settings.data_path / "overrides.json", key, body)
        return {"ok": True, "applied": applied}

    @app.get("/secrets")
    async def secrets_status():
        """Estado de las claves (sin exponer valores)."""
        return secrets_store.status()

    @app.post("/secrets")
    async def secrets_set(request: Request):
        """Guarda (cifrada) una clave nueva. Nunca devuelve el valor."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "JSON inválido")
        name, value = body.get("name", ""), body.get("value", "")
        if not secrets_store.can_edit(name):
            raise HTTPException(400, "clave no permitida")
        if not str(value).strip():
            return {"ok": False, "reason": "vacío"}
        try:
            secrets_store.save(name, str(value).strip())
        except RuntimeError as exc:
            raise HTTPException(400, str(exc))
        return {"ok": True}

    @app.get("/tts/health")
    async def tts_health():
        """Diagnóstico de la voz neural: dice si está configurada y prueba una síntesis real."""
        from . import tts as tts_mod
        return await tts_mod.diagnose()

    @app.get("/demo", response_class=HTMLResponse)
    async def demo_page(token: str | None = Query(None)):
        _check_token(token)
        from . import demo as demo_mod
        try:
            results = await demo_mod.run_demo(store)
        except Exception as e:  # noqa: BLE001
            return HTMLResponse(
                f"<h2>⚠️ No se pudo correr el demo</h2><p>{html.escape(str(e))}</p>"
                "<p>El modo demo necesita <code>ANTHROPIC_API_KEY</code> configurada "
                "(como secreto en Fly).</p><a href='/'>← volver</a>", status_code=400)
        cards = ""
        for r in results:
            p = r["proposal"]
            m = r["market"]
            action = p.get("action")
            head = ("🟢 COMPRA" if p.get("direction") == "buy" else "🔴 VENTA") \
                if action == "propose" else "⚪ SIN OPERACION"
            rp = r.get("risk_preview")
            risk_html = ""
            if rp:
                items = "".join(
                    f"<li>{'✅' if c['ok'] else '❌'} {html.escape(c['nombre'])} "
                    f"<span style='color:#888'>({html.escape(c['detalle'])})</span></li>"
                    for c in rp["checks"])
                verdict = "✅ pasa los filtros deterministas" if rp["passes_deterministic"] \
                    else "❌ seria vetada por el Risk Manager"
                risk_html = (f"<p><b>Vista previa del Risk Manager:</b> {verdict} "
                             f"(R:R {rp['risk_reward']})</p><ul>{items}</ul>"
                             f"<p style='color:#888;font-size:.8rem'>{html.escape(rp['nota'])}</p>")
            cards += (
                f"<div class='card'><h3>{html.escape(r['symbol'])} — {head} "
                f"(confianza {p.get('confidence', 0)})</h3>"
                f"<p><b>Tesis:</b> {html.escape(p.get('thesis', ''))}</p>"
                f"<p><b>Invalidacion:</b> {html.escape(p.get('invalidation', ''))}</p>"
                f"<p><b>Niveles:</b> entrada≈ {p.get('last_close')}  "
                f"SL {p.get('stop_loss')}  TP {p.get('take_profit')}</p>"
                f"<p style='color:#888;font-size:.8rem'>indicadores: EMA20 {m['ema20']} · "
                f"EMA50 {m['ema50']} · EMA200 {m['ema200']} · RSI {m['rsi14']} · ATR {m['atr14']}</p>"
                f"{risk_html}</div>")
        return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8">
<title>Hydra — demo</title><style>
 body{{font-family:system-ui,sans-serif;margin:2rem;max-width:900px}}
 .card{{border:1px solid #ddd;border-radius:10px;padding:1rem;margin:1rem 0}}
 .banner{{background:#fff8e1;border:1px solid #ffe082;padding:.8rem 1rem;border-radius:8px}}
</style></head><body>
<h1>🐉 Hydra — modo demo</h1>
<div class="banner">⚠️ Datos <b>sintéticos</b> (no es el mercado real) y <b>sin cTrader</b>.
Sirve para ver cómo el Analyst lee el mercado y cómo el Risk Manager evaluaría la propuesta.
Conecta tu cuenta en <a href="/oauth/login">/oauth/login</a> para operar de verdad.</div>
{cards}
<p><a href="/demo">🔄 correr otra vez</a> · <a href="/">← dashboard</a></p>
</body></html>""")

    # ------------------------------------------------------------------ data

    @app.get("/status")
    async def status():
        version, _ = store.playbook()
        out = {
            "env": settings.ctrader_env,
            "dry_run": settings.dry_run,
            "halted": store.halted,
            "connected": broker.client.account_authorized,
            "oauth_ok": tokens.has_tokens,
            "account_id": settings.ctrader_account_id,
            "symbols": settings.symbol_list,
            "timeframe": settings.timeframe,
            "playbook_version": version,
            "agents": {
                "sentinel_news": settings.enable_news,
                "auditor": settings.enable_auditor,
                "validator": settings.validate_playbook,
                "portfolio": settings.enable_portfolio_check,
                "telegram": bool(settings.telegram_bot_token and settings.telegram_chat_id),
            },
        }
        out["conn_error"] = getattr(broker.client, "last_error", "")
        if broker.client.account_authorized:
            # timeout corto para NO exceder el health check (5-8s); si tarda, usamos el último conocido
            try:
                trader = await asyncio.wait_for(broker.trader(), timeout=2.5)
                out["balance"] = trader["balance"]
                _bal_cache["value"] = trader["balance"]
            except Exception as exc:  # noqa: BLE001
                if _bal_cache["value"] is not None:
                    out["balance"] = _bal_cache["value"]
                else:
                    out["balance_error"] = str(exc)[:160]
        return out

    @app.get("/positions")
    async def positions():
        if not broker.client.account_authorized:
            return []
        pos = await broker.positions()
        for p in pos:
            p["symbol"] = await broker.symbol_name_by_id(p["symbol_id"])
        return pos

    @app.get("/journal")
    async def journal(limit: int = 100):
        return store.recent_journal(limit=min(limit, 500))

    @app.get("/playbook")
    async def playbook():
        version, content = store.playbook()
        return JSONResponse({"version": version, "content": content})

    @app.get("/agents")
    async def agents():
        """Todo lo que la UI JARVIS necesita en una sola llamada."""
        import time as _t
        from .agents_registry import AGENTS, is_enabled

        st = await status()
        journal = store.recent_journal(limit=400)
        by_agent: dict[str, list[dict]] = {}
        for e in journal:
            by_agent.setdefault(e["agent"], []).append(e)
        # las entradas del modo demo cuentan como actividad del Analyst
        by_agent.setdefault("analyst", [])
        by_agent["analyst"] = sorted(
            by_agent.get("analyst", []) + by_agent.get("demo", []),
            key=lambda e: e["ts"], reverse=True)

        now = _t.time()
        active_window = max(3600.0, settings.analysis_interval_min * 90.0)
        out_agents = []
        for a in AGENTS:
            entries = by_agent.get(a["key"], [])[:12]
            enabled = is_enabled(a["key"])
            last_ts = entries[0]["ts"] if entries else None
            if not enabled:
                state = "off"
            elif last_ts and now - last_ts <= active_window:
                state = "active"
            else:
                state = "idle"
            # el watchdog se pone en alerta si no hay conexion con cTrader
            if a["key"] == "watchdog" and st.get("oauth_ok") and not st["connected"]:
                state = "alert"
            out_agents.append({
                **a, "enabled": enabled, "state": state, "last_ts": last_ts,
                "params": agent_params.specs_for(a["key"]),
                "entries": [{
                    "ts": e["ts"], "kind": e["kind"], "symbol": e["symbol"],
                    "content": (e["content"] or "")[:600],
                } for e in entries],
            })
        return {
            "core": {
                "env": st["env"], "dry_run": st["dry_run"], "halted": st["halted"],
                "connected": st["connected"], "oauth_ok": st["oauth_ok"],
                "account_id": st["account_id"], "ctrader_env": settings.ctrader_env,
                "conn_error": st.get("conn_error", ""), "balance_error": st.get("balance_error", ""),
                "balance": st.get("balance"), "model": settings.model,
                "symbols": st["symbols"], "timeframe": st["timeframe"],
                "playbook_version": st["playbook_version"],
                "has_anthropic": bool(settings.anthropic_api_key),
                "voice_enabled": settings.voice_enabled,
                "owner_name": settings.owner_name,
                "owner_lang": settings.owner_lang,
                "tts_server": tts_mod.available(),
                "calendar_embed_url": settings.calendar_embed_url,
                "server_time": now,
            },
            "agents": out_agents,
        }

    @app.get("/calendar")
    async def calendar():
        """Calendario económico nativo: baja el JSON en el servidor (sin CORS ni
        bloqueo de iframe) y lo devuelve limpio para pintarlo con el estilo de la app.

        Fuente: CALENDAR_EMBED_URL si apunta a un JSON, si no NEWS_URL
        (ForexFactory via faireconomy). Devuelve los eventos de los próximos 7 días.
        """
        import time as _t

        import httpx as _httpx

        src = (settings.calendar_embed_url or "").strip()
        if not (src.lower().endswith(".json") or "json" in src.lower()):
            src = settings.news_url  # fuente por defecto (JSON semanal, sin API key)

        events: list[dict] = []
        error = None
        try:
            async with _httpx.AsyncClient(timeout=20, follow_redirects=True) as http:
                r = await http.get(src, headers={"User-Agent": "hydra-trading/1.0"})
                r.raise_for_status()
                raw = r.json()
        except Exception as exc:  # noqa: BLE001
            raw, error = [], str(exc)[:200]

        now = _t.time()
        horizon = now + 7 * 86400
        symbols_ccy = set()
        for s in settings.symbol_list:
            symbols_ccy |= {s[:3], s[3:6]}
        for e in (raw or []):
            date_s = e.get("date") or e.get("dateline") or ""
            ts = None
            try:
                ts = dt.datetime.fromisoformat(str(date_s).replace("Z", "+00:00")).timestamp()
            except Exception:  # noqa: BLE001
                continue
            if ts < now - 3600 or ts > horizon:
                continue
            cur = str(e.get("country") or e.get("currency") or "").upper()
            impact = str(e.get("impact") or "").strip() or "Low"
            events.append({
                "ts": ts,
                "currency": cur,
                "impact": impact,
                "title": str(e.get("title", ""))[:120],
                "forecast": str(e.get("forecast", "") or ""),
                "previous": str(e.get("previous", "") or ""),
                "actual": str(e.get("actual", "") or ""),
                "watched": cur in symbols_ccy,
            })
        events.sort(key=lambda x: x["ts"])
        return {"events": events[:120], "source": src, "server_time": now, "error": error}

    # ------------------------------------------------------------- dashboard

    @app.get("/", response_class=HTMLResponse)
    async def brain_page():
        from .ui import BRAIN_HTML
        return HTMLResponse(BRAIN_HTML)

    @app.get("/classic", response_class=HTMLResponse)
    async def home():
        st = await status()
        entries = store.recent_journal(limit=30)
        version, pb = store.playbook()
        rows = "".join(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td class='c'>{}</td></tr>".format(
                dt.datetime.fromtimestamp(e["ts"], dt.timezone.utc).strftime("%m-%d %H:%M"),
                html.escape(e["agent"]), html.escape(e["kind"]),
                html.escape(e["symbol"] or ""),
                html.escape((e["content"] or "")[:300]))
            for e in entries)
        badge = "🔴 HALTED" if st["halted"] else ("🟡 SIN CONEXION" if not st["connected"] else "🟢 ACTIVO")
        mode = "PAPEL (dry run)" if st["dry_run"] else "REAL"
        return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Hydra Trading</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:2rem;max-width:1100px}}
 table{{border-collapse:collapse;width:100%;font-size:.85rem}}
 td,th{{border:1px solid #ddd;padding:4px 8px;text-align:left;vertical-align:top}}
 .c{{font-family:monospace;font-size:.75rem;word-break:break-all}}
 pre{{background:#f6f6f6;padding:1rem;overflow-x:auto;font-size:.8rem}}
 .pill{{display:inline-block;padding:2px 10px;border-radius:99px;background:#eee;margin-right:8px}}
</style></head><body>
<h1>🐉 Hydra Trading {badge}</h1>
<p>
 <span class="pill">modo: <b>{mode}</b></span>
 <span class="pill">entorno: {st["env"]}</span>
 <span class="pill">cuenta: {st["account_id"] or "—"}</span>
 <span class="pill">balance: {st.get("balance", "—")}</span>
 <span class="pill">simbolos: {", ".join(st["symbols"])} @ {st["timeframe"]}</span>
 <span class="pill">playbook v{version}</span>
 <span class="pill">OAuth: {"✅" if st["oauth_ok"] else '❌ <a href="/oauth/login">conectar cTrader</a>'}</span>
</p>
<p>
 <b>Agentes:</b>
 <span class="pill">🔍 Analyst</span>
 <span class="pill">🛡️ Risk</span>
 <span class="pill">⚡ Executor</span>
 <span class="pill">🌙 Overnight</span>
 <span class="pill">📋 Reviewer</span>
 <span class="pill">🏗️ Architect</span>
 <span class="pill">📰 Sentinel {"✅" if st["agents"]["sentinel_news"] else "—"}</span>
 <span class="pill">🩺 Watchdog {"✅" if st["agents"]["telegram"] else "sin Telegram"}</span>
 <span class="pill">🧾 Auditor {"✅" if st["agents"]["auditor"] else "—"}</span>
 <span class="pill">🧪 Validator {"✅" if st["agents"]["validator"] else "—"}</span>
 <span class="pill">🔗 Portfolio {"✅" if st["agents"]["portfolio"] else "—"}</span>
</p>
{"" if st["connected"] else '''<div style="background:#e8f4ff;border:1px solid #90caf9;padding:.8rem 1rem;border-radius:8px;margin:1rem 0">
 <b>Aun no has conectado cTrader.</b> El cerebro esta en espera, pero puedes ver a los agentes
 en accion con datos de prueba: <a href="/demo"><b>▶ Probar el analista (modo demo)</b></a>.
 Para operar de verdad, <a href="/oauth/login">conecta tu cuenta</a>.</div>'''}
<p>
 <a href="/demo">▶ modo demo (sin cTrader)</a> ·
 Kill switch: <code>POST /halt</code> · <code>POST /resume</code>
 {"(requiere ?token=)" if settings.dashboard_token else ""}</p>
<h2>Diario (ultimas 30 entradas)</h2>
<table><tr><th>UTC</th><th>agente</th><th>evento</th><th>simbolo</th><th>detalle</th></tr>{rows}</table>
<h2>Playbook v{version}</h2><pre>{html.escape(pb)}</pre>
</body></html>"""

    return app
