"""Investigación web con Perplexity (noticias y contexto de mercado).

Usa el modelo `sonar` (el económico) de la API de Perplexity. Los hallazgos se
guardan en la memoria (vault) para que no se pierdan.
"""
from __future__ import annotations

import logging

import httpx

from .config import settings

log = logging.getLogger("research")

_URL = "https://api.perplexity.ai/chat/completions"


def available() -> bool:
    return bool(settings.perplexity_api_key)


async def ask(query: str, system: str | None = None) -> dict:
    """Pregunta a Perplexity. Devuelve {'text': ..., 'citations': [...]}"""
    if not available():
        raise RuntimeError("falta PERPLEXITY_API_KEY (ponla en Sistema → claves o en Fly)")
    sys_msg = system or ("Eres el investigador de un sistema de trading. Responde en español, "
                         "conciso y accionable, con datos y fechas concretas. Términos de "
                         "trading en inglés.")
    payload = {
        "model": settings.perplexity_model,
        "messages": [{"role": "system", "content": sys_msg},
                     {"role": "user", "content": query}],
        "max_tokens": 900,
    }
    headers = {"Authorization": f"Bearer {settings.perplexity_api_key}"}
    async with httpx.AsyncClient(timeout=45) as cli:
        r = await cli.post(_URL, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    cites = data.get("citations") or []
    return {"text": text, "citations": cites}


async def market_brief(symbols: list[str]) -> dict:
    """Brief diario: qué mueve hoy a los instrumentos del portafolio."""
    q = ("Resumen de HOY para un trader intradía sobre estos instrumentos: "
         + ", ".join(symbols) +
         ". Incluye: 1) drivers macro del día (datos, bancos centrales, geopolítica), "
         "2) sesgo actual por instrumento en una línea, 3) eventos de riesgo próximos "
         "con hora UTC. Máximo 300 palabras.")
    return await ask(q)
