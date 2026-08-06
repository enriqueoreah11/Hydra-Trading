"""Encuentra él mismo dónde hay ventaja, en vez de que se la enseñes.

El playbook escrito a mano tiene un problema que no se ve: es una creencia. Puede
estar bien, puede estar obsoleto, y no hay forma de distinguirlo mirándolo. Lo que
hace este módulo es sustituir la creencia por una medición: recorre TU histórico,
prueba combinaciones de las estrategias deterministas, y se queda solo con las que
sobreviven a las tres cosas que matan a casi todas.

**1. Fuera de muestra.** Buscar sobre todo el histórico SIEMPRE encuentra una
combinación preciosa. Se busca en la parte antigua y se puntúa en la reciente, que
el buscador no vio. Lo que decide es el tramo que no se optimizó.

**2. El coste.** Un backtest sin coste está mintiendo, y miente hacia arriba. Cada
operación paga spread y comisión, y en operaciones con stop ajustado eso se come
una parte enorme de la ventaja. Aquí se resta un coste estimado en R a CADA
operación, y va escrito en el resultado para que se vea con qué supuesto se hizo.

**3. Cuántas veces se intentó.** Probar 200 combinaciones y quedarse con la mejor
no es encontrar una ventaja: con 200 intentos, la mejor sale bien por casualidad
aunque no haya nada. Por eso el número de combinaciones probadas viaja siempre con
el resultado, y el filtro de fuera de muestra es el que manda — ese tramo se mira
una sola vez por combinación.

Lo que sale de aquí NO es "esto va a funcionar". Es "esto es lo que se sostuvo en
lo que ya pasó". Y cuando no se sostiene nada, la respuesta correcta es decir que
en ese instrumento no hay nada que operar — no quedarse callado, que se lee igual
que si nadie hubiera mirado.
"""
from __future__ import annotations

import logging

from . import optimize, strategies

log = logging.getLogger("descubridor")

# Mínimos para llamar ventaja a algo. Son deliberadamente incómodos: el coste de
# quedarse corto es no operar; el de pasarse es operar una casualidad con dinero.
MIN_OPS_OOS = 15          # menos de esto fuera de muestra no mide nada
MIN_EXPECTANCY_R = 0.10   # por debajo, cualquier cambio de spread se la come
CONSISTENCIA_MIN = 0.5    # fuera de muestra >= mitad de lo que lució dentro
MAX_DD_RATIO = 2.0        # racha mala mayor que 2x el total ganado = no operable

# Spread + comisión estimados, en múltiplos de R. Con stops de 1.5xATR en oro
# ronda esto; en índices con stop corto es peor. Es un supuesto, no una medida:
# por eso se declara en cada resultado.
COSTE_R = 0.05


def evaluar(ins: dict, oos: dict, coste_r: float = COSTE_R) -> dict:
    """Aplica el coste y decide si esa combinación es una ventaja o una casualidad."""
    n_oos = (oos or {}).get("trades") or 0
    e_oos = (oos or {}).get("expectancy_r")
    e_ins = (ins or {}).get("expectancy_r")
    out = {
        "ops_oos": n_oos, "ops_is": (ins or {}).get("trades") or 0,
        "coste_r": coste_r,
        "esperanza_oos": None if e_oos is None else round(e_oos - coste_r, 3),
        "esperanza_is": None if e_ins is None else round(e_ins - coste_r, 3),
        "win_pct_oos": (oos or {}).get("win_pct"),
        "dd_oos": (oos or {}).get("max_dd_r"),
        "vale": False, "motivo": "",
    }
    neta = out["esperanza_oos"]
    if n_oos < MIN_OPS_OOS:
        out["motivo"] = (f"solo {n_oos} operaciones fuera de muestra: hacen falta "
                         f"{MIN_OPS_OOS} para que signifique algo")
        return out
    if neta is None or neta < MIN_EXPECTANCY_R:
        out["motivo"] = (f"esperanza neta {neta}R: por debajo de {MIN_EXPECTANCY_R}R "
                         "el spread se la come")
        return out
    # Ajustada al ruido: dentro luce y fuera se desploma.
    if out["esperanza_is"] is not None and out["esperanza_is"] > 0:
        ratio = neta / out["esperanza_is"]
        if ratio < CONSISTENCIA_MIN:
            out["motivo"] = (f"dentro de muestra daba {out['esperanza_is']}R y fuera "
                             f"{neta}R: está ajustada al ruido, no al mercado")
            return out
    total = round(neta * n_oos, 2)
    dd = abs(out["dd_oos"] or 0)
    if total > 0 and dd > total * MAX_DD_RATIO:
        out["motivo"] = (f"gana {total}R pero por el camino llega a perder {dd}R: "
                         "no es operable aunque el saldo final salga")
        return out
    out["vale"] = True
    out["total_r_oos"] = total
    out["motivo"] = f"{n_oos} operaciones fuera de muestra, {neta}R por operación"
    return out


