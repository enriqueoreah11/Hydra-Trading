"""Analyst — lee el mercado y propone (o no) una operacion."""
from __future__ import annotations

import json

from .. import llm

PROPOSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["propose", "no_trade"]},
        "direction": {"type": "string", "enum": ["buy", "sell", "none"]},
        "stop_loss": {"type": "number"},
        "take_profit": {"type": "number"},
        "confidence": {"type": "integer"},
        "thesis": {"type": "string"},
        "invalidation": {"type": "string"},
    },
    "required": ["action", "direction", "stop_loss", "take_profit",
                 "confidence", "thesis", "invalidation"],
    "additionalProperties": False,
}

SYSTEM = """Eres el AGENTE ANALISTA de un sistema de trading algoritmico multi-agente.
Tu unico trabajo: leer los datos de mercado y decidir si existe un setup valido segun el playbook.
No colocas ordenes; solo propones. Un gestor de riesgo independiente puede vetar tu propuesta.

Reglas:
- Sigue el playbook al pie de la letra. Si el setup no cumple, responde action="no_trade".
- "no_trade" es una respuesta perfectamente buena; la mayoria de los ciclos no hay setup.
- stop_loss y take_profit son PRECIOS absolutos coherentes con la direccion.
- confidence es 0-100: tu conviccion real, no optimismo.
- thesis: 2-4 frases concretas. invalidation: que tendria que pasar para cerrar la idea.
- Si action="no_trade", pon direction="none", stop_loss=0, take_profit=0, confidence=0.
"""


async def analyze(symbol: str, timeframe: str, market: dict, playbook: str,
                  open_positions: list[dict]) -> dict:
    user = (
        f"## Playbook vigente\n{playbook}\n\n"
        f"## Simbolo: {symbol}  Timeframe: {timeframe}\n"
        f"## Snapshot de mercado (indicadores + ultimas 40 velas OHLC)\n"
        f"{json.dumps(market, ensure_ascii=False)}\n\n"
        f"## Posiciones abiertas actuales\n{json.dumps(open_positions, ensure_ascii=False)}\n\n"
        "Evalua si hay un setup valido AHORA y responde con el JSON del esquema."
    )
    result = await llm.ask(SYSTEM, user, schema=PROPOSAL_SCHEMA)
    assert isinstance(result, dict)
    result["symbol"] = symbol
    result["last_close"] = market.get("last_close")
    return result
