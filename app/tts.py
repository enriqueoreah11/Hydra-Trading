"""Text-to-speech neural por servidor (voz natural tipo Claude).

Soporta OpenAI (voz 'onyx' masculina) y ElevenLabs. Devuelve audio MP3.
Si no hay proveedor/clave configurados, devuelve None y la UI usa la voz del navegador.
"""
from __future__ import annotations

import logging

import httpx

from .config import settings

log = logging.getLogger("tts")

# Guardamos el ultimo error para poder diagnosticar por que se cae a la voz del navegador.
_last_error: str = ""


def available() -> bool:
    return bool(settings.tts_provider and settings.tts_api_key
                and (settings.tts_provider != "elevenlabs" or settings.elevenlabs_voice_id))


def last_error() -> str:
    return _last_error


async def synth(text: str) -> bytes | None:
    global _last_error
    if not available():
        _last_error = "no configurado (faltan TTS_PROVIDER / TTS_API_KEY / ELEVENLABS_VOICE_ID)"
        return None
    text = (text or "").strip()[:2000]
    if not text:
        return None
    provider = settings.tts_provider.lower()
    try:
        if provider == "openai":
            async with httpx.AsyncClient(timeout=40) as http:
                r = await http.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers={"Authorization": f"Bearer {settings.tts_api_key}"},
                    json={"model": settings.openai_tts_model, "voice": settings.openai_tts_voice,
                          "input": text, "speed": settings.tts_speed, "response_format": "mp3"})
                if r.status_code != 200:
                    _last_error = f"OpenAI {r.status_code}: {r.text[:200]}"
                    return None
                _last_error = ""
                return r.content
        if provider == "elevenlabs":
            async with httpx.AsyncClient(timeout=40) as http:
                r = await http.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}",
                    headers={"xi-api-key": settings.tts_api_key, "accept": "audio/mpeg"},
                    json={"text": text, "model_id": settings.elevenlabs_model,
                          "voice_settings": {"stability": 0.4, "similarity_boost": 0.8}})
                if r.status_code != 200:
                    _last_error = f"ElevenLabs {r.status_code}: {r.text[:220]}"
                    log.warning("tts elevenlabs error: %s", _last_error)
                    return None
                _last_error = ""
                return r.content
        _last_error = f"proveedor desconocido: {provider}"
    except Exception as exc:  # noqa: BLE001 - si falla, la UI cae a la voz del navegador
        _last_error = f"excepcion: {type(exc).__name__}: {str(exc)[:180]}"
        log.warning("tts synth failed: %s", _last_error)
    return None


async def diagnose() -> dict:
    """Estado del TTS neural: configuracion + una prueba real (sin exponer la clave)."""
    info = {
        "configured": available(),
        "provider": settings.tts_provider or "(vacio)",
        "api_key_set": bool(settings.tts_api_key),
        "voice_id_set": bool(settings.elevenlabs_voice_id),
        "voice_id": settings.elevenlabs_voice_id or settings.openai_tts_voice,
    }
    if not available():
        info["ok"] = False
        info["error"] = ("no configurado — pon los secrets TTS_PROVIDER, TTS_API_KEY"
                         " y (para ElevenLabs) ELEVENLABS_VOICE_ID, luego redespliega.")
        return info
    audio = await synth("prueba de voz")
    info["ok"] = bool(audio)
    info["bytes"] = len(audio) if audio else 0
    info["error"] = "" if audio else _last_error
    return info
