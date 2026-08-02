"""Resume el historial de operaciones: cuánto, con qué y qué tal salió.

Dos decisiones que cambian lo que ves:

1. **Las abiertas no cuentan en el resultado.** La Open API no manda el flotante, y
   estimarlo sin el valor del pip de cada símbolo daría una cifra que parece buena y
   no lo es. Se cuentan aparte, como lo que son: dinero en juego, todavía no dinero.

2. **Todo es NETO.** Bruto menos comisión más swap, que es lo que llega a la cuenta.
   Un resumen en bruto luce mejor y no es tu dinero.

El porcentaje de aciertos va siempre junto al resultado, nunca solo: una estrategia
puede acertar el 80% de las veces y perder dinero, y verlo suelto engaña.
"""
from __future__ import annotations


def _neto(r: dict) -> float:
    try:
        return float(r.get("pnl") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _grupo(rows: list[dict], clave: str) -> list[dict]:
    """Agrupa las CERRADAS por la clave que sea, ordenado por lo que más movió."""
    out: dict[str, dict] = {}
    for r in rows:
        if r.get("state") != "closed":
            continue
        k = str(r.get(clave) or "—")
        g = out.setdefault(k, {"key": k, "n": 0, "net": 0.0, "wins": 0,
                               "best": None, "worst": None})
        v = _neto(r)
        g["n"] += 1
        g["net"] += v
        g["wins"] += 1 if v > 0 else 0
        g["best"] = v if g["best"] is None else max(g["best"], v)
        g["worst"] = v if g["worst"] is None else min(g["worst"], v)
    for g in out.values():
        g["net"] = round(g["net"], 2)
        g["win_pct"] = round(g["wins"] / g["n"] * 100, 1) if g["n"] else None
        g["avg"] = round(g["net"] / g["n"], 2) if g["n"] else None
    # por lo que más pesa en la cuenta, no alfabético: lo que duele va arriba
    return sorted(out.values(), key=lambda g: -abs(g["net"]))


def summarize(rows: list[dict]) -> dict:
    """Totales, reparto por estrategia y por instrumento, y la racha."""
    cerradas = [r for r in rows if r.get("state") == "closed"]
    abiertas = [r for r in rows if r.get("state") == "open"]
    netos = [_neto(r) for r in cerradas]
    ganadoras = [v for v in netos if v > 0]
    perdedoras = [v for v in netos if v < 0]

    # peor racha: cuánto se llegó a perder desde el mejor momento. Es lo que
    # de verdad se aguanta, y no sale de mirar el total.
    acum = pico = peor = 0.0
    for v in sorted(cerradas, key=lambda r: r.get("ts") or 0):
        acum += _neto(v)
        pico = max(pico, acum)
        peor = min(peor, acum - pico)

    return {
        "n_closed": len(cerradas),
        "n_open": len(abiertas),
        "net": round(sum(netos), 2),
        "win_pct": round(len(ganadoras) / len(cerradas) * 100, 1) if cerradas else None,
        "avg_win": round(sum(ganadoras) / len(ganadoras), 2) if ganadoras else None,
        "avg_loss": round(sum(perdedoras) / len(perdedoras), 2) if perdedoras else None,
        "best": round(max(netos), 2) if netos else None,
        "worst": round(min(netos), 2) if netos else None,
        "max_dd": round(peor, 2),
        # lotes abiertos: lo que está en juego ahora, que no es resultado
        "open_lots": round(sum(float(r.get("lots") or 0) for r in abiertas), 2),
        "by_strategy": _grupo(rows, "strategy"),
        "by_symbol": _grupo(rows, "symbol"),
        "nota": ("las abiertas no cuentan en el resultado: la Open API no manda el "
                 "flotante y estimarlo daría una cifra que parece buena y no lo es"),
    }
