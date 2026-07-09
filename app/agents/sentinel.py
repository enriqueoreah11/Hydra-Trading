"""Sentinel — vigilante de noticias / calendario economico.

Descarga un calendario economico y crea "ventanas de bloqueo" alrededor de eventos
de alto impacto para las divisas que operas. Durante una ventana, el orquestador NO
abre nuevas posiciones en los simbolos afectados (protege contra gaps por noticias).

Fuente por defecto: JSON semanal de ForexFactory via faireconomy (gratuito, sin API key).
Si la descarga falla, reutiliza el ultimo calendario cacheado en disco; si nunca se
pudo descargar, hace fail-open (permite operar) pero lo registra como advertencia.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

from .. import fx
from ..config import settings

log = logging.getLogger("sentinel")

_IMPACT_RANK = {"low": 1, "medium": 2, "high": 3, "holiday": 0}


@dataclass
class Event:
    ts: float          # epoch seconds
    currency: str
    impact: str
    title: str


class Sentinel:
    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self.events: list[Event] = []
        self._last_fetch = 0.0
        self._ever_loaded = False
        self._load_cache()

    # ------------------------------------------------------------------ fetch

    async def refresh(self, force: bool = False) -> None:
        if not settings.enable_news:
            return
        if not force and time.time() - self._last_fetch < settings.news_refresh_min * 60:
            return
        self._last_fetch = time.time()
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as http:
                r = await http.get(settings.news_url, headers={"User-Agent": "hydra-trading/1.0"})
                r.raise_for_status()
                raw = r.json()
            self.events = self._parse(raw)
            self._ever_loaded = True
            self.cache_path.write_text(json.dumps(raw))
            log.info("sentinel: loaded %d events from calendar", len(self.events))
        except Exception:  # noqa: BLE001 - conservamos el cache previo
            log.warning("sentinel: calendar fetch failed; using cached events", exc_info=True)

    def _load_cache(self) -> None:
        if self.cache_path.exists():
            try:
                self.events = self._parse(json.loads(self.cache_path.read_text()))
                self._ever_loaded = True
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _parse(raw: list) -> list[Event]:
        out: list[Event] = []
        for e in raw or []:
            cur = str(e.get("country") or e.get("currency") or "").upper()
            impact = str(e.get("impact") or "").strip()
            date_s = e.get("date") or e.get("dateline") or ""
            if not cur or not date_s:
                continue
            ts = _parse_ts(date_s)
            if ts is None:
                continue
            out.append(Event(ts=ts, currency=cur, impact=impact, title=str(e.get("title", ""))))
        return out

    # --------------------------------------------------------------- blackout

    def blackout(self, symbol: str, at: float | None = None) -> Event | None:
        """Devuelve el evento que bloquea el simbolo AHORA, o None si esta despejado."""
        if not settings.enable_news:
            return None
        now = at if at is not None else time.time()
        min_rank = _IMPACT_RANK.get(settings.news_impact_min.lower(), 3)
        base, quote = fx.currencies_of(symbol)
        affected = {c for c in (base, quote) if c}
        before = settings.news_blackout_before_min * 60
        after = settings.news_blackout_after_min * 60
        for ev in self.events:
            if ev.currency not in affected:
                continue
            if _IMPACT_RANK.get(ev.impact.lower(), 0) < min_rank:
                continue
            if ev.ts - before <= now <= ev.ts + after:
                return ev
        return None

    def upcoming(self, symbol: str, within_min: int = 120) -> list[Event]:
        now = time.time()
        base, quote = fx.currencies_of(symbol)
        affected = {c for c in (base, quote) if c}
        min_rank = _IMPACT_RANK.get(settings.news_impact_min.lower(), 3)
        return sorted(
            [e for e in self.events
             if e.currency in affected
             and _IMPACT_RANK.get(e.impact.lower(), 0) >= min_rank
             and now <= e.ts <= now + within_min * 60],
            key=lambda e: e.ts)

    @property
    def has_data(self) -> bool:
        return self._ever_loaded


def _parse_ts(date_s: str) -> float | None:
    date_s = str(date_s).strip()
    for parser in (
        lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
    ):
        try:
            dtobj = parser(date_s)
            return dtobj.timestamp()
        except Exception:  # noqa: BLE001
            pass
    return None
