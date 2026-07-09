from app.backtest import sample_indices, simulate_trade
from app.broker import Candle


def c(o, h, l, cl):
    return Candle(ts=0, open=o, high=h, low=l, close=cl, volume=1)


def test_buy_hits_tp():
    candles = [c(100, 101, 99, 100)] + [c(100, 106, 100, 105) for _ in range(5)]
    # entry 100, sl 98 (risk 2), tp 104 -> +2R
    r = simulate_trade(candles, 0, "buy", 100, 98, 104, 5)
    assert r == 2.0


def test_buy_hits_sl():
    candles = [c(100, 101, 99, 100)] + [c(100, 100, 95, 96) for _ in range(5)]
    r = simulate_trade(candles, 0, "buy", 100, 98, 104, 5)
    assert r == -1.0


def test_sell_hits_tp():
    candles = [c(100, 101, 99, 100)] + [c(100, 100, 94, 95) for _ in range(5)]
    # sell entry 100, sl 102 (risk 2), tp 96 -> +2R
    r = simulate_trade(candles, 0, "sell", 100, 102, 96, 5)
    assert r == 2.0


def test_worst_case_sl_first_when_ambiguous():
    # una vela que toca SL y TP: debe contar como perdida (peor caso)
    candles = [c(100, 101, 99, 100), c(100, 106, 95, 100)]
    r = simulate_trade(candles, 0, "buy", 100, 98, 104, 5)
    assert r == -1.0


def test_timeout_closes_at_last():
    candles = [c(100, 101, 99, 100)] + [c(100, 101, 99, 101) for _ in range(3)]
    r = simulate_trade(candles, 0, "buy", 100, 98, 110, 3)
    # cierra a 101, risk 2 -> +0.5R
    assert abs(r - 0.5) < 1e-9


def test_zero_risk_returns_none():
    assert simulate_trade([c(100, 101, 99, 100)] * 3, 0, "buy", 100, 100, 104, 2) is None


def test_sample_indices_bounds():
    idx = sample_indices(500, 12, 60, 24)
    assert len(idx) == 12
    assert all(60 <= i <= 500 - 24 - 1 for i in idx)


def test_sample_indices_too_small():
    assert sample_indices(50, 12, 60, 24) == []
