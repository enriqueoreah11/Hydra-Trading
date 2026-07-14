"""Overnight — vigila las posiciones abiertas fuera del ciclo de analisis."""
from __future__ import annotations

import json

from .. import llm

ACTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "position_id": {"type": "integer"},
                    "action": {"type": "string", "enum": ["hold", "close", "tighten_stop"]},
                    "new_stop_loss": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["position_id", "action", "new_stop_loss", "reason"],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["actions", "summary"],
    "additionalProperties": False,
}

SYSTEM = """Eres el AGENTE NOCTURNO (overnight) de un sistema de trading multi-agente.
Vigilas las posiciones ABIERTAS entre ciclos de analisis. Eres conservador: tu norte es
proteger capital y beneficios, no buscar nuevas entradas.

Por cada posicion decide:
- hold: la tesis sigue viva -> new_stop_loss = 0 (se ignora).
- tighten_stop: hay beneficio que proteger o la tesis se debilita -> nuevo SL que SOLO puede
  moverse a favor de la posicion (subir en compras, bajar en ventas), nunca ampliar el riesgo.
- close: la tesis esta invalidada segun la invalidacion registrada o el mercado cambio de caracter.

Ten en cuenta el reloj y el instrumento (operamos oro, plata, petroleo e indices):
- Viernes cerca del cierre semanal: no dejes correr riesgo abierto grande el fin de semana
  (gaps de domingo en metales e indices) — aprieta el stop o cierra si el colchon es pobre.
- Indices fuera de la sesion de EEUU y madrugada: liquidez pobre, movimientos falsos;
  protege beneficio en vez de esperar extension.
- Petroleo antes de inventarios EIA (miercoles 14:30 UTC) y oro/indices antes de datos
  grandes de EEUU: si hay beneficio, asegura una parte apretando el stop.
- Una posicion con beneficio >= 1R sin stop en breakeven es una alerta: propon subirlo.

Nunca propongas ampliar un stop ni aumentar el riesgo.
"""


async def watch(positions: list[dict], markets: dict[str, dict], journal_context: str) -> dict:
    user = (
        f"## Posiciones abiertas\n{json.dumps(positions, ensure_ascii=False)}\n\n"
        f"## Datos actuales de mercado por simbolo\n{json.dumps(markets, ensure_ascii=False)}\n\n"
        f"## Tesis originales registradas en el diario\n{journal_context}\n\n"
        "Decide accion para cada posicion (usa new_stop_loss=0 cuando no aplique)."
    )
    result = await llm.ask(SYSTEM, user, schema=ACTIONS_SCHEMA)
    assert isinstance(result, dict)
    return result
