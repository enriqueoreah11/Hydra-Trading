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
from . import research
from . import secrets_store
from . import tts as tts_mod
from . import vault
from .broker import Broker
from .config import settings
from .oauth import TokenStore, build_auth_url
from .store import Store

# Modelos disponibles desde la UI, del más barato al más caro.
# El costo por 1M tokens es aproximado (entrada/salida) y solo sirve de guía.
MODELS: dict[str, dict] = {
    "claude-haiku-4-5-20251001": {"label": "Haiku 4.5", "tier": "económico",
                                  "hint": "el más barato (~20-30x menos que Opus)"},
    "claude-sonnet-5": {"label": "Sonnet 5", "tier": "balance",
                        "hint": "balance costo/calidad (recomendado)"},
    "claude-opus-4-8": {"label": "Opus 4.8", "tier": "máximo",
                        "hint": "el más capaz y el más caro"},
}


def create_app(store: Store, tokens: TokenStore, broker: Broker, brain=None) -> FastAPI:
    app = FastAPI(title="hydra-trading")
    _static = Path(__file__).parent / "static"
    if _static.is_dir():
        app.mount("/static", StaticFiles(directory=str(_static)), name="static")

    ICON_V = "4"          # súbelo cada vez que cambie el icono

    # iOS cachea el apple-touch-icon POR RUTA e ignora el ?v=, así que la versión
    # va dentro de la ruta: /icon/3/… es una URL nueva y no puede reusar la vieja.
    @app.get("/icon/{ver}/{name}")
    async def icon_versioned(ver: str, name: str):
        from fastapi.responses import FileResponse
        f = (Path(__file__).parent / "static" / name).resolve()
        static_dir = (Path(__file__).parent / "static").resolve()
        if static_dir not in f.parents or not f.is_file() or f.suffix != ".png":
            raise HTTPException(status_code=404, detail="no existe")
        # inmutable: la URL cambia cuando cambia el icono, así que se puede cachear
        return FileResponse(f, media_type="image/png",
                            headers={"Cache-Control": "public, max-age=31536000, immutable"})

    # Rutas que iOS busca por su cuenta si no le gusta el <link>. Sin caché para
    # que un icono viejo no se quede pegado.
    @app.get("/apple-touch-icon.png")
    @app.get("/apple-touch-icon-precomposed.png")
    async def apple_touch_icon():
        from fastapi.responses import FileResponse
        return FileResponse(Path(__file__).parent / "static" / "icon-180.png",
                            media_type="image/png",
                            headers={"Cache-Control": "no-store"})

    @app.get("/manifest.webmanifest")
    async def manifest():
        # ICON_V rompe la caché: el sistema operativo guarda el icono de la pantalla
        # de inicio con mucha fuerza y sin esto seguiría enseñando el viejo.
        return JSONResponse({
            "name": "HYDRA Trading", "short_name": "HYDRA", "start_url": "/",
            "display": "standalone", "background_color": "#04070e", "theme_color": "#04070e",
            "id": "/", "scope": "/",
            "icons": [
                # "any": ocupa todo el cuadro. "maskable": va con aire porque
                # Android lo recorta a un círculo y se comería las puntas.
                {"src": f"/icon/{ICON_V}/icon-192.png", "sizes": "192x192",
                 "type": "image/png", "purpose": "any"},
                {"src": f"/icon/{ICON_V}/icon-512.png", "sizes": "512x512",
                 "type": "image/png", "purpose": "any"},
                {"src": f"/icon/{ICON_V}/icon-maskable-192.png", "sizes": "192x192",
                 "type": "image/png", "purpose": "maskable"},
                {"src": f"/icon/{ICON_V}/icon-maskable-512.png", "sizes": "512x512",
                 "type": "image/png", "purpose": "maskable"},
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
    # modelo elegido desde la UI (controla el costo de la API de Anthropic)
    try:
        _md = (settings.data_path / "model.txt").read_text().strip()
        if _md in MODELS:
            settings.model = _md
    except Exception:  # noqa: BLE001
        pass
    # cerebro local (Ollama) elegido desde la UI
    try:
        _llm = json.loads((settings.data_path / "llm.json").read_text())
        if _llm.get("provider") in ("anthropic", "ollama", "hybrid"):
            settings.llm_provider = _llm["provider"]
        if _llm.get("ollama_model"):
            settings.ollama_model = str(_llm["ollama_model"])
    except Exception:  # noqa: BLE001
        pass
    # instrumentos vigilados y su estrategia asignada, editados desde la UI
    _watch: dict = {"symbols": [], "assign": {}}
    try:
        _w = json.loads((settings.data_path / "watchlist.json").read_text())
        if isinstance(_w.get("symbols"), list) and _w["symbols"]:
            _watch["symbols"] = [str(x).upper() for x in _w["symbols"]]
            settings.symbols = ",".join(_watch["symbols"])
        if isinstance(_w.get("assign"), dict):
            _watch["assign"] = {str(k).upper(): [str(v) for v in (vs or [])]
                                for k, vs in _w["assign"].items()}
    except Exception:  # noqa: BLE001
        pass
    # voz elegida desde la UI
    try:
        _v = json.loads((settings.data_path / "voice.json").read_text())
        if _v.get("provider") in ("", "voicebox", "openai", "elevenlabs"):
            settings.tts_provider = _v["provider"]
        if _v.get("profile"):
            settings.voicebox_profile = str(_v["profile"])
    except Exception:  # noqa: BLE001
        pass

    @app.on_event("startup")
    async def _autostart_ollama():
        """Si la configuración usa el cerebro local, lo encendemos nosotros.

        Así no hace falta dejar una terminal abierta con `ollama serve`: al
        abrir Hydra, el cerebro queda listo en segundo plano.
        """
        if settings.brain_for("analyst") != "ollama" and settings.llm_provider != "hybrid":
            return
        try:
            if await _ollama_alive(2):
                return
            import logging
            from . import ollama_boot
            ok, msg = ollama_boot.start()
            logging.getLogger("web").info("ollama autostart: %s", msg)
        except Exception:  # noqa: BLE001 - nunca debe tumbar el arranque
            import logging
            logging.getLogger("web").warning("ollama autostart falló", exc_info=True)

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

    @app.get("/model")
    async def get_model():
        return {"model": settings.model, "provider": settings.llm_provider,
                "ollama_model": settings.ollama_model,
                "options": [{"id": k, **v} for k, v in MODELS.items()]}

    @app.post("/model")
    async def set_model(request: Request):
        try:
            md = (await request.json()).get("model", "")
        except Exception:  # noqa: BLE001
            md = ""
        if md not in MODELS:
            return JSONResponse({"ok": False, "error": "modelo desconocido"}, status_code=400)
        settings.model = md
        (settings.data_path / "model.txt").write_text(md)
        store.log("system", "model", f"modelo cambiado a {md}")
        return {"ok": True, "model": md}

    @app.get("/llm/local")
    async def llm_local_status():
        """¿Hay un Ollama corriendo en local? Lista sus modelos descargados."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=4) as cli:
                r = await cli.get(settings.ollama_url.rstrip("/") + "/api/tags")
                r.raise_for_status()
                models = [m.get("name", "") for m in r.json().get("models", [])]
            return {"ok": True, "running": True, "provider": settings.llm_provider,
                    "models": models, "selected": settings.ollama_model,
                    "routing": _routing()}
        except Exception as exc:  # noqa: BLE001
            from . import ollama_boot
            return {"ok": True, "running": False, "provider": settings.llm_provider,
                    "error": f"{exc}"[:160], "url": settings.ollama_url,
                    "installed": bool(ollama_boot.binary() or ollama_boot.app_bundle()),
                    "boot": ollama_boot.state,
                    "routing": _routing()}

    def _routing() -> list[dict]:
        """Qué cerebro le toca a cada agente con la configuración actual."""
        roles = [("analyst", "Analista", "cada 15 min · el que más gasta"),
                 ("risk_manager", "Risk Manager", "por cada propuesta"),
                 ("overnight", "Overnight", "cada 30 min"),
                 ("tester", "Tester", "muchas muestras por backtest"),
                 ("reviewer", "Reviewer", "1 vez al día · juicio"),
                 ("architect", "Architect", "1 vez al día · evoluciona la estrategia")]
        return [{"role": r, "label": lbl, "why": why, "brain": settings.brain_for(r)}
                for r, lbl, why in roles]

    @app.get("/voice/local")
    async def voice_local_status():
        """¿Está Voicebox corriendo? Devuelve sus perfiles de voz."""
        from . import tts as tts_mod
        profiles = await tts_mod.voicebox_profiles()
        return {"ok": True, "running": profiles is not None,
                "provider": settings.tts_provider,
                "profiles": profiles or [], "selected": settings.voicebox_profile,
                "url": settings.voicebox_url}

    @app.post("/voice/local")
    async def voice_local_set(request: Request):
        """Cambia el proveedor de voz y/o el perfil de Voicebox."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        prov = body.get("provider", "")
        if prov not in ("", "voicebox", "openai", "elevenlabs"):
            return JSONResponse({"ok": False, "error": "proveedor inválido"}, status_code=400)
        settings.tts_provider = prov
        if body.get("profile"):
            settings.voicebox_profile = str(body["profile"])[:80]
        (settings.data_path / "voice.json").write_text(json.dumps(
            {"provider": prov, "profile": settings.voicebox_profile}))
        store.log("system", "tts_provider", f"voz: {prov or 'navegador'} ({settings.voicebox_profile})")
        return {"ok": True, "provider": prov, "profile": settings.voicebox_profile}

    @app.post("/llm/test")
    async def llm_test():
        """Prueba el cerebro local con EL MISMO prompt que usa el revisor de la flota.

        Así no solo comprueba que la conexión funciona: mide si el modelo juzga
        bien. El caso está armado como trampa — el edge BRUTO ya es negativo, así
        que la estrategia no tiene ventaja y mover el stop no se la va a crear.
        Un buen revisor responde 'no_change'; el que responde 'adjust' se dejó
        llevar por el 67% de salidas por SL sin mirar el edge.
        """
        import time as _t

        from . import llm as _llm
        from .fleet import REVIEW_SCHEMA, SYSTEM
        user = (
            "Estrategia: donchian  ·  XAUUSD M15\n"
            'Parámetros actuales: {"lookback": 20, "atr_mult": 1.5, "rr": 2.0}\n'
            'Rangos permitidos: {"lookback": [5, 60], "atr_mult": [0.5, 4.0], "rr": [0.5, 5.0]}\n\n'
            "Lote de 40 operaciones:\n"
            "- Edge BRUTO medio: -0.267R\n"
            "- Edge NETO medio (tras costos): -0.317R\n"
            "- Costo implícito: +0.050R por operación\n"
            "- Win rate: 32.5%\n"
            "- Salidas por stop loss: 67.0%\n"
            "- Perdedor medio: -1.02R\n"
            "- Ganador medio: +1.98R\n")
        prev = settings.llm_provider
        settings.llm_provider = "ollama"        # forzar la ruta local en la prueba
        t0 = _t.time()
        try:
            out = await _llm.ask(SYSTEM, user, schema=REVIEW_SCHEMA,
                                 max_tokens=1200)
            good = out.get("verdict") == "no_change"
            return {"ok": True, "model": settings.ollama_model,
                    "seconds": round(_t.time() - t0, 1), "reply": out,
                    "expected": "no_change", "good_judgement": good}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "model": settings.ollama_model,
                    "seconds": round(_t.time() - t0, 1), "error": f"{exc}"[:300]}
        finally:
            settings.llm_provider = prev

    async def _ollama_alive(timeout: float = 3) -> bool:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=timeout) as cli:
                r = await cli.get(settings.ollama_url.rstrip("/") + "/api/tags")
                return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    @app.post("/llm/local/start")
    async def llm_local_start():
        """Enciende Ollama en segundo plano si no está corriendo."""
        from . import ollama_boot
        if await _ollama_alive():
            return {"ok": True, "running": True, "message": "ya estaba encendido"}
        ok, msg = ollama_boot.start()
        if not ok:
            return JSONResponse({"ok": False, "error": msg}, status_code=400)
        # tarda un par de segundos en abrir el puerto
        for _ in range(12):
            await asyncio.sleep(1)
            if await _ollama_alive(2):
                store.log("system", "ollama", "cerebro local encendido")
                return {"ok": True, "running": True, "message": msg}
        return {"ok": True, "running": False,
                "message": msg + " — sigue arrancando, dale unos segundos"}

    @app.post("/llm/local")
    async def llm_local_set(request: Request):
        """Cambia entre el cerebro en la nube (Anthropic) y el local (Ollama)."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        prov = body.get("provider", "")
        if prov not in ("anthropic", "ollama", "hybrid"):
            return JSONResponse({"ok": False, "error": "proveedor inválido"}, status_code=400)
        settings.llm_provider = prov
        if body.get("ollama_model"):
            settings.ollama_model = str(body["ollama_model"])[:80]
        (settings.data_path / "llm.json").write_text(json.dumps(
            {"provider": prov, "ollama_model": settings.ollama_model}))
        store.log("system", "llm_provider", f"cerebro: {prov} ({settings.ollama_model})")
        return {"ok": True, "provider": prov, "ollama_model": settings.ollama_model}

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

    # DXY es sintético (se calcula de una canasta de divisas) y NO existe en el
    # broker: se vigila siempre como referencia, pero nunca se opera. Por eso vive
    # aparte de settings.symbols en vez de dentro.
    PINNED = ["DXY"]

    _STRAT_LABEL = {"donchian": "Ruptura Donchian", "rsi_fade": "Reversión RSI",
                    "momentum_burst": "Impulso", "ema_trend": "Tendencia EMA"}

    _instr_cache: dict = {"ts": 0.0, "data": None}
    _dxy_cache: dict = {"ts": 0.0, "row": None}

    @app.get("/instruments")
    async def instruments():
        """Panel lateral de instrumentos: precio, variación y mini-gráfica.

        Se cachea 25 s porque la pantalla la refresca sola y cada símbolo cuesta
        una petición de velas al broker.
        """
        import time as _t
        if _instr_cache["data"] and _t.time() - _instr_cache["ts"] < 25:
            return _instr_cache["data"]
        if not broker.client.account_authorized:
            return {"ok": False, "reason": "Conecta cTrader.", "rows": []}
        from . import indicators
        rows = []
        for sym in settings.symbol_list:
            try:
                cs = await asyncio.wait_for(
                    broker.candles(sym, settings.timeframe, 120), timeout=12)
                if len(cs) < 60:
                    continue
                snap = indicators.snapshot(cs)
                s = _summarize(snap)
                closes = [c.close for c in cs[-40:]]
                first = closes[0] or 1
                rows.append({"symbol": sym, "price": s["price"],
                             "change_pct": round((closes[-1] - first) / abs(first) * 100, 2),
                             "trend": s["trend"], "verdict": s["verdict"],
                             "rsi14": s["rsi14"], "spark": [round(c, 5) for c in closes]})
            except Exception:  # noqa: BLE001 - un símbolo caído no tumba el panel
                continue
        # DXY es sintético (6 pares por cálculo), así que va con su propia caché lenta.
        if _t.time() - _dxy_cache["ts"] > 180:
            try:
                snap = await _dxy_snapshot(settings.timeframe)
                if snap and not snap.get("__error__"):
                    s = _summarize(snap)
                    _dxy_cache.update({"ts": _t.time(), "row": {
                        "symbol": "DXY", "price": s["price"], "change_pct": 0.0,
                        "trend": s["trend"], "verdict": s["verdict"],
                        "rsi14": s["rsi14"], "spark": []}})
            except Exception:  # noqa: BLE001 - el DXY es un extra, no bloquea el panel
                pass
        if _dxy_cache["row"]:
            rows.append(_dxy_cache["row"])
        out = {"ok": True, "timeframe": settings.timeframe, "rows": rows}
        _instr_cache.update({"ts": _t.time(), "data": out})
        return out

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
            if tts_mod.state.get("played_locally"):
                # Voicebox ya lo reprodujo en las bocinas del Mac; si la UI cayera
                # a la voz del navegador se oiría dos veces.
                return Response(status_code=204)
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

    # -------------------------------------------------- trade_context (bot)

    def _pick(d: dict, *names, default=None):
        """Busca una clave sin importar mayúsculas ni guiones bajos.

        El bot está en C#: sus campos salen en PascalCase (ZonePrice, RawScore).
        Aceptamos cualquier variante para no depender de cómo serialice.
        """
        flat = {str(k).lower().replace("_", ""): v for k, v in d.items()}
        for n in names:
            v = flat.get(n.lower().replace("_", ""))
            if v is not None:
                return v
        return default

    @app.post("/ingest/trade-context")
    async def ingest_trade_context(request: Request):
        """Recibe el contexto de decisión del Confluence Bot y lo guarda inmutable.

        Acepta el payload TAL CUAL llegue: mapea los campos que reconoce a columnas
        indexadas y guarda el JSON íntegro en `raw_json`. Así podemos empezar a
        capturar sin conocer de antemano el formato exacto — nada se pierde.
        """
        if settings.dashboard_token:
            key = request.headers.get("x-api-key") or request.query_params.get("token")
            if key != settings.dashboard_token:
                return JSONResponse({"ok": False, "error": "no autorizado"}, status_code=401)
        try:
            raw = await request.json()
        except Exception:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": "JSON inválido"}, status_code=400)
        if isinstance(raw, list):                      # lotes
            ids = [_store_ctx(r) for r in raw if isinstance(r, dict)]
            return {"ok": True, "stored": len(ids), "ids": ids[:20]}
        if not isinstance(raw, dict):
            return JSONResponse({"ok": False, "error": "se esperaba un objeto"}, status_code=400)
        return {"ok": True, "id": _store_ctx(raw)}

    def _store_ctx(raw: dict) -> int:
        signals = _pick(raw, "signals", "levels", "confluences") or []
        fams = set()
        for s in signals if isinstance(signals, list) else []:
            lbl = str(_pick(s, "label", "name") or "") if isinstance(s, dict) else str(s)
            fams.add(_family(lbl))
        row = {
            "ts_bot": _pick(raw, "ts", "time", "timestamp", "serverTime"),
            "signal_id": _pick(raw, "key", "signalId", "signal_id", "id"),
            "broker_position_id": _pick(raw, "positionId", "broker_position_id"),
            "symbol": (_pick(raw, "symbol", "symbolName") or "").upper() or None,
            "timeframe": _pick(raw, "timeframe", "timeFrame", "tf"),
            "bias": _pick(raw, "bias", "direction", "side"),
            "outcome": _pick(raw, "outcome", "status", "reason", default="alerted"),
            "score": _pick(raw, "score", "adjustedScore"),
            "raw_score": _pick(raw, "rawScore"),
            "learning_mult": _pick(raw, "learningMult", "mult"),
            "corr_bonus": _pick(raw, "corrBonus"),
            "zone_price": _pick(raw, "zonePrice", "price"),
            "zone_top": _pick(raw, "zoneTop"),
            "zone_bottom": _pick(raw, "zoneBottom"),
            "zone_width_pips": _pick(raw, "zoneWidthPips", "zoneWidth"),
            "n_confluences": len(signals) if isinstance(signals, list) else None,
            "n_families": len(fams) or None,
            "dist_pips": _pick(raw, "distPips", "distance"),
            "spread_pips": _pick(raw, "spreadPips", "spread"),
            "regime": _pick(raw, "regime", "regimeStatus"),
            "bot_label": _pick(raw, "botLabel", "label"),
            "build_tag": _pick(raw, "buildTag", "build"),
            "signals_json": json.dumps(signals, ensure_ascii=False) if signals else None,
        }
        return store.add_trade_context(row, raw)

    def _family(label: str) -> str:
        """Misma taxonomía que ClassifyFamily() del bot (orden importa: HTF e IKL
        antes que KL, por los substrings compartidos)."""
        lb = label or ""
        if "HTF-KL" in lb:
            return "HTFKL"
        if "IKL" in lb:
            return "IKL"
        if "Key Level" in lb or " KL" in lb or "BR-KL" in lb:
            return "KeyLevel"
        if "Fib" in lb:
            return "Fib"
        if "Trend Line" in lb or " TL" in lb or "BR-TL" in lb:
            return "TrendLine"
        if lb.startswith("EMA"):
            return "EMA"
        if lb.startswith("SMA"):
            return "SMA"
        if "Session" in lb:
            return "Session"
        if lb.startswith("Round"):
            return "Round"
        return "Other"

    @app.get("/trade-context")
    async def trade_context_list(limit: int = 40, symbol: str = "", outcome: str = ""):
        return {"stats": store.trade_context_stats(),
                "rows": store.trade_contexts(min(int(limit), 200), symbol, outcome)}

    @app.get("/trade-context/{ctx_id}")
    async def trade_context_one(ctx_id: int):
        """El JSON íntegro de una captura — todo lo que mandó el bot, sin recortar."""
        row = store.trade_context_one(ctx_id)
        if row is None:
            return JSONResponse({"error": "no existe"}, status_code=404)
        return row

    # ------------------------------------------ instrumentos y sus estrategias

    def _save_watch() -> None:
        _watch["symbols"] = settings.symbol_list
        # una asignación sin instrumento vigilado no sirve de nada: se limpia
        _watch["assign"] = {k: v for k, v in _watch["assign"].items()
                            if k in _watch["symbols"] and v}
        (settings.data_path / "watchlist.json").write_text(
            json.dumps(_watch, ensure_ascii=False))

    def strategies_for(symbol: str) -> list[str]:
        """Estrategias asignadas a un instrumento. Sin asignación = todas."""
        from . import strategies as st
        got = _watch["assign"].get(symbol.upper()) or []
        return [s for s in got if s in st.STRATEGIES]

    @app.get("/watchlist")
    async def watchlist():
        """Instrumentos vigilados + qué estrategia lleva cada uno."""
        from . import strategies as st
        rows = [{"symbol": sym, "strategies": strategies_for(sym), "fixed": False}
                for sym in settings.symbol_list]
        rows += [{"symbol": sym, "strategies": [], "fixed": True,
                  "note": "referencia · no se opera"} for sym in PINNED]
        known = broker.symbol_names() if broker.client.account_authorized else []
        return {"symbols": rows,
                "available": [{"id": k, "label": _STRAT_LABEL.get(k, k),
                               "params": st.DEFAULTS.get(k, {})} for k in st.STRATEGIES],
                "broker_symbols": known[:400], "broker_ready": bool(known),
                "timeframe": settings.timeframe}

    @app.post("/watchlist")
    async def watchlist_set(request: Request):
        """Añade, quita o reemplaza la lista de instrumentos vigilados."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        syms = settings.symbol_list
        if isinstance(body.get("symbols"), list):
            syms = [str(x).strip().upper() for x in body["symbols"] if str(x).strip()]
        if body.get("add"):
            add = str(body["add"]).strip().upper()
            if add and add not in syms:
                syms = syms + [add]
        if body.get("remove"):
            rm = str(body["remove"]).strip().upper()
            if rm in PINNED:
                return JSONResponse(
                    {"ok": False, "error": f"{rm} es fijo: es la referencia del dólar "
                                           "y siempre se vigila"}, status_code=400)
            syms = [x for x in syms if x != rm]
        # sin duplicados y sin lista vacía (el cerebro no tendría nada que mirar)
        # los fijos nunca entran en la lista operable (no existen en el broker)
        seen, clean = set(), []
        for x in syms:
            if x not in seen and x not in PINNED:
                seen.add(x)
                clean.append(x)
        if not clean:
            return JSONResponse({"ok": False, "error": "deja al menos un instrumento"},
                                status_code=400)
        if len(clean) > 24:
            return JSONResponse({"ok": False, "error": "máximo 24 instrumentos"},
                                status_code=400)
        settings.symbols = ",".join(clean)
        _save_watch()
        store.log("system", "watchlist", "instrumentos: " + ", ".join(clean))
        return {"ok": True, "symbols": clean}

    @app.post("/watchlist/strategies")
    async def watchlist_strategies(request: Request):
        """Asigna estrategias a un instrumento, o un instrumento a una estrategia."""
        from . import strategies as st
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        if body.get("strategy") and body.get("symbols") is not None:
            # al revés: esta estrategia corre en estos instrumentos
            strat = str(body["strategy"])
            if strat not in st.STRATEGIES:
                return JSONResponse({"ok": False, "error": "estrategia desconocida"},
                                    status_code=400)
            want = {str(x).upper() for x in body["symbols"]}
            for sym in settings.symbol_list:
                cur = set(_watch["assign"].get(sym) or [])
                cur.add(strat) if sym in want else cur.discard(strat)
                _watch["assign"][sym] = sorted(cur)
            _save_watch()
            return {"ok": True, "strategy": strat, "symbols": sorted(want)}
        sym = str(body.get("symbol") or "").strip().upper()
        if sym in PINNED:
            return JSONResponse({"ok": False, "error": f"{sym} es solo referencia: "
                                 "no se le asignan estrategias"}, status_code=400)
        if sym not in settings.symbol_list:
            return JSONResponse({"ok": False, "error": "ese instrumento no está vigilado"},
                                status_code=400)
        picked = [str(x) for x in (body.get("strategies") or []) if x in st.STRATEGIES]
        _watch["assign"][sym] = picked
        _save_watch()
        return {"ok": True, "symbol": sym, "strategies": picked}

    # --------------------------------------------------------------- flota

    _fleet_state = {"running": False}

    def _fleet():
        from .fleet import Fleet
        return Fleet(store, broker)

    @app.get("/fleet")
    async def fleet_board():
        f = _fleet()
        return {"leaderboard": f.leaderboard(), "reviews": store.arm_reviews(20),
                "running": _fleet_state["running"]}

    @app.post("/fleet/seed")
    async def fleet_seed(request: Request):
        """Crea la flota: variantes por estrategia + un champion congelado."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        symbol = str(body.get("symbol") or (settings.symbol_list or ["XAUUSD"])[0]).upper()
        tf = str(body.get("timeframe") or settings.timeframe).upper()
        per = max(2, min(8, int(body.get("per_strategy", 5))))
        if body.get("reset"):
            store.clear_fleet()
        n = _fleet().seed(symbol, tf, per, only=strategies_for(symbol))
        store.log("system", "fleet_seed", f"{n} arms en {symbol} {tf}")
        return {"ok": True, "created": n, "symbol": symbol, "timeframe": tf,
                "strategies": strategies_for(symbol) or "todas"}

    @app.post("/fleet/cycle")
    async def fleet_cycle(request: Request):
        """Alimenta los arms con velas nuevas y revisa los que juntaron un lote."""
        if _fleet_state["running"]:
            return JSONResponse({"ok": False, "error": "ya hay un ciclo corriendo"},
                                status_code=409)
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        batch = max(10, min(200, int(body.get("batch", 40))))
        cost = float(body.get("cost_r", 0.05))
        _fleet_state["running"] = True
        try:
            res = await _fleet().cycle(batch=batch, cost_r=cost)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": f"{exc}"[:220]}, status_code=500)
        finally:
            _fleet_state["running"] = False
        store.log("system", "fleet_cycle", res)
        return res

    @app.post("/fleet/clear")
    async def fleet_clear():
        store.clear_fleet()
        return {"ok": True}

    # ------------------------------------- aprendizaje: propuestas vía MCP

    @app.get("/proposals")
    async def proposals_list():
        """Cambios que Claude Desktop propuso por MCP y esperan tu aprobación."""
        from . import mcp_gate
        return {"pending": store.proposals("awaiting_approval"),
                "recent": store.proposals(None, limit=10),
                "hypotheses": store.hypotheses("open"),
                "metrics": {"counts": store.postmortem_counts(),
                            "threshold": mcp_gate.HYPOTHESIS_MIN_OCCURRENCES}}

    @app.post("/proposals/{pid}/decide")
    async def proposal_decide(pid: int, request: Request):
        """Aprueba o rechaza una propuesta. Solo al aprobar se aplican los cambios."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        approve = bool(body.get("approve"))
        note = str(body.get("note", ""))[:400]
        p = store.proposal(pid)
        if not p:
            return JSONResponse({"ok": False, "error": "propuesta no encontrada"},
                                status_code=404)
        if p["status"] != "awaiting_approval":
            return JSONResponse({"ok": False, "error": f"ya estaba {p['status']}"},
                                status_code=409)
        if not approve:
            store.decide_proposal(pid, False, note)
            store.log("system", "proposal_rejected", {"id": pid, "note": note})
            return {"ok": True, "status": "rejected"}
        try:
            changes = json.loads(p["changes"])
        except Exception:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": "cambios ilegibles"}, status_code=400)
        applied: dict = {}
        try:
            for name, value in changes.items():
                agent_params.apply_and_save(settings.data_path / "overrides.json",
                                            _agent_owning(name), {name: value})
                applied[name] = getattr(settings, name, None)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": f"al aplicar: {exc}"[:200]},
                                status_code=500)
        store.decide_proposal(pid, True, note)
        store.log("system", "proposal_approved", {"id": pid, "applied": applied, "note": note})
        return {"ok": True, "status": "approved", "applied": applied}

    def _agent_owning(param: str) -> str:
        for key, names in agent_params.PARAMS.items():
            if param in names:
                return key
        return "analyst"

    # -------------------------------------------- memoria (vault Obsidian)

    @app.get("/vault")
    async def vault_list():
        return {"stats": vault.stats(), "notes": vault.list_notes()[:200]}

    @app.get("/vault/note")
    async def vault_note(p: str = Query(...)):
        try:
            return {"path": p, "markdown": vault.read_note(p)}
        except Exception:  # noqa: BLE001
            raise HTTPException(404, "nota no encontrada")

    @app.get("/vault/export")
    async def vault_export():
        data = vault.export_zip()
        return Response(content=data, media_type="application/zip",
                        headers={"Content-Disposition":
                                 'attachment; filename="HydraVault.zip"'})

    @app.post("/research")
    async def research_ask(request: Request):
        """Pregunta al investigador (Perplexity) y guarda el hallazgo en la memoria."""
        if not research.available():
            return JSONResponse({"ok": False, "error": "Falta la clave de Perplexity: "
                                 "ponla en Sistema → claves API."}, status_code=400)
        try:
            q = str((await request.json()).get("q", "")).strip()[:600]
        except Exception:  # noqa: BLE001
            q = ""
        if not q:
            return JSONResponse({"ok": False, "error": "pregunta vacía"}, status_code=400)
        try:
            res = await research.ask(q)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": f"Perplexity: {exc}"[:200]},
                                status_code=502)
        cites = "".join(f"\n- {c}" for c in res.get("citations", [])[:8])
        try:
            vault.note("Investigacion", q[:60],
                       f"**Pregunta:** {q}\n\n{res['text']}"
                       + ("\n\n## Fuentes" + cites if cites else ""),
                       tags=["investigacion"])
        except Exception:  # noqa: BLE001
            pass
        store.log("sentinel", "research", {"q": q, "a": res["text"][:800]})
        return {"ok": True, "text": res["text"], "citations": res.get("citations", [])}

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
            "pinned": PINNED,
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
