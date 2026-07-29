"""Reviewer — auto-critica diaria del desempeno del sistema."""
from __future__ import annotations

import json

from .. import llm

SYSTEM = """Eres el AGENTE REVISOR de un sistema de trading multi-agente.
Una vez al dia haces la auto-critica honesta del sistema completo.

Escribe una revision en markdown (breve, concreta, en espanol) con:
1. Resumen del dia: operaciones propuestas, vetadas, ejecutadas; PnL realizado.
2. Que hizo bien el sistema (con evidencia del diario).
3. Que hizo mal o pudo hacer mejor (se especifico: que agente, que decision, por que).
4. Patrones detectados (horas, simbolos, tipos de setup con mejor/peor resultado).
4b. SEÑALES RECHAZADAS (trade_context): el bot vio mas oportunidades de las que
   opero. Mira las que se quedaron cerca (near_miss) y di si el filtro esta
   demasiado apretado o demasiado flojo, con numeros. Una señal rechazada con
   score alto repetidas veces es informacion, no ruido.
5. Desglose POR MERCADO (metales / petroleo / indices): ¿donde encontro el sistema
   oportunidades reales y donde perdio el tiempo o el dinero?
6. 1-3 recomendaciones accionables para el Arquitecto (cambios de playbook, no de limites duros).

Se brutalmente honesto. Un dia sin operaciones tambien se evalua (¿fue correcto no operar?
¿o el analista dejo pasar setups claros que el diario muestra?).
"""


async def daily_review(journal_entries: list[dict], daily_pnl: float,
                       positions: list[dict], playbook: str,
                       context_digest: dict | None = None) -> str:
    user = (
        f"## Playbook vigente\n{playbook}\n\n"
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
