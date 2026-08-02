"""Las velas que pide el broker: las de siempre y las de un tramo concreto.

`candles()` se reescribió por dentro para compartir código con `candles_range()`.
Es el método del que come TODO —el analista, los indicadores, la ventana de
mercado— así que lo que se fija aquí es que no haya cambiado en nada de lo que se
ve desde fuera: el mismo recorte, el mismo orden y los mismos precios.
"""
import pytest

from app.broker import Broker


class ClienteFalso:
    """Devuelve trendbars como los manda cTrader: low absoluto + deltas."""

    account_authorized = True

    def __init__(self, n=10):
        self.n = n
        self.enviado = []

    async def send(self, tipo, payload):
        self.enviado.append(payload)
        base = 1_700_000_000 // 60          # en minutos, como la API
        return {"trendbar": [
            {"utcTimestampInMinutes": base + i * 15, "low": 100000,
             "deltaOpen": 500, "deltaHigh": 1500, "deltaClose": 1000, "volume": 7}
            for i in range(self.n)]}


@pytest.fixture
def broker():
    b = Broker.__new__(Broker)
    b.client = ClienteFalso()
    b.account_id = 1

    async def sid(_s, account_id=None):
        return 42
    b.symbol_id = sid
    return b


def corre(coro):
    import asyncio
    return asyncio.run(coro)


def test_the_prices_are_rebuilt_from_low_plus_deltas(broker):
    """cTrader manda el mínimo y diferencias. Sumar mal da precios plausibles y
    equivocados, que es lo peor: no salta nada."""
    c = corre(broker.candles("EURUSD", "M15", 5))[0]
    assert c.low == 1.0                      # 100000 / 100000
    assert c.open == 1.005 and c.high == 1.015 and c.close == 1.01
    assert c.volume == 7


def test_candles_still_returns_at_most_what_was_asked(broker):
    """Comportamiento de siempre: pide de más por los fines de semana y recorta."""
    broker.client.n = 50
    assert len(corre(broker.candles("EURUSD", "M15", 10))) == 10


def test_candles_come_in_time_order(broker):
    cs = corre(broker.candles("EURUSD", "M15", 10))
    assert [c.ts for c in cs] == sorted(c.ts for c in cs)


def test_a_range_asks_for_those_exact_dates_and_does_not_trim(broker):
    """El troceado depende de esto: si mandara `count` o recortara, cada trozo
    devolvería otra cosa y el histórico saldría con agujeros."""
    broker.client.n = 40
    out = corre(broker.candles_range("EURUSD", "M15", 1000, 2000))
    assert len(out) == 40, "un tramo no puede recortarse: son las velas de esas fechas"

    p = broker.client.enviado[-1]
    assert p["fromTimestamp"] == 1000 and p["toTimestamp"] == 2000
    assert "count" not in p, "con count el broker devuelve las últimas, no las del tramo"


def test_the_normal_call_does_send_a_count(broker):
    corre(broker.candles("EURUSD", "M15", 25))
    assert broker.client.enviado[-1]["count"] == 25


def test_no_bars_gives_an_empty_list_not_an_error(broker):
    """Un tramo sin datos es normal al llegar al final del histórico del bróker."""
    broker.client.n = 0
    assert corre(broker.candles_range("EURUSD", "M15", 1000, 2000)) == []
