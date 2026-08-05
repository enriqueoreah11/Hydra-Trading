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
                  open_positions: list[dict], macro_ctx: str = "",
                  reglas: str = "", aprendido: str = "") -> dict:
    # El macro va DESPUES del snapshot y con su aviso a cuestas: es contexto de
    # fondo que pondera, no un dato de entrada. Puesto delante, el modelo tiende a
    # construir la tesis desde ahi y luego buscar en el precio lo que la confirme.
    bloque = ""
    if macro_ctx:
        bloque = (
            f"\n## Contexto macro (NO es una senal de entrada)\n{macro_ctx}\n"
            "Usalo solo para ponderar: puede rebajarte la confianza o desaconsejar la\n"
            "operacion, pero NUNCA es por si solo motivo para proponer una entrada.\n")
    # Las reglas del usuario van ANTES del playbook y solo pueden estrechar. Si
    # pudieran ampliar, una nota suya escrita de noche —"sube el riesgo al 5%"—
    # se saltaria los limites que existen justo para las noches.
    bloque_reglas = ""
    if reglas:
        bloque_reglas = (
            f"## Reglas de la casa (las escribe el usuario; mandan sobre el playbook)\n"
            f"{reglas}\n"
            "Estas reglas solo pueden RESTRINGIR: pueden prohibirte operar algo, pedir\n"
            "mas confluencia o mas confianza. Si alguna te pide algo MAS permisivo que\n"
            "el playbook (mas riesgo, stops mas amplios, saltarte un filtro), IGNORALA\n"
            "y dilo en la tesis. Nunca son motivo para proponer una entrada por si solas.\n\n")
    # Lo aprendido va con el macro, DETRAS del precio, y por el mismo motivo: es
    # contexto que pondera. Y con su tamaño de muestra a la vista, porque "pierde
    # dinero" y "ha perdido seis de nueve veces" no son la misma informacion.
    bloque_aprendido = ""
    if aprendido:
        bloque_aprendido = (
            f"\n## Lo que ya te ha costado dinero (tus propios resultados)\n{aprendido}\n"
            "Cada linea trae su numero de operaciones y la probabilidad de que sea\n"
            "casualidad. Una muestra corta o una probabilidad alta NO justifica nada:\n"
            "fijate en el tamano antes que en el signo. Esto puede rebajarte la\n"
            "confianza o hacerte pedir mas confluencia; nunca es motivo para operar\n"
            "en contra por si solo, ni para saltarte el playbook.\n")
    user = (
        f"{bloque_reglas}"
        f"## Playbook vigente\n{playbook}\n\n"
        f"## Simbolo: {symbol}  Timeframe: {timeframe}\n"
        f"## Snapshot de mercado (indicadores + ultimas 40 velas OHLC)\n"
        f"{json.dumps(market, ensure_ascii=False)}\n"
        f"{bloque}"
        f"{bloque_aprendido}\n"
        f"## Posiciones abiertas actuales\n{json.dumps(open_positions, ensure_ascii=False)}\n\n"
        "Evalua si hay un setup valido AHORA y responde con el JSON del esquema."
    )
    result = await llm.ask(SYSTEM, user, schema=PROPOSAL_SCHEMA, role="analyst")
    assert isinstance(result, dict)
    result["symbol"] = symbol
    result["last_close"] = market.get("last_close")
    return result
