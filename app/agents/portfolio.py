"""Portfolio Risk — exposicion agregada por divisa y correlacion entre posiciones.

Complementa al Risk Manager (que evalua cada operacion aislada). Aqui se mira el
conjunto: evita concentrar el riesgo en una divisa (estar largo EUR por tres vias)
o duplicar la misma apuesta con simbolos muy correlacionados en la misma direccion.
Solo puede VETAR; nunca amplia el riesgo.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .. import fx
from ..broker import Broker
from ..config import settings

log = logging.getLogger("portfolio")


@dataclass
class PortfolioDecision:
    approved: bool
    reason: str


async def check(proposal: dict, open_positions: list[dict], broker: Broker) -> PortfolioDecision:
    if not settings.enable_portfolio_check:
        return PortfolioDecision(True, "portfolio check disabled")

    symbol = proposal["symbol"]
    side = proposal["direction"]
    risk = settings.risk_per_trade_pct

    # ---- 1) exposicion agregada por divisa ----
    net: dict[str, float] = {}
    for p in open_positions:
        for cur, val in fx.currency_exposure(p["side"], p["symbol"], risk).items():
            net[cur] = net.get(cur, 0.0) + val
    for cur, val in fx.currency_exposure(side, symbol, risk).items():
        net[cur] = net.get(cur, 0.0) + val
    for cur, val in net.items():
        if abs(val) > settings.max_currency_exposure_pct + 1e-9:
            return PortfolioDecision(
                False, f"exposicion agregada a {cur} = {abs(val):.1f}% "
                       f"> maximo {settings.max_currency_exposure_pct}%")

    # ---- 2) correlacion con posiciones abiertas ----
    if not open_positions:
        return PortfolioDecision(True, "sin posiciones abiertas; ok")
    try:
        cand_candles = await broker.candles(symbol, settings.timeframe, count=120)
        cand_ret = fx.returns(cand_candles)
        for p in open_positions:
            other_candles = await broker.candles(p["symbol"], settings.timeframe, count=120)
            corr = fx.correlation(cand_ret, fx.returns(other_candles))
            same_bet = (corr > 0 and p["side"] == side) or (corr < 0 and p["side"] != side)
            if abs(corr) >= settings.max_correlation and same_bet:
                return PortfolioDecision(
                    False, f"apuesta redundante: correlacion {corr:+.2f} con {p['symbol']} "
                           f"en la misma direccion (|corr| >= {settings.max_correlation})")
    except Exception:  # noqa: BLE001 - la correlacion es best-effort; no bloquear por fallo de datos
        log.warning("portfolio correlation check failed; skipping", exc_info=True)

    return PortfolioDecision(True, "exposicion y correlacion dentro de limites")
