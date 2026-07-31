"""Los frenos de abrir y cerrar: que no salga nada cuando no debe.

Aqui se mueve dinero real, asi que cada freno tiene su prueba: sin confirmacion, sin
stop, en HALT, pasado el tope de posiciones, y en modo papel (donde NO se debe llamar
al broker ni una vez). Y al reves: en modo real la orden tiene que llegar, con el stop
en su sitio y el lotaje convertido a unidades.

El broker es de mentira y registra las llamadas: no hace falta cuenta ni red.
"""
import pytest
from fastapi.testclient import TestClient

from app.broker import Candle
from app.config import settings
from app.store import Store
from app.web import create_app

BASE = {"symbol": "EURUSD", "side": "BUY", "lots": 0.1, "sl_pips": 30, "tp_pips": 60}


class _Client:
    account_authorized = True
    connected = True
    last_error = ""

    def __init__(self):
        self.authorized = set()

    async def authorize_account(self, aid):
        self.authorized.add(int(aid))
        return True


class FakeBroker:
    """Broker que APUNTA lo que se le pide, en vez de enviarlo a ningun sitio."""

    def __init__(self, n_open=0):
        self.client = _Client()
        self.n_open = n_open
        self.calls = []

    def symbol_names(self):
        return ["EURUSD"]

    async def positions(self):
        return [{"position_id": 77, "symbol_id": 1, "side": "BUY",
                 "volume_units": 100000, "entry_price": 1.1000, "stop_loss": 1.0950,
                 "take_profit": None, "open_ts": 0, "label": "x"}] * self.n_open

    async def symbol_name_by_id(self, sid):
        return "EURUSD"

    async def candles(self, sym, tf, n):
        return [Candle(ts=0, open=1.1, high=1.1, low=1.1, close=1.1000, volume=1)] * 2

    async def list_accounts(self, token):
        return [{"ctidTraderAccountId": 1, "isLive": False},
                {"ctidTraderAccountId": 2, "isLive": True, "brokerTitleShort": "prop"}]

    async def trader(self, account_id=None):
        return {"equity": 10000 if (account_id or 1) == 1 else 5000, "balance": 0}

    async def place_market_order(self, **kw):
        self.calls.append(("order", kw))
        return {"ok": 1}

    async def close_position(self, pid, units):
        self.calls.append(("close", pid, units))
        return {"ok": 1}


class FakeTokens:
    has_tokens = True

    async def get_access_token(self):
        return "x"


@pytest.fixture
def app(tmp_path, monkeypatch):
    def make(dry_run=True, n_open=0, halted=False):
        monkeypatch.setattr(settings, "data_dir", str(tmp_path))
        monkeypatch.setattr(settings, "dry_run", dry_run)
        monkeypatch.setattr(settings, "max_open_positions", 3)
        store = Store(tmp_path / "brain.db")
        store.set_halted(halted)
        br = FakeBroker(n_open)
        return TestClient(create_app(store, FakeTokens(), br, None)), store, br
    return make


def test_without_confirmation_nothing_is_sent(app):
    c, _, br = app()
    r = c.post("/order", json=BASE)
    assert r.status_code == 400 and "confirm" in r.json()["error"]
    assert br.calls == []


def test_a_stop_is_mandatory(app):
    c, _, br = app()
    r = c.post("/order", json={**BASE, "sl_pips": 0, "confirm": True})
    assert r.status_code == 400 and "stop" in r.json()["error"]
    assert br.calls == []


def test_paper_mode_never_reaches_the_broker(app):
    c, _, br = app(dry_run=True)
    j = c.post("/order", json={**BASE, "confirm": True}).json()
    assert j["ok"] and j["simulated"] is True
    assert j["stop_loss"] == pytest.approx(1.0970, abs=1e-6)   # 30 pips por debajo
    assert br.calls == []                                      # ni una llamada


def test_halt_blocks_opening(app):
    c, _, br = app(dry_run=False, halted=True)
    r = c.post("/order", json={**BASE, "confirm": True})
    assert r.status_code == 400 and "HALT" in r.json()["error"]
    assert br.calls == []


def test_the_open_positions_cap_is_respected(app):
    c, _, br = app(dry_run=False, n_open=3)
    r = c.post("/order", json={**BASE, "confirm": True})
    assert r.status_code == 400 and "tope" in r.json()["error"]
    assert br.calls == []


