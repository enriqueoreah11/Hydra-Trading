from app.broker import Candle
from app.indicators import atr, ema, rsi, snapshot, swing_levels


def make_candles(closes):
    out = []
    for i, c in enumerate(closes):
        out.append(Candle(ts=i * 900, open=c - 0.5, high=c + 1, low=c - 1, close=c, volume=100))
    return out


def test_ema_converges_to_constant():
    values = [10.0] * 50
    assert abs(ema(values, 20)[-1] - 10.0) < 1e-9


def test_rsi_bounds():
    up = [float(i) for i in range(1, 60)]
    down = [float(60 - i) for i in range(1, 60)]
    assert rsi(up, 14)[-1] > 90
    assert rsi(down, 14)[-1] < 10


def test_atr_positive():
    candles = make_candles([float(100 + (i % 5)) for i in range(60)])
    assert atr(candles, 14)[-1] > 0


def test_swing_levels_split_around_price():
    closes = [100, 102, 105, 103, 101, 99, 97, 100, 104, 107, 105, 102, 100, 98, 101] * 4
    candles = make_candles([float(c) for c in closes])
    levels = swing_levels(candles)
    last = candles[-1].close
    assert all(s < last for s in levels["supports"])
    assert all(r > last for r in levels["resistances"])


def test_snapshot_keys():
    candles = make_candles([float(100 + i * 0.1) for i in range(120)])
    snap = snapshot(candles)
    for key in ("last_close", "ema20", "ema50", "ema200", "rsi14", "atr14", "levels", "recent_candles"):
        assert key in snap
    assert len(snap["recent_candles"]) == 40
