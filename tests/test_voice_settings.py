"""Qué voz queda configurada al arrancar.

El fallo que se prueba aquí es mudo, literalmente: en el disco queda guardado un
proveedor de voz que ya no existe (el motor local que hubo un tiempo, o uno de pago
retirado), la app lo carga tal cual, `available()` dice que no y Hydra habla con la
voz del navegador sin explicar por qué. Nadie lo relaciona con un archivo viejo.
"""
import json

import pytest

from app import tts
from app.config import settings
from app.store import Store
from app.web import create_app


@pytest.fixture
def arranca(tmp_path, monkeypatch):
    """Arranca la app con un voice.json dado y devuelve el proveedor resultante."""
    def _go(guardado: dict | None, env_provider: str = "voicebox"):
        monkeypatch.setattr(settings, "data_dir", str(tmp_path))
        monkeypatch.setattr(settings, "tts_provider", env_provider)
        monkeypatch.setattr(settings, "voicebox_profile", "Jarvis")
        f = tmp_path / "voice.json"
        if guardado is None:
            f.unlink(missing_ok=True)
        else:
            f.write_text(json.dumps(guardado))
        create_app(Store(tmp_path / "brain.db"), None, None, None)
        return settings.tts_provider
    return _go


def test_a_retired_provider_does_not_leave_hydra_mute(arranca):
    """Es el caso real: quedó guardado el motor local que ya se quitó."""
    assert arranca({"provider": "local", "profile": "Jarvis 2"}) == "voicebox"
    assert tts.available(), "sin voz por un ajuste huérfano"


def test_the_chosen_profile_survives_the_change_of_provider(arranca):
    """Cambiar de proveedor no puede tirar el perfil que eligió el usuario."""
    arranca({"provider": "local", "profile": "Jarvis 2"})
    assert settings.voicebox_profile == "Jarvis 2"


def test_a_retired_provider_in_the_env_is_also_ignored(arranca):
    """Puede venir del .env, no solo del archivo: el mismo silencio."""
    assert arranca(None, env_provider="elevenlabs") == "voicebox"
    assert arranca(None, env_provider="local") == "voicebox"


def test_choosing_the_browser_voice_on_purpose_is_respected(arranca):
    """Cadena vacía = voz del navegador, y es una elección legítima, no un error."""
    assert arranca({"provider": ""}) == ""


def test_voicebox_stays_voicebox(arranca):
    assert arranca({"provider": "voicebox", "profile": "Jarvis"}) == "voicebox"


def test_a_corrupt_file_does_not_stop_the_app(arranca, tmp_path, monkeypatch):
    """Un JSON a medias (disco lleno, cierre en mitad de la escritura) no puede
    impedir arrancar: se ignora y se sigue con lo que hubiera."""
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "tts_provider", "voicebox")
    (tmp_path / "voice.json").write_text('{"provider": "voice')
    create_app(Store(tmp_path / "brain.db"), None, None, None)
    assert settings.tts_provider == "voicebox"


def test_the_endpoint_refuses_a_provider_that_no_longer_exists(tmp_path, monkeypatch):
    """Y no se puede volver a meter desde fuera: el que ya no existe se rechaza."""
    from fastapi.testclient import TestClient
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    cli = TestClient(create_app(Store(tmp_path / "brain.db"), None, None, None))
    assert cli.post("/voice/local", json={"provider": "local"}).status_code == 400
    assert cli.post("/voice/local", json={"provider": "voicebox"}).status_code == 200
