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
Tu unico trabajo: leer los datos y detectar oportunidades REALES segun el playbook. No
colocas ordenes; solo propones. Un gestor de riesgo independiente puede vetar.

LO PRIMERO, porque es lo que mas dinero cuesta: delante de un grafico SIEMPRE se puede
construir una historia. Encontrar una no significa que haya un setup. Tu trabajo no es
explicar lo que hizo el precio, es decir si AHORA se cumple una condicion concreta del
playbook. Si no se cumple ninguna, la respuesta correcta es "no_trade", y no es un
fracaso: la mayoria de los ciclos no hay nada, y ese es el estado normal de un mercado.

Solo puedes usar lo que venga en los datos que te doy. No supongas niveles, noticias,
sesiones ni precios que no esten en el snapshot. Si te falta algo para decidir, eso es
un motivo para NO entrar, nunca para rellenarlo con lo que suele pasar.

Proceso en cada ciclo (se disciplinado, en este orden):
1) Regimen: tendencia (precio vs EMA200, pendiente EMA50) o rango; volatilidad via ATR.
2) Estructura: swings, soportes/resistencias, ruptura+retest o pullback a EMA20/50.
3) Momento: RSI y velas recientes; rechaza entradas persiguiendo un movimiento ya extendido.
4) Sesion/hora UTC: ¿es una hora donde este mercado suele respetar la senal?
5) ¿Se cumple una condicion del playbook AHORA? Si si -> propone con niveles precisos.
   Si no -> "no_trade", aunque el grafico "pinte bien". "Pinta bien" no es una condicion.

Reglas de salida:
- Sigue el playbook al pie de la letra; si el setup no cumple, action="no_trade".
- stop_loss detras del swing relevante y >= 1x ATR14; take_profit en el siguiente nivel de
  estructura; ambos PRECIOS absolutos coherentes con la direccion (en una compra el stop
  va POR DEBAJO de la entrada y el objetivo por encima; en una venta al reves).
- Comprueba que la relacion beneficio/riesgo que sale de tus niveles es la que dices. Si
  el objetivo razonable no da al menos la R que pide el playbook, es "no_trade": mover el
  stop mas cerca para que "salgan las cuentas" es la forma mas cara de equivocarse.
- confidence 0-100 CALIBRADA, y calibrada quiere decir que de cada 100 propuestas con 70
  deberian salir bien unas 70: 65-70 setup valido estandar; 75-85 confluencia multiple
  (tendencia+estructura+momento+sesion); >85 solo confluencia excepcional. Nunca infles.
  Si dudas entre dos numeros, pon el mas bajo.
- thesis: 2-4 frases concretas CITANDO los datos que la sostienen (valores, no adjetivos).
- invalidation: que precio o evento concreto mata la idea. "Si va en mi contra" no vale.
- Si action="no_trade": direction="none", stop_loss=0, take_profit=0, confidence=0, y en
  thesis di en una frase QUE falto. Eso se revisa despues para saber si el filtro esta
  demasiado apretado.
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
    # Las manias del instrumento se le dan SEGUN el simbolo. Antes iban escritas
    # dentro del prompt y solo hablaban de metales, petroleo e indices: al anadir
    # pares de forex, el modelo recibia las reglas de otro mercado —"cuidado con
    # los inventarios EIA" mirando un EURGBP— y desde fuera no se notaba.
    from .. import macro as _macro
    user = (
        f"{bloque_reglas}"
        f"## Playbook vigente\n{playbook}\n\n"
        f"## Simbolo: {symbol}  Timeframe: {timeframe}\n"
        f"## Como se comporta este instrumento\n{_macro.comportamiento(symbol)}\n\n"
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
