"""Text-to-speech neural por servidor (voz natural tipo Claude).

Soporta OpenAI (voz 'onyx' masculina) y ElevenLabs. Devuelve audio MP3.
Si no hay proveedor/clave configurados, devuelve None y la UI usa la voz del navegador.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from urllib.parse import urljoin

import httpx

from .config import settings

log = logging.getLogger("tts")

# Guardamos el ultimo error para poder diagnosticar por que se cae a la voz del navegador.
_last_error: str = ""


def available() -> bool:
    if settings.tts_provider == "voicebox":
        return True                      # local: no necesita clave de nada
    return bool(settings.tts_provider and settings.tts_api_key
                and (settings.tts_provider != "elevenlabs" or settings.elevenlabs_voice_id))


def last_error() -> str:
    return _last_error


# ------------------------------------------------------- Voicebox (local)

async def _voicebox(text: str) -> bytes | None:
    """Voz local de Voicebox (Kokoro/Qwen3-TTS, sin API key ni internet).

    Voicebox reproduce el audio en las bocinas del Mac Y lo guarda. Si logramos
    recuperar el archivo, lo devolvemos para que lo toque el navegador (así el
    botón de silenciar sigue mandando). Si no, marcamos `played_locally` para
    que la UI NO caiga a la voz del navegador — si no, se oiría dos veces.
    """
    global _last_error
    state["played_locally"] = False
    base = settings.voicebox_url.rstrip("/")
    mcp = base + "/mcp"
    session: dict = {"id": None, "url": mcp}

    async def rpc(http: httpx.AsyncClient, method: str, params: dict | None = None):
        body: dict = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            body["params"] = params
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        if session["id"]:
            headers["Mcp-Session-Id"] = session["id"]
        # follow_redirects: los servidores MCP redirigen /mcp -> /mcp/
        r = await http.post(session["url"], json=body, headers=headers,
                            follow_redirects=True)
        session["url"] = str(r.url)
        if not session["id"]:
            session["id"] = r.headers.get("Mcp-Session-Id")
        r.raise_for_status()
        for line in r.text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                line = line[5:].strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        return {}

    def unwrap(res: dict) -> dict:
        out = (res or {}).get("result") or {}
        for block in out.get("content") or []:
            if block.get("type") == "text":
                try:
                    return json.loads(block.get("text") or "{}")
                except json.JSONDecodeError:
                    return {}
        return {}

    async with httpx.AsyncClient(timeout=settings.voicebox_timeout_s) as http:
        await rpc(http, "initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "hydra", "version": "1.0"}})
        args: dict = {"text": text}
        if settings.voicebox_profile:
            args["profile"] = settings.voicebox_profile
        spoken = unwrap(await rpc(http, "tools/call",
                                  {"name": "voicebox.speak", "arguments": args}))
        gen = spoken.get("generation_id") or spoken.get("id")
        if not gen:
            _last_error = f"Voicebox no devolvió id: {str(spoken)[:160]}"
            return None

        # El estado es un stream SSE; esperamos a que termine de generar.
        poll = urljoin(base + "/", (spoken.get("poll_url") or
                                    f"/generate/{gen}/status").lstrip("/"))
        try:
            async with http.stream("GET", poll,
                                   headers={"Accept": "text/event-stream"}) as r:
                async for line in r.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    try:
                        ev = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    st = str(ev.get("status") or "").lower()
                    if st in _TERMINAL:
                        if ev.get("error"):
                            _last_error = f"Voicebox: {str(ev['error'])[:160]}"
                            return None
                        break
        except Exception:  # noqa: BLE001 - el stream puede cortarse al terminar
            pass

        # ¿Podemos recuperar el archivo? (así lo toca el navegador y se puede silenciar)
        audio = await _voicebox_audio(http, base, gen)
        if audio:
            _last_error = ""
            return audio

    # No hubo forma de leerlo, pero YA SONÓ en las bocinas: no caigas al navegador.
    state["played_locally"] = True
    _last_error = ""
    return None


async def voicebox_profiles() -> list[dict] | None:
    """Perfiles de voz de Voicebox. None si la app no está abierta."""
    base = settings.voicebox_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=6) as http:
            headers = {"Content-Type": "application/json",
                       "Accept": "application/json, text/event-stream"}
            r = await http.post(base + "/mcp", follow_redirects=True, headers=headers,
                                json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                      "params": {"protocolVersion": "2025-06-18",
                                                 "capabilities": {},
                                                 "clientInfo": {"name": "hydra",
                                                                "version": "1.0"}}})
            r.raise_for_status()
            if r.headers.get("Mcp-Session-Id"):
                headers["Mcp-Session-Id"] = r.headers["Mcp-Session-Id"]
            r = await http.post(str(r.url), follow_redirects=True, headers=headers,
                                json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                      "params": {"name": "voicebox.list_profiles",
                                                 "arguments": {}}})
            r.raise_for_status()
            for line in r.text.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    line = line[5:].strip()
                if not line.startswith("{"):
                    continue
                res = json.loads(line).get("result") or {}
                for block in res.get("content") or []:
                    if block.get("type") == "text":
                        return json.loads(block["text"]).get("profiles") or []
    except Exception:  # noqa: BLE001 - app cerrada o versión distinta
        return None
    return None


async def _voicebox_audio(http: httpx.AsyncClient, base: str, gen: str) -> bytes | None:
    """Intenta leer el audio ya generado: primero por HTTP, luego desde Captures."""
    for path in (f"/generate/{gen}/audio", f"/captures/{gen}/audio", f"/audio/{gen}"):
        try:
            r = await http.get(base + path, follow_redirects=True)
            if r.status_code == 200 and (
                    r.headers.get("Content-Type", "").startswith("audio")
                    or len(r.content) > 4000):
                return r.content
        except Exception:  # noqa: BLE001
            continue
    # La app guarda cada generación en Captures; de ahí sacamos la ruta real.
    try:
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "voicebox.list_captures", "arguments": {"limit": 5}}}
        r = await http.post(base + "/mcp", json=body, follow_redirects=True,
                            headers={"Content-Type": "application/json",
                                     "Accept": "application/json, text/event-stream"})
        for m in re.finditer(r'([/\\][^"\\]*?\.(?:wav|mp3|m4a|ogg|flac))', r.text, re.I):
            p = Path(m.group(1).replace("\\/", "/"))
            if p.is_file() and p.stat().st_size > 1000:
                return p.read_bytes()
    except Exception:  # noqa: BLE001
        pass
    return None


_TERMINAL = {"done", "complete", "completed", "finished", "ready", "success",
             "error", "failed", "cancelled", "canceled"}
# played_locally: True cuando Voicebox ya lo reprodujo y no hay que repetirlo
state: dict = {"played_locally": False}


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
        if provider == "voicebox":
            return await _voicebox(text)
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
        "provider": settings.tts_provider or "(vacio: usa la voz del navegador)",
        "api_key_set": bool(settings.tts_api_key),
        "voice_id_set": bool(settings.elevenlabs_voice_id),
        "voice_id": settings.elevenlabs_voice_id or settings.openai_tts_voice,
    }
    if settings.tts_provider == "voicebox":
        # Local: no hay claves que revisar, solo si la app esta abierta.
        profiles = await voicebox_profiles()
        info.update({"url": settings.voicebox_url, "profile": settings.voicebox_profile,
                     "app_running": profiles is not None,
                     "profiles": [p.get("name") for p in (profiles or [])]})
        if profiles is None:
            info["ok"] = False
            info["error"] = ("la app Voicebox no responde — abrela desde /Applications "
                             "(el servidor corre dentro de ella).")
            return info
        names = [p.get("name") for p in profiles]
        if settings.voicebox_profile not in names:
            info["ok"] = False
            info["error"] = (f"el perfil '{settings.voicebox_profile}' no existe. "
                             f"Disponibles: {', '.join(map(str, names)) or '(ninguno)'}")
            return info
        audio = await synth("prueba de voz")
        info["ok"] = True
        info["bytes"] = len(audio) if audio else 0
        info["modo"] = ("audio al navegador (silenciar funciona)" if audio
                        else "suena en las bocinas del Mac (fuera del navegador)")
        info["error"] = _last_error
        return info
    if not available():
        info["ok"] = False
        info["error"] = ("sin proveedor de voz neural. En Sistema elige 'Voicebox' "
                         "(local y gratis) o configura TTS_PROVIDER / TTS_API_KEY.")
        return info
    audio = await synth("prueba de voz")
    info["ok"] = bool(audio)
    info["bytes"] = len(audio) if audio else 0
    info["error"] = "" if audio else _last_error
    return info
