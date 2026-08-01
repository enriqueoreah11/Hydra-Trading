"""Servidor MCP local: conecta Claude Desktop (tu suscripción) con Hydra.

    Claude Desktop  ──lee/escribe──▶  este servidor  ──▶  Hydra (SQLite + broker)

La dirección importa: Claude Desktop es un cliente, no un servidor. Hydra NO puede
"mandarle un mensaje" a una conversación. Lo que sí funciona es al revés: tú abres
Claude Desktop, dices "revisa Hydra", y Claude llama estas herramientas.

Ventaja: cero tokens de la API de Anthropic. Usas tu suscripción.

Además de leer el diario, desde aquí se puede **hacer backtest sobre tu propio
histórico** (`data_status`, `backtest_run`, `backtest_optimize`). Se mide sobre el
mismo archivo de velas que usa la app, no sobre una fuente remota: un backtest solo
sirve si da el mismo resultado dentro de tres meses.

Reglas de seguridad (deliberadas, no las relajes):
  - NINGUNA herramienta coloca órdenes, mueve stops ni cambia el lotaje en vivo.
    Eso queda en tu mano, en el navegador.
  - Los cambios de parámetros NO se aplican solos: `propose_change` los deja en
    estado 'awaiting_approval' y tú apruebas o rechazas desde el panel Sistema.
  - `open_hypothesis` exige un umbral de ocurrencias: una pérdida suelta es ruido,
    no señal. Sin fricción estadística el bot se sobreajusta al pasado.

Arranque:  python -m app.mcp_server        (transporte stdio)
"""
from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import indicators
from .config import settings
from .mcp_gate import CATEGORIES, HYPOTHESIS_MIN_OCCURRENCES, MAX_PARAMS_PER_PROPOSAL
from .store import Store

mcp = FastMCP("hydra-trading")

_store: Store | None = None


def store() -> Store:
    global _store
    if _store is None:
        _store = Store(Path(settings.data_dir) / "brain.db")
    return _store


_cdb: dict = {"db": None}


def _candles_file() -> Path:
    return Path(settings.data_dir) / "candles.db"


def _candles():
    """El MISMO archivo de velas que usa la app.

    A propósito: lo que mides desde Claude Desktop tiene que ser exactamente el
    histórico con el que opera Hydra. Dos almacenes distintos darían dos verdades.
    """
    from . import history

    if _cdb["db"] is None:
        _cdb["db"] = history.CandleDB(_candles_file())
    return _cdb["db"]


# ------------------------------------------------------------------- lectura

@mcp.tool()
def get_status() -> dict:
    """Estado actual de Hydra: modo, halt, playbook activo y universo de símbolos."""
    s = store()
    version, _ = s.playbook()
    return {
        "halted": s.halted,
        "dry_run": settings.dry_run,
        "entorno": settings.ctrader_env,
        "cuenta": settings.ctrader_account_id,
        "modelo_ia": settings.model,
        "simbolos": settings.symbol_list,
        "timeframe": settings.timeframe,
        "playbook_version": version,
        "riesgo_por_trade_pct": settings.risk_per_trade_pct,
        "max_perdida_diaria_pct": settings.max_daily_loss_pct,
        "confianza_minima": settings.min_confidence,
        "rr_minimo": settings.min_risk_reward,
    }


@mcp.tool()
def get_playbook() -> dict:
    """El playbook activo: las reglas que Hydra sigue ahora mismo."""
    version, content = store().playbook()
    return {"version": version, "markdown": content}


@mcp.tool()
def query_journal(agent: str = "", kind: str = "", limit: int = 50) -> list[dict]:
    """Diario de Hydra. Filtra por agente (analyst, risk_manager, executor, reviewer…)
    y por tipo de entrada. Devuelve lo más reciente primero."""
    rows = store().recent_journal(limit=min(int(limit), 300))
    if agent:
        rows = [r for r in rows if r["agent"] == agent]
    if kind:
        rows = [r for r in rows if r["kind"] == kind]
    for r in rows:
        r["content"] = (r["content"] or "")[:2000]
    return rows


