"""Modo demo — deja ver a los agentes trabajar SIN conectar cTrader.

Genera velas sinteticas (una caminata aleatoria con tendencia) y corre el Analyst
real sobre ellas, mas una vista previa de los chequeos deterministas del Risk Manager.
Requiere ANTHROPIC_API_KEY (el Analyst usa el modelo); no toca ninguna cuenta ni envia
ordenes. Sirve para entender que hace el sistema antes de conectar tu cuenta.
"""
from __future__ import annotations

import random
import time

from . import indicators
from .agents import analyst
from .broker import Candle
from .config import settings
from .constants import TRENDBAR_PERIOD_MINUTES
from .store import Store

# precios base plausibles por simbolo (solo para que las velas se vean realistas)
_BASE_PRICE = {"EURUSD": 1.0850, "GBPUSD": 1.2700, "USDJPY": 156.0,
               "XAUUSD": 2350.0, "XAGUSD": 30.0, "AUDUSD": 0.6600}


def synthetic_candles(symbol: str, n: int = 200) -> list[Candle]:
    """Caminata aleatoria con una ligera tendencia, reproducible por simbolo+dia."""
    seed = hash((symbol, time.strftime("%Y-%m-%d"))) & 0xFFFFFFFF
    rng = random.Random(seed)
    base = _BASE_PRICE.get(symbol.upper(), 100.0)
    vol = base * 0.0015                       # ~0.15% de rango por vela
    drift = vol * rng.uniform(-0.15, 0.15)    # tendencia suave (arriba o abajo)
    minutes = TRENDBAR_PERIOD_MINUTES.get(settings.timeframe, 15)
    now = int(time.time())
    price = base
    candles: list[Candle] = []
    for i in range(n):
        o = price
        step = rng.gauss(drift, vol)
        c = max(o + step, base * 0.5)
        hi = max(o, c) + abs(rng.gauss(0, vol * 0.4))
        lo = min(o, c) - abs(rng.gauss(0, vol * 0.4))
        ts = now - (n - i) * minutes * 60
        candles.append(Candle(ts=ts, open=round(o, 5), high=round(hi, 5),
                              low=round(lo, 5), close=round(c, 5),
                              volume=rng.randint(500, 5000)))
        price = c
    return candles


def _risk_preview(proposal: dict) -> dict:
    """Chequeos deterministas del Risk Manager que no necesitan datos de cuenta."""
    entry = float(proposal["last_close"])
    sl = float(proposal["stop_loss"])
    tp = float(proposal["take_profit"])
    direction = proposal["direction"]
    checks = []
    ok_conf = proposal.get("confidence", 0) >= settings.min_confidence
    checks.append(("confianza >= minimo", ok_conf,
                   f"{proposal.get('confidence')} vs {settings.min_confidence}"))
    coherent = ((direction == "buy" and sl < entry < tp) or
                (direction == "sell" and tp < entry < sl))
    checks.append(("niveles coherentes", coherent, f"SL {sl} / entrada {entry} / TP {tp}"))
    rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
    ok_rr = rr >= settings.min_risk_reward
    checks.append(("riesgo/beneficio >= minimo", ok_rr, f"{rr:.2f} vs {settings.min_risk_reward}"))
    passes = all(c[1] for c in checks)
    return {"passes_deterministic": passes, "risk_reward": round(rr, 2),
            "checks": [{"nombre": n, "ok": o, "detalle": d} for n, o, d in checks],
            "nota": "el tamaño final y el veto cualitativo se calculan con datos de la cuenta real"}


async def run_demo(store: Store) -> list[dict]:
    if not settings.anthropic_api_key:
        raise RuntimeError("falta ANTHROPIC_API_KEY: el modo demo necesita el modelo para el Analyst")
    _, playbook = store.playbook()
    results: list[dict] = []
    for symbol in settings.symbol_list:
        candles = synthetic_candles(symbol, 200)
        market = indicators.snapshot(candles)
        proposal = await analyst.analyze(symbol, settings.timeframe, market, playbook, [])
        entry = {"symbol": symbol, "market": {k: market[k] for k in
                 ("last_close", "ema20", "ema50", "ema200", "rsi14", "atr14")},
                 "proposal": proposal}
        if proposal.get("action") == "propose":
            entry["risk_preview"] = _risk_preview(proposal)
        store.log("demo", "demo_analysis", entry, symbol=symbol)
        results.append(entry)
    return results
