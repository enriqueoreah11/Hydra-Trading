from app.fx import correlation, currencies_of, currency_exposure, returns
from app.broker import Candle


def test_currencies_of_fx_pair():
    assert currencies_of("EURUSD") == ("EUR", "USD")
    assert currencies_of("GBPJPY") == ("GBP", "JPY")


def test_currencies_of_metal():
    assert currencies_of("XAUUSD") == ("XAU", "USD")
    assert currencies_of("XAGUSD") == ("XAG", "USD")


def test_currencies_of_unknown():
    base, quote = currencies_of("US500")
    assert base is None and quote == "US500"


def test_currency_exposure_signs():
    exp = currency_exposure("buy", "EURUSD", 1.0)
    assert exp["EUR"] == 1.0 and exp["USD"] == -1.0
    exp2 = currency_exposure("sell", "EURUSD", 1.0)
    assert exp2["EUR"] == -1.0 and exp2["USD"] == 1.0


def test_correlation_identical_is_one():
    a = [0.1, -0.2, 0.3, -0.1, 0.05, 0.2]
    assert abs(correlation(a, a) - 1.0) < 1e-9


def test_correlation_opposite_is_minus_one():
    a = [0.1, -0.2, 0.3, -0.1, 0.05, 0.2]
    b = [-x for x in a]
    assert abs(correlation(a, b) + 1.0) < 1e-9


def test_returns_length():
    candles = [Candle(ts=i, open=1, high=1, low=1, close=1.0 + i * 0.01, volume=1)
               for i in range(6)]
    assert len(returns(candles)) == 5