@mcp.tool()
def query_trade_context(symbol: str = "", outcome: str = "", limit: int = 40) -> list[dict]:
    """Cómo se veía el mercado en el instante en que el bot decidió cada señal.

    Incluye las RECHAZADAS (outcome empieza por 'blocked' o 'low_score'), que es
    donde está el aprendizaje: el bot vio la oportunidad y algo la filtró.
    Filtra por símbolo y/o por outcome (prefijo).
    """
    return store().trade_contexts(min(int(limit), 200), symbol, outcome)


@mcp.tool()
def get_trade_context(ctx_id: int) -> dict:
    """El JSON íntegro de una captura: todo lo que mandó el bot, sin recortar."""
    row = store().trade_context_one(int(ctx_id))
    return row or {"error": "no existe"}


@mcp.tool()
def trade_context_digest(hours: float = 24, symbol: str = "") -> dict:
    """El PATRÓN, no las filas: cuántas señales, cuántas se bloquearon y por qué,
    score medio de las que pasaron frente a las que no, las que se quedaron cerca
    y qué familias de confluencia aparecen. Empieza por aquí antes de pedir filas.
    """
    return store().trade_context_digest(float(hours), symbol)


@mcp.tool()
def get_metrics() -> dict:
    """Métricas de aprendizaje: cuántos post-mortems hay por categoría y cuáles
    ya superan el umbral para abrir una hipótesis."""
    counts = store().postmortem_counts()
    return {
        "umbral_para_hipotesis": HYPOTHESIS_MIN_OCCURRENCES,
        "por_categoria": counts,
        "listas_para_hipotesis": [c["category"] for c in counts
                                  if c["count"] >= HYPOTHESIS_MIN_OCCURRENCES],
        "total": sum(c["count"] for c in counts),
    }


@mcp.tool()
def list_postmortems(category: str = "", limit: int = 50) -> list[dict]:
    """Post-mortems registrados, opcionalmente de una sola categoría."""
    return store().postmortems(category or None, limit=min(int(limit), 200))


@mcp.tool()
def list_hypotheses(status: str = "open") -> list[dict]:
    """Hipótesis abiertas (o promoted / rejected)."""
    return store().hypotheses(status or None)


@mcp.tool()
def list_proposals(status: str = "awaiting_approval") -> list[dict]:
    """Cambios propuestos y su estado. Los 'awaiting_approval' esperan tu decisión
    en el panel Sistema de la app — este servidor NO los aplica."""
    return store().proposals(status or None)


@mcp.tool()
def get_parameters() -> dict:
    """Parámetros ajustables por agente, con su valor actual. Úsalo para saber
    qué se puede proponer en `propose_change`."""
    from . import agent_params
    out: dict = {}
    for key in agent_params.PARAMS:
        specs = agent_params.specs_for(key)
        if specs:
            out[key] = {s["name"]: s.get("value") for s in specs}
    return out


@mcp.tool()
def get_categories() -> dict:
    """La taxonomía cerrada de post-mortems. Clasifica SIEMPRE con una de estas."""
    return CATEGORIES


# ------------------------------------------------- escritura (con compuerta)

@mcp.tool()
def record_postmortem(category: str, notes: str = "", ref: str = "",
                      symbol: str = "") -> dict:
    """Clasifica una operación perdedora en la taxonomía cerrada. NO propone nada.

    Recuerda: si el setup era válido y simplemente salió mal, la categoría correcta
    es 'perdida_esperada'. Esa es la respuesta correcta la mayoría de las veces.
    """
    if category not in CATEGORIES:
        return {"ok": False,
                "error": f"categoría inválida: {category}",
                "categorias_validas": list(CATEGORIES)}
    pid = store().add_postmortem(category, notes, ref, symbol or None)
    counts = {c["category"]: c["count"] for c in store().postmortem_counts()}
    n = counts.get(category, 0)
    return {"ok": True, "id": pid, "categoria": category, "ocurrencias": n,
            "puede_abrir_hipotesis": n >= HYPOTHESIS_MIN_OCCURRENCES,
            "faltan": max(0, HYPOTHESIS_MIN_OCCURRENCES - n)}


