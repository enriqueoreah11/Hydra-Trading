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
        "levels": swing_levels(candles),
        "recent_candles": [
            {"ts": c.ts, "o": c.open, "h": c.high, "l": c.low, "c": c.close}
            for c in candles[-40:]
        ],
    }