def descubrir(candles, symbol: str, cuales: list[str] | None = None,
              steps: int = 3, horizon: int = 60, split: float = 0.7,
              coste_r: float = COSTE_R) -> dict:
    """Prueba las estrategias sobre este histórico y devuelve lo que se sostiene."""
    nombres = cuales or list(strategies.STRATEGIES.keys())
    hallazgos, descartes, combos = [], [], 0

    # "No se sostuvo nada" y "no había con qué medir" acaban los dos en una lista
    # vacía, y piden cosas opuestas: lo primero es no operar ese instrumento; lo
    # segundo es bajarse más histórico. Se separan aquí, antes de medir.
    minimo = optimize.WARMUP + horizon + 5
    if len(candles) < minimo:
        return {"symbol": (symbol or "").upper(), "hallazgos": [],
                "descartes": [{"estrategia": n,
                               "motivo": f"hacen falta al menos {minimo} velas y hay "
                                         f"{len(candles)}: no se ha medido nada"}
                              for n in nombres],
                "combinaciones_probadas": 0, "velas": len(candles),
                "coste_r": coste_r, "sin_datos": True,
                "aviso": (f"sin histórico suficiente ({len(candles)} de {minimo} velas). "
                          "Esto no es «aquí no hay ventaja», es «aquí no se ha mirado»")}

    for nombre in nombres:
        try:
            res = optimize.optimize(candles, nombre, steps=steps, horizon=horizon,
                                    split=split, top=3, min_trades=10)
        except Exception as exc:  # noqa: BLE001 - una estrategia rota no para el resto
            log.info("%s/%s: no se pudo medir (%s)", symbol, nombre, str(exc)[:80])
            continue
        if not res.get("ok"):
            descartes.append({"estrategia": nombre, "motivo": res.get("error", "sin datos")})
            continue
        combos += res.get("combos") or 0
        mejor = None
        for fila in res.get("top") or []:
            v = evaluar(fila.get("in_sample") or {}, fila.get("out_of_sample") or {},
                        coste_r)
            cand = {"estrategia": nombre, "params": fila.get("params") or {}, **v}
            if v["vale"] and (mejor is None or
                              (v["esperanza_oos"] or 0) > (mejor["esperanza_oos"] or 0)):
                mejor = cand
            elif mejor is None:
                # se guarda el mejor descarte para poder decir POR QUE no pasó
                if not descartes or descartes[-1].get("estrategia") != nombre:
                    descartes.append({"estrategia": nombre, "motivo": v["motivo"],
                                      "params": cand["params"]})
        if mejor:
            hallazgos.append(mejor)
    hallazgos.sort(key=lambda h: -(h["esperanza_oos"] or 0))
    return {"symbol": (symbol or "").upper(), "hallazgos": hallazgos,
            "descartes": descartes, "combinaciones_probadas": combos,
            "velas": len(candles), "coste_r": coste_r,
            "aviso": ("medido fuera de muestra y con coste; es lo que se sostuvo en "
                      f"lo que ya pasó, no una promesa. Se probaron {combos} "
                      "combinaciones: cuantas más se prueban, más fácil es que la "
                      "mejor lo sea por casualidad")}


