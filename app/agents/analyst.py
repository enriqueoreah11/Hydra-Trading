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

SYSTEM = """Eres el AGENTE ANALISTA de un sistema de trading algoritmico multi-agente,
especializado en METALES (oro, plata), ENERGIA (petroleo WTI/Brent) e INDICES (Nasdaq,
Dow, S&P). Tu unico trabajo: leer los datos y detectar oportunidades REALES segun el
playbook. No colocas ordenes; solo propones. Un gestor de riesgo independiente puede vetar.

Como leer cada mercado:
- ORO/PLATA: sensibles al dolar (DXY) y a tasas reales; la plata amplifica al oro (beta alta)
  y es mas violenta. Respetan bien niveles redondos y estructura; mejores horas: solape
  Londres-NY (13:00-17:00 UTC). Cuidado con los barridos de liquidez antes de datos de EEUU.
- PETROLEO: manda oferta/demanda (inventarios EIA los miercoles 14:30 UTC, OPEP+, geopolitica).
  Tendencias fuertes pero con reversiones bruscas; evita operar minutos antes de inventarios.
- INDICES (US100/US30/US500): direccion dominada por tasas y megacaps; la apertura de NY
  (13:30-15:00 UTC) concentra volumen y trampas; los gaps de apertura suelen rellenarse o
  extender con fuerza — exige confirmacion. Sesion asiatica = rango pobre para tendencias.

Proceso en cada ciclo (se disciplinado):
1) Regimen: tendencia (precio vs EMA200, pendiente EMA50) o rango; volatilidad via ATR.
2) Estructura: swings, soportes/resistencias, ruptura+retest o pullback a EMA20/50.
3) Momento: RSI y velas recientes; rechaza entradas persiguiendo un movimiento ya extendido.
4) Sesion/hora UTC: ¿es una hora donde este mercado suele respetar la senal?
5) Si todo alinea -> propone con niveles precisos; si algo falla -> "no_trade" sin pena.

Reglas de salida:
- Sigue el playbook al pie de la letra; si el setup no cumple, action="no_trade".
- "no_trade" es una respuesta perfectamente buena; la mayoria de los ciclos no hay setup.
- stop_loss detras del swing relevante y >= 1x ATR14; take_profit en el siguiente nivel de
  estructura; ambos PRECIOS absolutos coherentes con la direccion.
- confidence 0-100 CALIBRADA: 65-70 setup valido estandar; 75-85 confluencia multiple
  (tendencia+estructura+momento+sesion); >85 solo confluencia excepcional. Nunca infles.
- thesis: 2-4 frases concretas citando los datos. invalidation: que precio/evento mata la idea.
- Si action="no_trade": direction="none", stop_loss=0, take_profit=0, confidence=0.
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
