"""Los oídos: que lo que llegue al cerebro sea lo que dijiste.

El fallo caro de esto no es que falle la transcripción — eso se ve. Es que Whisper
NO devuelve vacío ante el silencio: se inventa una frase de las que salían en los
vídeos con los que se entrenó. Sueltas el botón sin querer, no dices nada, y el
sistema recibe "Gracias por ver el video" como si lo hubieras dicho tú. Eso acaba
en una nota fantasma en la memoria, y ahí ya no hay forma de distinguirla de una
que escribiste tú.
"""
import asyncio

import pytest

from app import stt
from app.config import settings


@pytest.fixture(autouse=True)
def voicebox(monkeypatch):
    monkeypatch.setattr(settings, "tts_provider", "voicebox")
    monkeypatch.setattr(settings, "stt_enabled", True)
    monkeypatch.setattr(settings, "voicebox_url", "http://127.0.0.1:17493")


AUDIO = b"\x00" * 5000


def respuesta(monkeypatch, cuerpo, status=200, visto=None):
    class R:
        status_code = status

        def raise_for_status(self):
            if status >= 400:
                raise RuntimeError(f"http {status}")

        def json(self):
            if isinstance(cuerpo, (dict, list)):
                return cuerpo
            raise ValueError("no es json")

        @property
        def text(self):
            return cuerpo if isinstance(cuerpo, str) else ""

    class Http:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **kw):
            if visto is not None:
                visto.update({"url": url, **kw})
            return R()

    monkeypatch.setattr(stt.httpx, "AsyncClient", lambda **k: Http())


# ------------------------------------------------- lo que Whisper se inventa

@pytest.mark.parametrize("frase", [
    "Subtítulos realizados por la comunidad de Amara.org",
    "Gracias por ver el video",
    "¡Gracias!",
    "you",
    "Thanks for watching!",
    "...",
])
def test_whisper_hallucinations_never_reach_the_system(monkeypatch, frase):
    """EL fallo. Ninguna de estas la dijo nadie: son residuos del entrenamiento."""
    respuesta(monkeypatch, {"text": frase})
    r = asyncio.run(stt.transcribe(AUDIO, ms=2000))
    assert r["ok"] is False and r["text"] == ""


def test_the_discard_is_explained_not_silent(monkeypatch):
    """Descartar sin decir nada se ve igual que un micro roto."""
    respuesta(monkeypatch, {"text": "Gracias por ver el video"})
    r = asyncio.run(stt.transcribe(AUDIO, ms=2000))
    assert "no se entendió" in r["error"]


def test_a_real_sentence_that_starts_like_one_is_kept(monkeypatch):
    """El residuo siempre viene solo. Una frase de verdad no se toca aunque empiece
    con la misma palabra, o el filtro se comería lo que sí dijiste."""
    respuesta(monkeypatch, {"text": "Gracias, ahora dime cómo va el oro esta mañana"})
    r = asyncio.run(stt.transcribe(AUDIO, ms=3000))
    assert r["ok"] is True and "oro" in r["text"]


def test_a_short_real_command_still_gets_through(monkeypatch):
    respuesta(monkeypatch, {"text": "cierra el oro"})
    assert asyncio.run(stt.transcribe(AUDIO, ms=1500))["ok"] is True


@pytest.mark.parametrize("frase", ["sí", "no", "Sí.", "No"])
def test_yes_and_no_are_never_filtered(monkeypatch, frase):
    """Son las dos respuestas que más falta hace que lleguen enteras. Perder un
    "gracias" da igual; perder un "no" delante de una confirmación, no."""
    respuesta(monkeypatch, {"text": frase})
    assert asyncio.run(stt.transcribe(AUDIO, ms=800))["ok"] is True


# ------------------------------------------------------- grabaciones vacías

def test_a_click_is_not_sent_to_be_transcribed(monkeypatch):
    """Un clic sin voz es justo la entrada con la que Whisper alucina. Se corta antes."""
    visto = {}
    respuesta(monkeypatch, {"text": "lo que sea"}, visto=visto)
    r = asyncio.run(stt.transcribe(b"\x00" * 50, ms=100))
    assert r["ok"] is False and visto == {}, "se mandó a transcribir una grabación vacía"


def test_the_empty_recording_says_what_to_do(monkeypatch):
    respuesta(monkeypatch, {"text": "x"})
    r = asyncio.run(stt.transcribe(b"", ms=0))
    assert "mantén pulsado" in r["error"]


# ------------------------------------------------ formas de la respuesta

@pytest.mark.parametrize("cuerpo", [
    {"text": "cómo va el oro"},
    {"transcript": "cómo va el oro"},
    {"result": {"text": "cómo va el oro"}},
    {"data": [{"text": "cómo va el oro"}]},
    "cómo va el oro",
])
def test_the_text_is_found_whatever_shape_it_comes_in(monkeypatch, cuerpo):
    """La forma exacta cambia entre versiones de Voicebox; no quiero que una
    actualización suya deje los oídos mudos sin decir por qué."""
    respuesta(monkeypatch, cuerpo)
    assert asyncio.run(stt.transcribe(AUDIO, ms=2000))["text"] == "cómo va el oro"


def test_the_audio_goes_as_a_file_with_the_model(monkeypatch):
    visto = {}
    respuesta(monkeypatch, {"text": "hola que tal amigo"}, visto=visto)
    asyncio.run(stt.transcribe(AUDIO, ms=2000))
    assert visto["url"].endswith("/transcribe")
    assert visto["files"]["audio"][1] == AUDIO
    assert visto["data"]["model"] == settings.stt_model


# --------------------------------------------------------------- fallos

def test_an_old_voicebox_is_told_to_update(monkeypatch):
    """404 aquí significa una cosa concreta: su Voicebox es anterior a /transcribe."""
    respuesta(monkeypatch, {}, status=404)
    r = asyncio.run(stt.transcribe(AUDIO, ms=2000))
    assert r["ok"] is False and "actualízala" in r["error"]


def test_voicebox_closed_does_not_raise(monkeypatch):
    class Http:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise ConnectionError("connection refused")
    monkeypatch.setattr(stt.httpx, "AsyncClient", lambda **k: Http())
    r = asyncio.run(stt.transcribe(AUDIO, ms=2000))
    assert r["ok"] is False and "Voicebox" in r["error"]


def test_without_voicebox_the_ears_say_so(monkeypatch):
    monkeypatch.setattr(settings, "tts_provider", "")
    assert stt.available() is False
    r = asyncio.run(stt.transcribe(AUDIO, ms=2000))
    assert "Voicebox" in r["error"]


def test_the_mic_can_be_turned_off(monkeypatch):
    monkeypatch.setattr(settings, "stt_enabled", False)
    assert stt.available() is False
