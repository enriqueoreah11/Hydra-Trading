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


async def ask(system: str, user: str, schema: dict | None = None,
              max_tokens: int = 8000) -> dict | str:
    """One-shot call. With `schema`, the response is schema-validated JSON."""
    kwargs: dict = {
        "model": settings.model,
        "max_tokens": max_tokens,
        "system": system,
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
