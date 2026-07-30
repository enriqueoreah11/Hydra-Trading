"""Estrategias deterministas para la flota.

Punto clave del diseño: **la entrada NO la decide un LLM**. Son reglas puras y
rápidas. El LLM entra solo después, a revisar lotes de operaciones y proponer
ajustes. Eso es lo que hace viable correr 20 variantes a la vez: si cada entrada
costara una llamada al modelo, ni el costo ni el tiempo darían.

Cada estrategia recibe las velas y un dict de parámetros, y devuelve una señal
(o None) para la última vela cerrada.
"""
from __future__ import annotations

from . import indicators as ind
from .broker import Candle


class Signal:
    __slots__ = ("direction", "entry", "sl", "tp")

    def __init__(self, direction: str, entry: float, sl: float, tp: float):
        self.direction = direction      # "buy" | "sell"
        self.entry = entry
        self.sl = sl
        self.tp = tp

    def as_dict(self) -> dict:
        return {"direction": self.direction, "entry": self.entry,
                "sl": self.sl, "tp": self.tp}


def _stops(entry: float, atr_v: float, p: dict, direction: str) -> tuple[float, float]:
    """SL y TP en múltiplos de ATR (así el riesgo se adapta a la volatilidad)."""
    risk = atr_v * float(p.get("atr_mult", 1.5))
    rr = float(p.get("rr", 2.0))
    if direction == "buy":
        return entry - risk, entry + risk * rr
    return entry + risk, entry - risk * rr


# ------------------------------------------------------------------ señales

def donchian(candles: list[Candle], p: dict, i: int) -> Signal | None:
    """Ruptura de canal: compra al superar el máximo de N velas."""
    n = int(p.get("lookback", 20))
    if i < n + 15:
        return None
    hi = max(c.high for c in candles[i - n:i])
    lo = min(c.low for c in candles[i - n:i])
    c = candles[i]
    a = ind.atr(candles[:i + 1], 14)[-1]
    if not a:
        return None
    if c.close > hi:
        return Signal("buy", c.close, *_stops(c.close, a, p, "buy"))
    if c.close < lo:
        return Signal("sell", c.close, *_stops(c.close, a, p, "sell"))
    return None


def rsi_fade(candles: list[Candle], p: dict, i: int) -> Signal | None:
    """Reversión: compra sobreventa extrema, vende sobrecompra extrema."""
    per = int(p.get("rsi_period", 2))
    lowv = float(p.get("rsi_low", 10))
    highv = float(p.get("rsi_high", 90))
    if i < 30:
        return None
    r = ind.rsi([c.close for c in candles[:i + 1]], per)
    if not r:
        return None
    a = ind.atr(candles[:i + 1], 14)[-1]
    c = candles[i]
    if not a:
        return None
    if r[-1] <= lowv:
        return Signal("buy", c.close, *_stops(c.close, a, p, "buy"))
    if r[-1] >= highv:
        return Signal("sell", c.close, *_stops(c.close, a, p, "sell"))
    return None


def momentum_burst(candles: list[Candle], p: dict, i: int) -> Signal | None:
    """Impulso: entra a favor cuando el precio se mueve más de X ATR en N velas."""
    n = int(p.get("burst_bars", 5))
    mult = float(p.get("burst_atr", 1.2))
    if i < n + 20:
        return None
    a = ind.atr(candles[:i + 1], 14)[-1]
    if not a:
        return None
    c = candles[i]
    move = c.close - candles[i - n].close
    if move > a * mult:
        return Signal("buy", c.close, *_stops(c.close, a, p, "buy"))
    if move < -a * mult:
        return Signal("sell", c.close, *_stops(c.close, a, p, "sell"))
    return None


def ema_trend(candles: list[Candle], p: dict, i: int) -> Signal | None:
    """Tendencia: opera cruces de EMA rápida sobre lenta."""
    fast = int(p.get("ema_fast", 20))
    slow = int(p.get("ema_slow", 50))
    if i < slow + 15:
        return None
    closes = [c.close for c in candles[:i + 1]]
    ef, es = ind.ema(closes, fast), ind.ema(closes, slow)
    if len(ef) < 2 or len(es) < 2:
        return None
    a = ind.atr(candles[:i + 1], 14)[-1]
    c = candles[i]
    if not a:
        return None
    if ef[-2] <= es[-2] and ef[-1] > es[-1]:
        return Signal("buy", c.close, *_stops(c.close, a, p, "buy"))
    if ef[-2] >= es[-2] and ef[-1] < es[-1]:
        return Signal("sell", c.close, *_stops(c.close, a, p, "sell"))
    return None


