"""Pure-python technical indicators computed from Candle lists (no numpy needed)."""
from __future__ import annotations

from .broker import Candle


def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def sma(values: list[float], period: int) -> list[float]:
    """Media simple. No es lo mismo que la EMA, y muchos planes usan las dos: la
    SMA200 como línea de agua y una EMA rápida para el gatillo. Antes de tener
    `period` velas se promedia lo que haya, para no dejar huecos."""
    if not values or period < 1:
        return []
    out, acc = [], 0.0
    for i, v in enumerate(values):
        acc += v
        if i >= period:
            acc -= values[i - period]
        out.append(acc / min(i + 1, period))
    return out


def ma_stack(closes: list[float]) -> dict:
    """Cómo están ordenadas las medias y dónde queda el precio.

    Devuelve la LECTURA, no solo los números: es lo que hace falta para decidir si
    hay tendencia o si el precio anda peleado con sus medias. `enough_history`
    avisa cuando la SMA200 aún no tiene 200 velas y por tanto no se puede creer.
    """
    if not closes:
        return {}
    e20, e50 = ema(closes, 20), ema(closes, 50)
    s50, s200 = sma(closes, 50), sma(closes, 200)
    last = closes[-1]
    above = [n for n, v in (("ema20", e20[-1]), ("ema50", e50[-1]),
                            ("sma50", s50[-1]), ("sma200", s200[-1])) if last > v]
    if last > s200[-1] and e20[-1] > e50[-1]:
        read = "alcista"
    elif last < s200[-1] and e20[-1] < e50[-1]:
        read = "bajista"
    else:
        read = "mixto"
    return {"sma50": round(s50[-1], 6), "sma200": round(s200[-1], 6),
            "price_above": above, "lectura": read,
            "enough_history": len(closes) >= 200}


def rsi(values: list[float], period: int = 14) -> list[float]:
    if len(values) < period + 1:
        return [50.0] * len(values)
    gains, losses = [], []
    for i in range(1, len(values)):
        ch = values[i] - values[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    out = [50.0] * (period + 1)
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        rs = avg_g / avg_l if avg_l else float("inf")
        out.append(100 - 100 / (1 + rs) if avg_l else 100.0)
    return out


def atr(candles: list[Candle], period: int = 14) -> list[float]:
    if not candles:
        return []
    trs = [candles[0].high - candles[0].low]
    for i in range(1, len(candles)):
        c0, c1 = candles[i - 1], candles[i]
        trs.append(max(c1.high - c1.low, abs(c1.high - c0.close), abs(c1.low - c0.close)))
    return ema(trs, period)


def swing_levels(candles: list[Candle], lookback: int = 5) -> dict:
    """Nearest support/resistance from swing pivots."""
    highs, lows = [], []
    for i in range(lookback, len(candles) - lookback):
        window = candles[i - lookback:i + lookback + 1]
        if candles[i].high == max(x.high for x in window):
            highs.append(candles[i].high)
        if candles[i].low == min(x.low for x in window):
            lows.append(candles[i].low)
    last = candles[-1].close if candles else 0
    resistances = sorted([h for h in highs if h > last])[:3]
    supports = sorted([l for l in lows if l < last], reverse=True)[:3]
    return {"supports": supports, "resistances": resistances}


def snapshot(candles: list[Candle]) -> dict:
    """Compact market snapshot the Analyst receives."""
    closes = [c.close for c in candles]
    e20, e50, e200 = ema(closes, 20), ema(closes, 50), ema(closes, 200)
    r = rsi(closes, 14)
    a = atr(candles, 14)
    return {
        "last_close": closes[-1],
        "ema20": round(e20[-1], 6),
        "ema50": round(e50[-1], 6),
        "ema200": round(e200[-1], 6),
        "rsi14": round(r[-1], 2),
        "atr14": round(a[-1], 6),
        # las medias simples y la lectura del abanico: el Analyst las recibe ya
        # interpretadas, no tiene que deducir el orden de cuatro números
        "ma": ma_stack(closes),
        "levels": swing_levels(candles),
        "recent_candles": [
            {"ts": c.ts, "o": c.open, "h": c.high, "l": c.low, "c": c.close}
            for c in candles[-40:]
        ],
    }
