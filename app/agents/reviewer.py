"""Reviewer — auto-critica diaria del desempeno del sistema."""
from __future__ import annotations

import json

from .. import llm

SYSTEM = """Eres el AGENTE REVISOR de un sistema de trading multi-agente.
Una vez al dia haces la auto-critica honesta del sistema completo.

La trampa de este puesto es contar la historia del dia. Un dia son cuatro o cinco
decisiones: no da para detectar ningun patron, y lo que sale de intentarlo son
coincidencias contadas con seguridad. Cuando te den evidencia medida sobre todo el
historial, esa manda; el diario de hoy sirve para explicar decisiones concretas, no para
sacar leyes.

Escribe una revision en markdown (breve, concreta, en espanol) con:
1. Resumen del dia: operaciones propuestas, vetadas, ejecutadas; PnL realizado.
2. Que hizo bien el sistema, citando la entrada del diario que lo demuestra.
3. Que hizo mal o pudo hacer mejor: que agente, que decision concreta, y por que.
4. Patrones. Usa la evidencia medida si la tienes. Si solo tienes el dia de hoy, di
   explicitamente que no da para concluir en vez de concluir igualmente.
4b. SEÑALES RECHAZADAS (trade_context): el bot vio mas oportunidades de las que opero.
   Mira las que se quedaron cerca (near_miss) y di si el filtro esta demasiado apretado o
   demasiado flojo, CON NUMEROS. Una señal rechazada con score alto muchas veces es
   informacion; una vez es ruido.
5. Desglose por tipo de instrumento (metales, energia, indices, forex, cripto — solo los
   que se hayan operado): ¿donde encontro oportunidades reales y donde perdio el tiempo
   o el dinero?
6. 1-3 recomendaciones accionables para el Arquitecto (cambios de playbook, no de limites
   duros). Cada una con la evidencia que la motiva. Si no tienes evidencia suficiente para
   ninguna, di eso: "sin cambios, hace falta mas muestra" es una recomendacion valida y
   mejor que inventarse una.

Se brutalmente honesto, tambien contigo: si el sistema tuvo un buen dia por suerte,
dilo. Un dia sin operaciones tambien se evalua — ¿fue correcto no operar, o el analista
dejo pasar setups que el diario muestra? Las dos respuestas son utiles; la que no vale es
no mirarlo.
"""


async def daily_review(journal_entries: list[dict], daily_pnl: float,
                       positions: list[dict], playbook: str,
                       context_digest: dict | None = None,
                       aprendido: str = "") -> str:
    # Antes de esto, los "patrones" del punto 4 salian de mirar UN dia de diario, y
    # un dia no da para detectar ningun patron: lo que salia eran coincidencias
    # contadas con seguridad. Aqui van las cuentas sobre el historial completo.
    bloque = ""
    if aprendido:
        bloque = (f"## Evidencia medida sobre todo el historial\n{aprendido}\n\n"
                  "Usa ESTO para el punto 4 en vez de deducir patrones de un solo dia.\n"
                  "Cada linea trae su muestra: si es corta, dilo en vez de concluir.\n\n")
    user = (
        f"## Playbook vigente\n{playbook}\n\n"
        f"{bloque}"
        f"## Diario de hoy (todas las decisiones de los agentes)\n"
        f"{json.dumps(journal_entries, ensure_ascii=False)}\n\n"
        f"## PnL realizado hoy: {daily_pnl:.2f}\n"
        f"## Posiciones aun abiertas\n{json.dumps(positions, ensure_ascii=False)}\n\n"
    )
    if context_digest and context_digest.get("total"):
        user += ("## Contexto de decision del bot (trade_context)\n"
                 "Como se veia el mercado en el instante exacto de cada señal, "
                 "INCLUIDAS las que se rechazaron:\n"
                 f"{json.dumps(context_digest, ensure_ascii=False)}\n\n")
    user += "Escribe la revision diaria."

    result = await llm.ask(SYSTEM, user, max_tokens=4000, role="reviewer")
    assert isinstance(result, str)
    return result
