"""De «habla» hasta que suena: la cadena completa de la voz.

El síntoma que se persigue es siempre el mismo y nunca dice por qué: «configuré mi
voz y sigo oyendo la del navegador». Puede romperse en cuatro sitios distintos y
desde fuera se ven igual, así que aquí se fija cada eslabón por separado:

  ¿está anunciada como disponible?  ->  ¿/tts responde?  ->  ¿204 (ya sonó) o audio?
  ->  ¿un fallo se distingue de un silencio?

El 204 es el que más importa. Voicebox reproduce por las bocinas del Mac y no
devuelve el audio; si /tts contestara 200 con un cuerpo vacío, el navegador lo
tocaría encima y se oirían dos voces. Y si contestara error, la interfaz caería a
la voz del navegador cuando en realidad ya había sonado bien.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app import tts
from app.config import settings
from app.store import Store
from app.web import create_app


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "tts_provider", "voicebox")
    tts.state.update({"played_locally": False, "last_speak": ""})
    return TestClient(create_app(Store(tmp_path / "brain.db"), None, None, None))


def voicebox_falsa(monkeypatch, respuesta=None, revienta=False):
    """Sustituye la llamada a Voicebox. `respuesta` es lo que contestaría su MCP."""
    llamadas = []

    async def _fake(text):
        llamadas.append(text)
        if revienta:
            raise ConnectionError("Connection refused")
        # el camino real: habla por las bocinas y no devuelve audio
        tts.state["played_locally"] = True
        return None

    monkeypatch.setattr(tts, "_voicebox", _fake)
    return llamadas


# ------------------------------------------------- ¿se anuncia como disponible?

def test_with_voicebox_chosen_the_app_says_the_voice_is_ready(cli):
    """`tts_server` es lo que hace que la interfaz NO use la del navegador.
    Si esto es falso, da igual lo bien configurado que esté todo lo demás."""
    assert tts.available() is True


def test_the_browser_voice_is_a_deliberate_choice_not_a_failure(cli, monkeypatch):
    monkeypatch.setattr(settings, "tts_provider", "")
    assert tts.available() is False


# ------------------------------------------------------------- /tts responde

def test_when_voicebox_speaks_the_browser_must_not_repeat_it(cli, monkeypatch):
    """204 y sin cuerpo. Con 200 y cuerpo vacío se oiría doble."""
    llamadas = voicebox_falsa(monkeypatch)
    r = cli.post("/tts", content="hola".encode())
    assert r.status_code == 204
    assert not r.content
    assert llamadas == ["hola"]


def test_if_voicebox_is_closed_it_says_so_instead_of_going_quiet(cli, monkeypatch):
    """Un 503 con motivo es lo que dispara el aviso y el intento de abrirla.
    Un 204 aquí sería el peor caso: silencio absoluto sin explicación."""
    voicebox_falsa(monkeypatch, revienta=True)
    r = cli.post("/tts", content="hola".encode())
    assert r.status_code == 503
    assert r.status_code != 204


def test_the_reason_travels_so_it_can_be_shown(cli, monkeypatch):
    voicebox_falsa(monkeypatch, revienta=True)
    r = cli.post("/tts", content="hola".encode())
    assert "refused" in r.text.lower() or "excepcion" in r.text.lower()


def test_empty_text_does_not_wake_voicebox(cli, monkeypatch):
    llamadas = voicebox_falsa(monkeypatch)
    cli.post("/tts", content="   ".encode())
    assert llamadas == []


# --------------------------------------------------------- abrir la app sola

def test_the_start_endpoint_exists_and_answers(cli):
    """La interfaz lo llama sola al encender la voz. Si no existiera, el arranque
    automático fallaría en silencio y volveríamos a «ve a abrirla a mano»."""
    r = cli.post("/voice/local/start")
    assert r.status_code in (200, 400)          # 400 = no está instalada aquí
    assert "ok" in r.json()


def test_the_status_endpoint_says_if_it_is_running(cli):
    d = cli.get("/voice/local").json()
    assert d["ok"] and "running" in d and d["provider"] == "voicebox"


# ------------------------------------------------------------- diagnóstico

def test_the_diagnosis_points_at_the_app_when_it_is_closed(cli, monkeypatch):
    """/tts/health es lo que se mira cuando «no usa mi voz». Tiene que decir
    cuál de los dos falla, no un ok/ko a secas."""
    async def sin_app():
        return None
    monkeypatch.setattr(tts, "voicebox_profiles", sin_app)
    d = cli.get("/tts/health").json()
    assert d["ok"] is False
    assert "voicebox" in json.dumps(d).lower()
    assert "abrela" in json.dumps(d).lower() or "ábrela" in json.dumps(d).lower()


def test_a_profile_that_does_not_exist_is_named(cli, monkeypatch):
    """Elegir «Jarvis 2» y que Voicebox solo tenga «Jarvis» es un fallo real y
    silencioso: habla, pero con otra voz."""
    async def perfiles():
        return [{"name": "Jarvis", "language": "es"}]
    monkeypatch.setattr(tts, "voicebox_profiles", perfiles)
    monkeypatch.setattr(settings, "voicebox_profile", "Jarvis 2")
    d = cli.get("/tts/health").json()
    assert d["ok"] is False
    assert "Jarvis 2" in d["error"] and "Jarvis" in d["error"]
