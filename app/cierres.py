"""Cada operación cerrada se revisa y se clasifica sola.

Es el tercer punto de tu maestro y el que faltaba entero: el sistema revisaba el
día en bloque, pero ninguna operación concreta se miraba una por una. Y una
revisión en bloque no distingue lo único que importa — si la pérdida era el coste
normal de tener ventaja o si hubo un fallo concreto que se repite.

Cómo se clasifica, y en qué orden:

1. **Primero lo que se puede saber de los números.** Si la operación tocó el stop
   habiendo estado a más de 1R a favor, eso es un stop mal colocado y se sabe con
   aritmética. Si duró tres velas, entró tarde. Etcétera. Esta parte no opina.
2. **Solo lo que queda sin explicar va al modelo.** Y va con la clasificación que
   ya salió de los números, para que no la contradiga sin motivo.

Lo importante es el sesgo del punto 1: **la categoría por defecto es
`perdida_esperada`**. Una estrategia con ventaja pierde el 40% de las veces sin que
nada esté roto, y un sistema que le busca causa a cada pérdida acaba cambiando
reglas por ruido — que es exactamente cómo se destruye una estrategia que
funcionaba.
"""
from __future__ import annotations

import logging

log = logging.getLogger("cierres")

# Cuánto tiene que haber ido a favor antes de morir para que el stop sea sospechoso.
R_DEVUELTA = 1.0
# Menos velas que esto es una operación que no llegó a desarrollarse.
VELAS_CORTAS = 3


def clasificar(trade: dict, contexto: dict | None = None) -> dict:
    """Clasifica un cierre con lo que se puede deducir. Sin opinar.

    `trade`: {pnl, r, side, entry, sl, tp, max_favor_r, velas, symbol, ts, strategy}
    Los campos que falten se ignoran: se clasifica con lo que haya y se dice cuánta
    confianza da eso, en vez de rellenar huecos con supuestos.
    """
    c = contexto or {}
    r = trade.get("r")
    pnl = trade.get("pnl")
    gano = (r is not None and r > 0) or (r is None and (pnl or 0) > 0)

    faltan = [k for k in ("r", "max_favor_r", "velas") if trade.get(k) is None]
    base = {"symbol": trade.get("symbol"), "ts": trade.get("ts"),
            "strategy": trade.get("strategy"), "gano": bool(gano),
            "r": r, "faltan_datos": faltan}

    if gano:
        return {**base, "categoria": None, "seguro": True,
                "nota": "ganadora: no hay nada que diagnosticar"}

    # --- lo que se sabe por aritmética ---
    favor = trade.get("max_favor_r")
    velas = trade.get("velas")

    if favor is not None and favor >= R_DEVUELTA:
        return {**base, "categoria": "sl_muy_ajustado", "seguro": True,
                "nota": (f"llegó a ir {favor:.2f}R a favor y acabó en el stop: el "
                         "stop estaba donde el ruido lo alcanza")}
    if velas is not None and velas <= VELAS_CORTAS and (favor or 0) < 0.3:
        return {**base, "categoria": "entrada_tardia", "seguro": True,
                "nota": (f"murió en {velas} velas sin ir nunca a favor: se entró con "
                         "el movimiento ya hecho o en el sitio equivocado")}
    if c.get("noticia_alto_impacto"):
        return {**base, "categoria": "noticia_no_filtrada", "seguro": True,
                "nota": "había un evento de alto impacto sin filtrar"}
    if c.get("sesion") in ("Asia/madrugada",) and (favor or 0) < 0.3:
        return {**base, "categoria": "sesion_baja_liquidez", "seguro": False,
                "nota": "operó en sesión pobre y no llegó a ir a favor"}
    if c.get("spread_r") is not None and c["spread_r"] > 0.15:
        return {**base, "categoria": "ejecucion", "seguro": True,
                "nota": f"el spread se llevó {c['spread_r']:.2f}R de la operación"}

    # --- por defecto, y a propósito ---
    # Una estrategia con ventaja pierde el 40% de las veces sin que nada este roto.
    # Buscarle causa a cada perdida acaba cambiando reglas por ruido, y asi es como
    # se rompe una estrategia que funcionaba.
    return {**base, "categoria": "perdida_esperada", "seguro": True,
            "nota": ("pérdida dentro de lo normal: no hay nada en los números que "
                     "señale un fallo concreto")}


def resumen(clasificados: list[dict]) -> dict:
    """Qué categorías se repiten. Lo que se repite es lo único accionable."""
    cuenta: dict[str, int] = {}
    for x in clasificados:
        cat = x.get("categoria")
        if cat:
            cuenta[cat] = cuenta.get(cat, 0) + 1
    n = len(clasificados)
    perdidas = sum(1 for x in clasificados if not x.get("gano"))
    esperadas = cuenta.get("perdida_esperada", 0)
    orden = sorted(cuenta.items(), key=lambda kv: -kv[1])
    return {"n": n, "perdidas": perdidas, "categorias": dict(orden),
            "pct_ruido": round(esperadas / perdidas * 100, 1) if perdidas else None,
            "lectura": _lectura(perdidas, esperadas, orden)}


def _lectura(perdidas: int, esperadas: int, orden: list) -> str:
    if not perdidas:
        return "sin pérdidas que diagnosticar"
    if esperadas == perdidas:
        return ("todas las pérdidas son el coste normal de tener ventaja: no hay "
                "nada que arreglar, y tocar la estrategia aquí sería empeorarla")
    reales = [(k, v) for k, v in orden if k != "perdida_esperada"]
    if not reales:
        return "sin patrón claro"
    k, v = reales[0]
    if v < 3:
        return (f"«{k}» aparece {v} vez/veces: todavía no es un patrón, es un caso. "
                "Hace falta que se repita para que signifique algo")
    return (f"«{k}» aparece {v} veces de {perdidas} pérdidas: eso ya es un patrón y "
            "merece mirarse")
