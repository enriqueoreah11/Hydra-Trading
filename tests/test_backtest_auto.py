"""Probar una estrategia sin descargar nada antes.

El paso de «primero baja el histórico, luego prueba» sobra: se pulsa backtest y, si
faltan las velas, se piden a tu bróker en el momento. Lo que se prueba es que la
segunda vez NO se vuelvan a pedir —si no, cada prueba tardaría lo mismo y castigaría
justo lo que hay que hacer mucho: probar combinaciones— y que se diga de dónde
salieron los datos, porque medir con las velas de otro bróker mide otro bot.
"""
import time

import pytest
from fastapi.testclient import TestClient

from app.broker import Candle
from app.config import settings
from app.store import Store
from app.web import create_app


class ClienteFalso:
    account_authorized = True


class BrokerFalso:
    """Devuelve una serie con tendencia, suficiente para que salgan operaciones."""

    client = ClienteFalso()

    def __init__(self):
        self.peticiones = 0

    async def candles_range(self, symbol, tf, from_ms, to_ms):
        self.peticiones += 1
        ini, fin = int(from_ms / 1000), int(to_ms / 1000)
        out, precio = [], 1.0
        for i, ts in enumerate(range(ini, fin, 900)):
            sube = bool(i % 7)
            precio += 0.0005 * (1 if sube else -3)
            out.append(Candle(ts=ts, open=precio, high=precio if sube else precio + 0.001,
                              low=precio - 0.001 if sube else precio,
                              close=precio, volume=1))
        return out


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    b = BrokerFalso()
    return TestClient(create_app(Store(tmp_path / "brain.db"), None, b, None)), b


def test_a_backtest_with_no_history_fetches_it_by_itself(cli):
    c, broker = cli
    r = c.post("/backtest/run", json={"symbol": "XAUUSD", "tf": "M15",
                                      "strategy": "donchian", "days": 30}).json()
    assert r["ok"], r
    assert broker.peticiones > 0, "no pidió nada: se habría quedado sin datos"
    assert r["datos"]["fuente"].startswith("cTrader")
    assert r["bars"] > 400


def test_the_second_time_it_does_not_ask_the_broker_again(cli):
    """Si volviera a pedirlo, probar diez combinaciones tardaría diez veces más."""
    c, broker = cli
    c.post("/backtest/run", json={"symbol": "XAUUSD", "tf": "M15", "days": 30})
    tras_la_primera = broker.peticiones

    r = c.post("/backtest/run", json={"symbol": "XAUUSD", "tf": "M15", "days": 30}).json()
    assert broker.peticiones == tras_la_primera, "volvió a bajar lo que ya tenía"
    assert r["datos"]["fuente"] == "guardado"


def test_optimising_also_works_without_downloading_first(cli):
    c, _ = cli
    r = c.post("/backtest/optimize", json={"symbol": "XAUUSD", "tf": "M15",
                                           "steps": 2, "min_trades": 1,
                                           "days": 30}).json()
    assert r["ok"] and r["bars"] > 400
    assert r["datos"]["fuente"].startswith("cTrader")


def test_it_says_where_the_candles_came_from(cli):
    """Medir con las velas de otro bróker mide otro bot. Hay que poder saberlo."""
    c, _ = cli
    r = c.post("/backtest/run", json={"symbol": "XAUUSD", "tf": "M15", "days": 30}).json()
    assert "datos" in r and "fuente" in r["datos"]


def test_without_a_broker_it_explains_instead_of_a_bare_error(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    c = TestClient(create_app(Store(tmp_path / "brain.db"), None, None, None))
    r = c.post("/backtest/run", json={"symbol": "XAUUSD", "tf": "M15"})
    assert r.status_code == 400
    assert "cTrader" in r.json()["error"]


def test_the_downloaded_candles_are_the_ones_it_measures_with(cli):
    """Bajar y medir con otra cosa sería el fallo silencioso perfecto."""
    c, _ = cli
    c.post("/backtest/run", json={"symbol": "XAUUSD", "tf": "M15", "days": 30})
    inv = c.get("/data/status").json()
    guardadas = next(s["bars"] for s in inv["series"]
                     if s["symbol"] == "XAUUSD" and s["tf"] == "M15")
    r = c.post("/backtest/run", json={"symbol": "XAUUSD", "tf": "M15", "days": 30}).json()
    assert r["bars"] == guardadas


def test_the_clock_moves_forward_in_the_series(cli):
    """Las peticiones van del presente hacia atrás; si se pegaran en ese orden, el
    backtest leería el tiempo al revés."""
    c, _ = cli
    c.post("/backtest/run", json={"symbol": "XAUUSD", "tf": "M15", "days": 30})
    inv = next(s for s in c.get("/data/status").json()["series"]
               if s["symbol"] == "XAUUSD")
    assert inv["from_ts"] < inv["to_ts"] <= time.time() + 86400
