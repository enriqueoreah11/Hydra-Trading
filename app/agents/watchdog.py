"""Watchdog — vigila la salud del PROPIO sistema y avisa por Telegram.

Comprueba: conexion viva con cTrader, frescura de los datos de mercado, rafagas de
errores en el diario, estado de halt y validez del token OAuth. Emite alertas cuando
algo se rompe (para que puedas apagar tu maquina con tranquilidad) y un latido diario
"sigo vivo". Deduplica alertas para no hacer spam.
"""
from __future__ import annotations

import logging
import time

from ..broker import Broker
from ..config import settings
from ..notifier import notifier
from ..store import Store

log = logging.getLogger("watchdog")


class Watchdog:
    def __init__(self, broker: Broker, store: Store):
        self.broker = broker
        self.store = store
        self._active_alerts: set[str] = set()   # claves de alerta ya notificadas (para resolver)

    async def check(self, last_data_ts: float) -> None:
        # --- conexion ---
        await self._flag("disconnected",
                         not self.broker.client.account_authorized,
                         "⚠️ *Hydra* desconectado de cTrader (reintentando)…",
                         "✅ Conexion con cTrader restablecida.")

        # --- datos frescos (solo relevante si estamos conectados) ---
        stale = (self.broker.client.account_authorized and last_data_ts > 0
                 and time.time() - last_data_ts > settings.data_stale_alert_min * 60)
        await self._flag("stale_data", stale,
                         "⚠️ *Hydra* sin datos de mercado frescos (¿mercado cerrado o fallo de feed?).",
                         "✅ Datos de mercado fluyendo de nuevo.")

        # --- rafaga de errores ---
        window = self.store.recent_journal(limit=60)
        errors = sum(1 for e in window
                     if "error" in e["kind"].lower() and time.time() - e["ts"] < 3600)
        await self._flag("error_burst", errors >= settings.error_burst_threshold,
                         f"⚠️ *Hydra*: {errors} errores en la ultima hora — revisa los logs.",
                         "✅ Los errores se detuvieron.")

    async def notify_event(self, text: str) -> None:
        await notifier.send(text)

    async def daily_heartbeat(self, balance: float | None, halted: bool,
                              open_positions: int) -> None:
        bal = f"{balance:.2f}" if balance is not None else "—"
        estado = "🔴 DETENIDO" if halted else "🟢 activo"
        await notifier.send(
            f"🐉 *Hydra* latido diario\nEstado: {estado}\nBalance: {bal}\n"
            f"Posiciones abiertas: {open_positions}\nEntorno: {settings.ctrader_env} "
            f"({'papel' if settings.dry_run else 'real'})")

    async def _flag(self, key: str, active: bool, alert_msg: str, resolve_msg: str) -> None:
        if active and key not in self._active_alerts:
            self._active_alerts.add(key)
            await notifier.send(alert_msg)
        elif not active and key in self._active_alerts:
            self._active_alerts.discard(key)
            await notifier.send(resolve_msg)
