import asyncio

from app.agents.risk_manager import RiskDecision, position_size, review
from app.broker import SymbolInfo
from app.config import settings

INFO = SymbolInfo(symbol_id=1, name="EURUSD", digits=5, pip_position=4,
                  lot_size_units=100_000, min_volume_units=1_000,
                  step_volume_units=1_000, max_volume_units=10_000_000)


def proposal(**over):
    base = {
        "action": "propose", "symbol": "EURUSD", "direction": "buy",
        "last_close": 1.1000, "stop_loss": 1.0950, "take_profit": 1.1100,
        "confidence": 80, "thesis": "t", "invalidation": "i",
    }
    base.update(over)
    return base


def run_review(**kwargs):
    defaults = dict(proposal=proposal(), balance=10_000.0, initial_balance=10_000.0,
                    daily_realized_pnl=0.0, open_positions=[], info=INFO,
                    halted=False, playbook="pb")
    defaults.update(kwargs)
    # every case below hits a deterministic hard-limit branch, so no LLM call is made
    return asyncio.run(review(**defaults))


def test_position_size_math():
    # risk 1% of 10k = 100; distance 0.0050 -> 20_000 units
    units = position_size(10_000, 1.1000, 1.0950, INFO, 1.0)
    assert units == 20_000


def test_position_size_below_min_returns_zero():
    tiny = SymbolInfo(symbol_id=1, name="X", digits=5, pip_position=4,
                      lot_size_units=100_000, min_volume_units=1_000_000,
                      step_volume_units=1_000, max_volume_units=10_000_000)
    assert position_size(100, 1.1, 1.0, tiny, 1.0) == 0.0


def test_halted_vetoes():
    d = run_review(halted=True)
    assert isinstance(d, RiskDecision) and not d.approved


def test_low_confidence_vetoes():
    d = run_review(proposal=proposal(confidence=10))
    assert not d.approved


def test_daily_loss_limit_vetoes():
    d = run_review(daily_realized_pnl=-10_000 * settings.max_daily_loss_pct / 100 - 1)
    assert not d.approved


def test_incoherent_levels_veto():
    d = run_review(proposal=proposal(direction="buy", stop_loss=1.2, take_profit=1.3))
    assert not d.approved


def test_bad_risk_reward_veto():
    d = run_review(proposal=proposal(stop_loss=1.0950, take_profit=1.1010))
    assert not d.approved


def test_max_positions_veto():
    d = run_review(open_positions=[{"symbol": f"S{i}"} for i in range(settings.max_open_positions)])
    assert not d.approved


def test_same_symbol_open_veto():
    d = run_review(open_positions=[{"symbol": "EURUSD"}])
    assert not d.approved
