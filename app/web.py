"""FastAPI dashboard: estado, OAuth de cTrader, diario, playbook y kill switch."""
from __future__ import annotations

import asyncio
import datetime as dt
import html
import json
import time
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

    # Favicon en SVG: Safari guarda los favicons en una base de datos propia que
    # no se limpia ni con recarga forzada, pero la entrada es por tipo de recurso.
    # Ofrecer un SVG (que prefiere sobre el PNG) le hace pedir uno nuevo.
    _MARK_SVG = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">'
        '<rect width="120" height="120" fill="#04070e"/><g fill="#7ff6ff">'
        '<path fill-rule="evenodd" d="M60 5 L107.6 32.5 L107.6 87.5 L60 115 L12.4 87.5 '
        'L12.4 32.5 Z M60 17.6 L96.7 38.8 L96.7 81.2 L60 102.4 L23.3 81.2 L23.3 38.8 Z"/>'
        '<path d="M60 23 L65 34.5 L60 41.5 L55 34.5 Z"/>'
        '<path d="M26.5 40.5 L54 55 L54 59 L26.5 49 Z"/>'
        '<path d="M93.5 40.5 L66 55 L66 59 L93.5 49 Z"/>'
        '<path d="M27.5 62.5 L38 67 L38 78.5 L27.5 72 Z"/>'
        '<path d="M92.5 62.5 L82 67 L82 78.5 L92.5 72 Z"/>'
        '<path d="M42 62 L78 62 L78 67.5 L71.5 84 L67 68.5 L63.5 74 L60 67.5 '
        'L56.5 74 L53 68.5 L48.5 84 L42 67.5 Z"/>'
        '<path d="M52 87 L56.5 81.5 L60 85.5 L63.5 81.5 L68 87 L60 96.5 Z"/>'
        '</g></svg>')

    @app.get("/icon/{ver}/mark.svg")
    async def icon_svg(ver: str):
        return Response(content=_MARK_SVG, media_type="image/svg+xml",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})

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

    # Rutas que el navegador busca por su cuenta si no le gusta el <link>.
    # Sin caché para que un icono viejo no se quede pegado.
    @app.get("/favicon.ico")
    async def favicon_ico():
        from fastapi.responses import FileResponse
        return FileResponse(Path(__file__).parent / "static" / "favicon.png",
                            media_type="image/png",
                            headers={"Cache-Control": "no-store"})

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
    # carpeta de .algo elegida desde la UI
    try:
        _ad = (settings.data_path / "algo_dir.txt").read_text().strip()
        if _ad:
            settings.algo_dir = _ad
    except Exception:  # noqa: BLE001
        pass
    # el vigilante de esa carpeta: cada cuánto vuelve a mirar y qué vio la última vez
    _ALGO_WATCH_MIN = 10
    _algo_watch: dict = {"last": None, "result": None}
    # los CSV que escriben los bots (el registro «shadow»)
    _SHADOW_WATCH_MIN = 2
    _shadow_watch: dict = {"last": None, "imported": 0, "files": 0, "error": ""}
    try:
        _sd = (settings.data_path / "shadow_dir.txt").read_text().strip()
        if _sd:
            settings.shadow_dir = _sd
    except Exception:  # noqa: BLE001
        pass
    # parámetros de los indicadores de Hydra (EMA, SMA, RSI, ATR, R:R…), editados
    # desde la ventana de BOTS. Se meten DENTRO de strategies.DEFAULTS para que los
    # lean todos los que ya lo consultan (flota, réplica, panel) sin tocar nada más.
    try:
        from . import strategies as _st_boot
        _sp = json.loads((settings.data_path / "strategy_params.json").read_text())
        for _k, _v2 in (_sp or {}).items():
            if _k in _st_boot.DEFAULTS and isinstance(_v2, dict):
                _st_boot.DEFAULTS[_k] = _st_boot.clamp(_k, {**_st_boot.DEFAULTS[_k], **_v2})
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
    async def _autostart_voicebox():
        """Si la voz elegida es Voicebox, se abre la app al arrancar.

        Sin esto, con la app cerrada la voz cae a la del navegador y no hay ninguna
        pista de por qué: la configuración estaba bien, faltaba abrirla.
        """
        if settings.tts_provider != "voicebox":
            return
        import logging
        lg = logging.getLogger("web")
        try:
            from . import tts as tts_mod
            from . import voicebox_boot
            if await tts_mod.voicebox_profiles() is not None:
                return
            ok, msg = await asyncio.to_thread(voicebox_boot.start)
            lg.info("voicebox autostart: %s", msg)
        except Exception:  # noqa: BLE001 - nunca debe tumbar el arranque
            lg.warning("voicebox autostart falló", exc_info=True)

    @app.on_event("startup")
    async def _watch_shadow_logs():
        """Recoge los CSV de los bots cada pocos minutos, sin que nadie los abra.

        Cada dos minutos es agresivo a propósito: el bot escribe una fila por vela y
        la gracia es verlas casi en vivo. Solo se lee lo NUEVO de cada archivo, así
        que la pasada cuesta lo mismo con un CSV de 2 KB que con uno de 200 MB.
        """
        import logging
        lg = logging.getLogger("web")

        async def loop():
            while True:
                try:
                    res = await asyncio.to_thread(_shadow_scan_once)
                    if not res.get("ok"):
                        _shadow_watch["error"] = str(res.get("error") or "")
                    elif res.get("imported"):
                        lg.info("shadow: %s filas nuevas de %s",
                                res["imported"], res.get("dir"))
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001 - nunca debe tumbar la app
                    lg.warning("vigilante de CSV falló", exc_info=True)
                await asyncio.sleep(_SHADOW_WATCH_MIN * 60)

        try:
            asyncio.create_task(loop(), name="shadow-watch")
        except Exception:  # noqa: BLE001
            lg.warning("no se pudo arrancar el vigilante de CSV", exc_info=True)

    @app.on_event("startup")
    async def _watch_algo_dir():
        """Deja la carpeta de los cBots fija y la relee sola.

        Objetivo: no volver a pulsar «escanear». Al arrancar se fija la carpeta
        (si no lo estaba), se importa lo que haya, y luego se mira cada
        _ALGO_WATCH_MIN minutos. Al recompilar un bot en cTrader —o al bajar uno
        nuevo del repo sincronizado— aparece sin tocar nada.
        """
        import logging
        lg = logging.getLogger("web")

        async def loop():
            first = True
            while True:
                try:
                    if not (settings.algo_dir or "").strip():
                        await asyncio.to_thread(_algo_autopin)
                    # SOLO refresca los bots ya elegidos: los nuevos se suben de uno
                    # en uno desde la lista. La carpeta tiene decenas y una lista
                    # completa no sirve de nada.
                    res = await asyncio.to_thread(_algo_scan_once, True, "")
                    _algo_watch["last"] = time.time()
                    _algo_watch["result"] = {
                        "ok": bool(res.get("ok")),
                        "error": res.get("error"),
                        "added": len(res.get("added") or []),
                        "updated": len(res.get("updated") or []),
                        "unchanged": res.get("unchanged") or 0,
                        "failed": len(res.get("failed") or []),
                    }
                    n = (_algo_watch["result"]["added"]
                         + _algo_watch["result"]["updated"])
                    if n or first:      # en silencio si no cambió nada
                        lg.info("cbots: %s en %s", _algo_watch["result"],
                                settings.algo_dir or "(sin carpeta)")
                    first = False
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001 - el vigilante nunca tumba la app
                    lg.warning("vigilante de .algo falló", exc_info=True)
                await asyncio.sleep(_ALGO_WATCH_MIN * 60)

        try:
            asyncio.create_task(loop(), name="algo-watch")
        except Exception:  # noqa: BLE001
            lg.warning("no se pudo arrancar el vigilante de .algo", exc_info=True)

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

    def _oauth_error(msg: str, code_hint: str = "") -> HTMLResponse:
        """Página de error legible: un 500 crudo no dice nada y aquí es donde más
        se atasca la gente."""
        return HTMLResponse(
            "<div style=\"font-family:ui-monospace,Menlo,monospace;background:#04070e;"
            "color:#cfe8f2;padding:28px;line-height:1.6\">"
            "<h2 style='color:#ff5d73'>No pude completar la conexión</h2>"
            f"<p style='color:#ffb4c0'>{html.escape(msg)}</p>"
            "<h3 style='color:#7ff6ff;font-size:14px;margin-top:22px'>Qué revisar</h3>"
            "<ol>"
            "<li>La <b>URL de retorno</b> registrada en tu aplicación de cTrader "
            "(openapi.ctrader.com → tu app → Redirect URIs) tiene que ser "
            f"<code>{html.escape(settings.ctrader_redirect_uri)}</code>, "
            "<b>igual letra por letra</b> — incluido http/https y el puerto.</li>"
            "<li>El <b>Client Secret</b> del .env tiene que ser el de ESA misma "
            "aplicación.</li>"
            "<li>Un código de autorización <b>solo sirve una vez y caduca en "
            "1 minuto</b>: si recargaste esta página o tardaste, vuelve a empezar "
            "el permiso y déjalo terminar sin tocar nada.</li>"
            "</ol>"
            f"<p style='margin-top:20px'><a style='color:#7ff6ff' href='/oauth/login'>"
            "↻ intentar de nuevo</a> &nbsp;·&nbsp; "
            "<a style='color:#7ff6ff' href='/health/ctrader'>ver diagnóstico</a> "
            "&nbsp;·&nbsp; <a style='color:#7ff6ff' href='/'>← volver</a></p>"
            f"{code_hint}</div>", status_code=400)

    @app.get("/oauth/callback")
    async def oauth_callback(code: str = "", error: str = "",
                             error_description: str = ""):
        if error or error_description:
            return _oauth_error(f"cTrader devolvió un error: {error} {error_description}".strip())
        if not code:
            return _oauth_error("cTrader no devolvió ningún código de autorización. "
                                "Casi siempre es la URL de retorno.")
        try:
            await tokens.exchange_code(code)
        except Exception as exc:  # noqa: BLE001 - el motivo debe verse, no ser un 500
            store.log("system", "oauth_error", str(exc)[:400])
            return _oauth_error(str(exc))
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

    @app.post("/voice/local/start")
    async def voice_local_start():
        """Abre Voicebox. El servidor de voz vive dentro de la app: si está cerrada
        no hay voz, y Hydra cae a la del navegador sin que se sepa por qué."""
        from . import tts as tts_mod
        from . import voicebox_boot
        if await tts_mod.voicebox_profiles() is not None:
            return {"ok": True, "already": True, "msg": "Voicebox ya estaba abierta"}
        ok, msg = await asyncio.to_thread(voicebox_boot.start)
        if not ok:
            return JSONResponse({"ok": False, "error": msg}, status_code=400)
        for _ in range(20):                 # hasta ~10 s: la app tarda en abrir
            await asyncio.sleep(0.5)
            if await tts_mod.voicebox_profiles() is not None:
                return {"ok": True, "msg": msg}
        return {"ok": False, "error": msg + ", pero su servidor aún no responde. "
                                            "Ábrela a mano y mira que esté activa."}

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
                "resistances": lv.get("resistances", []),
                "ma": s.get("ma") or {}}      # medias simples + lectura del abanico

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
                    "momentum_burst": "Impulso", "ema_trend": "Tendencia EMA",
                    "ma_pullback": "Retroceso a la media (EMA + SMA)"}

    def now_ts() -> float:
        import time as _t
        return _t.time()

    # calendario: el feed es semanal, así que se cachea de verdad
    _cal_cache: dict = {"raw": None, "ts": 0.0, "retry_after": 0.0}

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

    def _store_ctx(raw: dict, ts: float | None = None) -> int:
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
        # el instante REAL de la captura: para lo que llega por HTTP es ahora, pero
        # una fila de un CSV viejo tiene el suyo y no debe parecer actividad de ahora
        return store.add_trade_context(row, raw, ts if ts is not None else row["ts_bot"])

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

    # -------------------------------------------------- bots de cTrader (.algo)

    def _bots_dir():
        d = settings.data_path / "bots"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _algo_dir():
        d = (settings.algo_dir or "").strip()
        return Path(d).expanduser() if d else None

    def _algo_guesses() -> list[Path]:
        # Rutas donde cTrader deja los .algo según instalación. Se buscan de más
        # concreta a más general: el escaneo es recursivo, así que apuntar a la
        # raíz de cAlgo ya encuentra todo lo que haya debajo.
        home = Path.home()
        return [home / "cAlgo", home / "cAlgo" / "Sources" / "Robots",
                home / "cAlgo" / "Robots",
                home / "Documents" / "cAlgo",
                home / "Documents" / "cAlgo" / "Sources" / "Robots",
                home / "Documents" / "cAlgo" / "Robots"]

    def _algo_autopin() -> str:
        """Fija la carpeta de .algo sola, la primera vez, y la deja guardada.

        La carpeta local gana a clonar el repo de GitHub: los `.algo` los compila
        cTrader en esta máquina, y esa carpeta YA se sincroniza. Leyéndola nunca
        se va por detrás de lo que de verdad está corriendo, y no hace falta red
        ni permisos. Si un día se quiere leer el repo, basta apuntar aquí a la
        copia local del repo: es la misma lectura.
        """
        if (settings.algo_dir or "").strip():
            return settings.algo_dir
        best = ""
        for g in _algo_guesses():                 # la primera que tenga .algo
            if g.is_dir() and any(g.rglob("*.algo")):
                best = str(g)
                break
        if not best:                              # ninguna con bots: vale la raíz
            for g in _algo_guesses():
                if g.is_dir():
                    best = str(g)
                    break
        if best:
            settings.algo_dir = best
            try:
                (settings.data_path / "algo_dir.txt").write_text(best)
            except Exception:  # noqa: BLE001
                pass
        return best

    # cTrader deja EL MISMO bot compilado en varios sitios: bin/Debug, bin/Release y
    # los intermedios de obj/. Por eso una carpeta con 20 bots enseña 116 archivos y
    # cada nombre sale repetido. Aquí se agrupa por bot y se elige una sola copia.
    _BUILD_NOISE = ("/obj/", "/.git/", "/node_modules/")

    def _algo_rank(f: Path) -> tuple:
        """Cuál copia gana: LA MÁS RECIENTE, y solo a igualdad de fecha, Release.

        Antes ganaba Release y eso escogía compilaciones viejas: cTrader construye
        en Debug al pulsar Build, así que un Release de hace meses tapaba el build
        de hoy — con menos parámetros, y por eso parecía que el bot había perdido
        los del reporte a Hydra.
        """
        s = str(f).lower()
        return (f.stat().st_mtime, 1 if "/release/" in s else 0)

    def _algo_unique(d: Path) -> list[tuple[Path, int]]:
        """Un .algo por bot: [(archivo elegido, cuántas copias había)]."""
        by: dict[str, list[Path]] = {}
        for f in d.rglob("*.algo"):
            s = str(f).replace("\\", "/").lower()
            if any(n in s for n in _BUILD_NOISE):
                continue
            by.setdefault(f.stem.lower(), []).append(f)
        out = []
        for copies in by.values():
            best = max(copies, key=_algo_rank)
            out.append((best, len(copies)))
        out.sort(key=lambda t: -t[0].stat().st_mtime)
        return out

    @app.get("/algo/dir")
    async def algo_dir_get():
        d = _algo_dir()
        found, n_files, n_bots = [], 0, 0
        if d and d.is_dir():
            uniq = _algo_unique(d)
            n_bots = len(uniq)
            n_files = sum(c for _, c in uniq)
            found = [str(f.relative_to(d)) for f, _ in uniq][:200]
        real = [str(g) for g in _algo_guesses() if g.is_dir()]
        # cuántos .algo hay en cada sugerencia: así se ve de un vistazo cuál sirve
        counts = {g: len(list(Path(g).rglob("*.algo"))) for g in real}
        return {"dir": str(d) if d else "", "exists": bool(d and d.is_dir()),
                "found": found, "n_found": n_bots, "n_files": n_files,
                "guesses": real or [str(g) for g in _algo_guesses()],
                "guess_counts": counts,
                "auto": bool(d) and str(d) in real,
                "watch_minutes": _ALGO_WATCH_MIN,
                "last_scan": _algo_watch.get("last"),
                "last_result": _algo_watch.get("result")}

    @app.post("/algo/dir")
    async def algo_dir_set(request: Request):
        """Fija la carpeta de .algo y la guarda para los próximos arranques."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        d = str(body.get("dir") or "").strip()
        if d:
            p = Path(d).expanduser()
            if not p.is_dir():
                return JSONResponse({"ok": False, "error": f"no existe la carpeta {p}"},
                                    status_code=400)
            d = str(p)
        settings.algo_dir = d
        (settings.data_path / "algo_dir.txt").write_text(d)
        return {"ok": True, "dir": d}

    def _algo_known() -> dict:
        """Lo ya importado, por ruta de origen: {src_path: (mtime, bytes)}."""
        known: dict = {}
        for f in _bots_dir().glob("*.json"):
            try:
                j = json.loads(f.read_text())
                if j.get("src_path"):
                    known[j["src_path"]] = (j.get("src_mtime"), j.get("file_bytes"))
            except Exception:  # noqa: BLE001
                pass
        return known

    def _algo_scan_once(only_known: bool = False, only_file: str = "") -> dict:
        """Lee .algo de la carpeta y guarda sus parámetros.

        Tres modos, y el que manda es el segundo:
        - todo (por defecto): importa cuanto haya. Útil una vez, no cada 10 min.
        - only_known: NO añade bots nuevos; solo refresca los que ya elegiste. Es
          lo que usa el vigilante, porque con una carpeta de decenas de bots una
          lista completa no se puede leer y no es lo que se quiere ver.
        - only_file: uno concreto, el que se pide desde la lista.

        Es E/S de disco bloqueante: desde el vigilante se llama en un hilo.
        """
        from . import algo as algo_mod
        import time as _t
        d = _algo_dir()
        if not d or not d.is_dir():
            return {"ok": False, "error": "primero fija la carpeta"}
        known = _algo_known()

        if only_file:
            target = (d / only_file).resolve()
            if d.resolve() not in target.parents or target.suffix != ".algo":
                return {"ok": False, "error": "esa ruta no está en tu carpeta"}
            if not target.is_file():
                return {"ok": False, "error": f"no existe {only_file}"}
            files = [target]
        else:
            # una copia por bot: sin esto se importa Debug Y Release del mismo y
            # aparecen dos entradas del mismo bot
            files = [f for f, _ in _algo_unique(d)]

        # ¿Se importó una copia VIEJA de un bot y hay otra más nueva en otra carpeta
        # (Debug frente a Release)? Se adopta la nueva y se tira la ficha vieja: si
        # no, el bot se queda congelado en una compilación anterior y parece que ha
        # perdido parámetros que sí tiene.
        allow, adopted, missing = set(), [], []
        if only_known:
            best = {f.stem.lower(): f for f, _ in _algo_unique(d)}
            for old, prev in list(known.items()):
                nb = best.get(Path(old).stem.lower())
                # el archivo ya no está y no hay otra copia: se dice, no se borra su
                # ficha a la callada — quitarla es decisión del dueño
                if not nb and not Path(old).is_file():
                    missing.append(Path(old).stem)
                if not nb or str(nb) == old:
                    continue
                if nb.stat().st_mtime <= (prev[0] or 0):
                    continue
                for jf in _bots_dir().glob("*.json"):
                    try:
                        if json.loads(jf.read_text()).get("src_path") == old:
                            jf.unlink()
                    except Exception:  # noqa: BLE001
                        pass
                known.pop(old, None)
                allow.add(str(nb))
                adopted.append({"bot": Path(old).stem, "from": old, "to": str(nb)})
            if allow:
                files = files + [Path(x) for x in allow if Path(x) not in files]

        added, updated, same, failed = [], [], [], []
        for f in files:
            if only_known and str(f) not in known and str(f) not in allow:
                continue                  # no se cuela nadie que no hayas elegido
            st = f.stat()
            sig = (int(st.st_mtime), st.st_size)
            prev = known.get(str(f))
            if prev and tuple(prev) == sig:
                same.append(f.name)
                continue
            try:
                parsed = algo_mod.parse(f.read_bytes())
            except Exception as exc:  # noqa: BLE001 - un .algo roto no corta el escaneo
                failed.append({"file": f.name, "error": str(exc)[:120]})
                continue
            # El nombre que se muestra es el DEL ARCHIVO, que es como lo ves en
            # cTrader y en tu carpeta ("Confluence Bot"). El interno del código
            # ("ConfluenceAlertBotV2") se guarda aparte: sirve para entenderlo, pero
            # no es como se llama el bot para su dueño.
            parsed.update({"imported_ts": _t.time(), "file_bytes": st.st_size,
                           "src_path": str(f), "src_mtime": int(st.st_mtime),
                           "type_label": parsed.get("name"), "name": f.stem})
            safe = "".join(c for c in f.stem
                           if c.isalnum() or c in "-_ ")[:60].strip() or "bot"
            dest = _bots_dir() / f"{safe}.json"
            # Un mismo archivo no puede tener DOS fichas: si el nombre cambió (o
            # antes se guardaba por el nombre interno), la vieja se va.
            for jf in _bots_dir().glob("*.json"):
                if jf == dest:
                    continue
                try:
                    if json.loads(jf.read_text()).get("src_path") == str(f):
                        jf.unlink()
                except Exception:  # noqa: BLE001
                    pass
            # Dos archivos distintos con el MISMO nombre: se desambigua con su
            # carpeta, o uno pisaría al otro sin avisar.
            if dest.exists():
                try:
                    other = json.loads(dest.read_text()).get("src_path")
                except Exception:  # noqa: BLE001
                    other = None
                if other and other != str(f):
                    tag = "".join(c for c in f.parent.name if c.isalnum())[:20]
                    dest = _bots_dir() / f"{safe}__{tag}.json"
                    parsed["name"] = f"{f.stem} ({f.parent.name})"
            dest.write_text(json.dumps(parsed, ensure_ascii=False, indent=1))
            (updated if prev else added).append(
                {"name": parsed["name"], "params": parsed["n_params"],
                 "can_report": parsed["can_report"],
                 "chart_bound": len(parsed["chart_bound"])})
        if added or updated or failed:      # sin cambios no se ensucia el registro
            store.log("system", "algo_scan",
                      f"{len(added)} nuevos, {len(updated)} actualizados, "
                      f"{len(same)} sin cambios, {len(failed)} con error")
        if adopted:
            store.log("system", "algo_adopt",
                      "; ".join(f"{a['bot']}: {a['to']}" for a in adopted))
        return {"ok": True, "dir": str(d), "added": added, "updated": updated,
                "unchanged": len(same), "failed": failed, "adopted": adopted,
                "missing": missing}

    @app.post("/algo/scan")
    async def algo_scan():
        res = _algo_scan_once()
        if not res.get("ok"):
            return JSONResponse(res, status_code=400)
        return res

    # ------------------------------------ indicadores propios de Hydra (EMA/SMA/…)

    _IND_HELP = {
        "ema_fast": "EMA rápida: el gatillo.",
        "ema_slow": "EMA lenta: con quién se cruza la rápida.",
        "sma_trend": "SMA de fondo: decide de qué lado se puede operar.",
        "touch_atr": "Cuánta holgura (en ATR) cuenta como «tocar» la media.",
        "lookback": "Velas del canal de ruptura.",
        "rsi_period": "Periodo del RSI.",
        "rsi_low": "RSI por debajo = sobreventa.",
        "rsi_high": "RSI por encima = sobrecompra.",
        "burst_bars": "Velas en las que se mide el impulso.",
        "burst_atr": "Cuántos ATR de movimiento cuentan como impulso.",
        "atr_mult": "Stop loss en múltiplos de ATR.",
        "rr": "Riesgo:beneficio del objetivo.",
    }

    @app.get("/strategies/params")
    async def strategies_params_get():
        """Los indicadores de Hydra con su valor, su rango y para qué sirven."""
        from . import strategies as st2
        out = []
        for name, params in st2.DEFAULTS.items():
            rng = st2.TUNABLE.get(name, {})
            out.append({"id": name, "label": _STRAT_LABEL.get(name, name),
                        "params": [{"name": k, "value": v,
                                    "min": rng.get(k, (None, None))[0],
                                    "max": rng.get(k, (None, None))[1],
                                    "help": _IND_HELP.get(k, "")}
                                   for k, v in params.items()]})
        return {"ok": True, "strategies": out}

    @app.post("/strategies/params")
    async def strategies_params_set(request: Request):
        """Cambia los indicadores. Se recortan al rango permitido y se guardan.

        Ojo con lo que NO hace: los brazos de la flota que ya existen conservan los
        suyos (por eso se puede comparar). Esto manda en lo que se cree de aquí en
        adelante y en la medición de réplica.
        """
        from . import strategies as st2
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        name = str(body.get("strategy") or "")
        if name not in st2.DEFAULTS:
            return JSONResponse({"ok": False, "error": "esa estrategia no existe"},
                                status_code=400)
        st2.DEFAULTS[name] = st2.clamp(name, {**st2.DEFAULTS[name],
                                              **(body.get("params") or {})})
        try:
            f = settings.data_path / "strategy_params.json"
            allp = {}
            if f.is_file():
                allp = json.loads(f.read_text()) or {}
            allp[name] = st2.DEFAULTS[name]
            f.write_text(json.dumps(allp, ensure_ascii=False, indent=1))
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": f"no pude guardar: {exc}"},
                                status_code=500)
        store.log("system", "strategy_params",
                  f"{name}: {json.dumps(st2.DEFAULTS[name], ensure_ascii=False)}")
        return {"ok": True, "strategy": name, "params": st2.DEFAULTS[name]}

    @app.post("/algo/refresh")
    async def algo_refresh():
        """Refresca SOLO los bots ya elegidos (por si los recompilaste). No añade
        ninguno nuevo: eso se hace a mano desde la lista de la carpeta."""
        res = await asyncio.to_thread(_algo_scan_once, True, "")
        if not res.get("ok"):
            return JSONResponse(res, status_code=400)
        return res

    @app.get("/algo/folder")
    async def algo_folder(q: str = "", limit: int = 40):
        """Qué .algo hay en la carpeta, para elegir DE UNO EN UNO.

        No importa nada: solo lista y dice cuál está ya guardado. Con decenas de
        bots una lista entera es ilegible, así que se busca y se corta.
        """
        d = _algo_dir()
        if not d or not d.is_dir():
            return {"ok": False, "error": "primero fija la carpeta"}
        known = _algo_known()
        ql = q.strip().lower()
        rows, total, n_files = [], 0, 0
        # UNA fila por bot: si no, Debug y Release salen como dos bots distintos y
        # la lista miente sobre cuántos tienes.
        for f, copies in _algo_unique(d):
            rel = str(f.relative_to(d))
            n_files += copies
            if ql and ql not in rel.lower():
                continue
            total += 1
            if len(rows) >= max(1, min(200, limit)):
                continue
            st = f.stat()
            prev = known.get(str(f))
            where = str(f.parent.relative_to(d)) if f.parent != d else "."
            rows.append({"file": rel, "name": f.stem, "kb": round(st.st_size / 1024, 1),
                         "mtime": int(st.st_mtime), "imported": bool(prev),
                         "where": where, "copies": copies,
                         "stale": bool(prev and tuple(prev) != (int(st.st_mtime), st.st_size))})
        return {"ok": True, "dir": str(d), "total": total, "shown": len(rows),
                "files": rows, "n_imported": len(known), "n_files": n_files}

    @app.post("/algo/pick")
    async def algo_pick(request: Request):
        """Importa UN .algo de la carpeta: el que se elija en la lista."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        rel = str(body.get("file") or "").strip()
        if not rel:
            return JSONResponse({"ok": False, "error": "falta el archivo"},
                                status_code=400)
        res = await asyncio.to_thread(_algo_scan_once, False, rel)
        if not res.get("ok"):
            return JSONResponse(res, status_code=400)
        if res.get("failed"):
            return JSONResponse({"ok": False, "error": res["failed"][0]["error"]},
                                status_code=400)
        got = (res.get("added") or []) + (res.get("updated") or [])
        return {"ok": True, "bot": got[0] if got else None,
                "unchanged": not got}

    @app.post("/algo/import")
    async def algo_import(request: Request):
        """Recibe un .algo en crudo y guarda sus parámetros.

        Del .algo solo se puede sacar la CONFIGURACIÓN: nombres, tipos, valores por
        defecto y rangos. La lógica va en una DLL de .NET que solo ejecuta el host
        de cTrader — eso no se puede correr aquí, y conviene decirlo claro.
        """
        from . import algo as algo_mod
        raw = await request.body()
        if not raw:
            return JSONResponse({"ok": False, "error": "no llegó ningún archivo"},
                                status_code=400)
        if len(raw) > 20 * 1024 * 1024:
            return JSONResponse({"ok": False, "error": "archivo demasiado grande"},
                                status_code=400)
        try:
            parsed = algo_mod.parse(raw)
        except algo_mod.AlgoError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
        parsed["imported_ts"] = __import__("time").time()
        parsed["file_bytes"] = len(raw)
        safe = "".join(c for c in str(parsed["name"]) if c.isalnum() or c in "-_")[:60] or "bot"
        (_bots_dir() / f"{safe}.json").write_text(
            json.dumps(parsed, ensure_ascii=False, indent=1))
        store.log("system", "algo_import",
                  f"{parsed['name']}: {parsed['n_params']} parámetros en "
                  f"{parsed['n_groups']} grupos")
        return {"ok": True, "bot": safe, **{k: parsed[k] for k in
                ("name", "kind", "api_version", "n_params", "n_groups", "chart_bound")}}

    @app.get("/algo/bots")
    async def algo_bots():
        out = []
        for f in sorted(_bots_dir().glob("*.json")):
            try:
                d = json.loads(f.read_text())
            except Exception:  # noqa: BLE001
                continue
            out.append({"file": f.stem, "name": d.get("name"),
                        "type_label": d.get("type_label") or "", "kind": d.get("kind"),
                        "n_params": d.get("n_params"), "n_groups": d.get("n_groups"),
                        "api_version": d.get("api_version"),
                        "built_at": d.get("built_at"),
                        "chart_bound": d.get("chart_bound") or [],
                        "chart_maybe": d.get("chart_maybe") or [],
                        "chart_mode": d.get("chart_mode") or "desconocido",
                        "chart_mode_param": d.get("chart_mode_param") or "",
                        "can_report": bool(d.get("can_report")),
                        "remote_params": d.get("remote_params") or {},
                        "has_explanation": bool(d.get("explanation")),
                        "imported_ts": d.get("imported_ts")})
        return {"bots": out}

    @app.delete("/algo/bots")
    async def algo_bots_clear():
        """Vacía la lista de bots leídos. NO toca ningún .algo de la carpeta.

        Hace falta porque antes la carpeta se importaba entera: quedaron decenas
        guardados y sin esto no hay manera de empezar de cero y elegir a mano.
        """
        n = 0
        for f in _bots_dir().glob("*.json"):
            try:
                f.unlink()
                n += 1
            except OSError:
                pass
        if n:
            store.log("system", "algo_clear", f"{n} bots quitados de la lista")
        return {"ok": True, "removed": n}

    @app.get("/algo/bots/{name}")
    async def algo_bot(name: str, group: str = "", q: str = ""):
        f = (_bots_dir() / (name + ".json")).resolve()
        if _bots_dir().resolve() not in f.parents or not f.is_file():
            return JSONResponse({"error": "no existe"}, status_code=404)
        d = json.loads(f.read_text())
        if group or q:
            ql = q.lower()
            gs = []
            for g in d.get("groups") or []:
                if group and g["group"] != group:
                    continue
                ps = [p for p in g["params"]
                      if not ql or ql in p["name"].lower() or ql in str(p["label"]).lower()]
                if ps:
                    gs.append({"group": g["group"], "params": ps})
            d["groups"] = gs
        return d

    @app.post("/algo/bots/{name}/explain")
    async def algo_explain(name: str, request: Request):
        """Le pide al cerebro que explique la estrategia leyendo sus parámetros.

        Se guarda junto al bot: la explicación cuesta tokens y no cambia si el
        .algo no cambia, así que se reusa salvo que se pida rehacerla.
        """
        f = (_bots_dir() / (name + ".json")).resolve()
        if _bots_dir().resolve() not in f.parents or not f.is_file():
            return JSONResponse({"ok": False, "error": "no existe"}, status_code=404)
        d = json.loads(f.read_text())
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        if d.get("explanation") and not body.get("redo"):
            return {"ok": True, "cached": True, "explanation": d["explanation"],
                    "explained_ts": d.get("explained_ts")}
        if not settings.anthropic_api_key and settings.brain_for("architect") == "anthropic":
            return JSONResponse(
                {"ok": False, "error": "falta la clave de Anthropic (o pon el cerebro "
                                       "en Local/Híbrido para usar Ollama)"},
                status_code=400)
        from . import algo_explain as ax
        import time as _t
        try:
            text = await ax.explain(d)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": str(exc)[:240]}, status_code=502)
        d["explanation"] = text
        d["explained_ts"] = _t.time()
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1))
        store.log("system", "algo_explain", f"{d.get('name')}: {len(text)} caracteres")
        return {"ok": True, "cached": False, "explanation": text,
                "explained_ts": d["explained_ts"]}

    @app.delete("/algo/bots/{name}")
    async def algo_bot_del(name: str):
        f = (_bots_dir() / (name + ".json")).resolve()
        if _bots_dir().resolve() in f.parents and f.is_file():
            f.unlink()
            return {"ok": True}
        return JSONResponse({"ok": False, "error": "no existe"}, status_code=404)

    @app.get("/bots/active")
    async def bots_active(minutes: float = 45):
        """Solo los bots que están HACIENDO algo: operando o analizando.

        Dos fuentes distintas y complementarias: las posiciones abiertas dicen
        quién opera, y las capturas de trade_context dicen quién está mirando el
        mercado aunque no haya abierto nada. Si un bot no aparece, o no reporta o
        no está haciendo nada.
        """
        out: dict = {}

        def slot(label: str) -> dict:
            key = (label or "").strip() or "(sin etiqueta)"
            return out.setdefault(key, {"label": key, "open": 0, "seen": 0,
                                        "alerted": 0, "symbols": [], "last_ts": 0})

        try:
            for a in store.trade_context_active(minutes):
                g = slot(a["label"])
                g["seen"] += a["seen"]
                g["alerted"] += a["alerted"]
                g["last_ts"] = max(g["last_ts"], int(a["last_ts"] or 0))
                for s in a["symbols"]:
                    if s not in g["symbols"]:
                        g["symbols"].append(s)
        except Exception:  # noqa: BLE001 - el panel no debe caerse por esto
            pass

        # esta ventana tiene que pintar SIEMPRE: sin broker aún, se muestra lo que
        # se sabe por las capturas y ya está.
        if broker is not None and broker.client.account_authorized:
            try:
                pos = await asyncio.wait_for(broker.positions(), timeout=12)
                for p in pos:
                    p["symbol"] = await broker.symbol_name_by_id(p["symbol_id"])
                    g = slot(str(p.get("label") or ""))
                    g["open"] += 1
                    g["last_ts"] = max(g["last_ts"], int(p.get("open_ts") or 0))
                    if p["symbol"] not in g["symbols"]:
                        g["symbols"].append(p["symbol"])
            except Exception:  # noqa: BLE001
                pass

        bots = sorted(out.values(), key=lambda r: (-r["open"], -r["last_ts"]))
        for b in bots:
            b["state"] = "opera" if b["open"] else "analiza"
        return {"ok": True, "minutes": minutes, "bots": bots}

    # ------------------------------- registro «shadow»: los CSV que escribe el bot

    def _shadow_dir():
        d = (settings.shadow_dir or "").strip()
        if d:
            return Path(d).expanduser()
        # por defecto, donde cTrader deja los datos de los cBots
        for g in (Path.home() / "cAlgo" / "Data", Path.home() / "Documents" / "cAlgo" / "Data",
                  Path.home() / "cAlgo", Path.home() / "Documents" / "cAlgo"):
            if g.is_dir():
                return g
        return None

    def _shadow_state_file():
        return settings.data_path / "shadow_state.json"

    def _shadow_scan_once(limit_files: int = 40) -> dict:
        """Lee lo NUEVO de cada CSV y lo guarda en trade_context.

        No interpreta el formato: cada fila se convierte en {columna: valor} y la
        mapea el mismo código que ya recibe los envíos del bot por HTTP. Lo que no
        reconoce se guarda igual en raw_json, así que nada se pierde por no haber
        acertado con el nombre de una columna.
        """
        from . import shadow as sh
        d = _shadow_dir()
        if not d or not d.is_dir():
            return {"ok": False, "error": "no encuentro la carpeta de registros; fíjala"}
        state = sh.load_state(_shadow_state_file())
        # SOLO los bots elegidos. La carpeta Data de cTrader tiene una subcarpeta por
        # cada cBot del espacio de trabajo: leerlas todas hacía aparecer 13 bots
        # "analizando" cuando el usuario solo había elegido 3.
        mine: set[str] = set()
        for jf in _bots_dir().glob("*.json"):
            try:
                j = json.loads(jf.read_text())
            except Exception:  # noqa: BLE001
                continue
            for cand in (j.get("name"), j.get("type_label"), jf.stem,
                         Path(j.get("src_path") or "").stem):
                k = "".join(ch for ch in str(cand or "").lower() if ch.isalnum())
                if k:
                    mine.add(k)

        def _is_mine(f: Path) -> bool:
            if not mine:
                return False           # sin bots elegidos no se importa nada
            for part in (f.parent.name, f.stem):
                k = "".join(ch for ch in part.lower() if ch.isalnum())
                if not k:
                    continue
                if any(k == m or k in m or m in k for m in mine):
                    return True
            return False

        files = [f for f in sh.find_logs(d) if _is_mine(f)][:max(1, limit_files)]
        skipped = len([f for f in sh.find_logs(d) if not _is_mine(f)])
        total, per_file, allrows = 0, [], []
        for f in files:
            try:
                rows, st = sh.read_new(f, state.get(str(f), {}))
            except Exception as exc:  # noqa: BLE001 - un archivo raro no corta el resto
                per_file.append({"file": f.name, "error": str(exc)[:100]})
                continue
            state[str(f)] = st
            if not rows:
                continue
            # cTrader guarda los datos de cada cBot en una carpeta con SU nombre
            # (Data/ConfluenceBot/log.csv), asi que la carpeta identifica mejor que
            # un nombre de archivo generico tipo "shadow_log".
            par = f.parent.name
            label = par if par and par.lower() not in ("data", "logs", "log") else f.stem
            stored = 0
            for r in rows:
                r.setdefault("bot_label", label)
                r.setdefault("source", "csv")
                try:
                    _store_ctx(r)         # su instante sale de la propia fila
                    stored += 1
                except Exception:  # noqa: BLE001 - una fila mala no tira las demás
                    pass
            total += stored
            allrows.extend(rows)
            per_file.append({"file": f.name, "rows": stored, "total_rows": st.get("rows")})
        sh.save_state(_shadow_state_file(), state)
        _shadow_watch.update({"last": time.time(), "imported": total,
                              "files": len(files), "skipped": skipped, "error": ""})
        if total:
            store.log("system", "shadow_import",
                      f"{total} análisis leídos de {len([x for x in per_file if x.get('rows')])} CSV")
            # y una nota en Obsidian: el resumen del día, no una copia de cada fila
            try:
                dg = sh.digest(allrows)
                vault.note("Bots", f"Analisis del bot ({dg['n']} nuevos)",
                           "## Lo que leyó Hydra de tus CSV\n\n"
                           f"- filas nuevas: **{dg['n']}**\n"
                           f"- por instrumento: {dg['by_symbol'] or '—'}\n"
                           f"- por resultado: {dg['by_outcome'] or '—'}\n\n"
                           "Cada fila queda además en el contexto de decisión "
                           "(inmutable), consultable desde el módulo CONTEXT.",
                           tags=["bots", "shadow"])
            except Exception:  # noqa: BLE001 - la nota es un extra
                pass
        return {"ok": True, "dir": str(d), "imported": total,
                "files": per_file[:20], "n_files": len(files),
                "skipped_not_mine": skipped, "my_bots": len(mine)}

    @app.get("/shadow/status")
    async def shadow_status():
        from . import shadow as sh
        d = _shadow_dir()
        logs = sh.find_logs(d)[:20] if d else []
        state = sh.load_state(_shadow_state_file())
        return {"ok": True, "dir": str(d) if d else "",
                "exists": bool(d and d.is_dir()),
                "n_all": len(logs), "watch_minutes": _SHADOW_WATCH_MIN,
                "skipped_not_mine": _shadow_watch.get("skipped") or 0,
                "last": _shadow_watch.get("last"),
                "last_imported": _shadow_watch.get("imported"),
                "files": [{"file": str(f.relative_to(d)),
                           "kb": round(f.stat().st_size / 1024, 1),
                           "mtime": int(f.stat().st_mtime),
                           "read_rows": (state.get(str(f)) or {}).get("rows") or 0}
                          for f in logs]}

    @app.post("/shadow/dir")
    async def shadow_dir_set(request: Request):
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        d = str(body.get("dir") or "").strip()
        if d:
            p2 = Path(d).expanduser()
            if not p2.is_dir():
                return JSONResponse({"ok": False, "error": f"no existe la carpeta {p2}"},
                                    status_code=400)
            d = str(p2)
        settings.shadow_dir = d
        (settings.data_path / "shadow_dir.txt").write_text(d)
        return {"ok": True, "dir": d}

    @app.post("/shadow/scan")
    async def shadow_scan():
        res = await asyncio.to_thread(_shadow_scan_once)
        if not res.get("ok"):
            return JSONResponse(res, status_code=400)
        return res

    @app.get("/trades/recent")
    async def trades_recent(days: float = 3, limit: int = 12):
        """Las operaciones del bot para la cinta de abajo: qué, cuánto y cuánto dio.

        Dos clases de fila, y se distinguen a propósito:
        - CERRADAS: traen su resultado real (bruto − comisión + swap). Eso es dinero.
        - ABIERTAS: van marcadas como abiertas y SIN resultado. La Open API no manda
          el flotante, y calcularlo a ojo (sin el valor del pip de cada símbolo ni la
          divisa de la cuenta) daría una cifra que parece buena y no lo es. Antes de
          inventarla, se dice que está abierta.

        La "estrategia" es la ETIQUETA con la que el cBot abrió: funciona con
        cualquier bot sin tocarlo.
        """
        import logging as _lg
        if broker is None or not broker.client.account_authorized:
            return {"ok": False, "error": "conecta cTrader", "rows": []}
        lim = max(1, min(60, int(limit)))
        rows: list[dict] = []
        try:
            pos = await asyncio.wait_for(broker.positions(), timeout=12)
            for p in pos:
                sym = await broker.symbol_name_by_id(p["symbol_id"])
                rows.append({"state": "open", "ts": p.get("open_ts") or 0,
                             "strategy": (p.get("label") or "").strip() or "(sin etiqueta)",
                             "symbol": sym, "side": p.get("side", ""),
                             "lots": round(float(p.get("volume_units") or 0) / 100000, 2),
                             "units": p.get("volume_units"), "pnl": None})
        except Exception as exc:  # noqa: BLE001 - una parte caída no tumba la cinta
            _lg.getLogger("web").debug("trades_recent posiciones: %s", exc)
        try:
            deals = await asyncio.wait_for(
                broker.deals_since(time.time() - max(0.1, days) * 86400), timeout=20)
            for d in deals:
                if not d.get("closed"):
                    continue
                sym = await broker.symbol_name_by_id(d["symbol_id"])
                rows.append({"state": "closed", "ts": d.get("ts") or 0,
                             "strategy": (d.get("label") or "").strip() or "(sin etiqueta)",
                             "symbol": sym, "side": d.get("side", ""),
                             "lots": round(float(d.get("volume_units") or 0) / 100000, 2),
                             "units": d.get("volume_units"),
                             "pnl": round(d.get("gross", 0.0) - abs(d.get("commission", 0.0))
                                          + d.get("swap", 0.0), 2)})
        except Exception as exc:  # noqa: BLE001
            _lg.getLogger("web").debug("trades_recent deals: %s", exc)
        # abiertas primero (es lo que está en juego ahora) y, dentro, lo más reciente
        rows.sort(key=lambda r: (0 if r["state"] == "open" else 1, -(r["ts"] or 0)))
        closed = [r for r in rows if r["state"] == "closed"]
        return {"ok": True, "days": days, "rows": rows[:lim],
                "n_open": sum(1 for r in rows if r["state"] == "open"),
                "n_closed": len(closed),
                "pnl_closed": round(sum(r["pnl"] or 0 for r in closed), 2)}

    @app.get("/bots/live")
    async def bots_live(days: float = 7):
        """Qué está haciendo CADA bot en la cuenta, agrupado por su etiqueta.

        Esto NO necesita que el bot colabore: cada cBot pone su etiqueta al abrir,
        y se lee de la cuenta por la Open API. Sirve para los bots que no tienen
        parámetros de reporte — que son la mayoría.
        """
        import time as _t
        if not broker.client.account_authorized:
            return {"ok": False, "error": "conecta cTrader"}
        since = _t.time() - max(0.5, min(90.0, float(days))) * 86400
        try:
            pos = await asyncio.wait_for(broker.positions(), timeout=20)
            for p in pos:
                p["symbol"] = await broker.symbol_name_by_id(p["symbol_id"])
        except Exception as exc:  # noqa: BLE001
            pos, _ = [], exc
        try:
            deals = await asyncio.wait_for(broker.deals_since(since), timeout=25)
            for d in deals:
                d["symbol"] = await broker.symbol_name_by_id(d["symbol_id"])
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"no pude leer el histórico: {str(exc)[:140]}"}

        SIN = "(sin etiqueta · manual o bot que no la pone)"
        groups: dict[str, dict] = {}

        def slot(label: str) -> dict:
            key = label or SIN
            return groups.setdefault(key, {
                "label": key, "open": 0, "closed": 0, "net": 0.0,
                "wins": 0, "losses": 0, "symbols": {}, "last_ts": 0})

        for p in pos:
            g = slot(str(p.get("label") or ""))
            g["open"] += 1
            g["symbols"][p["symbol"]] = g["symbols"].get(p["symbol"], 0) + 1
            g["last_ts"] = max(g["last_ts"], int(p.get("open_ts") or 0))
        for d in deals:
            if not d["closed"]:
                continue
            g = slot(d["label"])
            g["closed"] += 1
            net = d["gross"] + d["commission"] + d["swap"]
            g["net"] = round(g["net"] + net, 2)
            g["wins" if net > 0 else "losses"] += 1
            g["symbols"][d["symbol"]] = g["symbols"].get(d["symbol"], 0) + 1
            g["last_ts"] = max(g["last_ts"], d["ts"])

        out = []
        for g in groups.values():
            tot = g["wins"] + g["losses"]
            out.append({**g, "symbols": sorted(g["symbols"], key=lambda k: -g["symbols"][k]),
                        "win_pct": round(g["wins"] / tot * 100, 1) if tot else None})
        out.sort(key=lambda r: -(r["open"] * 1000 + r["closed"]))
        return {"ok": True, "days": days, "bots": out,
                "nota": "cada cBot pone su propia etiqueta al abrir; los bots que no "
                        "la ponen caen todos en el mismo grupo y no se pueden separar"}

    @app.post("/replica/compare")
    async def replica_compare(request: Request):
        """Mide si las estrategias de Hydra coinciden con lo que decidió tu bot.

        Usa las capturas de trade_context (el bot real, con su instante exacto) y
        evalúa las estrategias sobre las MISMAS velas. No mide si la operación
        habría ganado: mide si Hydra habría visto la misma señal.
        """
        from . import replica
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        limit = max(10, min(500, int(body.get("limit", 200))))
        symbol = str(body.get("symbol") or "").upper()
        tol = max(0, min(5, int(body.get("tolerance_bars", 1))))

        ctxs = store.trade_contexts(limit, symbol, "")
        if not ctxs:
            return {"ok": False, "error": "no hay capturas todavía. Apunta el bot a "
                    f"{str(request.base_url).rstrip('/')}/ingest/trade-context y deja "
                    "que corra un rato."}
        if not broker.client.account_authorized:
            return {"ok": False, "error": "hace falta cTrader conectado para traer "
                                          "las velas de esos instantes"}

        syms = sorted({str(c.get("symbol") or "").upper() for c in ctxs if c.get("symbol")})
        candles: dict = {}
        errors: dict = {}
        for sym in syms[:12]:
            try:
                candles[sym] = await asyncio.wait_for(
                    broker.candles(sym, settings.timeframe, 1500), timeout=25)
            except Exception as exc:  # noqa: BLE001
                errors[sym] = str(exc)[:120]

        out = replica.compare(ctxs, candles, tolerance_bars=tol)
        # el aviso viaja CON el resultado: la cifra no se puede leer sin esto
        # Con matiz: solo es un techo si el bot DE VERDAD depende de dibujos con los
        # valores que tiene puestos. En modo automático no depende de ninguno, y en
        # mixto detecta sus propios niveles y además lee los tuyos.
        chart_bound: list[str] = []
        modes: set[str] = set()
        for f in _bots_dir().glob("*.json"):
            try:
                d = json.loads(f.read_text())
            except Exception:  # noqa: BLE001
                continue
            chart_bound += d.get("chart_bound") or []
            modes.add(str(d.get("chart_mode") or "desconocido"))
        names = ", ".join(sorted(set(chart_bound)))
        if not chart_bound:
            aviso = ""
        elif "mixto" in modes:
            aviso = ("tu bot está en modo combinado: detecta sus propios niveles y ADEMÁS "
                     "lee lo que dibujas (" + names + "). La parte automática sí se puede "
                     "replicar; lo que dibujaste a mano, no. Por eso la cifra puede "
                     "quedarse corta sin que las estrategias fallen")
        else:
            aviso = ("tu bot toma los niveles del gráfico (" + names + "): esa entrada no "
                     "existe fuera de cTrader, así que el porcentaje es el techo de lo "
                     "replicable, no un fallo de las estrategias")
        out.update({"ok": True, "timeframe": settings.timeframe,
                    "candle_errors": errors, "chart_modes": sorted(modes),
                    "aviso": aviso})
        store.log("system", "replica_compare",
                  f"{out['compared']} capturas comparadas")
        return out

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

    @app.get("/health/ctrader")
    async def ctrader_health(request: Request):
        """Diagnóstico de la cadena completa hasta los datos del broker.

        Revisa en orden: credenciales, URL de retorno, tokens, cuentas, cuenta
        elegida, conexión, resolución de símbolos y una petición real de velas.
        Se para en el primer eslabón roto y dice qué hacer.
        """
        out: dict = {"steps": [], "ok": False}

        # charset explicito: sin el, el navegador pinta los acentos como Ã± / Ã©
        def _diag(payload: dict) -> JSONResponse:
            return JSONResponse(payload, media_type="application/json; charset=utf-8")

        def step(name, ok, detail="", fix=""):
            out["steps"].append({"paso": name, "ok": bool(ok),
                                 "detalle": detail, "arreglo": fix})
            return ok

        # 1) credenciales de la aplicación
        if not step("Credenciales de la app", bool(settings.ctrader_client_id
                                                  and settings.ctrader_client_secret),
                    f"client_id {'puesto' if settings.ctrader_client_id else 'FALTA'}, "
                    f"secret {'puesto' if settings.ctrader_client_secret else 'FALTA'}",
                    "añade CTRADER_CLIENT_ID y CTRADER_CLIENT_SECRET a tu .env y reinicia"):
            return _diag(out)

        # 1b) FORMA de las credenciales. "Malformed client_id" casi siempre son
        #     comillas, espacios o un salto de línea que se colaron al copiar.
        #     Se describe la forma, nunca el valor.
        import re as _re

        def shape(raw: str) -> tuple[list[str], str]:
            problems = []
            if raw != raw.strip():
                problems.append("sobra espacio o salto de línea en los extremos")
            v = raw.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                problems.append("está entre comillas (quítalas: en el .env van sin ellas)")
            if any(c.isspace() for c in v):
                problems.append("tiene un espacio o salto de línea DENTRO")
            if "\\" in v:
                problems.append("tiene una barra invertida")
            return problems, v

        # Lo que de verdad se envia sale de tokens.*: si no coincide con settings,
        # el canje va con otras credenciales que las que ves configuradas.
        sent_ok = (tokens.client_id == settings.ctrader_client_id.strip()
                   and tokens.client_secret == settings.ctrader_client_secret.strip())
        step("Credenciales que se envian", sent_ok,
             f"client_id enviado: {len(tokens.client_id)} caracteres"
             + (" (COINCIDE)" if sent_ok else " — DISTINTO del configurado"),
             "" if sent_ok else "reinicia la app para que tome las claves guardadas")

        cid_probs, cid = shape(settings.ctrader_client_id)
        sec_probs, sec = shape(settings.ctrader_client_secret)
        if not _re.fullmatch(r"\d+_[A-Za-z0-9]+", cid):
            cid_probs.append("no tiene la forma de un client_id de cTrader, que es "
                             "NÚMERO_LETRASYNÚMEROS (por ejemplo 12345_aB3dEf...). "
                             "¿Seguro que no pegaste el Client Secret o el id de otra cosa?")
        detail = (f"client_id: {len(cid)} caracteres"
                  + (f", prefijo numérico {cid.split('_')[0]}" if "_" in cid else ", sin prefijo")
                  + f" · secret: {len(sec)} caracteres")
        if not step("Forma de las credenciales", not (cid_probs or sec_probs), detail,
                    "client_id — " + "; ".join(cid_probs) if cid_probs else
                    ("secret — " + "; ".join(sec_probs) if sec_probs else "")):
            return _diag(out)

        # 2) URL de retorno: la causa más común de que el OAuth no deje tokens.
        #    La que usa la app tiene que estar registrada TAL CUAL en cTrader.
        origin = str(request.base_url).rstrip("/")
        expected = origin + "/oauth/callback"
        same = settings.ctrader_redirect_uri.rstrip("/") == expected
        step("URL de retorno", same,
             f"la app usa {settings.ctrader_redirect_uri} y estás entrando por {origin}",
             "" if same else
             f"pon CTRADER_REDIRECT_URI={expected} en tu .env, y registra ESA MISMA "
             f"URL en tu aplicación de cTrader (openapi.ctrader.com → tu app → "
             f"Redirect URIs). Si no coinciden letra por letra, cTrader nunca "
             f"devuelve el código y te quedas sin tokens.")

        # 3) tokens
        if not step("Tokens de OAuth", tokens.has_tokens,
                    "guardados en data/tokens.json" if tokens.has_tokens else "no hay",
                    "" if tokens.has_tokens else
                    f"abre {origin}/oauth/login y completa el permiso. Si vuelves a "
                    f"esta pantalla sin tokens, el fallo es la URL de retorno (paso 2)"):
            return _diag(out)

        # 4) cuentas autorizadas
        try:
            token = await tokens.get_access_token()
            await broker.client.start()
            await broker.client.wait_connected(timeout=12)
            accs = await asyncio.wait_for(broker.list_accounts(token), timeout=15)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            # el fallo de certificado NO es un problema de demo/live: es que Python
            # en macOS no usa el llavero del sistema y se queda sin raices
            if "CERTIFICATE_VERIFY_FAILED" in msg or "SSLCertVerification" in msg:
                fix = ("faltan las raices de confianza de Python. Instalalas en el "
                       "entorno de la app:  cd ~/Hydra-Trading && "
                       ".venv/bin/pip install -U certifi  y reinicia. "
                       "Con Python de python.org tambien vale ejecutar "
                       "'Install Certificates.command' de su carpeta en Aplicaciones.")
            else:
                fix = "revisa que el entorno (demo/live) del paso 5 coincida con tu cuenta"
            step("Cuentas autorizadas", False, msg[:200], fix)
            return _diag(out)
        listed = [{"id": a.get("ctidTraderAccountId"), "live": bool(a.get("isLive")),
                   "login": a.get("traderLogin")} for a in accs]
        if not step("Cuentas autorizadas", bool(listed), f"{len(listed)}: {listed}",
                    "en cTrader autoriza al menos una cuenta para esta aplicación"):
            return _diag(out)

        # 5) cuenta elegida y entorno
        aid = settings.ctrader_account_id
        match = next((a for a in listed if a["id"] == aid), None)
        if not step("Cuenta elegida", bool(match),
                    f"CTRADER_ACCOUNT_ID={aid or '(sin elegir)'}, entorno={settings.ctrader_env}",
                    "elige la cuenta en Sistema → CONEXIÓN, o pon su id en "
                    "CTRADER_ACCOUNT_ID. Debe ser una de las de arriba"):
            return _diag(out)
        env_ok = (settings.ctrader_env == "live") == match["live"]
        if not step("Entorno demo/live", env_ok,
                    f"la cuenta {aid} es {'LIVE' if match['live'] else 'DEMO'} y "
                    f"la app apunta a {settings.ctrader_env.upper()} ({settings.ws_url})",
                    f"cambia a {'live' if match['live'] else 'demo'}: son servidores "
                    f"distintos y con el equivocado la autorización se rechaza"):
            return _diag(out)

        # 6) autorización de la cuenta en el websocket
        if not step("Cuenta autorizada", broker.client.account_authorized,
                    getattr(broker.client, "last_error", "") or "sin error reportado",
                    "reinicia la app; si persiste, vuelve a hacer /oauth/login"):
            return _diag(out)

        # 7) los símbolos vigilados existen en ESTE broker
        names = broker.symbol_names()
        bad = []
        for sym in settings.symbol_list:
            try:
                await asyncio.wait_for(broker.symbol_id(sym), timeout=10)
            except Exception as exc:  # noqa: BLE001
                bad.append(f"{sym}: {str(exc)[:60]}")
        step("Símbolos vigilados", not bad,
             f"{len(settings.symbol_list) - len(bad)}/{len(settings.symbol_list)} resueltos"
             + (f" — fallan {bad}" if bad else ""),
             "en Sistema → INSTRUMENTOS quita los que fallen y añade el nombre que "
             "usa tu broker (el campo sugiere los reales)" if bad else "")

        # 8) una petición de velas de verdad: es lo que alimenta los paneles
        probe = settings.symbol_list[0] if settings.symbol_list else "EURUSD"
        try:
            cs = await asyncio.wait_for(
                broker.candles(probe, settings.timeframe, 60), timeout=20)
            step("Velas reales", len(cs) >= 30,
                 f"{probe} {settings.timeframe}: {len(cs)} velas, "
                 f"último cierre {cs[-1].close if cs else '—'}",
                 "" if len(cs) >= 30 else "el broker responde pero manda poco "
                 "histórico: prueba otra temporalidad")
        except Exception as exc:  # noqa: BLE001
            step("Velas reales", False, f"{probe}: {str(exc)[:200]}",
                 "si aquí falla con la cuenta autorizada, suele ser que el símbolo "
                 "no cotiza a esta hora o que el broker lo tiene con otro nombre")

        out["ok"] = all(x["ok"] for x in out["steps"])
        out["resumen"] = ("todo en orden" if out["ok"] else
                          "falla: " + ", ".join(x["paso"] for x in out["steps"] if not x["ok"]))
        out["symbols_del_broker"] = len(names)
        return _diag(out)

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
        raw = None
        # El feed es SEMANAL: bajarlo en cada visita solo sirve para que nos corten
        # con un 429. Se cachea en memoria, se comparte el fichero del Sentinel (que
        # ya lo baja para los bloqueos) y ante un fallo se sirve lo último bueno.
        cache_file = settings.data_path / "calendar.json"
        cached = _cal_cache["raw"]
        fresh = cached is not None and now_ts() - _cal_cache["ts"] < 1800
        cooling = now_ts() < _cal_cache["retry_after"]
        if fresh or (cooling and cached is not None):
            raw = cached
            if cooling and not fresh:
                error = ("la fuente nos limitó (429); mostrando lo último "
                         f"descargado hace {int((now_ts() - _cal_cache['ts']) / 60)} min")
        else:
            try:
                async with _httpx.AsyncClient(timeout=20, follow_redirects=True) as http:
                    r = await http.get(src, headers={"User-Agent": "hydra-trading/1.0"})
                if r.status_code == 429:
                    # respetamos Retry-After; si no viene, 30 min de descanso
                    wait = 1800.0
                    try:
                        wait = max(60.0, float(r.headers.get("Retry-After", "") or 1800))
                    except ValueError:
                        pass
                    _cal_cache["retry_after"] = now_ts() + wait
                    raise RuntimeError(
                        "la fuente del calendario nos limitó por exceso de peticiones "
                        f"(429). Reintento en {int(wait / 60)} min")
                r.raise_for_status()
                raw = r.json()
                _cal_cache.update({"raw": raw, "ts": now_ts(), "retry_after": 0.0})
                try:
                    cache_file.write_text(json.dumps(raw))
                except Exception:  # noqa: BLE001 - la caché es un extra
                    pass
            except Exception as exc:  # noqa: BLE001
                error = str(exc)[:200]
                raw = cached
                if raw is None and cache_file.exists():
                    try:                      # el que dejó el Sentinel
                        raw = json.loads(cache_file.read_text())
                        _cal_cache.update({"raw": raw,
                                           "ts": cache_file.stat().st_mtime})
                        error += " — mostrando el último calendario guardado"
                    except Exception:  # noqa: BLE001
                        pass
                if raw is None:
                    raw = []

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
        return {"events": events[:120], "source": src, "server_time": now,
                "error": error, "fetched_ts": _cal_cache["ts"] or None}

    # ------------------------------------------------------------- dashboard

    @app.get("/", response_class=HTMLResponse)
    async def brain_page():
        """El tablero. Se sirve SIN caché a propósito.

        Toda la interfaz va dentro de este HTML, así que si el navegador se queda
        con una copia vieja —y la app instalada en el iPhone lo hace— se ven los
        cambios de hace días y parece que el despliegue no funcionó. Con no-store
        cada apertura trae la versión que de verdad está corriendo.
        """
        from .ui import BRAIN_HTML
        return HTMLResponse(BRAIN_HTML, headers={
            "Cache-Control": "no-store, must-revalidate", "Pragma": "no-cache"})

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
