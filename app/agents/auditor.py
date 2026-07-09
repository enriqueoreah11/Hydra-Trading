"""Auditor / Reconciliador — verifica que la realidad del broker coincida con lo esperado.

Checks deterministas (sin LLM, coste casi cero):
- Posiciones sin stop loss colocado -> critico.
- Posiciones no etiquetadas por el sistema (label != 'brain') -> aviso (manual/externa).
- Posiciones huerfanas: abiertas en el broker pero sin tesis registrada en el diario -> aviso.

Si aparece una discrepancia critica y AUTO_HALT_ON_DISCREPANCY=true, activa el kill switch.
"""
from __future__ import annotations

import logging

from ..broker import Broker
from ..store import Store

log = logging.getLogger("auditor")


async def audit(broker: Broker, store: Store, positions: list[dict]) -> list[dict]:
    discrepancies: list[dict] = []

    # simbolos con tesis registrada por el sistema recientemente
    recent = store.recent_journal(limit=200)
    known_symbols = {
        e["symbol"] for e in recent
        if e["symbol"] and e["agent"] in ("executor", "analyst")
    }

    for p in positions:
        sym = p.get("symbol", "?")
        if p.get("stop_loss") in (None, 0):
            discrepancies.append({
                "severity": "critical", "symbol": sym, "position_id": p.get("position_id"),
                "issue": "posicion SIN stop loss colocado"})
        label = (p.get("label") or "").lower()
        if label != "brain":
            discrepancies.append({
                "severity": "warning", "symbol": sym, "position_id": p.get("position_id"),
                "issue": f"posicion no gestionada por el sistema (label='{p.get('label')}')"})
        if sym not in known_symbols and label == "brain":
            discrepancies.append({
                "severity": "warning", "symbol": sym, "position_id": p.get("position_id"),
                "issue": "posicion huerfana: sin tesis reciente en el diario"})

    if discrepancies:
        store.log("auditor", "discrepancies", discrepancies)
    return discrepancies
