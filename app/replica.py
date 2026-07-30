"""¿Replica Hydra lo que hace tu bot de cTrader?

No se responde opinando: se mide. El bot real manda cada decisión a
/ingest/trade-context con el instante exacto. Aquí se toman esas capturas, se
buscan las velas de ese mismo momento y se evalúan las estrategias deterministas
de Hydra sobre la MISMA barra. Después se compara señal contra señal.

Lo que se mide, y lo que no:
- SÍ: si Hydra habría dado señal donde el bot la dio, y en la misma dirección.
- NO: si la operación habría ganado. Eso es otra pregunta y no se mezcla.

Y una advertencia que va en el resultado: si el bot lee dibujos hechos a mano en
el gráfico, ninguna réplica puede igualarlo. La cifra de coincidencia hay que
leerla sabiendo eso.
"""
from __future__ import annotations

import logging

from . import strategies
from .broker import Candle

log = logging.getLogger("replica")

# Una captura y una vela nunca caen en el mismo milisegundo: se acepta que la
# señal esté en la barra que contiene el instante de la decisión.
_TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800,
               "H1": 3600, "H4": 14400, "D1": 86400}


def _bar_index(candles: list[Candle], ts: float, tf: str) -> int | None:
    """Índice de la barra que contiene ese instante, o None si queda fuera."""
    if not candles or not ts:
        return None
    width = _TF_SECONDS.get(tf.upper(), 900)
    best, best_d = None, width * 1.5
    for i, c in enumerate(candles):
        d = abs(float(c.ts) - ts)
        if d < best_d:
            best, best_d = i, d
    return best


def _norm_side(v: str) -> str:
    v = str(v or "").lower()
    if v.startswith("b") or "buy" in v or "bull" in v or "long" in v:
        return "buy"
    if v.startswith("s") or "sell" in v or "bear" in v or "short" in v:
        return "sell"
    return ""


def compare(contexts: list[dict], candles_by_symbol: dict[str, list[Candle]],
            params_by_strategy: dict[str, dict] | None = None,
            tolerance_bars: int = 1) -> dict:
    """Compara cada captura del bot contra las estrategias de Hydra.

    `tolerance_bars`: se acepta la coincidencia si Hydra dio la señal en la misma
    barra o hasta N barras antes (un bot puede confirmar con un poco de retraso).
    """
    params_by_strategy = params_by_strategy or {}
    per_strategy: dict[str, dict] = {
        name: {"hits": 0, "wrong_side": 0, "misses": 0, "extra": 0}
        for name in strategies.STRATEGIES
    }
    rows: list[dict] = []
    skipped = {"sin_velas": 0, "fuera_de_rango": 0, "sin_direccion": 0}

    for ctx in contexts:
        sym = str(ctx.get("symbol") or "").upper()
        tf = str(ctx.get("timeframe") or "M15").upper()
        side = _norm_side(ctx.get("bias"))
        ts = float(ctx.get("ts_bot") or ctx.get("ts") or 0)
        cs = candles_by_symbol.get(sym) or []
        if not cs:
            skipped["sin_velas"] += 1
            continue
        if not side:
            skipped["sin_direccion"] += 1
            continue
        idx = _bar_index(cs, ts, tf)
        if idx is None or idx < 210:            # las estrategias necesitan histórico
            skipped["fuera_de_rango"] += 1
            continue

        detail = {"id": ctx.get("id"), "symbol": sym, "timeframe": tf, "bar": idx,
                  "bot_side": side, "bot_outcome": ctx.get("outcome"),
                  "bot_score": ctx.get("score"), "hydra": {}}
        for name, fn in strategies.STRATEGIES.items():
            p = params_by_strategy.get(name) or strategies.DEFAULTS.get(name, {})
            got = None
            for back in range(0, max(1, tolerance_bars + 1)):
                j = idx - back
                if j < 210:
                    break
                try:
                    sig = fn(cs, p, j)
                except Exception:  # noqa: BLE001 - una estrategia rota no tumba la medición
                    sig = None
                if sig is not None:
                    got = _norm_side(getattr(sig, "direction", ""))
                    break
            detail["hydra"][name] = got or "-"
            st = per_strategy[name]
            if got is None:
                st["misses"] += 1
            elif got == side:
                st["hits"] += 1
            else:
                st["wrong_side"] += 1
        rows.append(detail)

    n = len(rows)
    board = []
    for name, st in per_strategy.items():
        board.append({
            "strategy": name,
            "hits": st["hits"], "wrong_side": st["wrong_side"], "misses": st["misses"],
            "agreement_pct": round(st["hits"] / n * 100, 1) if n else None,
        })
    board.sort(key=lambda r: -(r["agreement_pct"] or 0))
    return {"compared": n, "skipped": skipped, "leaderboard": board,
            "rows": rows[:120]}
