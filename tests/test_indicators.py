from app.broker import Candle
from app.indicators import atr, ema, ma_stack, rsi, sma, snapshot, swing_levels


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


def test_sma_is_the_plain_average_once_the_window_is_full():
    values = [float(i) for i in range(1, 21)]      # 1..20
    out = sma(values, 5)
    assert abs(out[-1] - sum(values[-5:]) / 5) < 1e-9
    # antes de llenar la ventana promedia lo que hay, sin dejar huecos
    assert len(out) == len(values)
    assert abs(out[0] - 1.0) < 1e-9
    assert abs(out[2] - 2.0) < 1e-9               # (1+2+3)/3


def test_sma_differs_from_ema_on_a_trend():
    values = [float(i) for i in range(1, 101)]
    # en una subida limpia la EMA va por delante de la SMA: si salieran iguales,
    # una de las dos estaria mal calculada
    assert ema(values, 20)[-1] > sma(values, 20)[-1]


def test_ma_stack_reads_the_trend_and_admits_short_history():
    up = [float(100 + i * 0.5) for i in range(260)]
    st = ma_stack(up)
    assert st["lectura"] == "alcista"
    assert "sma200" in st and st["enough_history"] is True
    assert "ema20" in st["price_above"] and "sma200" in st["price_above"]

    down = [float(300 - i * 0.5) for i in range(260)]
    assert ma_stack(down)["lectura"] == "bajista"
    assert ma_stack(down)["price_above"] == []

    corto = [float(100 + i * 0.5) for i in range(60)]
    assert ma_stack(corto)["enough_history"] is False   # la SMA200 aun no vale


def test_snapshot_carries_the_moving_averages():
    candles = make_candles([float(100 + i * 0.1) for i in range(220)])
    ma = snapshot(candles)["ma"]
    assert ma["sma50"] > 0 and ma["sma200"] > 0
    assert ma["lectura"] in ("alcista", "bajista", "mixto")