def test_in_live_mode_the_order_arrives_with_its_stop(app):
    c, _, br = app(dry_run=False, n_open=0)
    j = c.post("/order", json={**BASE, "confirm": True}).json()
    assert j["ok"] and not j.get("simulated")
    sent = [x for x in br.calls if x[0] == "order"][-1][1]
    assert sent["volume_units"] == 10000            # 0.1 lotes = 10 000 unidades
    assert sent["stop_loss"] == pytest.approx(1.0970, abs=1e-6)
    assert sent["take_profit"] == pytest.approx(1.1060, abs=1e-6)
    assert sent["label"] == "hydra-manual"          # separado de lo de tus bots


def test_sell_puts_the_stop_above(app):
    c, _, br = app(dry_run=False)
    j = c.post("/order", json={**BASE, "side": "SELL", "confirm": True}).json()
    assert j["stop_loss"] > j["price"] > j["take_profit"]


def test_closing_sends_the_right_volume(app):
    c, _, br = app(dry_run=False, n_open=1)
    j = c.post("/positions/77/close", json={"pct": 50}).json()
    assert j["ok"] and j["units"] == 50000
    assert br.calls[-1] == ("close", 77, 50000.0)
    j = c.post("/positions/77/close", json={}).json()          # todo
    assert j["units"] == 100000


def test_closing_something_that_is_not_open_says_so(app):
    c, _, br = app(dry_run=False, n_open=1)
    r = c.post("/positions/999/close", json={})
    assert r.status_code == 404
    assert br.calls == []


def test_closing_in_paper_mode_does_not_reach_the_broker(app):
    c, _, br = app(dry_run=True, n_open=1)
    j = c.post("/positions/77/close", json={}).json()
    assert j["ok"] and j["simulated"] is True and br.calls == []


# ---------------------------------------------- varias cuentas a la vez

def test_the_order_is_mirrored_to_the_other_accounts(app, tmp_path):
    """La segunda cuenta tiene la mitad de capital: le toca la mitad de lotaje."""
    c, _, br = app(dry_run=False)
    r = c.post("/mirror", json={"dests": [
        {"account_id": 2, "alias": "prop", "enabled": True, "mode": "equity",
         "suffix": ".raw"}]})
    assert r.json()["ok"]
    j = c.post("/order", json={**BASE, "confirm": True}).json()
    envs = [x for x in br.calls if x[0] == "order"]
    assert len(envs) == 2                       # principal + destino
    dest = envs[-1][1]
    assert dest["account_id"] == 2
    assert dest["volume_units"] == 5000         # 0.1 lotes × (5000/10000)
    # el sufijo conserva SU forma: los brokers los escriben en minúscula
    assert dest["symbol"] == "EURUSD.raw"
    assert j["accounts"][0]["status"] == "enviada"


def test_a_disabled_account_gets_nothing(app):
    c, _, br = app(dry_run=False)
    c.post("/mirror", json={"dests": [
        {"account_id": 2, "enabled": False, "mode": "same"}]})
    c.post("/order", json={**BASE, "confirm": True})
    assert len([x for x in br.calls if x[0] == "order"]) == 1     # solo la principal


def test_risk_mode_uses_that_accounts_capital(app):
    c, _, br = app(dry_run=False)
    c.post("/mirror", json={"dests": [
        {"account_id": 2, "enabled": True, "mode": "risk", "value": 1.0}]})
    c.post("/order", json={**BASE, "confirm": True})              # stop de 30 pips
    dest = [x for x in br.calls if x[0] == "order"][-1][1]
    # 1% de 5000 = 50 USD; 50 / (30 pips × 10) = 0.166 -> 0.17 lotes
    assert dest["volume_units"] == 17000


def test_a_symbol_not_allowed_in_that_account_is_not_sent(app):
    c, _, br = app(dry_run=False)
    c.post("/mirror", json={"dests": [
        {"account_id": 2, "enabled": True, "mode": "same", "never": ["EURUSD"]}]})
    j = c.post("/order", json={**BASE, "confirm": True}).json()
    assert len([x for x in br.calls if x[0] == "order"]) == 1
    assert "no está permitido" in j["accounts"][0]["why"]


def test_paper_mode_does_not_mirror_either(app):
    c, _, br = app(dry_run=True)
    c.post("/mirror", json={"dests": [
        {"account_id": 2, "enabled": True, "mode": "same"}]})
    j = c.post("/order", json={**BASE, "confirm": True}).json()
    assert br.calls == []
    assert j["accounts"][0]["status"].startswith("simulado")


def test_an_unknown_mode_is_rejected(app):
    c, _, _ = app()
    r = c.post("/mirror", json={"dests": [{"account_id": 2, "mode": "loqueSea"}]})
    assert r.status_code == 400
