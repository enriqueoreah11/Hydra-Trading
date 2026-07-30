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


async def _token_call(http: httpx.AsyncClient, payload: dict) -> dict:
    """Pide tokens a cTrader.

    Su endpoint es un GET con los parametros en la QUERY. Documentado asi:

        curl -X GET "https://openapi.ctrader.com/apps/token?grant_type=...&code=...
             &redirect_uri=...&client_id=...&client_secret=..."
             -H "Accept: application/json"

    Con un POST contesta 200 y "INVALID_REQUEST — Malformed client_id parameter",
    que despista muchisimo porque el client_id es correcto: simplemente no lo lee
    de donde se lo mandas. Se prueban las tres formas por si cambia.
    """
    hdr = {"Accept": "application/json", "Content-Type": "application/json"}
    attempts = (
        ("GET query", lambda: http.get(TOKEN_URL, params=payload, headers=hdr)),
        ("POST query", lambda: http.post(TOKEN_URL, params=payload, headers=hdr)),
        ("POST cuerpo", lambda: http.post(TOKEN_URL, data=payload)),
    )
    fails = []
    for how, call in attempts:
        r = await call()
        try:
            body = r.json()
        except Exception:  # noqa: BLE001 - HTML de error o respuesta de un proxy
            fails.append(f"({how}) {r.status_code}, no era JSON: {r.text[:120]}")
            continue
        if isinstance(body, dict) and isinstance(body.get("data"), dict):
            body = {**body, **body["data"]}          # algunas versiones lo anidan
        err = body.get("errorCode") or body.get("error") if isinstance(body, dict) else None
        if not err and r.status_code < 400:
            return body
        desc = ""
        if isinstance(body, dict):
            desc = (body.get("description") or body.get("error_description")
                    or body.get("errorDescription") or "")
        fails.append(f"({how}) {r.status_code}: {err or 'sin codigo'}"
                     + (f" — {desc}" if desc else ""))
    raise RuntimeError("cTrader rechazo la peticion de tokens. " + " | ".join(fails))


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
            try:
                body = await _token_call(http, {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                })
            except RuntimeError as exc:
                raise RuntimeError(f"{exc} · redirect_uri enviado: {self.redirect_uri}") from None
        self._store_response(body)

    async def refresh(self) -> None:
        refresh_token = self._data.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("no refresh token stored — redo the OAuth flow at /oauth/login")
        async with httpx.AsyncClient(timeout=30) as http:
            body = await _token_call(http, {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            })
        self._store_response(body)

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