@mcp.tool()
def open_hypothesis(description: str, category: str = "", param: str = "",
                    evidence: str = "") -> dict:
    """Registra una teoría sobre qué falla. NO la aplica.

    Solo se permite cuando la categoría ya acumuló al menos
    HYPOTHESIS_MIN_OCCURRENCES post-mortems. Antes de eso, observa.
    """
    if category:
        counts = {c["category"]: c["count"] for c in store().postmortem_counts()}
        n = counts.get(category, 0)
        if n < HYPOTHESIS_MIN_OCCURRENCES:
            return {"ok": False,
                    "error": f"'{category}' solo tiene {n} ocurrencias; se necesitan "
                             f"{HYPOTHESIS_MIN_OCCURRENCES}. Una pérdida individual es "
                             f"ruido, no señal. Sigue observando.",
                    "ocurrencias": n}
    else:
        n = 0
    hid = store().add_hypothesis(description, category, param, evidence, n)
    return {"ok": True, "id": hid, "estado": "open",
            "siguiente": "usa propose_change() para proponer el ajuste; quedará "
                         "esperando aprobación del dueño."}


@mcp.tool()
def propose_change(changes: dict, rationale: str, hypothesis_id: int = 0) -> dict:
    """Propone un ajuste de parámetros. NO lo aplica: queda 'awaiting_approval'
    hasta que el dueño lo apruebe desde el panel Sistema de la app.

    `changes` es {nombre_parametro: valor_nuevo}. Usa get_parameters() para los
    nombres válidos y sus valores actuales.
    """
    from . import agent_params
    valid: set[str] = set()
    for key in agent_params.PARAMS:
        valid.update(s["name"] for s in agent_params.specs_for(key))
    unknown = [k for k in changes if k not in valid]
    if unknown:
        return {"ok": False, "error": f"parámetros desconocidos: {unknown}",
                "validos": sorted(valid)}
    if not changes:
        return {"ok": False, "error": "no propusiste ningún cambio"}
    # Límite duro: cambiar muchas cosas a la vez hace imposible saber cuál ayudó.
    if len(changes) > MAX_PARAMS_PER_PROPOSAL:
        return {"ok": False,
                "error": f"máximo {MAX_PARAMS_PER_PROPOSAL} parámetros por propuesta — "
                         "si cambias muchos a la vez no se puede saber cuál funcionó"}
    pid = store().add_proposal(json.dumps(changes, ensure_ascii=False),
                               rationale, hypothesis_id or None)
    return {"ok": True, "id": pid, "estado": "awaiting_approval",
            "nota": "El dueño debe aprobarlo en la app (Sistema → Propuestas). "
                    "Este servidor no aplica cambios."}


# ------------------------------------------------------------------ mercado

@mcp.tool()
def data_status() -> dict:
    """Qué histórico de velas tiene Hydra guardado: símbolos, temporalidades, cuántas
    velas y desde cuándo. Mira esto ANTES de pedir un backtest: si el símbolo no está
    aquí, no hay nada que medir y hay que importarlo o descargarlo primero."""
    db = _candles()
    inv = db.inventory()
    return {"ok": True, "mb": round(_candles_file().stat().st_size / 1e6, 2)
            if _candles_file().exists() else 0,
            "series": inv, "bars": sum(x["bars"] for x in inv),
            "nota": "las velas son de TU descarga: el mismo backtest da el mismo "
                    "resultado hoy y dentro de tres meses"}


@mcp.tool()
def list_strategies() -> dict:
    """Las estrategias que Hydra sabe simular, con sus parámetros por defecto y el
    rango permitido de cada uno (lo que `backtest_optimize` puede recorrer)."""
    from . import strategies
    return {"estrategias": sorted(strategies.STRATEGIES),
            "por_defecto": strategies.DEFAULTS,
            "rangos": {k: {p: list(v) for p, v in rng.items()}
                       for k, rng in strategies.TUNABLE.items()}}


