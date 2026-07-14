"""Async cTrader Open API client over WebSocket using the JSON protocol.

Envelope: {"clientMsgId": "...", "payloadType": <int>, "payload": {...}}
Endpoint: wss://demo.ctraderapi.com:5036 / wss://live.ctraderapi.com:5036
"""
from __future__ import annotations

import asyncio
import itertools
import json
import logging
from typing import Any, Awaitable, Callable

import websockets

from . import constants as c

log = logging.getLogger("ctrader")

HEARTBEAT_SECONDS = 10
REQUEST_TIMEOUT = 20


class CTraderError(Exception):
    def __init__(self, error_code: str, description: str = ""):
        self.error_code = error_code
        self.description = description
        super().__init__(f"{error_code}: {description}")


class CTraderClient:
    """Maintains the connection, correlates requests/responses and dispatches events."""

    def __init__(
        self,
        ws_url: str,
        client_id: str,
        client_secret: str,
        account_id: int,
        access_token_provider: Callable[[], Awaitable[str]],
    ):
        self.ws_url = ws_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.account_id = account_id
        self.access_token_provider = access_token_provider

        self._ws: websockets.WebSocketClientProtocol | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._msg_counter = itertools.count(1)
        self._event_handlers: list[Callable[[int, dict], Awaitable[None]]] = []
        self._tasks: list[asyncio.Task] = []
        self._connected = asyncio.Event()
        self._stopping = False
        self.account_authorized = False

    # ------------------------------------------------------------------ public

    def on_event(self, handler: Callable[[int, dict], Awaitable[None]]) -> None:
        self._event_handlers.append(handler)

    async def start(self) -> None:
        """Connect and keep the connection alive forever (until stop()). Idempotente."""
        if self._tasks:
            return
        self._stopping = False
        self._tasks.append(asyncio.create_task(self._run(), name="ctrader-run"))

    async def stop(self) -> None:
        self._stopping = True
        for t in self._tasks:
            t.cancel()
        if self._ws:
            await self._ws.close()

    async def wait_connected(self, timeout: float = 60) -> None:
        await asyncio.wait_for(self._connected.wait(), timeout)

    async def send(self, payload_type: int, payload: dict | None = None,
                   timeout: float = REQUEST_TIMEOUT) -> dict:
        """Send a request and await the correlated response payload."""
        await self._connected.wait()
        assert self._ws is not None
        msg_id = f"m{next(self._msg_counter)}"
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = fut
        frame = {"clientMsgId": msg_id, "payloadType": payload_type, "payload": payload or {}}
        try:
            await self._ws.send(json.dumps(frame))
            return await asyncio.wait_for(fut, timeout)
        finally:
            self._pending.pop(msg_id, None)

    # ----------------------------------------------------------------- internal

    async def _run(self) -> None:
        backoff = 2
        while not self._stopping:
            try:
                log.info("connecting to %s", self.ws_url)
                async with websockets.connect(self.ws_url, max_size=16 * 1024 * 1024) as ws:
                    self._ws = ws
                    self._connected.set()
                    hb = asyncio.create_task(self._heartbeat())
                    try:
                        await self._authenticate()
                        backoff = 2
                        await self._read_loop(ws)
                    finally:
                        hb.cancel()
            except asyncio.CancelledError:
                return
            except Exception as e:  # noqa: BLE001 - reconnect on any transport error
                log.warning("connection lost (%s); reconnecting in %ss", e, backoff)
            self._connected.clear()
            self.account_authorized = False
            self._fail_pending(ConnectionError("connection lost"))
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

    async def _authenticate(self) -> None:
        await self._raw_request(c.APPLICATION_AUTH_REQ, {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
        })
        log.info("application authorized")
        if self.account_id:
            token = await self.access_token_provider()
            await self._raw_request(c.ACCOUNT_AUTH_REQ, {
                "ctidTraderAccountId": self.account_id,
                "accessToken": token,
            })
            self.account_authorized = True
            log.info("account %s authorized", self.account_id)

    async def _raw_request(self, payload_type: int, payload: dict) -> dict:
        """send() variant usable during authentication (connection already set)."""
        assert self._ws is not None
        msg_id = f"m{next(self._msg_counter)}"
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = fut
        await self._ws.send(json.dumps(
            {"clientMsgId": msg_id, "payloadType": payload_type, "payload": payload}))
        # responses are consumed here because _read_loop is not running yet
        while not fut.done():
            raw = await asyncio.wait_for(self._ws.recv(), REQUEST_TIMEOUT)
            self._handle_frame(raw)
        return fut.result()

    async def _read_loop(self, ws: websockets.WebSocketClientProtocol) -> None:
        async for raw in ws:
            self._handle_frame(raw)

    def _handle_frame(self, raw: str | bytes) -> None:
        try:
            frame = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("non-JSON frame ignored")
            return
        ptype = frame.get("payloadType")
        payload = frame.get("payload") or {}
        msg_id = frame.get("clientMsgId")

        if msg_id and msg_id in self._pending:
            fut = self._pending[msg_id]
            if not fut.done():
                if ptype in (c.PROTO_ERROR_RES, c.OA_ERROR_RES):
                    fut.set_exception(CTraderError(
                        payload.get("errorCode", "UNKNOWN"), payload.get("description", "")))
                else:
                    fut.set_result(payload)
            return

        if ptype == c.HEARTBEAT_EVENT:
            return
        # unsolicited event -> dispatch
        for handler in self._event_handlers:
            asyncio.get_running_loop().create_task(self._safe_dispatch(handler, ptype, payload))

    async def _safe_dispatch(self, handler, ptype: int, payload: dict) -> None:
        try:
            await handler(ptype, payload)
        except Exception:  # noqa: BLE001
            log.exception("event handler failed for payloadType=%s", ptype)

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            try:
                if self._ws:
                    await self._ws.send(json.dumps({"payloadType": c.HEARTBEAT_EVENT, "payload": {}}))
            except Exception:  # noqa: BLE001
                return

    def _fail_pending(self, exc: Exception) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()
