"""FastAPI dashboard: estado, OAuth de cTrader, diario, playbook y kill switch."""
from __future__ import annotations

import datetime as dt
import html
import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .broker import Broker
from .config import settings
from .oauth import TokenStore, build_auth_url
from .store import Store


def create_app(store: Store, tokens: TokenStore, broker: Broker) -> FastAPI:
    app = FastAPI(title="hydra-trading")

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
            accounts = await broker.list_accounts(token)
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
        if broker.client.account_authorized:
            try:
                trader = await broker.trader()
                out["balance"] = trader["balance"]
            except Exception:  # noqa: BLE001
                pass
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

    # ------------------------------------------------------------- dashboard

    @app.get("/", response_class=HTMLResponse)
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
