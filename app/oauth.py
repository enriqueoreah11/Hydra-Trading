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
        """Canjea el código por tokens.

        El endpoint de cTrader puede contestar 200 CON un cuerpo de error, así que
        no vale con raise_for_status: hay que mirar el cuerpo. Y cuando falla, el
        motivo tiene que llegar a la pantalla, no morir en el log como un 500.
        """
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(TOKEN_URL, data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            })
        try:
            body = r.json()
        except Exception:  # noqa: BLE001 - HTML o texto suelto
            raise RuntimeError(
                f"el endpoint de tokens respondió {r.status_code} y no era JSON: "
                f"{r.text[:300]}") from None
        if isinstance(body, dict) and isinstance(body.get("data"), dict):
            body = {**body, **body["data"]}          # algunas versiones lo anidan
        err = (body.get("errorCode") or body.get("error") or
               body.get("error_description")) if isinstance(body, dict) else None
        if err or r.status_code >= 400:
            desc = (body.get("description") or body.get("error_description")
                    or body.get("errorDescription") or "") if isinstance(body, dict) else ""
            raise RuntimeError(
                f"cTrader rechazó el canje ({r.status_code}): {err or 'sin código'}"
                + (f" — {desc}" if desc else "")
                + f". redirect_uri enviado: {self.redirect_uri}")
        self._store_response(body)

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
