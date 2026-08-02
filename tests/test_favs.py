"""Favoritos: qué sale primero en las ventanitas del tablero.

Una estrella en una app que opera podría entenderse como algo mucho más serio, así
que lo que se fija aquí es lo que NO hace: marcar un instrumento no cambia lo que
Hydra vigila ni con qué estrategia, y marcar una cuenta no cambia con cuál opera ni
a cuáles se mandan las órdenes. Es orden de pantalla y nada más.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.store import Store
from app.web import create_app


class TokensFalsos:
    has_tokens = True

    async def get_access_token(self):
        return "tok"


class ClienteFalso:
    account_authorized = True

    async def start(self):
        return None

    async def wait_connected(self, timeout=0):
        return True


class BrokerFalso:
    client = ClienteFalso()

    def symbol_names(self):
        return ["XAUUSD", "EURUSD", "US100", "GBPUSD"]

    async def list_accounts(self, token):
        return [{"ctidTraderAccountId": 4002, "isLive": False, "traderLogin": 1},
                {"ctidTraderAccountId": 4003, "isLive": True, "traderLogin": 2}]


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "symbols", "XAUUSD,EURUSD,US100")
    monkeypatch.setattr(settings, "ctrader_account_id", 4002)
    return TestClient(create_app(Store(tmp_path / "brain.db"), TokensFalsos(),
                                 BrokerFalso(), None)), tmp_path


# ------------------------------------------------------------- instrumentos

def test_starring_an_instrument_is_saved(cli):
    c, tmp = cli
    d = c.post("/watchlist/eurusd/fav", json={}).json()
    assert d["ok"] and d["fav"] is True and d["symbol"] == "EURUSD"
    assert json.loads((tmp / "fav_symbols.json").read_text()) == ["EURUSD"]


def test_pressing_the_star_again_removes_it(cli):
    c, tmp = cli
    c.post("/watchlist/EURUSD/fav", json={})
    d = c.post("/watchlist/EURUSD/fav", json={}).json()
    assert d["fav"] is False
    assert json.loads((tmp / "fav_symbols.json").read_text()) == []


def test_starring_does_not_change_what_hydra_watches(cli):
    """Lo importante: es orden de pantalla, no configuración de trading."""
    c, _ = cli
    antes = list(settings.symbol_list)
    c.post("/watchlist/EURUSD/fav", json={})
    assert settings.symbol_list == antes


def test_the_star_travels_with_the_watchlist(cli):
    c, _ = cli
    c.post("/watchlist/EURUSD/fav", json={})
    d = c.get("/watchlist").json()
    por = {r["symbol"]: r for r in d["symbols"]}
    assert por["EURUSD"]["fav"] is True
    assert por["XAUUSD"]["fav"] is False, "una estrella no puede contagiarse a las demás"
    assert d["favs"] == ["EURUSD"]


def test_a_corrupt_favourites_file_does_not_break_the_list(cli, tmp_path):
    """Se pierden los favoritos (ya eran ilegibles), pero la lista sigue saliendo."""
    c, tmp = cli
    (tmp / "fav_symbols.json").write_text("[esto no es json")
    d = c.get("/watchlist").json()
    assert d["favs"] == [] and len(d["symbols"]) >= 3


# ------------------------------------------------------------------ cuentas

@pytest.fixture
def cuentas(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "ctrader_account_id", 4002)
    return TestClient(create_app(Store(tmp_path / "brain.db"), TokensFalsos(),
                                 BrokerFalso(), None)), tmp_path


def test_starring_an_account_is_saved_and_travels(cuentas):
    c, tmp = cuentas
    assert c.post("/accounts/4003/fav", json={}).json()["fav"] is True
    assert json.loads((tmp / "fav_accounts.json").read_text()) == [4003]

    por = {a["id"]: a for a in c.get("/accounts").json()["accounts"]}
    assert por[4003]["fav"] is True and por[4002]["fav"] is False


def test_starring_an_account_never_changes_which_one_trades(cuentas):
    """El fallo caro seria creer que marcaste una favorita y haber cambiado la activa."""
    c, _ = cuentas
    antes = settings.ctrader_account_id
    c.post("/accounts/4003/fav", json={})
    assert settings.ctrader_account_id == antes
    assert c.get("/accounts").json()["current"] == antes


def test_the_star_and_the_name_are_independent(cuentas):
    """Se guardan en archivos distintos: quitar una no puede llevarse la otra."""
    c, _ = cuentas
    c.post("/accounts/4003/fav", json={})
    c.post("/accounts/4003/name", json={"name": "FTMO"})
    c.post("/accounts/4003/fav", json={})          # se quita la estrella

    a = next(x for x in c.get("/accounts").json()["accounts"] if x["id"] == 4003)
    assert a["fav"] is False and a["name"] == "FTMO"


def test_an_explicit_value_wins_over_toggling(cuentas):
    """Con `fav` explícito no se alterna: dos clientes a la vez no se pisan."""
    c, _ = cuentas
    assert c.post("/accounts/4003/fav", json={"fav": True}).json()["fav"] is True
    assert c.post("/accounts/4003/fav", json={"fav": True}).json()["fav"] is True
