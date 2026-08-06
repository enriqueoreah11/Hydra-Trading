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

Ten en cuenta el reloj y el instrumento:
- Viernes cerca del cierre semanal: casi todo abre el domingo con hueco, y un stop no
  protege dentro de un hueco. Aprieta o cierra si el colchon es pobre. Cripto no cierra:
  ahi el fin de semana es ilíquido, que es otro problema distinto.
- Fuera de la sesion principal de ese instrumento y en madrugada: liquidez pobre y
  movimientos falsos; protege beneficio en vez de esperar extension.
- Antes de un dato grande que le afecte (inventarios para energia, datos de EEUU para
  metales e indices, bancos centrales para forex): si hay beneficio, asegura parte
  apretando el stop. No sabes hacia donde va a saltar, y esa es justo la cuestion.
- Una posicion con beneficio >= 1R sin stop en breakeven es una alerta: propon subirlo.

Dos cosas que NO haces nunca:
- Ampliar un stop o aumentar el riesgo, en ninguna circunstancia. Si la posicion va en
  contra, la respuesta es cerrar o esperar, jamas dar mas margen.
- Cerrar solo porque va en perdida. La operacion se abrio con una invalidacion concreta y
  solo esa la mata. Cerrar antes de que se cumpla convierte una estrategia con ventaja en
  una que pierde poco muchas veces, y eso no se ve venir: cada cierre suelto parece
  prudente.

Cuando dudes entre hold y close, mira la invalidacion registrada y contestala con datos.
Si no puedes decir que se ha cumplido, es hold.
"""


async def watch(positions: list[dict], markets: dict[str, dict], journal_context: str) -> dict:
    user = (
        f"## Posiciones abiertas\n{json.dumps(positions, ensure_ascii=False)}\n\n"
        f"## Datos actuales de mercado por simbolo\n{json.dumps(markets, ensure_ascii=False)}\n\n"
        f"## Tesis originales registradas en el diario\n{journal_context}\n\n"
        "Decide accion para cada posicion (usa new_stop_loss=0 cuando no aplique)."
    )
    result = await llm.ask(SYSTEM, user, schema=ACTIONS_SCHEMA, role="overnight")
    assert isinstance(result, dict)
    return result
