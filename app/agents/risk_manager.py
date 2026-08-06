"""Risk Manager — calcula tamano de posicion (sizes) y tiene poder de veto (vetoes).

Dos capas:
1. Checks deterministas en codigo (limites duros de .env, no negociables).
2. Revision LLM: puede vetar por razones cualitativas, nunca ampliar el riesgo.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .. import llm
from ..broker import SymbolInfo
from ..config import settings

VETO_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["approve", "veto"]},
        "reasons": {"type": "string"},
    },
    "required": ["verdict", "reasons"],
    "additionalProperties": False,
}

SYSTEM = """Eres el AGENTE GESTOR DE RIESGO de un sistema de trading multi-agente. Los
limites duros (riesgo por operacion, perdida diaria maxima, exposicion) ya se verificaron
en codigo antes de llegar a ti. Tu trabajo es la ultima linea de defensa CUALITATIVA:
vetar propuestas que cumplen los numeros pero no se sostienen.

Tu sesgo tiene que ser al veto, y el motivo es que los dos errores no cuestan lo mismo:
vetar una buena cuesta una oportunidad, y hay otra en el siguiente ciclo. Dejar pasar una
mala cuesta dinero y, si el fallo es sistematico, lo cuesta muchas veces. Ante la duda,
veta.

El analista tiende a estar mas seguro de lo que deberia: ha construido una historia y te
la cuenta entera. Tu no evaluas la historia, evaluas si los DATOS la sostienen.

Veta si detectas:
- Tesis incoherente con los datos, o que cita cosas que no estan en el snapshot.
- Stop ilogico: del lado equivocado, o tan cercano que el ruido normal del instrumento
  (ATR14) lo barre sin que la idea llegue a estar equivocada.
- Que la relacion beneficio/riesgo real que sale de los niveles no es la que dice la tesis.
- Senales contradictorias entre indicadores presentadas como si alinearan.
- Operar contra una tendencia clara sin justificacion excepcional y explicita.
- Entrada persiguiendo un movimiento ya extendido (RSI extremo + lejos de la media).
- Apuesta duplicada: dos instrumentos hermanos en la misma direccion son UNA posicion con
  dos nombres. Oro y plata; los indices de EEUU entre si; pares de forex que comparten
  divisa (largo EURUSD y corto USDCHF es la misma apuesta contra el dolar, dos veces).
- Hora mala para ESE instrumento: minutos previos a un dato grande, apertura sin
  confirmacion, madrugada iliquida donde el spread se come la ventaja. Los horarios
  concretos dependen del instrumento; si no sabes cual aplica, eso ya es motivo de duda.
- Confianza alta sin confluencia que la respalde: un 85 con un solo argumento es un 65.

No puedes modificar la propuesta ni ampliar el riesgo: solo aprobar o vetar. Cuando vetes,
di exactamente QUE dato lo motiva — esas razones se revisan despues para saber si estas
vetando de mas, y "no me convence" no se puede revisar.
"""


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    volume_units: float = 0.0


def _round_step(value: float, step: float) -> float:
    return round(round(value / step) * step, 8) if step > 0 else value


def position_size(balance: float, entry: float, stop_loss: float,
                  info: SymbolInfo, risk_pct: float) -> float:
    """Units such that (entry - SL) * units == balance * risk%.

    Nota: asume que la divisa de la cuenta es la divisa cotizada del simbolo
    (p.ej. cuenta USD operando EURUSD o XAUUSD). Documentado en el README.
    """
    distance = abs(entry - stop_loss)
    if distance <= 0:
        return 0.0
    risk_amount = balance * risk_pct / 100
    units = risk_amount / distance
    units = _round_step(units, info.step_volume_units)
    if units < info.min_volume_units:
        return 0.0
    return min(units, info.max_volume_units)


async def review(proposal: dict, balance: float, initial_balance: float,
                 daily_realized_pnl: float, open_positions: list[dict],
                 info: SymbolInfo, halted: bool, playbook: str) -> RiskDecision:
    # ---------- capa 1: limites duros deterministas ----------
    if halted:
        return RiskDecision(False, "sistema en HALT (kill switch activado)")
    if len(open_positions) >= settings.max_open_positions:
        return RiskDecision(False, f"max posiciones abiertas ({settings.max_open_positions}) alcanzado")
    if any(p.get("symbol") == proposal["symbol"] for p in open_positions):
        return RiskDecision(False, f"ya hay posicion abierta en {proposal['symbol']}")
    if proposal.get("confidence", 0) < settings.min_confidence:
        return RiskDecision(False, f"confianza {proposal.get('confidence')} < minimo {settings.min_confidence}")
    if daily_realized_pnl <= -(initial_balance * settings.max_daily_loss_pct / 100):
        return RiskDecision(False, f"limite de perdida diaria alcanzado ({daily_realized_pnl:.2f})")
    if balance < initial_balance * settings.equity_floor_pct / 100:
        return RiskDecision(False, "balance por debajo del suelo de equity — sistema debe detenerse")

    entry = float(proposal["last_close"])
    sl = float(proposal["stop_loss"])
    tp = float(proposal["take_profit"])
    direction = proposal["direction"]
    if direction == "buy" and not (sl < entry < tp):
        return RiskDecision(False, "niveles incoherentes para compra (se requiere SL < precio < TP)")
    if direction == "sell" and not (tp < entry < sl):
        return RiskDecision(False, "niveles incoherentes para venta (se requiere TP < precio < SL)")
    rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
    if rr < settings.min_risk_reward:
        return RiskDecision(False, f"riesgo/beneficio {rr:.2f} < minimo {settings.min_risk_reward}")

    units = position_size(balance, entry, sl, info, settings.risk_per_trade_pct)
    if units <= 0:
        return RiskDecision(False, "tamano calculado por debajo del volumen minimo del simbolo")

    # ---------- capa 2: veto cualitativo LLM ----------
    user = (
        f"## Playbook\n{playbook}\n\n"
        f"## Propuesta del analista\n{json.dumps(proposal, ensure_ascii=False)}\n\n"
        f"## Estado de la cuenta\nbalance={balance:.2f}, pnl_realizado_hoy={daily_realized_pnl:.2f}, "
        f"posiciones_abiertas={json.dumps(open_positions, ensure_ascii=False)}\n\n"
        f"## Tamano ya calculado\n{units} unidades (riesgo {settings.risk_per_trade_pct}% del balance)\n\n"
        "Aprueba o veta."
    )
    result = await llm.ask(SYSTEM, user, schema=VETO_SCHEMA, role="risk_manager")
    assert isinstance(result, dict)
    if result["verdict"] != "approve":
        return RiskDecision(False, f"veto LLM: {result['reasons']}")
    return RiskDecision(True, result["reasons"], volume_units=units)
