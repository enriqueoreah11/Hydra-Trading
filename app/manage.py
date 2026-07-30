"""Gestiona posiciones YA ABIERTAS con la política del propio bot.

Lo que hace y lo que no, porque aquí se mueve dinero:
- SÍ: mover el stop (break-even, trailing) y cerrar parte o todo.
- NO: abrir. Nunca. Ni aquí ni en ningún sitio de este módulo.

Invariante que no se negocia: **el stop nunca se aleja del precio**. Un trailing mal
calculado que ensanche el stop convierte una pérdida acotada en una abierta, así que
cualquier propuesta que empeore el stop actual se descarta antes de salir de aquí.

`plan()` es pura: recibe números y devuelve acciones. Así se puede probar cada caso
sin broker, sin red y sin arriesgar una cuenta.
"""
from __future__ import annotations


def pip_size(symbol: str) -> float:
    """Tamaño de pip por convención del símbolo (basta para gestionar)."""
    s = (symbol or "").upper()
    if "JPY" in s:
        return 0.01
    if s.startswith("XAU") or s.startswith("XAG") or s.startswith("XTI"):
        return 0.01 if s.startswith("XAG") else 0.1
    if any(s.startswith(x) for x in ("US", "DE", "UK", "JPN", "NAS", "SPX")):
        return 1.0
    return 0.0001


def profit_pips(side: str, entry: float, price: float, pip: float) -> float:
    if not pip:
        return 0.0
    d = (price - entry) if str(side).upper().startswith("B") else (entry - price)
    return d / pip


def _better(side: str, new_sl: float, cur_sl: float | None) -> bool:
    """¿El stop nuevo protege MÁS que el actual? Solo entonces se mueve."""
    if new_sl is None:
        return False
    if cur_sl is None:
        return True
    return new_sl > cur_sl if str(side).upper().startswith("B") else new_sl < cur_sl


def plan(pos: dict, policy: dict, price: float, done: set | None = None) -> list[dict]:
    """Acciones a aplicar sobre UNA posición. Lista vacía = no tocar nada.

    `done` son los pasos ya ejecutados para esta posición (p. ej. {"p1"}), para no
    cerrar el mismo parcial dos veces.
    """
    done = done or set()
    out: list[dict] = []
    side = str(pos.get("side") or "")
    entry = float(pos.get("entry_price") or 0)
    if not entry or not price:
        return out
    pip = pip_size(pos.get("symbol") or "")
    gain = profit_pips(side, entry, price, pip)
    cur_sl = pos.get("stop_loss")
    buy = side.upper().startswith("B")
    # 1R = lo que ARRIESGA esta posición. Se mide del stop real si lo hay; si no, del
    # SL que dicen sus parámetros. Sin R no se pueden usar disparadores en R, y es
    # mejor no hacer nada que inventarse el riesgo.
    risk_pips = None
    if cur_sl:
        risk_pips = abs(entry - float(cur_sl)) / pip if pip else None
    if not risk_pips:
        risk_pips = policy.get("sl_pips")

    # 1) PARCIALES antes que el stop: si el precio ya dio para cerrar parte, se
    #    asegura el dinero primero y luego se protege el resto.
    for i, p in enumerate(policy.get("partials") or [], start=1):
        key = f"p{i}"
        if key in done or not p.get("on"):
            continue
        trig = p.get("trigger_pips")
        if trig is None and p.get("trigger_r") and risk_pips:
            trig = float(p["trigger_r"]) * float(risk_pips)     # 1R -> pips
        if trig is None or gain < float(trig):
            continue
        units = float(pos.get("volume_units") or 0) * float(p["pct"]) / 100.0
        if units <= 0:
            continue
        out.append({"action": "close_partial", "step": key, "units": round(units, 2),
                    "reason": f"parcial {p['pct']:.0f}% a +{gain:.1f} pips "
                              f"(su parámetro pedía {trig})"})

    # 2) TRAILING: manda sobre el break-even cuando ya está en marcha, porque
    #    siempre propone un stop igual o mejor.
    tr = policy.get("trailing") or {}
    new_sl = None
    reason = ""
    if tr.get("on") and gain > 0:
        start = tr.get("start_pips")
        if start is None or gain >= float(start):
            if tr.get("distance_pips"):
                d = float(tr["distance_pips"]) * pip
                new_sl = (price - d) if buy else (price + d)
                reason = (f"trailing a {tr['distance_pips']} pips del precio "
                          f"(+{gain:.1f} pips de ganancia)")
            elif tr.get("keep_pct"):
                # conserva ese % de lo ganado: el stop sube con la ganancia
                keep = gain * float(tr["keep_pct"]) / 100.0 * pip
                new_sl = (entry + keep) if buy else (entry - keep)
                reason = (f"trailing conservando el {tr['keep_pct']:.0f}% de "
                          f"+{gain:.1f} pips")

    # 3) BREAK-EVEN: solo si el trailing no propuso ya algo mejor.
    be = policy.get("breakeven") or {}
    if be.get("on") and be.get("trigger_pips") is not None:
        if gain >= float(be["trigger_pips"]):
            off = float(be.get("offset_pips") or 0) * pip
            cand = (entry + off) if buy else (entry - off)
            if not _better(side, new_sl, cand):
                new_sl, reason = cand, (
                    f"break-even a +{gain:.1f} pips "
                    f"(su parámetro disparaba en {be['trigger_pips']})")

    if new_sl is not None and _better(side, new_sl, cur_sl):
        out.append({"action": "amend_sl", "stop_loss": round(new_sl, 5),
                    "from": cur_sl, "reason": reason})
    return out


def explain(policy: dict) -> list[str]:
    """La política en frases, para poder revisarla antes de dejarla suelta."""
    out: list[str] = []
    be, tr = policy.get("breakeven") or {}, policy.get("trailing") or {}
    if be.get("on") and be.get("trigger_pips") is not None:
        off = be.get("offset_pips") or 0
        out.append(f"Mover el stop a la entrada al llegar a +{be['trigger_pips']} pips"
                   + (f" (dejando {off} pips de margen)" if off else ""))
    if tr.get("on") and tr.get("distance_pips"):
        st = tr.get("start_pips")
        out.append(f"Trailing de {tr['distance_pips']} pips"
                   + (f", a partir de +{st} pips" if st else ""))
    if tr.get("on") and tr.get("keep_pct") and not tr.get("distance_pips"):
        out.append(f"Trailing conservando el {tr['keep_pct']:.0f}% de lo ganado")
    for i, p in enumerate(policy.get("partials") or [], start=1):
        if not p.get("on"):
            continue
        if p.get("trigger_pips"):
            out.append(f"Cerrar {p['pct']:.0f}% al llegar a +{p['trigger_pips']} pips")
        elif p.get("trigger_r"):
            out.append(f"Cerrar {p['pct']:.0f}% al llegar a {p['trigger_r']}R "
                       "(R = lo que arriesga esa posición)")
    if not out:
        out.append("Sus parámetros no describen ninguna gestión que se pueda repetir "
                   "aquí: no se tocará nada.")
    return out
