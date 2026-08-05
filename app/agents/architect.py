"""Architect — evoluciona el playbook cada dia a partir de las revisiones.

Solo puede editar el playbook (estrategia). Los limites duros de riesgo viven en
variables de entorno y NO pasan por este agente.
"""
from __future__ import annotations

import json

from .. import llm

PLAYBOOK_SCHEMA = {
    "type": "object",
    "properties": {
        "changes_summary": {"type": "string"},
        "new_playbook_markdown": {"type": "string"},
        "no_change": {"type": "boolean"},
    },
    "required": ["changes_summary", "new_playbook_markdown", "no_change"],
    "additionalProperties": False,
}

SYSTEM = """Eres el AGENTE ARQUITECTO de un sistema de trading multi-agente.
Una vez al dia evolucionas el PLAYBOOK (el documento de estrategia que leen el Analista,
el Gestor de Riesgo y el Nocturno) usando las revisiones diarias como evidencia.

Reglas:
- Cambios INCREMENTALES y justificados por evidencia de las revisiones. Nada de reescrituras
  radicales por un solo dia malo o bueno.
- NO puedes tocar limites de riesgo (% por operacion, perdida diaria, nro de posiciones):
  eso vive fuera de tu alcance. Si crees que deben cambiar, anotalo en "Notas del arquitecto"
  como recomendacion para el humano.
- Manten el playbook por debajo de ~600 lineas, claro y accionable.
- Conserva la estructura POR MERCADO del playbook (metales / petroleo / indices): si la
  evidencia muestra que un setup funciona en oro pero no en Nasdaq, ajusta esa seccion,
  no la regla global.
- Si no hay evidencia suficiente para cambiar nada, devuelve no_change=true y el playbook igual.
"""


async def evolve(playbook: str, recent_reviews: list[dict], stats: dict,
                 aprendido: str = "") -> dict:
    # Las revisiones diarias son relato: lo que un modelo entendio de una jornada.
    # Esto son cuentas sobre el historial real, con su muestra. Va primero a
    # proposito — cuando el relato y los numeros no coinciden, mandan los numeros.
    bloque = ""
    if aprendido:
        bloque = (
            f"## Evidencia medida sobre el historial real\n{aprendido}\n\n"
            "Cada linea trae su numero de operaciones y la probabilidad de que sea\n"
            "casualidad. Cambia el playbook por lo que digan estas cuentas, no por lo\n"
            "que sugiera el relato de un dia suelto. Una muestra corta NO justifica una\n"
            "regla nueva: si la evidencia es preliminar, dilo en el resumen en vez de\n"
            "escribir una norma que luego nadie sabra por que esta ahi.\n\n")
    user = (
        f"## Playbook actual\n{playbook}\n\n"
        f"{bloque}"
        f"## Revisiones diarias recientes (mas nueva primero)\n"
        f"{json.dumps(recent_reviews, ensure_ascii=False)}\n\n"
        f"## Estadisticas\n{json.dumps(stats, ensure_ascii=False)}\n\n"
        "Propon la nueva version del playbook (o no_change=true)."
    )
    result = await llm.ask(SYSTEM, user, schema=PLAYBOOK_SCHEMA, max_tokens=16000,
                           role="architect")
    assert isinstance(result, dict)
    return result