def ma_pullback(candles: list[Candle], p: dict, i: int) -> Signal | None:
    """Retroceso a la media dentro de la tendencia (EMA corta + SMA de fondo).

    Es la confluencia que más se repite en los planes de manual: la SMA larga dice
    de qué lado se puede operar, y solo se entra cuando el precio vuelve a tocar la
    EMA corta y la respeta. Nunca se opera contra la SMA.
    """
    fast = int(p.get("ema_fast", 20))
    trend = int(p.get("sma_trend", 200))
    if i < trend + 15:
        return None
    closes = [c.close for c in candles[:i + 1]]
    ef, st = ind.ema(closes, fast), ind.sma(closes, trend)
    if len(ef) < 3 or len(st) < 3:
        return None
    a = ind.atr(candles[:i + 1], 14)[-1]
    if not a:
        return None
    c, prev = candles[i], candles[i - 1]
    tol = a * float(p.get("touch_atr", 0.25))       # "tocar" con holgura de ATR
    up = c.close > st[-1] and ef[-1] > st[-1]
    dn = c.close < st[-1] and ef[-1] < st[-1]
    if up and prev.low <= ef[-1] + tol and c.close > ef[-1] and c.close > prev.close:
        return Signal("buy", c.close, *_stops(c.close, a, p, "buy"))
    if dn and prev.high >= ef[-1] - tol and c.close < ef[-1] and c.close < prev.close:
        return Signal("sell", c.close, *_stops(c.close, a, p, "sell"))
    return None


STRATEGIES = {
    "donchian": donchian,
    "rsi_fade": rsi_fade,
    "momentum_burst": momentum_burst,
    "ema_trend": ema_trend,
    "ma_pullback": ma_pullback,
}

# Parámetros ajustables por estrategia, con rango permitido. El revisor solo
# puede proponer valores dentro del rango — así un ajuste nunca se sale de madre.
TUNABLE: dict[str, dict[str, tuple[float, float]]] = {
    "donchian": {"lookback": (5, 60), "atr_mult": (0.5, 4.0), "rr": (0.5, 5.0)},
    "rsi_fade": {"rsi_period": (2, 14), "rsi_low": (5, 35), "rsi_high": (65, 95),
                 "atr_mult": (0.5, 4.0), "rr": (0.5, 5.0)},
    "momentum_burst": {"burst_bars": (2, 20), "burst_atr": (0.3, 3.0),
                       "atr_mult": (0.5, 4.0), "rr": (0.5, 5.0)},
    "ema_trend": {"ema_fast": (5, 50), "ema_slow": (20, 200),
                  "atr_mult": (0.5, 4.0), "rr": (0.5, 5.0)},
    "ma_pullback": {"ema_fast": (5, 50), "sma_trend": (50, 200),
                    "touch_atr": (0.05, 1.0), "atr_mult": (0.5, 4.0), "rr": (0.5, 5.0)},
}

DEFAULTS: dict[str, dict] = {
    "donchian": {"lookback": 20, "atr_mult": 1.5, "rr": 2.0},
    "rsi_fade": {"rsi_period": 2, "rsi_low": 10, "rsi_high": 90, "atr_mult": 1.5, "rr": 2.0},
    "momentum_burst": {"burst_bars": 5, "burst_atr": 1.2, "atr_mult": 1.5, "rr": 2.0},
    "ema_trend": {"ema_fast": 20, "ema_slow": 50, "atr_mult": 1.5, "rr": 2.0},
    "ma_pullback": {"ema_fast": 20, "sma_trend": 200, "touch_atr": 0.25,
                    "atr_mult": 1.5, "rr": 2.0},
}


def clamp(strategy: str, params: dict) -> dict:
    """Recorta cada parámetro a su rango permitido y descarta los desconocidos."""
    rng = TUNABLE.get(strategy, {})
    out = dict(DEFAULTS.get(strategy, {}))
    for k, v in (params or {}).items():
        if k not in rng:
            continue
        lo, hi = rng[k]
        try:
            out[k] = max(lo, min(hi, float(v)))
        except (TypeError, ValueError):
            continue
    return out
