"""Descarga histórico de Dukascopy y lo deja en VELAS, no en ticks.

Dukascopy publica un archivo por HORA con los ticks de esa hora, comprimido con LZMA:

    https://datafeed.dukascopy.com/datafeed/EURUSD/2024/00/02/10h_ticks.bi5
                                              símbolo  año mes día hora

Ojo con el mes: va de **0 a 11**. Enero es `00`. Es el error clásico y te trae los
datos de otro mes sin avisar de nada.

Cada tick son 20 bytes: milisegundos desde el inicio de la hora, ask y bid como
enteros (hay que dividir por 10^digits), y los volúmenes en float.

Decisión importante: **los ticks no se guardan**. Un día de EURUSD son cientos de
miles de ticks; un año, decenas de millones. Se agregan a velas al vuelo y se tira el
archivo. Las velas de un año de M15 ocupan un megabyte largo: eso sí cabe.
"""
from __future__ import annotations

import datetime as dt
import logging
import lzma
import struct

log = logging.getLogger("dukascopy")

BASE = "https://datafeed.dukascopy.com/datafeed"
TICK = struct.Struct(">IIIff")          # ms, ask, bid, askVol, bidVol
TICK_SIZE = TICK.size                   # 20 bytes

# Cuántos decimales usa cada familia. Con el divisor equivocado, los precios salen
# multiplicados por mil y el backtest mide otra cosa.
def digits_for(symbol: str) -> int:
    s = symbol.upper()
    if "JPY" in s:
        return 3
    if s.startswith(("XAU", "XAG", "XTI", "XBR", "BRENT", "LIGHT")):
        return 3
    if s.startswith(("USA", "US", "DEU", "GBR", "JPN", "EUS", "DE", "UK")):
        return 2
    return 5


def url_for(symbol: str, when: dt.datetime) -> str:
    """La URL de esa hora. El mes va 0-11: enero es 00."""
    return (f"{BASE}/{symbol.upper()}/{when.year:04d}/{when.month - 1:02d}/"
            f"{when.day:02d}/{when.hour:02d}h_ticks.bi5")


def decode(raw: bytes, hour_start: float, digits: int) -> list[dict]:
    """Descomprime y convierte a ticks con precio real y hora absoluta."""
    if not raw:
        return []
    try:
        data = lzma.decompress(raw)
    except lzma.LZMAError as exc:
        log.warning("bi5 ilegible: %s", exc)
        return []
    div = 10 ** digits
    out = []
    for off in range(0, len(data) - TICK_SIZE + 1, TICK_SIZE):
        ms, ask, bid, av, bv = TICK.unpack_from(data, off)
        out.append({"ts": hour_start + ms / 1000.0,
                    "ask": ask / div, "bid": bid / div,
                    "vol": (av or 0) + (bv or 0)})
    return out


def to_candles(ticks: list[dict], tf_seconds: int) -> list[dict]:
    """Agrupa ticks en velas usando el precio MEDIO (bid+ask)/2.

    El punto medio es lo que se usa para comparar señales: si se usara solo el bid,
    las compras saldrían sistemáticamente mejor de lo que fueron.
    """
    if not ticks or tf_seconds <= 0:
        return []
    out: list[dict] = []
    cur = None
    for t in ticks:
        mid = (t["bid"] + t["ask"]) / 2.0
        bucket = int(t["ts"] // tf_seconds) * tf_seconds
        if cur is None or bucket != cur["ts"]:
            if cur is not None:
                out.append(cur)
            cur = {"ts": bucket, "open": mid, "high": mid, "low": mid,
                   "close": mid, "volume": t["vol"]}
        else:
            cur["high"] = max(cur["high"], mid)
            cur["low"] = min(cur["low"], mid)
            cur["close"] = mid
            cur["volume"] += t["vol"]
    if cur is not None:
        out.append(cur)
    return out


def hours_between(start: dt.datetime, end: dt.datetime) -> list[dt.datetime]:
    """Las horas a pedir. Se saltan sábado y domingo: el mercado está cerrado y esos
    archivos vienen vacíos — pedirlos es tiempo tirado."""
    out, cur = [], start.replace(minute=0, second=0, microsecond=0)
    while cur < end:
        if cur.weekday() < 5:
            out.append(cur)
        cur += dt.timedelta(hours=1)
    return out
