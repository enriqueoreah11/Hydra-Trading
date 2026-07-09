"""Executor — coloca las operaciones aprobadas (o las simula en DRY_RUN)."""
from __future__ import annotations

import logging

from ..broker import Broker
from ..config import settings
from ..store import Store

log = logging.getLogger("executor")


async def execute(broker: Broker, store: Store, proposal: dict, volume_units: float) -> dict:
    symbol = proposal["symbol"]
    order = {
        "symbol": symbol,
        "direction": proposal["direction"],
        "volume_units": volume_units,
        "entry_ref": proposal["last_close"],
        "stop_loss": proposal["stop_loss"],
        "take_profit": proposal["take_profit"],
        "dry_run": settings.dry_run,
    }
    if settings.dry_run:
        store.log("executor", "order_simulated", order, symbol=symbol)
        log.info("[DRY RUN] simulated order: %s", order)
        return {"status": "simulated", **order}

    try:
        res = await broker.place_market_order(
            symbol=symbol,
            side=proposal["direction"],
            volume_units=volume_units,
            stop_loss=proposal["stop_loss"],
            take_profit=proposal["take_profit"],
            entry_ref=proposal["last_close"],
            label="brain",
        )
        store.log("executor", "order_placed", {**order, "response": str(res)[:2000]}, symbol=symbol)
        log.info("order placed on %s: %s %s units", symbol, proposal["direction"], volume_units)
        return {"status": "placed", **order}
    except Exception as e:  # noqa: BLE001
        store.log("executor", "order_error", {**order, "error": str(e)}, symbol=symbol)
        log.exception("order failed")
        return {"status": "error", "error": str(e), **order}
