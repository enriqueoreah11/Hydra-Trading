"""Los endpoints de oír, apuntar y preguntar.

Lo que se vigila aquí es sobre todo el código de estado. Una grabación en la que no
se entiende nada NO es un error del servidor: si contesta 4xx o 5xx, la interfaz lo
pinta como avería y acabas revisando la app cuando lo único que pasó es que hablaste
lejos del micro.
"""
import pytest
from fastapi.testclient import TestClient

from app import stt, vault
from app.config import settings
from app.store import Store
from app.web import create_app


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "obsidian_vault_path", "")
    monkeypatch.setattr(settings, "tts_provider", "voicebox")
    monkeypatch.setattr(settings, "stt_enabled", True)
    return TestClient(create_app(Store(tmp_path / "brain.db"), None, None, None))


def oye(monkeypatch, texto):
    async def _t(audio, ms=0, filename="x.webm"):
        return {"ok": True, "text": texto, "error": ""}
    monkeypatch.setattr(stt, "transcribe", _t)


# --------------------------------------------------------------- /stt

def test_speech_comes_back_with_what_to_do_with_it(cli, monkeypatch):
    oye(monkeypatch, "apunta que el oro respetó el 3400")
    d = cli.post("/stt?ms=2000", content=b"x" * 4000).json()
    assert d["ok"] is True and d["intencion"]["tipo"] == "nota"


def test_not_understanding_is_not_a_server_error(cli, monkeypatch):
    """EL detalle. Con un 5xx aquí, hablar flojo se ve igual que la app rota."""
    async def _t(audio, ms=0, filename="x.webm"):
        return {"ok": False, "text": "", "error": "no se entendió nada"}
    monkeypatch.setattr(stt, "transcribe", _t)
    r = cli.post("/stt?ms=2000", content=b"x" * 4000)
    assert r.status_code == 200 and r.json()["ok"] is False


def test_an_empty_body_is_answered_not_crashed(cli):
    r = cli.post("/stt?ms=0", content=b"")
    assert r.status_code == 200 and r.json()["ok"] is False


def test_the_health_check_says_why_the_ears_are_off(cli, monkeypatch):
    monkeypatch.setattr(settings, "stt_enabled", False)
    d = cli.get("/stt/health").json()
    assert d["ok"] is False and "apagado" in d["error"]


# -------------------------------------------------------- /voice/note

def test_a_dictated_note_lands_in_the_memory(cli, tmp_path):
    r = cli.post("/voice/note", json={"text": "el oro falló tres veces en el 3400"})
    assert r.json()["ok"] is True
    assert any("3400" in p.read_text(encoding="utf-8")
               for p in (tmp_path / "vault").rglob("*.md"))


def test_the_dictated_note_is_tagged_so_the_brain_can_read_it_back(cli, tmp_path):
    """Sin la etiqueta se guardaría y nadie la volvería a leer: sería un diario."""
    cli.post("/voice/note", json={"text": "el petróleo se mueve raro los miércoles"})
    assert [x["name"] for x in vault.search("petróleo")] != []


def test_an_empty_note_is_refused(cli):
    assert cli.post("/voice/note", json={"text": "   "}).status_code == 400


# --------------------------------------------------------- /voice/ask

def test_a_question_is_answered_out_of_the_real_state(cli, monkeypatch):
    visto = {}

    async def _resp(pregunta, estado):
        visto.update({"q": pregunta, "estado": estado})
        return "Vas plano, sin nada abierto."
    from app.agents import copiloto
    monkeypatch.setattr(copiloto, "responder", _resp)
    d = cli.post("/voice/ask", json={"text": "cómo voy hoy"}).json()
    assert d["ok"] is True and "plano" in d["text"]
    assert visto["estado"]["dry_run"] == settings.dry_run


def test_the_copilot_is_told_when_the_broker_is_down_not_left_guessing(cli, monkeypatch):
    """Si el bróker no contesta y se calla, el copiloto diría «no tienes nada
    abierto» — que es lo contrario de lo que pasa."""
    visto = {}

    class BrokerCaido:
        async def trader(self):
            raise RuntimeError("sin conexión")

        async def positions(self):
            return []

    async def _resp(pregunta, estado):
        visto.update(estado)
        return "x"
    from app.agents import copiloto
    monkeypatch.setattr(copiloto, "responder", _resp)
    import app.web as web
    app = web.create_app(Store(settings.data_path / "b.db"), None, BrokerCaido(), None)
    TestClient(app).post("/voice/ask", json={"text": "qué tengo abierto"})
    assert "error_broker" in visto


def test_an_empty_question_is_refused(cli):
    assert cli.post("/voice/ask", json={"text": ""}).status_code == 400


# ------------------------------------------------------- /vault (estado)

def test_the_vault_status_says_where_it_is_writing(cli):
    d = cli.get("/vault/estado").json()
    assert d["obsidian"] is False and "dentro de la app" in d["motivo"]


def test_a_bad_vault_path_is_refused_before_being_saved(cli):
    """Guardar una ruta que no existe dejaría la memoria escribiendo donde él no
    mira, sin un solo error por ninguna parte."""
    r = cli.post("/vault/vault-path", json={"path": "/ruta/que/no/existe"})
    assert r.status_code == 400 and "no existe" in r.json()["error"]
    assert settings.obsidian_vault_path == ""


def test_a_good_vault_path_is_accepted(cli, tmp_path):
    v = tmp_path / "MiVault"
    v.mkdir()
    d = cli.post("/vault/vault-path", json={"path": str(v)}).json()
    assert d["ok"] is True and d["obsidian"] is True
    settings.obsidian_vault_path = ""            # no se lo dejamos a otra prueba


def test_the_vault_path_survives_a_restart(cli, tmp_path):
    """Si solo se aplicara en caliente, al reiniciar la memoria volvería dentro de
    la app y las notas dejarían de aparecer en Obsidian sin avisar de nada."""
    from app import agent_params
    v = tmp_path / "MiVault"
    v.mkdir()
    cli.post("/vault/vault-path", json={"path": str(v)})
    settings.obsidian_vault_path = ""                    # como si arrancara de cero
    agent_params.load_overrides(tmp_path / "overrides.json")
    assert settings.obsidian_vault_path == str(v)
    settings.obsidian_vault_path = ""


def test_clearing_the_path_also_survives(cli, tmp_path):
    from app import agent_params
    v = tmp_path / "MiVault"
    v.mkdir()
    cli.post("/vault/vault-path", json={"path": str(v)})
    cli.post("/vault/vault-path", json={"path": ""})
    settings.obsidian_vault_path = str(v)
    agent_params.load_overrides(tmp_path / "overrides.json")
    assert settings.obsidian_vault_path == ""
