"""Backtest y búsqueda de parámetros sobre TU histórico.

Dos cosas que hacen que esto sirva para algo o no sirva para nada:

1. **Peor caso intrabar.** Si en la misma vela se tocan el stop y el objetivo, se
   cuenta el stop. Cualquier otra elección infla los resultados y no lo sabrías.

2. **Fuera de muestra.** Optimizar sobre todo el histórico siempre encuentra una
   combinación preciosa… que no vuelve a funcionar. Aquí se parte el histórico: se
   busca en la primera parte y se PUNTÚA en la última, que el motor no vio. Se
   devuelven las dos cifras, y si difieren mucho es que la combinación estaba
   ajustada al ruido — que es justo lo que hay que ver antes de arriesgar dinero.

Se mide en múltiplos de R (lo arriesgado en cada operación), no en dinero: así el
resultado no depende del lotaje ni de la cuenta.
"""
from __future__ import annotations

import itertools

from . import strategies
from .backtest import simulate_trade_detail
from .broker import Candle

WARMUP = 210            # las estrategias necesitan histórico antes de opinar


def run(candles: list[Candle], strategy: str, params: dict,
        horizon: int = 60, start: int = 0, end: int = 0) -> dict:
    """Recorre las velas, toma cada señal y resuelve la operación en R.

    `start`/`end` acotan el tramo (para separar la parte de búsqueda de la de
    comprobación). Una posición a la vez: encadenar señales solapadas mediría otra
    cosa distinta de lo que hace el bot.
    """
    fn = strategies.STRATEGIES.get(strategy)
    if not fn:
        return {"ok": False, "error": f"no existe la estrategia {strategy}"}
    n = len(candles)
    end = end or n
    if n < WARMUP + horizon + 5:
        return {"ok": False, "error": f"hacen falta al menos {WARMUP + horizon + 5} "
                                      f"velas y hay {n}"}
    rs: list[float] = []
    # las operaciones con su vela de entrada y de salida: sirve para auditar el
    # backtest (¿de verdad no se solapan?) y para dibujarlas después
    taken: list[dict] = []
    wins = busy_until = 0
    for i in range(max(start, WARMUP), min(end, n - horizon - 1)):
        if i < busy_until:
            continue                     # ya hay una operación viva
        try:
            sig = fn(candles, params, i)
        except Exception:  # noqa: BLE001 - una estrategia rota no tumba la medición
            continue
        if sig is None:
            continue
        got = simulate_trade_detail(candles, i, sig.direction, sig.entry,
                                    sig.sl, sig.tp, horizon)
        if got is None:
            continue
        r, exit_idx = got
        rs.append(r)
        taken.append({"bar": i, "exit": exit_idx, "r": round(r, 3),
                      "side": sig.direction, "ts": candles[i].ts})
        wins += 1 if r > 0 else 0
        # UNA posición a la vez: hasta que esa operación no se cierra no se mira otra
        # señal. Sin esto se cuentan entradas que el bot nunca habría podido tomar.
        busy_until = exit_idx + 1
    if not rs:
        return {"ok": True, "trades": 0, "expectancy_r": None, "total_r": 0.0,
                "win_pct": None, "max_dd_r": 0.0, "note": "no hubo ni una señal"}
    # racha peor: cuánto se llegó a perder desde el mejor momento
    peak = run_sum = worst = 0.0
    for r in rs:
        run_sum += r
        peak = max(peak, run_sum)
        worst = min(worst, run_sum - peak)
    return {"ok": True, "trades": len(rs),
            "expectancy_r": round(sum(rs) / len(rs), 3),
            "total_r": round(sum(rs), 2),
            "win_pct": round(wins / len(rs) * 100, 1),
            "max_dd_r": round(worst, 2),
            "best_r": round(max(rs), 2), "worst_r": round(min(rs), 2),
            "trades_detail": taken[:200]}


def grid(strategy: str, steps: int = 3, params: dict | None = None) -> list[dict]:
    """Combinaciones a probar, dentro de los rangos permitidos de esa estrategia."""
    rng = strategies.TUNABLE.get(strategy, {})
    base = dict(params or strategies.DEFAULTS.get(strategy, {}))
    if not rng:
        return [base]
    axes = []
    for k, (lo, hi) in rng.items():
        if steps <= 1:
            axes.append([base.get(k, lo)])
            continue
        span = (hi - lo) / (steps - 1)
        vals = [round(lo + span * i, 4) for i in range(steps)]
        # los enteros se quedan enteros: un "lookback" de 12.5 velas no existe
        if float(base.get(k, lo)).is_integer() and float(lo).is_integer():
            vals = sorted({int(round(v)) for v in vals})
        axes.append(vals)
    out = []
    for combo in itertools.product(*axes):
        out.append({**base, **dict(zip(rng.keys(), combo))})
    return out


def optimize(candles: list[Candle], strategy: str, steps: int = 3,
             horizon: int = 60, split: float = 0.7, top: int = 8,
             min_trades: int = 10) -> dict:
    """Busca en la primera parte del histórico y COMPRUEBA en la última.

    Se ordena por lo que hizo FUERA de muestra, no por lo que lució al optimizar. Y
    se exige un mínimo de operaciones: una combinación con tres trades y expectativa
    de 2R no es una estrategia, es una casualidad.
    """
    n = len(candles)
    cut = int(n * max(0.3, min(0.9, split)))
    combos = grid(strategy, steps)
    rows = []
    for p in combos:
        ins = run(candles, strategy, p, horizon, 0, cut)
        if not ins.get("ok") or (ins.get("trades") or 0) < min_trades:
            continue
        oos = run(candles, strategy, p, horizon, cut, n)
        rows.append({"params": p, "in_sample": ins, "out_of_sample": oos,
                     "score": (oos.get("expectancy_r") if oos.get("trades") else None)})
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    return {"ok": True, "strategy": strategy, "combos": len(combos),
            "evaluated": len(rows), "split_bar": cut, "bars": n,
            "top": rows[:top],
            "aviso": ("ordenado por el resultado FUERA de muestra. Si una combinación "
                      "luce mucho mejor dentro que fuera, está ajustada al ruido: no "
                      "la lleves a real")}
