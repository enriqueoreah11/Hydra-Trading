"""Saca del .algo CÓMO gestiona el bot sus posiciones, para poder hacerlo igual.

La lógica de entrada del bot está compilada y no se puede leer. Pero la GESTIÓN
(break-even, trailing, parciales) casi siempre vive en sus parámetros, y eso sí se
puede leer y reproducir: la Open API de cTrader permite mover el stop y cerrar,
que es exactamente lo que hace falta.

Regla de la casa: aquí NUNCA se deduce una entrada. Solo gestión de lo ya abierto.

Lo que no se sepa mapear se DEVUELVE en `unmapped`. Un parámetro de gestión que se
ignore en silencio es peor que no tener política: el dueño creería que se está
respetando algo que no se está tocando.
"""
from __future__ import annotations

_TRUE = (True, "true", "True", 1, "1", "yes", "si", "sí")


def _norm(s: str) -> str:
    return "".join(c for c in str(s or "").lower() if c.isalnum())


def _flat(parsed: dict) -> list[dict]:
    return [p for g in (parsed.get("groups") or []) for p in (g.get("params") or [])]


def _on(v) -> bool:
    return v in _TRUE


def _num(v, default=None):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    # cTrader usa el maximo de un entero (2147483647) como "sin limite". Tomarlo por
    # un valor real daria un trailing de dos mil millones de pips, que en la practica
    # es "no muevas nunca el stop" disfrazado de configuracion.
    if abs(f) > 1e6:
        return default
    return f


# Cada regla: (clave, palabras que la identifican, palabras que la descartan).
# Los prefijos cortos (Ttp = trailing take profit, Ptp = partial take profit, Ts =
# trailing stop) salen de bots reales: sin ellos, un bot bien hecho parecía no tener
# gestión ninguna.
_MATCH = (
    ("be_on",        ("usebreakeven", "enablebreakeven", "breakevenenabled",
                      "moveslbreakeven", "usebe", "beenable"), ()),
    ("be_trigger",   ("breakeventrigger", "breakevenpips", "betrigger", "bestart",
                      "breakevenstart", "breakevenafter", "beactivatepips"), ()),
    ("be_offset",    ("breakevenoffset", "beoffset", "breakevenlock",
                      "breakevenplus"), ()),
    ("tr_on",        ("usetrailing", "enabletrailing", "trailingenabled",
                      "trailingstopenabled", "usetrail", "ttpenable", "tsenable"), ()),
    ("tr_start",     ("ttpactivatepips", "trailingstart", "trailingtrigger",
                      "trailingafter", "trailstart", "trailingactivation",
                      "tsactivatepips"), ()),
    ("tr_distance",  ("ttptrailpips", "trailingdistance", "trailingstoppips",
                      "trailingpips", "traildistance", "trailingstep",
                      "trailingstop", "tstrailpips"), ("enabled", "enable", "pct")),
    # trailing por PORCENTAJE de lo ganado: otra mecánica, no un pips fijo
    ("tr_pct",       ("tstrailpct", "trailpct", "trailingpct",
                      "trailingpercent"), ()),
    ("sl_pips",      ("slfixedpips", "stoplosspips", "slpips", "fixedsl",
                      "initialsl"), ("learn", "sim", "backtest", "min", "max",
                                     "buffer", "atr", "mode", "trailing", "breakeven")),
    ("tp_pips",      ("tpfixedpips", "takeprofitpips", "tppips",
                      "fixedtp"), ("learn", "sim", "backtest", "min", "max", "buffer",
                                   "mode", "partial", "rr", "second", "third")),
    ("p1_on",        ("ptpenable", "usepartial", "enablepartial", "partialenabled",
                      "usepartialclose"), ()),
    ("p1_pct",       ("ptpclosepct", "partialclosepct", "partial1pct",
                      "partialpercent", "closepartialpercent", "tp1percent",
                      "partialvolume"), ()),
    ("p1_trigger",   ("partialclosepips", "partial1pips", "tp1pips",
                      "partialtrigger", "partialafter"), ()),
    # disparador en múltiplos de R (1R = lo que arriesga esa posición)
    ("p1_trigger_r", ("ptpfirstr", "partialfirstr", "partialr", "tp1r"), ()),
)

# Palabras que delatan un parámetro DE GESTIÓN. Si uno de estos no se mapea, se
# avisa: es justo el que el dueño espera que se respete.
_MGMT_HINTS = ("breakeven", "trailing", "trail", "partial", "stoploss", "takeprofit",
               "slpips", "tppips", "closeafter", "timestop", "maxbars", "movesl")


def from_params(parsed: dict) -> dict:
    """Devuelve la política de gestión leída del bot, y qué no se pudo mapear."""
    found: dict[str, dict] = {}
    for p in _flat(parsed):
        n = _norm(p.get("name"))
        for key, words, avoid in _MATCH:
            if key in found:
                continue
            if any(w in n for w in words) and not any(a in n for a in avoid):
                found[key] = p
                break

    def val(key, default=None):
        """TU valor manda sobre el de fábrica.

        `value` lo pone el .cbotset que subes; `default` viene del .algo. Gestionar
        con el de fábrica teniendo tú otro puesto es el fallo silencioso de todo
        esto: no da error, simplemente mueve el stop donde no toca.
        """
        p = found.get(key)
        if p is None:
            return default
        return p["value"] if p.get("value") is not None else p.get("default")

    be_trigger = _num(val("be_trigger"))
    tr_dist = _num(val("tr_distance"))
    tr_pct = _num(val("tr_pct"))
    p1_pct = _num(val("p1_pct"))
    p1_r = _num(val("p1_trigger_r"))
    pol = {
        "breakeven": {
            # si el bot no trae interruptor, manda que haya un disparador puesto
            "on": _on(val("be_on", be_trigger is not None and be_trigger > 0)),
            "trigger_pips": be_trigger,
            "offset_pips": _num(val("be_offset"), 0.0),
        },
        "trailing": {
            "on": _on(val("tr_on", (tr_dist is not None and tr_dist > 0)
                                   or (tr_pct is not None and 0 < tr_pct < 100))),
            "start_pips": _num(val("tr_start"), be_trigger),
            "distance_pips": tr_dist,
            # "conserva el X% de lo ganado": el stop sube con la ganancia
            "keep_pct": tr_pct if (tr_pct is not None and 0 < tr_pct < 100) else None,
        },
        "partials": [],
        "sl_pips": _num(val("sl_pips")),
        "tp_pips": _num(val("tp_pips")),
    }
    if p1_pct and p1_pct > 0:
        pol["partials"].append({
            "pct": min(90.0, p1_pct if p1_pct > 1 else p1_pct * 100),
            "trigger_pips": _num(val("p1_trigger")),
            "trigger_r": p1_r,          # 1R = lo que arriesga esa posición
            "on": _on(val("p1_on", True)),
        })

    # de dónde salió cada cosa: sin esto no se puede auditar lo que Hydra hará
    pol["source"] = {k: found[k].get("name") for k in found}
    used = {found[k].get("name") for k in found}
    pol["unmapped"] = sorted(
        p.get("name") for p in _flat(parsed)
        if p.get("name") not in used and any(h in _norm(p.get("name")) for h in _MGMT_HINTS)
    )
    pol["usable"] = bool(
        pol["breakeven"]["on"] and pol["breakeven"]["trigger_pips"]
        or pol["trailing"]["on"] and (pol["trailing"]["distance_pips"]
                                      or pol["trailing"]["keep_pct"])
        or [p for p in pol["partials"] if p.get("on")])
    return pol
