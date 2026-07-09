"""Notificador por Telegram. Si no hay token configurado, no hace nada (no-op).

Crear el bot: habla con @BotFather en Telegram -> /newbot -> copia el token en
TELEGRAM_BOT_TOKEN. Para tu chat id: habla con @userinfobot (o envia un mensaje
a tu bot y consulta https://api.telegram.org/bot<token>/getUpdates) y pon el id
en TELEGRAM_CHAT_ID.
"""
from __future__ import annotations

import logging

import httpx

from .config import settings

log = logging.getLogger("notifier")


class Notifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)

    async def send(self, text: str) -> None:
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=15) as http:
                await http.post(url, json={
                    "chat_id": self.chat_id,
                    "text": text[:4000],
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                })
        except Exception:  # noqa: BLE001 - nunca dejar que una notificacion tumbe el sistema
            log.warning("telegram notification failed", exc_info=True)


notifier = Notifier(settings.telegram_bot_token, settings.telegram_chat_id)
