"""Tester — prueba estrategias/cBots definidos por el usuario.

El usuario pega SUS reglas (o describe qué hace su cBot). El Tester aplica esas
reglas EXACTAS sobre datos de mercado para: (a) backtestearlas contra el histórico
y (b) buscar entradas ahora. No inventa criterio propio: solo ejecuta la estrategia.
"""
from __future__ import annotations

from .. import indicators, llm

DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "enter": {"type": "boolean"},
        "direction": {"type": "string", "enum": ["buy", "sell", "none"]},
        "entry": {"type": "number"},
        "stop_loss": {"type": "number"},
        "take_profit": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["enter", "direction", "entry", "stop_loss", "take_profit", "reason"],
    "additionalProperties": False,
}

SYSTEM = """Eres el AGENTE TESTER de un sistema de trading. Recibes una ESTRATEGIA
definida por el usuario (reglas, o la descripción/código de un cBot) y un snapshot de
mercado (indicadores + últimas velas OHLC). Tu ÚNICO trabajo es aplicar EXACTAMENTE
esas reglas: no uses tu propio criterio ni inventes; si las reglas no se cumplen, NO
entras. Decide si la estrategia entraría AHORA. Si entra, da entry, stop_loss y
take_profit coherentes con las reglas (usa el último precio si la regla no especifica).
Responde solo con el JSON del esquema."""


async def decide(strategy: str, symbol: str, timeframe: str, market: dict) -> dict:
    user = (
        f"## ESTRATEGIA DEL USUARIO (aplícala tal cual)\n{strategy}\n\n"
        f"## Símbolo: {symbol}  Timeframe: {timeframe}\n"
        f"## Snapshot de mercado\n{_json(market)}\n\n"
        "¿La estrategia entraría AHORA según sus reglas? Responde con el JSON."
    )
    result = await llm.ask(SYSTEM, user, schema=DECISION_SCHEMA)
    assert isinstance(result, dict)
    return result


def _json(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


def _resolve(direction: str, entry: float, sl: float, tp: float, future) -> str:
    """Resuelve un trade simulado mirando las velas siguientes: 'win', 'loss' u 'open'."""
    for c in future:
        if direction == "buy":
            if c.low <= sl:
                return "loss"
            if c.high >= tp:
                return "win"
        else:  # sell
            if c.high >= sl:
                return "loss"
            if c.low <= tp:
                return "win"
    return "open"


async def backtest(strategy: str, symbol: str, timeframe: str, candles: list,
                   samples: int = 10, horizon: int = 30) -> dict:
    """Corre la estrategia sobre puntos del histórico y resuelve cada trade."""
    n = len(candles)
    if n < 80:
        return {"symbol": symbol, "ok": False, "reason": "pocos datos para backtestear"}
    start, end = 60, n - horizon - 1
    if end <= start:
        return {"symbol": symbol, "ok": False, "reason": "histórico insuficiente"}
    step = max(1, (end - start) // max(1, samples))
    trades, wins, losses, opens, entries = 0, 0, 0, 0, []
    for i in range(start, end, step):
        if trades >= samples:
            break
        window = candles[: i + 1]
        market = indicators.snapshot(window)
        try:
            d = await decide(strategy, symbol, timeframe, market)
        except Exception:  # noqa: BLE001
            continue
        if not d.get("enter") or d.get("direction") not in ("buy", "sell"):
            continue
        trades += 1
        entry = float(d.get("entry") or window[-1].close)
        sl, tp = float(d.get("stop_loss") or 0), float(d.get("take_profit") or 0)
        if sl <= 0 or tp <= 0:
            opens += 1
            continue
        res = _resolve(d["direction"], entry, sl, tp, candles[i + 1: i + 1 + horizon])
        if res == "win":
            wins += 1
        elif res == "loss":
            losses += 1
        else:
            opens += 1
        entries.append({"i": i, "dir": d["direction"], "entry": entry,
                        "sl": sl, "tp": tp, "result": res})
    resolved = wins + losses
    win_rate = round(100 * wins / resolved, 1) if resolved else 0.0
    return {"symbol": symbol, "ok": True, "trades": trades, "wins": wins,
            "losses": losses, "open": opens, "win_rate": win_rate, "entries": entries}
