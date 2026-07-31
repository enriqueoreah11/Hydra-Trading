"""Manda la MISMA operación a varias cuentas a la vez.

No es un copiador clásico (nadie lee las operaciones de otro y las persigue): es la
misma orden enviada a cada cuenta en el momento de abrirla. Sale más limpio — sin
retraso de copia y sin depender de que la cuenta origen sea visible.

Lo que hay que tener claro, porque cambia lo que se puede hacer:
- una sola autorización de cTrader cubre las cuentas de ESE cTrader ID. Se autoriza
  cada una en la misma sesión y se le manda su orden.
- una cuenta de otra propiedad (otra prop firm con su propio login) NO entra ahí:
  necesitaría su propia autorización.

El tamaño no se copia a ciegas. Mandar 1 lote a una cuenta de 100.000 y a otra de
2.000 no es replicar: es reventar la pequeña. Por eso cada destino dice CÓMO se
dimensiona, y por defecto es proporcional al capital.
"""
from __future__ import annotations

MODES = ("risk", "equity", "same", "mult")

# Valor de un pip por LOTE (100 000 unidades) en la divisa de cotización. Para un par
# con 5 decimales: 0.0001 × 100 000 = 10. Es exacto cuando esa divisa es la de tu
# cuenta; si no, es una aproximación y se dice — un tamaño de posición calculado con
# un valor de pip inventado es exactamente la clase de error que vacía cuentas.
def pip_value_per_lot(symbol: str, pip: float) -> float:
    return pip * 100000


def lots_for_risk(equity: float, risk_pct: float, sl_pips: float,
                  pip_value: float) -> float:
    """Lotes para arriesgar ese % del capital con ESE stop."""
    if not (equity and risk_pct and sl_pips and pip_value):
        return 0.0
    return (float(equity) * float(risk_pct) / 100.0) / (float(sl_pips) * float(pip_value))


def map_symbol(dest: dict, symbol: str) -> str:
    """El nombre que ese instrumento tiene EN ESA cuenta.

    Las prop firms renombran: EURUSD.raw, XAUUSD.pro, US500.cash. Primero manda la
    tabla que pongas tú; si no hay entrada, se prueba con el sufijo de la cuenta; y si
    tampoco, se deja el nombre tal cual y que lo resuelva el catálogo de esa cuenta,
    que ya tolera sufijos y alias.
    """
    sym = str(symbol or "").upper()
    table = {str(k).upper(): str(v) for k, v in (dest.get("symbols") or {}).items()}
    if sym in table:
        return table[sym]
    suf = str(dest.get("suffix") or "")
    return (sym + suf) if suf else sym


def allowed(dest: dict, symbol: str) -> bool:
    """¿Este destino acepta ese instrumento? Lista blanca y lista negra, opcionales."""
    sym = str(symbol or "").upper()
    only = [str(x).upper() for x in (dest.get("only") or [])]
    never = [str(x).upper() for x in (dest.get("never") or [])]
    if sym in never:
        return False
    return (sym in only) if only else True


def clamp_lots(lots: float, min_lots: float = 0.01, max_lots: float = 100.0) -> float:
    """Redondea al centésimo (el paso habitual) y encaja en los límites."""
    if lots <= 0:
        return 0.0
    return max(min_lots, min(max_lots, round(lots + 1e-9, 2)))


def size_for(dest: dict, base_lots: float, base_equity: float,
             dest_equity: float | None, sl_pips: float = 0,
             pip_value: float = 10.0) -> tuple[float, str]:
    """Cuántos lotes van a ESE destino, y por qué.

    - risk:   el % del capital DE ESA CUENTA que quieres arriesgar en esta operación.
              Es el modo honesto: cada cuenta arriesga lo suyo, no lo de la otra.
    - equity: proporcional al capital (misma exposición relativa que la principal).
    - same:   lo mismo que la cuenta principal.
    - mult:   lo de la principal por un factor que tú pones.

    Si falta un dato para calcular (capital, stop), se devuelve 0 y se dice por qué:
    es mejor no mandar nada que mandar un tamaño inventado a una cuenta real.
    """
    mode = str(dest.get("mode") or "equity").lower()
    if mode == "risk":
        pct = float(dest.get("value") or 0)
        if not (dest_equity and pct and sl_pips):
            return 0.0, ("falta el capital de esa cuenta, el % de riesgo o el stop: "
                         "no mando nada antes que inventarme el tamaño")
        lots = lots_for_risk(dest_equity, pct, sl_pips, pip_value)
        return clamp_lots(lots), (f"{pct:g}% de {dest_equity:g} con stop de "
                                  f"{sl_pips:g} pips")
    if mode == "same":
        return clamp_lots(base_lots), "mismo lotaje que la principal"
    if mode == "mult":
        f = float(dest.get("value") or 1)
        return clamp_lots(base_lots * f), f"x{f:g} sobre la principal"
    if not base_equity or not dest_equity:
        return 0.0, ("no sé el capital de una de las dos cuentas: no mando nada "
                     "antes que mandar un tamaño inventado")
    ratio = float(dest_equity) / float(base_equity)
    return clamp_lots(base_lots * ratio), (
        f"proporcional al capital ({dest_equity:g} / {base_equity:g} = {ratio:.2f}x)")


def plan(dests: list[dict], base_lots: float, base_equity: float,
         equities: dict, symbol: str = "", sl_pips: float = 0,
         pip_value: float = 10.0) -> list[dict]:
    """El reparto completo, listo para revisarlo ANTES de enviar nada."""
    out = []
    for d in dests:
        if not d.get("enabled"):
            continue
        aid = int(d.get("account_id") or 0)
        if not aid:
            continue
        row = {"account_id": aid, "alias": d.get("alias") or str(aid),
               "mode": d.get("mode") or "equity",
               "symbol": map_symbol(d, symbol) if symbol else ""}
        if symbol and not allowed(d, symbol):
            row.update({"lots": 0.0, "units": 0.0, "skip": True,
                        "why": f"{symbol} no está permitido en esta cuenta"})
            out.append(row)
            continue
        lots, why = size_for(d, base_lots, base_equity, equities.get(aid),
                             sl_pips, pip_value)
        row.update({"lots": lots, "units": round(lots * 100000, 2),
                    "why": why, "skip": lots <= 0})
        out.append(row)
    return out
