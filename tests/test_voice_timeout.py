"""Que «Probar mi voz» conteste SIEMPRE, aunque Voicebox se quede colgada.

El fallo era este: Voicebox acepta la petición, empieza a hablar, y luego no cierra
el stream de estado. El cliente tenía 120 s de paciencia y ninguna de las dos partes
tenía tope propio, así que el botón se quedaba en «Probando…» y parecía que la app
se había muerto. Un diagnóstico que se cuelga es peor que no tener diagnóstico:
mientras esperas no puedes saber si el problema es la voz o la app entera.
"""
import asyncio
import time

import pytest

from app import tts
from app.config import settings


@pytest.fixture(autouse=True)
def voicebox(monkeypatch):
    monkeypatch.setattr(settings, "tts_provider", "voicebox")
    monkeypatch.setattr(settings, "voicebox_profile", "Jarvis")
    tts._last_error = ""
    tts.state.update({"played_locally": False, "last_speak": ""})


def perfiles_ok(monkeypatch):
    async def _p():
        return [{"name": "Jarvis", "language": "es"}]
    monkeypatch.setattr(tts, "voicebox_profiles", _p)


def test_the_diagnosis_answers_even_if_synth_never_returns(monkeypatch):
    """EL caso. Antes se esperaba hasta dos minutos; ahora contesta y dice qué hacer."""
    perfiles_ok(monkeypatch)
    monkeypatch.setattr(tts, "_DIAG_MAX", 0.4)

    async def colgada(_text):
        await asyncio.sleep(30)
    monkeypatch.setattr(tts, "synth", colgada)

    t0 = time.time()
    d = asyncio.run(tts.diagnose())
    assert time.time() - t0 < 5, "se quedó esperando"
    assert d["ok"] is False
    assert "no contestó" in d["error"]


def test_the_timeout_message_says_what_to_do(monkeypatch):
    """«Se acabó el tiempo» no ayuda a nadie; «ciérrala y ábrela» sí."""
    perfiles_ok(monkeypatch)
    monkeypatch.setattr(tts, "_DIAG_MAX", 0.3)

    async def colgada(_text):
        await asyncio.sleep(30)
    monkeypatch.setattr(tts, "synth", colgada)

    d = asyncio.run(tts.diagnose())
    assert "ciérrala" in d["error"].lower() or "abrirla" in d["error"].lower()


def test_a_normal_answer_is_not_slowed_down(monkeypatch):
    """El tope no puede añadir espera cuando todo va bien."""
    perfiles_ok(monkeypatch)

    async def rapida(_text):
        tts.state["played_locally"] = True
        return None
    monkeypatch.setattr(tts, "synth", rapida)

    t0 = time.time()
    d = asyncio.run(tts.diagnose())
    assert time.time() - t0 < 1
    assert d["ok"] is True and d["sono_en_el_mac"] is True


def test_a_hung_status_stream_does_not_hang_the_speech(monkeypatch):
    """Si el stream de estado no cierra, se sigue igual: a esas alturas Voicebox YA
    está hablando por las bocinas — lo que falta es el aviso de que terminó, y eso
    no cambia nada de lo que se oye. Se recorre el camino REAL de _voicebox."""
    monkeypatch.setattr(tts, "_POLL_MAX", 0.4)

    class Respuesta:
        url = "http://x/mcp"
        headers: dict = {}
        text = ('data: {"jsonrpc":"2.0","id":1,"result":{"content":'
                '[{"type":"text","text":"{\\"generation_id\\": \\"abc\\"}"}]}}')

        def raise_for_status(self):
            return None

    class StreamColgado:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def aiter_lines(self):
            await asyncio.sleep(30)      # nunca manda el estado final
            yield "data: {}"

    class HttpFalso:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return Respuesta()

        def stream(self, *a, **k):
            return StreamColgado()

    monkeypatch.setattr(tts.httpx, "AsyncClient", lambda **k: HttpFalso())

    t0 = time.time()
    out = asyncio.run(tts._voicebox("hola"))
    tardo = time.time() - t0

    assert tardo < 5, f"se colgó esperando el estado ({tardo:.1f}s)"
    assert out is None                            # nunca devuelve audio: ya sonó
    assert tts.state["played_locally"] is True, "se dio por fallida habiendo hablado"
    assert tts.last_error() == "", "un stream que no cierra no es un error de voz"


def test_the_caps_are_far_apart_so_they_do_not_fight():
    """El del stream tiene que ser bastante menor que el del diagnóstico: si no, el
    de fuera salta primero y se pierde el mensaje bueno del de dentro."""
    assert tts._POLL_MAX < tts._DIAG_MAX
    assert tts._DIAG_MAX < settings.voicebox_timeout_s
