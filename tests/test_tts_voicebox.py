"""Voicebox: que Hydra no se rinda cuando la voz SÍ sonó.

El fallo que arreglan estas pruebas: si `voicebox.speak` contestaba sin un id de
generación, se devolvía error y la interfaz caía a la voz genérica del navegador.
Desde fuera se veía como «configuré mi voz y no la usa», cuando en realidad ya
había sonado por las bocinas.

Se falsea el cliente HTTP: no hace falta la app ni red.
"""
import asyncio
import json
import types

import pytest

from app import tts
from app.config import settings


class _Resp:
    def __init__(self, payload):
        self.text = json.dumps(payload)
        self.url = "http://127.0.0.1:17493/mcp"
        self.headers = {"Mcp-Session-Id": "s1"}

    def raise_for_status(self):
        pass


def _fake_client(payloads):
    class _C:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None, follow_redirects=None):
            return _Resp(payloads.pop(0))

        def stream(self, *a, **k):
            class _S:
                async def __aenter__(s):
                    return s

                async def __aexit__(s, *a):
                    return False

                async def aiter_lines(s):
                    yield 'data: {"status":"done"}'

            return _S()

    return lambda *a, **k: _C()


def _speak(reply, monkeypatch):
    monkeypatch.setattr(settings, "tts_provider", "voicebox")
    monkeypatch.setattr(settings, "voicebox_profile", "Jarvis")
    monkeypatch.setattr(tts, "httpx", types.SimpleNamespace(
        AsyncClient=_fake_client([{"result": {}}, reply])))
    tts.state["played_locally"] = False
    out = asyncio.run(tts.synth("hola"))
    return out, tts.state["played_locally"], tts.last_error()


def _text_reply(payload, is_error=False):
    res = {"content": [{"type": "text", "text": json.dumps(payload)}]}
    if is_error:
        res["isError"] = True
    return {"result": res}


def test_with_generation_id_it_waits_and_counts_as_played(monkeypatch):
    out, played, err = _speak(_text_reply({"generation_id": "g1"}), monkeypatch)
    assert out is None          # a propósito: lo reproduce Voicebox, no el navegador
    assert played is True
    assert err == ""


def test_without_id_but_no_error_it_still_counts_as_played(monkeypatch):
    """El caso del fallo: sin id NO se puede esperar, pero sí sonó."""
    out, played, err = _speak(_text_reply({"success": True}), monkeypatch)
    assert out is None
    assert played is True
    assert err == ""


def test_a_real_error_is_reported_and_not_faked(monkeypatch):
    reply = {"result": {"isError": True,
                        "content": [{"type": "text", "text": "unknown profile 'Jarvis'"}]}}
    out, played, err = _speak(reply, monkeypatch)
    assert out is None
    assert played is False              # aquí NO sonó nada: no se puede mentir
    assert "unknown profile" in err


def test_the_raw_reply_is_kept_for_diagnosis(monkeypatch):
    _speak(_text_reply({"success": True}), monkeypatch)
    assert "success" in tts.state.get("last_speak", "")


@pytest.mark.parametrize("provider", ["", "openai"])
def test_only_voicebox_plays_locally(provider, monkeypatch):
    monkeypatch.setattr(settings, "tts_provider", provider)
    monkeypatch.setattr(settings, "tts_api_key", "")
    tts.state["played_locally"] = False
    assert asyncio.run(tts.synth("hola")) is None
    assert tts.state["played_locally"] is False
