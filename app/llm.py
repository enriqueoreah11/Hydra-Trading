"""Thin wrapper around the Anthropic API used by every agent."""
from __future__ import annotations

import json
import logging

from anthropic import AsyncAnthropic

from .config import settings

log = logging.getLogger("llm")

_client: AsyncAnthropic | None = None


def client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key or None)
    return _client


_LANG = {
    "es": "Escribe TODO el texto libre (tesis, razones, resúmenes) en español.",
    "en": "Write ALL free text (thesis, reasons, summaries) in English.",
    "mix": "Escribe el texto libre en español, pero mantén los términos técnicos de "
           "trading en inglés (buy, sell, breakout, pullback, stop loss, take profit, etc.).",
}


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
        "options": {"num_predict": max_tokens},
    }
    if schema is not None:
        payload["format"] = schema        # Ollama valida contra el JSON Schema
    url = settings.ollama_url.rstrip("/") + "/api/chat"
    async with httpx.AsyncClient(timeout=settings.ollama_timeout_s) as cli:
        r = await cli.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    text = (data.get("message") or {}).get("content", "")
    if schema is not None:
        return json.loads(text)
    return text


async def ask(system: str, user: str, schema: dict | None = None,
              max_tokens: int = 8000, role: str = "") -> dict | str:
    """One-shot call. With `schema`, the response is schema-validated JSON.

    `role` es la clave del agente que llama (analyst, reviewer, architect…). En
    modo híbrido decide qué cerebro le toca: local para el volumen, Claude para
    el juicio. Ver Settings.brain_for().
    """
    lang = _LANG.get(settings.owner_lang, _LANG["mix"])
    if settings.brain_for(role) == "ollama":
        return await _ask_ollama(lang + "\n\n" + system, user, schema, max_tokens)
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