# ------------------------------------------------------ playbook automático

def _regla(h: dict) -> str:
    p = ", ".join(f"{k}={v}" for k, v in sorted((h.get("params") or {}).items()))
    return (f"- **{h['estrategia']}** ({p}) — {h['esperanza_oos']}R por operación "
            f"en {h['ops_oos']} operaciones fuera de muestra, "
            f"{h['win_pct_oos']}% de acierto, peor racha {h['dd_oos']}R.")


def a_playbook(por_symbol: dict[str, dict], coste_r: float = COSTE_R) -> str:
    """El playbook escrito por la medición, no por nosotros.

    Incluye a propósito los símbolos donde NO se encontró nada. Un playbook que
    solo lista lo que funciona deja al analista sin saber si el resto está sin
    mirar o mirado y descartado, y esas dos cosas piden lo contrario.
    """
    hoy = []
    hoy.append("# Playbook automático")
    hoy.append("")
    hoy.append("Este playbook no lo ha escrito nadie: sale de medir las estrategias "
               "sobre el histórico real de cada instrumento, puntuando SIEMPRE en el "
               "tramo que el buscador no vio y restando un coste estimado de "
               f"{coste_r}R por operación.")
    hoy.append("")
    hoy.append("## Cómo se usa")
    hoy.append("")
    hoy.append("**Solo se propone una entrada si una de las condiciones listadas "
               "abajo se está dando AHORA en ese instrumento.** Si ninguna se cumple, "
               "la respuesta es `no_trade`. No inventes setups que no estén aquí: lo "
               "que no está listado es que se midió y no se sostuvo, o que todavía no "
               "hay histórico para medirlo — en los dos casos, no se opera.")
    hoy.append("")
    hoy.append("El contexto (macro, sesión, noticias, lo aprendido de tus resultados) "
               "sirve para NO entrar o para entrar con menos confianza. Nunca para "
               "entrar donde no hay condición.")
    hoy.append("")
    con, sin = [], []
    for sym in sorted(por_symbol):
        d = por_symbol[sym] or {}
        (con if d.get("hallazgos") else sin).append((sym, d))
    for sym, d in con:
        hoy.append(f"## {sym}")
        hoy.append("")
        hoy += [_regla(h) for h in d["hallazgos"]]
        hoy.append("")
        hoy.append(f"<sub>{d.get('velas', 0)} velas, "
                   f"{d.get('combinaciones_probadas', 0)} combinaciones probadas.</sub>")
        hoy.append("")
    if sin:
        hoy.append("## Instrumentos sin ventaja medible")
        hoy.append("")
        hoy.append("Aquí se midió y no se sostuvo nada. **No se opera**, y eso es una "
                   "decisión, no un olvido:")
        hoy.append("")
        for sym, d in sin:
            motivos = "; ".join(x.get("motivo", "") for x in (d.get("descartes") or [])[:2])
            hoy.append(f"- **{sym}** — {motivos or 'ninguna combinación pasó los mínimos'}")
        hoy.append("")
    hoy.append("## Lo que este playbook no sabe")
    hoy.append("")
    hoy.append("- Que lo que se sostuvo en el pasado siga sosteniéndose. Se vuelve a "
               "medir cada día; si deja de cumplirse, desaparece de aquí solo.")
    hoy.append(f"- El coste real de tu bróker. Se asumió {coste_r}R por operación: si "
               "tu spread es peor, estas cifras están infladas.")
    hoy.append("- Nada de lo que no esté en las velas: noticias, subastas, cierres de "
               "mes. De eso avisan el Sentinel y el contexto macro.")
    return "\n".join(hoy)


def texto(d: dict) -> str:
    """Los setups medidos de un símbolo, para el prompt del analista."""
    h = (d or {}).get("hallazgos") or []
    if not h:
        return ""
    return (f"Setups con ventaja medida en {d.get('symbol', '')} "
            f"(fuera de muestra, coste {d.get('coste_r', COSTE_R)}R incluido):\n"
            + "\n".join(_regla(x) for x in h))
