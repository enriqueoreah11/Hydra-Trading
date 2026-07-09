"""cTrader OAuth2: authorization URL, code exchange, refresh, token persistence.

Flow: user visits the auth URL -> approves -> cTrader redirects to
CTRADER_REDIRECT_URI with ?code=... -> we exchange it at
https://openapi.ctrader.com/apps/token. Access tokens last ~30 days;
refresh tokens don't expire.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx

TOKEN_URL = "https://openapi.ctrader.com/apps/token"
AUTH_URL = "https://id.ctrader.com/my/settings/openapi/grantingaccess/"


def build_auth_url(client_id: str, redirect_uri: str, scope: str = "trading") -> str:
    return AUTH_URL + "?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "product": "web",
    })


class TokenStore:
    """Persists access/refresh tokens as JSON on the data volume."""

    def __init__(self, path: Path, client_id: str, client_secret: str, redirect_uri: str):
        self.path = path
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._data: dict = {}
        if path.exists():
            self._data = json.loads(path.read_text())

    @property
    def has_tokens(self) -> bool:
        return bool(self._data.get("access_token"))

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2))

    def _store_response(self, body: dict) -> None:
        # the endpoint has returned both snake_case and camelCase historically
        access = body.get("access_token") or body.get("accessToken")
        refresh = body.get("refresh_token") or body.get("refreshToken")
        expires_in = body.get("expires_in") or body.get("expiresIn") or 2_628_000
        if not access:
            raise RuntimeError(f"token endpoint returned no access token: {body}")
        self._data = {
            "access_token": access,
            "refresh_token": refresh,
            "expires_at": time.time() + float(expires_in),
        }
        self._save()

    async def exchange_code(self, code: str) -> None:
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(TOKEN_URL, data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            })
            r.raise_for_status()
            self._store_response(r.json())

    async def refresh(self) -> None:
        refresh_token = self._data.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("no refresh token stored — redo the OAuth flow at /oauth/login")
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(TOKEN_URL, data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            })
            r.raise_for_status()
            self._store_response(r.json())

    async def get_access_token(self) -> str:
        if not self.has_tokens:
            raise RuntimeError("no cTrader tokens — complete OAuth at /oauth/login first")
        # refresh a day before expiry
        if time.time() > float(self._data.get("expires_at", 0)) - 86_400:
            try:
                await self.refresh()
            except Exception:  # noqa: BLE001 - keep using current token if refresh hiccups
                pass
        return self._data["access_token"]