@mcp.tool()
def backtest_run(symbol: str, tf: str = "H1", strategy: str = "donchian",
                 params: dict | None = None, horizon: int = 60) -> dict:
    """Backtest de una estrategia sobre el histórico guardado, medido en múltiplos de R.

    Reglas del motor, para que interpretes bien el resultado:
      - Peor caso intrabar: si en la misma vela se tocan stop y objetivo, cuenta el stop.
      - Una posición a la vez: no se encadenan señales solapadas.
      - En R, no en dinero: el resultado no depende del lotaje ni de la cuenta.

    `params` vacío usa los valores por defecto de esa estrategia.
    """
    from . import optimize as opt
    from . import strategies
    sym, t = symbol.upper(), tf.upper()
    cs = _candles().series(sym, t)
    if not cs:
        return {"ok": False, "error": f"no hay velas de {sym} {t} guardadas",
                "disponible": _candles().inventory()}
    p = dict(params or strategies.DEFAULTS.get(strategy, {}))
    res = opt.run(cs, strategy, p, int(horizon))
    res.update({"symbol": sym, "tf": t, "strategy": strategy, "params": p,
                "bars": len(cs)})
    return res


@mcp.tool()
def backtest_optimize(symbol: str, tf: str = "H1", strategy: str = "donchian",
                      steps: int = 3, horizon: int = 60, split: float = 0.7,
                      top: int = 8, min_trades: int = 10) -> dict:
    """Prueba combinaciones de parámetros y las ordena por lo que hicieron FUERA de
    muestra: se busca en la primera parte del histórico y se puntúa en la última, que
    el motor no vio.

    Lee las dos cifras juntas. Si una combinación luce mucho mejor dentro que fuera,
    está ajustada al ruido — no la propongas para real por bonito que sea el número
    de dentro. `steps` alto multiplica las combinaciones: empieza por 3.
    """
    from . import optimize as opt
    sym, t = symbol.upper(), tf.upper()
    cs = _candles().series(sym, t)
    if not cs:
        return {"ok": False, "error": f"no hay velas de {sym} {t} guardadas",
                "disponible": _candles().inventory()}
    res = opt.optimize(cs, strategy, int(steps), int(horizon), float(split),
                       int(top), int(min_trades))
    res.update({"symbol": sym, "tf": t})
    return res


@mcp.tool()
def list_setups(days: float = 30, limit: int = 40) -> dict:
    """Los setups acumulados: los que capturó Hydra y los que reportan tus cBots.
    Sirve para comparar lo que el bot ve en vivo con lo que sale en el backtest."""
    return {"ok": True, "days": days, "setups": store().setups(float(days), int(limit))}


@mcp.tool()
def get_market(symbol: str, timeframe: str = "H1") -> dict:
    """Technicals de un instrumento leídos del broker: precio, tendencia, RSI,
    ATR, niveles clave. Solo lectura."""
    import asyncio

    from .broker import Broker
    from .ctrader import CTraderClient
    from .oauth import TokenStore

    async def _go() -> dict:
        data = Path(settings.data_dir)
        tokens = TokenStore(data / "tokens.json", settings.ctrader_client_id,
                            settings.ctrader_client_secret, settings.ctrader_redirect_uri)
        client = CTraderClient(
            ws_url=settings.ws_url, client_id=settings.ctrader_client_id,
            client_secret=settings.ctrader_client_secret,
            account_id=settings.ctrader_account_id,
            access_token_provider=tokens.get_access_token)
        broker = Broker(client, settings.ctrader_account_id)
        await client.start()
        await client.wait_connected(timeout=15)
        try:
            candles = await broker.candles(symbol.upper(), timeframe.upper(), 200)
            snap = indicators.snapshot(candles)
            return {"symbol": symbol.upper(), "timeframe": timeframe.upper(), **snap}
        finally:
            await client.stop()

    try:
        return asyncio.run(_go())
    except Exception as exc:  # noqa: BLE001 - el MCP nunca debe tronar la conversación
        return {"error": f"no pude leer el mercado: {exc}"[:300]}


if __name__ == "__main__":
    mcp.run()
