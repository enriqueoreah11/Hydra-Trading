"""Ponerle nombre a cada cuenta para saber cuál es cuál.

Un ctidTraderAccountId de ocho cifras no distingue nada cuando tienes seis cuentas,
y es justo cuando más importa acertar: la demo de pruebas y la real se parecen
muchísimo escritas. Lo que se prueba aquí es que la etiqueta sea SOLO eso — que
renombrar no toque con qué cuenta opera Hydra, porque ese sería un fallo caro y
silencioso: creerías estar en demo y estar en real.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.store import Store
from app.web import create_app


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "ctrader_account_id", 4002)
    return TestClient(create_app(Store(tmp_path / "brain.db"), None, None, None)), tmp_path


def nombres(tmp_path):
    f = tmp_path / "account_names.json"
    return json.loads(f.read_text()) if f.is_file() else {}


def test_a_name_is_saved_and_survives_a_restart(cli, monkeypatch):
    c, tmp = cli
    assert c.post("/accounts/4002/name", json={"name": "FTMO 100k"}).json()["ok"]
    assert nombres(tmp)["4002"] == "FTMO 100k"

    # otra app sobre la misma carpeta: el nombre sigue ahí
    c2 = TestClient(create_app(Store(tmp / "brain.db"), None, None, None))
    assert c2.post("/accounts/4003/name", json={"name": "mi demo"}).json()["ok"]
    assert nombres(tmp) == {"4002": "FTMO 100k", "4003": "mi demo"}


def test_renaming_never_changes_which_account_trades(cli):
    """EL punto. Si esto cambiara la cuenta activa, creerías estar en demo y no."""
    c, _ = cli
    antes = settings.ctrader_account_id
    c.post("/accounts/4003/name", json={"name": "la real"})
    c.post("/accounts/4002/name", json={"name": "la demo"})
    assert settings.ctrader_account_id == antes


def test_an_empty_name_removes_it_instead_of_saving_a_blank(cli):
    c, tmp = cli
    c.post("/accounts/4002/name", json={"name": "temporal"})
    c.post("/accounts/4002/name", json={"name": "   "})
    assert "4002" not in nombres(tmp)


def test_a_very_long_name_is_cut_not_refused(cli, tmp_path):
    """Cortar es mejor que rechazar: el nombre es cosmético, no hay por qué pelear."""
    c, tmp = cli
    c.post("/accounts/4002/name", json={"name": "x" * 200})
    assert len(nombres(tmp)["4002"]) == 40


def test_a_corrupt_file_does_not_stop_you_from_renaming(cli):
    """Se pierde lo viejo (ya era ilegible) pero se puede seguir usando la app."""
    c, tmp = cli
    (tmp / "account_names.json").write_text('{"4002": ')
    assert c.post("/accounts/4002/name", json={"name": "nuevo"}).json()["ok"]
    assert nombres(tmp)["4002"] == "nuevo"


def test_without_a_body_it_does_not_explode(cli):
    c, _ = cli
    assert c.post("/accounts/4002/name").status_code == 200


class TokensFalsos:
    has_tokens = True

    async def get_access_token(self):
        return "token"


class ClienteFalso:
    async def start(self):
        return None

    async def wait_connected(self, timeout=0):
        return True


class BrokerFalso:
    client = ClienteFalso()

    async def list_accounts(self, token):
        return [{"ctidTraderAccountId": 4002, "isLive": False, "traderLogin": 111},
                {"ctidTraderAccountId": 4003, "isLive": True, "traderLogin": 222}]


def test_the_names_travel_with_the_account_list(tmp_path, monkeypatch):
    """De nada sirve guardarlos si /accounts no los devuelve."""
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "ctrader_account_id", 4002)
    c = TestClient(create_app(Store(tmp_path / "brain.db"), TokensFalsos(),
                              BrokerFalso(), None))
    c.post("/accounts/4002/name", json={"name": "FTMO 100k"})

    d = c.get("/accounts").json()
    assert d["ok"], d
    por_id = {a["id"]: a for a in d["accounts"]}
    assert por_id[4002]["name"] == "FTMO 100k"
    assert por_id[4003]["name"] == "", "una cuenta sin nombre no puede heredar el de otra"
    # y lo que de verdad importa: sigue operando la misma
    assert d["current"] == 4002


def test_the_name_also_reaches_the_destination_accounts(tmp_path, monkeypatch):
    """Sale en dos listas distintas. Si el nombre solo llega a una, renombras arriba
    y abajo sigues viendo un número — que es exactamente el problema que resuelve."""
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "ctrader_account_id", 4002)

    class ClientAutorizado(ClienteFalso):
        account_authorized = True

    class BrokerAutorizado(BrokerFalso):
        client = ClientAutorizado()

    c = TestClient(create_app(Store(tmp_path / "brain.db"), TokensFalsos(),
                              BrokerAutorizado(), None))
    c.post("/accounts/4003/name", json={"name": "FTMO 100k"})

    d = c.get("/mirror").json()
    assert d["ok"], d
    destino = next(a for a in d["accounts"] if a["account_id"] == 4003)
    assert destino["name"] == "FTMO 100k"


def test_a_name_never_hides_whether_it_is_real_or_demo(tmp_path, monkeypatch):
    """Llamarla «mi demo» no puede tapar que sea REAL: el nombre lo pones tú y te
    puedes equivocar; `live` viene del broker y es el que manda."""
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    c = TestClient(create_app(Store(tmp_path / "brain.db"), TokensFalsos(),
                              BrokerFalso(), None))
    c.post("/accounts/4003/name", json={"name": "mi demo de pruebas"})

    real = next(a for a in c.get("/accounts").json()["accounts"] if a["id"] == 4003)
    assert real["live"] is True
