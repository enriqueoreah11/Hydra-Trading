"""Thin wrapper around the Anthropic API used by every agent."""
from __future__ import annotations

import json
import logging
import re

from anthropic import AsyncAnthropic

from .config import settings

log = logging.getLogger("llm")

_client: AsyncAnthropic | None = None
_client_key: str = ""


def client() -> AsyncAnthropic:
    """Cliente de Anthropic, recreado si la clave cambia.

    Se guarda con qué clave se construyó: si la pones desde el panel después del
    primer uso, el cliente cacheado seguiría con la vieja (o sin ninguna) y todo
    fallaría con un error de autenticación que no lleva a ninguna parte.
    """
    global _client, _client_key
    key = (settings.anthropic_api_key or "").strip()
    if _client is None or _client_key != key:
        _client = AsyncAnthropic(api_key=key or None)
        _client_key = key
    return _client


_LANG = {
    "es": "Escribe TODO el texto libre (tesis, razones, resúmenes) en español.",
    "en": "Write ALL free text (thesis, reasons, summaries) in English.",
    "mix": "Escribe el texto libre en español, pero mantén los términos técnicos de "
           "trading en inglés (buy, sell, breakout, pullback, stop loss, take profit, etc.).",
}


_THINK_TAG = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def _clean(text: str) -> str:
    """Quita el razonamiento que los modelos tipo Qwen3 escriben en <think>…</think>.

    Sin esto, un modelo pensante rompe json.loads(): el JSON viene precedido de
    su cadena de pensamiento. Ollama suele separarlo en `message.thinking`, pero
    no siempre, así que lo limpiamos también aquí.
    """
    return _THINK_TAG.sub("", text or "").strip()


async def _ask_ollama(system: str, user: str, schema: dict | None,
                      max_tokens: int) -> dict | str:
    """Modelo LOCAL vía Ollama: inferencia gratis e ilimitada, sin API key.

    Esto es lo que permite revisar cada lote de operaciones sin que cueste nada,
    que es la única forma de que un ciclo de auto-corrección sea sostenible.
    """
    import httpx

    payload: dict = {
        "model": settings.ollama_model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            # CRÍTICO: sin num_ctx explícito, Ollama usa una ventana corta y
            # RECORTA EN SILENCIO el principio del prompt. El agente recibiría
            # el playbook a medias sin ningún error visible.
            "num_ctx": settings.ollama_num_ctx,
        },
        # los modelos pensantes (Qwen3) razonan antes de responder; para una
        # salida estructurada solo estorba y se come el presupuesto de tokens
        "think": False,
    }
    if schema is not None:
        payload["format"] = schema        # Ollama valida contra el JSON Schema
    url = settings.ollama_url.rstrip("/") + "/api/chat"
    async with httpx.AsyncClient(timeout=settings.ollama_timeout_s) as cli:
        r = await cli.post(url, json=payload)
        if r.status_code == 400 and "think" in r.text.lower():
            payload.pop("think", None)     # Ollama viejo: no conoce el parámetro
            r = await cli.post(url, json=payload)
        if r.status_code == 404:
            raise RuntimeError(
                f"Ollama no tiene el modelo '{settings.ollama_model}'. "
                f"Descárgalo con:  ollama pull {settings.ollama_model}")
        r.raise_for_status()
        data = r.json()
    text = _clean((data.get("message") or {}).get("content", ""))
    if schema is not None:
        if not text:
            raise RuntimeError("Ollama devolvió una respuesta vacía "
                               "(¿num_predict muy bajo o modelo sin soporte de schema?)")
        return json.loads(text)
    return text


# Cuántas veces se ha tenido que tirar de Claude porque el cerebro local no estaba.
# Se CUENTA a propósito: el modo híbrido se elige para no gastar, así que si acaba
# gastando hay que poder verlo, no enterarse en la factura.
fallbacks: dict = {"n": 0, "last": "", "last_role": "", "last_ts": 0.0}


async def ask(system: str, user: str, schema: dict | None = None,
              max_tokens: int = 8000, role: str = "") -> dict | str:
    """One-shot call. With `schema`, the response is schema-validated JSON.

    `role` es la clave del agente que llama (analyst, reviewer, architect…). En
    modo híbrido decide qué cerebro le toca: local para el volumen, Claude para
    el juicio. Ver Settings.brain_for().

    Si el cerebro local no responde (Ollama cerrado, el Mac dormido, el modelo sin
    descargar) NO se cae la llamada: se sigue con Claude. Un analista que deja de
    analizar es peor que un análisis que cuesta unos centavos — pero se cuenta en
    `fallbacks` y se ve en la app, porque el híbrido se eligió para no gastar.
    """
    lang = _LANG.get(settings.owner_lang, _LANG["mix"])
    if settings.brain_for(role) == "ollama":
        try:
            return await _ask_ollama(lang + "\n\n" + system, user, schema, max_tokens)
        except Exception as exc:  # noqa: BLE001 - da igual por qué; lo que importa es seguir
            import time as _t

            if not (settings.anthropic_api_key or "").strip():
                # sin Claude detrás no hay a dónde caer: se dice qué falta de verdad
                raise RuntimeError(
                    f"el cerebro local no respondió ({str(exc)[:120]}) y no hay "
                    "ANTHROPIC_API_KEY para continuar") from None
            fallbacks.update({"n": fallbacks["n"] + 1, "last": str(exc)[:160],
                              "last_role": role, "last_ts": _t.time()})
            log.warning("cerebro local caído en %s (%s): sigo con Claude",
                        role or "?", str(exc)[:120])
    kwargs: dict = {
        "model": settings.model,
        "max_tokens": max_tokens,
        "system": lang + "\n\n" + system,
        "thinking": {"type": "adaptive"},
        "messages": [{"role": "user", "content": user}],
    }
    if schema is not None:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}

    resp = await client().messages.create(**kwargs)
    if resp.stop_reason == "refusal":
        raise RuntimeError("model refused the request")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    if schema is not None:
        return json.loads(text)
    return text
