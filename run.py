"""Entry point: runs the web dashboard + the brain in one asyncio loop.

    python run.py
"""
from __future__ import annotations

import asyncio
import logging
import os

import uvicorn

from app.broker import Broker
from app.config import settings
from app.ctrader import CTraderClient
from app.oauth import TokenStore
from app.orchestrator import Brain
from app.store import Store
from app.web import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("main")


async def main() -> None:
    data = settings.data_path
    store = Store(data / "brain.db")
    tokens = TokenStore(data / "tokens.json", settings.ctrader_client_id,
                        settings.ctrader_client_secret, settings.ctrader_redirect_uri)

    client = CTraderClient(
        ws_url=settings.ws_url,
        client_id=settings.ctrader_client_id,
        client_secret=settings.ctrader_client_secret,
        account_id=settings.ctrader_account_id,
        access_token_provider=tokens.get_access_token,
    )
    broker = Broker(client, settings.ctrader_account_id)
    brain = Brain(broker, store)

    app = create_app(store, tokens, broker, brain=brain)
    # Fly.io / Railway / Render inyectan el puerto via $PORT; respetalo si existe.
    port = int(os.getenv("PORT", str(settings.web_port)))
    log.info("web escuchando en %s:%s", settings.web_host, port)
    server = uvicorn.Server(uvicorn.Config(
        app, host=settings.web_host, port=port, log_level="info"))

    tasks = [asyncio.create_task(server.serve(), name="web")]

    if settings.ctrader_client_id and tokens.has_tokens:
        # abre la conexion + auth de app aunque falte account_id (permite listar/elegir cuenta).
        # el cerebro lo arranca el evento startup de la app (o el selector de cuenta en la UI).
        await client.start()
        if not settings.ctrader_account_id:
            log.warning("conexion cTrader lista (app), pero falta cuenta: eligela en ⚙ Sistema o /accounts.")
    else:
        log.warning(
            "brain idle: falta configuracion. Pasos: 1) define CTRADER_CLIENT_ID/SECRET, "
            "2) visita /oauth/login para autorizar tu cuenta, 3) define CTRADER_ACCOUNT_ID "
            "y reinicia. El dashboard web ya esta disponible.")

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
