"""Bóveda de claves API cifradas (para gestionarlas desde el panel Sistema).

- Las claves se cifran con Fernet (AES) usando una llave maestra derivada de
  settings.app_secret_key (el secret APP_SECRET_KEY de Fly). Sin esa llave
  maestra no se pueden guardar (solo se puede ver el estado).
- Se guardan cifradas en data/secrets.enc (volumen persistente) y se aplican
  en caliente sobre `settings`.
- La API NUNCA devuelve el valor completo: solo si está puesta y una pista
  con los últimos 4 caracteres. No se puede ver ni copiar la clave.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from .config import settings

# name en Settings -> etiqueta visible
SECRETS: list[tuple[str, str]] = [
    ("anthropic_api_key", "Anthropic (cerebro IA)"),
    ("tts_api_key", "Voz neural (ElevenLabs / OpenAI)"),
    ("ctrader_client_id", "cTrader · Client ID"),
    ("ctrader_client_secret", "cTrader · Client Secret"),
    ("telegram_bot_token", "Telegram · Bot Token"),
]
_NAMES = {n for n, _ in SECRETS}


def can_edit(name: str) -> bool:
    return name in _NAMES


def _path() -> Path:
    return settings.data_path / "secrets.enc"


def _fernet():
    key = (settings.app_secret_key or "").strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        fkey = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
        return Fernet(fkey)
    except BaseException:  # noqa: BLE001 - libreria ausente o rota: degradar sin tronar
        return None


def _read() -> dict:
    try:
        return json.loads(_path().read_text())
    except Exception:  # noqa: BLE001
        return {}


def has_master_key() -> bool:
    return _fernet() is not None


def status() -> dict:
    """Estado (sin exponer valores): puesta o no + pista de los últimos 4."""
    items = []
    for name, label in SECRETS:
        val = str(getattr(settings, name, "") or "")
        hint = ("••••" + val[-4:]) if len(val) >= 4 else ("••••" if val else "")
        items.append({"name": name, "label": label, "set": bool(val), "hint": hint})
    return {"master_key": has_master_key(), "items": items}


def save(name: str, value: str) -> None:
    if not can_edit(name):
        raise RuntimeError("clave no permitida")
    f = _fernet()
    if f is None:
        raise RuntimeError("falta la llave maestra APP_SECRET_KEY (ponla en Fly y redeploy)")
    value = str(value)
    data = _read()
    data[name] = f.encrypt(value.encode()).decode()
    _path().write_text(json.dumps(data))
    setattr(settings, name, value)


def load() -> None:
    """Al arrancar: descifra y aplica las claves guardadas sobre settings."""
    f = _fernet()
    if f is None:
        return
    for name, tok in _read().items():
        if name not in _NAMES:
            continue
        try:
            setattr(settings, name, f.decrypt(str(tok).encode()).decode())
        except Exception:  # noqa: BLE001 - token inválido o llave cambiada
            pass
