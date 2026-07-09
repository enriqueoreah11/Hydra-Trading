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
5. 1-3 recomendaciones accionables para el Arquitecto (cambios de playbook, no de limites duros).

Se brutalmente honesto. Un dia sin operaciones tambien se evalua (¿fue correcto no operar?).
"""


async def daily_review(journal_entries: list[dict], daily_pnl: float,
                       positions: list[dict], playbook: str) -> str:
    user = (
        f"## Playbook vigente\n{playbook}\n\n"
        f"## Diario de hoy (todas las decisiones de los agentes)\n"
        f"{json.dumps(journal_entries, ensure_ascii=False)}\n\n"
        f"## PnL realizado hoy: {daily_pnl:.2f}\n"
        f"## Posiciones aun abiertas\n{json.dumps(positions, ensure_ascii=False)}\n\n"
        "Escribe la revision diaria."
    )
    result = await llm.ask(SYSTEM, user, max_tokens=4000)
    assert isinstance(result, str)
    return result
