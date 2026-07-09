"""Motor de simulacion minimal para validar el playbook (no es un backtest completo).

simulate_trade recorre las velas hacia adelante desde el punto de entrada y resuelve
la operacion en multiplos de R (riesgo = |entry - SL|). Ante ambiguedad intrabar
(SL y TP tocados en la misma vela) asume el peor caso: el stop primero.
"""
from __future__ import annotations

from .broker import Candle


def simulate_trade(candles: list[Candle], entry_idx: int, direction: str,
                   entry: float, sl: float, tp: float, horizon: int) -> float | None:
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    end = min(entry_idx + horizon, len(candles) - 1)
    for i in range(entry_idx + 1, end + 1):
        bar = candles[i]
        if direction == "buy":
            if bar.low <= sl:                       # peor caso primero
                return -1.0
            if bar.high >= tp:
                return abs(tp - entry) / risk
        else:  # sell
            if bar.high >= sl:
                return -1.0
            if bar.low <= tp:
                return abs(entry - tp) / risk
    # sin resolver dentro del horizonte: cerrar al ultimo cierre
    exit_price = candles[end].close
    signed = (exit_price - entry) if direction == "buy" else (entry - exit_price)
    return signed / risk


def sample_indices(n_candles: int, samples: int, warmup: int, horizon: int) -> list[int]:
    lo, hi = warmup, n_candles - horizon - 1
    if hi <= lo or samples <= 0:
        return []
    if samples >= hi - lo:
        return list(range(lo, hi))
    step = (hi - lo) / samples
    return [int(lo + step * k) for k in range(samples)]
