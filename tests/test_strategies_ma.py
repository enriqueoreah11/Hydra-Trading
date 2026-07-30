"""La estrategia de retroceso a la media: que entre donde debe y calle donde no.

Se construyen series con la respuesta conocida. Lo que se comprueba no es que dé
señales, sino que respete el lado de la SMA — el fallo caro sería comprar en
tendencia bajista porque tocó la EMA.
"""
from app.broker import Candle
from app.strategies import DEFAULTS, ma_pullback


def candles(closes, wick=1.0):
    out = []
    for i, c in enumerate(closes):
        out.append(Candle(ts=i * 900, open=c, high=c + wick, low=c - wick,
                          close=c, volume=100))
    return out


def _p(**kw):
    p = dict(DEFAULTS["ma_pullback"])
    p.update(kw)
    return p


def test_no_signal_without_enough_history():
    cs = candles([100.0 + i * 0.1 for i in range(120)])
    assert ma_pullback(cs, _p(sma_trend=200), len(cs) - 1) is None


def test_buys_the_pullback_in_an_uptrend():
    # subida larga y limpia, y al final un retroceso que toca la EMA y rebota
    closes = [100.0 + i * 0.30 for i in range(260)]
    closes[-2] = closes[-3] - 3.0          # la vela anterior perfora hacia la EMA
    closes[-1] = closes[-3] + 0.6          # y la actual cierra por encima
    sig = ma_pullback(candles(closes), _p(ema_fast=20, sma_trend=200), len(closes) - 1)
    assert sig is not None and sig.direction == "buy"
    assert sig.sl < sig.entry < sig.tp


def test_sells_the_pullback_in_a_downtrend():
    closes = [200.0 - i * 0.30 for i in range(260)]
    closes[-2] = closes[-3] + 3.0
    closes[-1] = closes[-3] - 0.6
    sig = ma_pullback(candles(closes), _p(ema_fast=20, sma_trend=200), len(closes) - 1)
    assert sig is not None and sig.direction == "sell"
    assert sig.tp < sig.entry < sig.sl


def test_never_buys_below_the_trend_sma():
    """El caso que importa: mismo gesto de retroceso, pero bajo la SMA200."""
    closes = [200.0 - i * 0.30 for i in range(260)]
    closes[-2] = closes[-3] - 3.0          # retroceso "de compra"…
    closes[-1] = closes[-3] + 0.6          # …en plena tendencia bajista
    sig = ma_pullback(candles(closes), _p(ema_fast=20, sma_trend=200), len(closes) - 1)
    assert sig is None or sig.direction == "sell"


def test_quiet_when_price_is_glued_to_the_average():
    cs = candles([100.0] * 260)
    assert ma_pullback(cs, _p(), len(cs) - 1) is None
