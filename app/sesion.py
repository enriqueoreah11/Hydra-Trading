"""Sesiones de análisis: dos días por semana, y las operaciones puestas.

Analizar todo el rato tiene un coste que no se ve: cada ciclo es otra oportunidad
de encontrar una historia en el gráfico, y con seis símbolos cada quince minutos
son doscientas al día. Analizar dos veces por semana no es analizar menos, es
decidir con la cabeza fría y dejar el resto al mercado.

Pero eso obliga a cambiar CÓMO se entra. Si el domingo se manda una orden a
mercado, se entra al precio del domingo — que casi nunca es el de la zona que
justificaba la operación. Por eso una sesión deja órdenes PENDIENTES en las zonas,
con caducidad hasta la siguiente sesión.

La caducidad es la pieza que más se olvida y la que más cara sale. Una orden
puesta el domingo que sigue viva tres semanas después se ejecuta en un mercado que
ya no es el que la justificó, y esa entrada no la decidió nadie.
"""
from __future__ import annotations

import datetime as dt
import logging

log = logging.getLogger("sesion")

DIAS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
NOMBRES = {v: k for k, v in DIAS.items()}
ES = {"mon": "lunes", "tue": "martes", "wed": "miércoles", "thu": "jueves",
      "fri": "viernes", "sat": "sábado", "sun": "domingo"}


def dias_config(txt: str) -> list[int]:
    """De 'sun,wed' a [6, 2]. Lo que no se entienda se ignora y se dice."""
    out = []
    for x in str(txt or "").replace(";", ",").split(","):
        k = x.strip().lower()[:3]
        if k in DIAS and DIAS[k] not in out:
            out.append(DIAS[k])
    return sorted(out)


def toca_ahora(ahora: dt.datetime, dias: list[int], hora: int) -> bool:
    return bool(dias) and ahora.weekday() in dias and ahora.hour == int(hora)


def proxima(ahora: dt.datetime, dias: list[int], hora: int) -> dt.datetime | None:
    """Cuándo es la siguiente sesión. Es lo que fija la caducidad de las órdenes."""
    if not dias:
        return None
    for d in range(1, 15):
        cand = (ahora + dt.timedelta(days=d)).replace(
            hour=int(hora), minute=0, second=0, microsecond=0)
        if cand.weekday() in dias and cand > ahora:
            return cand
    return None


def caducidad(ahora: dt.datetime, dias: list[int], hora: int) -> float:
    """Epoch hasta el que vive una orden de esta sesión.

    Hasta la siguiente sesión, no más. Si no hay siguiente (configuración vacía),
    una semana: nunca 'para siempre', porque para siempre es como se cuelan
    entradas que nadie recuerda haber decidido.
    """
    p = proxima(ahora, dias, hora)
    return (p or (ahora + dt.timedelta(days=7))).timestamp()


def descripcion(dias: list[int], hora: int) -> str:
    if not dias:
        return "sin días configurados: no se analizará nunca"
    nombres = ", ".join(ES[NOMBRES[d]] for d in dias)
    return f"{nombres} a las {int(hora):02d}:00 UTC"
