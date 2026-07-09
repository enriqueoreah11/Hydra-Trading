"""Text-to-speech neural por servidor (voz natural tipo Claude).

Soporta OpenAI (voz 'onyx' masculina) y ElevenLabs. Devuelve audio MP3.
Si no hay proveedor/clave configurados, devuelve None y la UI usa la voz del navegador.
"""
from __future__ import annotations

import logging

import httpx

from .config import settings

log = logging.getLogger("tts")


def available() -> bool:
    return bool(settings.tts_provider and settings.tts_api_key
                and (settings.tts_provider != "elevenlabs" or settings.elevenlabs_voice_id))


async def synth(text: str) -> bytes | None:
    if not available():
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
                r.raise_for_status()
                return r.content
        if provider == "elevenlabs":
            async with httpx.AsyncClient(timeout=40) as http:
                r = await http.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}",
                    headers={"xi-api-key": settings.tts_api_key, "accept": "audio/mpeg"},
                    json={"text": text, "model_id": settings.elevenlabs_model,
                          "voice_settings": {"stability": 0.4, "similarity_boost": 0.8}})
                r.raise_for_status()
                return r.content
    except Exception:  # noqa: BLE001 - si falla, la UI cae a la voz del navegador
        log.warning("tts synth failed", exc_info=True)
    return None
