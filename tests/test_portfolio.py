import asyncio

from app.agents.portfolio import check
from app.config import settings


class FakeBroker:
    """Broker minimo: no se llega a pedir velas en estos casos deterministas."""
    async def candles(self, *a, **k):
        return []


def prop(symbol="GBPUSD", direction="buy"):
    return {"symbol": symbol, "direction": direction, "last_close": 1.25,
            "stop_loss": 1.24, "take_profit": 1.27, "confidence": 80}


def run(**kwargs):
    defaults = dict(proposal=prop(), open_positions=[], broker=FakeBroker())
    defaults.update(kwargs)
    return asyncio.run(check(**defaults))


def test_currency_exposure_veto():
    settings.enable_portfolio_check = True
    settings.max_currency_exposure_pct = 2.0
    settings.risk_per_trade_pct = 1.0
    # ya largo USD-corto via EURUSD buy y USDJPY sell -> agregar GBPUSD buy dispara USD
    open_pos = [{"symbol": "EURUSD", "side": "buy"}, {"symbol": "AUDUSD", "side": "buy"}]
    d = run(proposal=prop("GBPUSD", "buy"), open_positions=open_pos)
    # USD acumula -3% (tres cortos de USD) -> supera 2%
    assert not d.approved


def test_no_positions_ok():
    settings.enable_portfolio_check = True
    d = run(open_positions=[])
    assert d.approved


def test_disabled_always_ok():
    settings.enable_portfolio_check = False
    d = run(open_positions=[{"symbol": "EURUSD", "side": "buy"}] * 5)
    assert d.approved
    settings.enable_portfolio_check = True
