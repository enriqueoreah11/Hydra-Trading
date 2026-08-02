"""Bajar histórico de velas del PROPIO cTrader, no de un tercero.

Por qué importa: Dukascopy y tu bróker son dos proveedores de liquidez distintos.
Cada uno tiene sus precios, sus spreads y sus cierres de vela. Un XAUUSD de
Dukascopy y el XAUUSD de IC Markets se parecen muchísimo, pero no son iguales — y
un stop que en unos datos se toca por dos décimas, en los otros no. Eso no da error
en ningún sitio: simplemente el backtest mide un bot que no es el tuyo.

Si vas a operar en cTrader, la única fuente que responde a «¿qué habría pasado?» es
cTrader. Dukascopy sigue valiendo para lo que no tenga tu bróker o para contrastar.

La Open API limita cada petición por VENTANA DE TIEMPO, no por número de velas, y
el límite depende de la temporalidad. Por eso se pide por trozos hacia atrás. Las
ventanas de aquí van holgadas a propósito: pedir de menos cuesta una petición más,
pedir de más devuelve un error y te quedas sin nada.
"""
from __future__ import annotations

# Días que se piden de una vez por temporalidad. Conservador a propósito.
CHUNK_DAYS = {
    "M1": 4, "M5": 14, "M15": 30, "M30": 60,
    "H1": 120, "H4": 365, "D1": 1500, "W1": 3650,
}


def chunk_days(tf: str) -> int:
    return CHUNK_DAYS.get(str(tf or "").upper(), 30)


def windows(tf: str, days: float, now_ts: float) -> list[tuple[int, int]]:
    """Los trozos (desde_ms, hasta_ms) a pedir, del más reciente al más viejo.

    Se empieza por lo NUEVO: si la descarga se corta a la mitad —o el bróker deja de
    dar histórico más atrás— te quedas con lo reciente, que es lo que se usa. Al
    revés te quedarías con un trozo antiguo y un hueco hasta hoy, y un hueco en
    medio del histórico no se ve al hacer backtest: solo salen menos operaciones.
    """
    total = max(0.0, float(days))
    if total <= 0:
        return []
    paso = chunk_days(tf) * 86400.0
    out: list[tuple[int, int]] = []
    fin = float(now_ts)
    limite = float(now_ts) - total * 86400.0
    while fin > limite:
        ini = max(limite, fin - paso)
        out.append((int(ini * 1000), int(fin * 1000)))
        fin = ini
    return out


def merge(trozos: list[list]) -> list:
    """Junta los trozos quitando repetidas y dejándolas en orden.

    Los bordes se solapan (una vela puede venir en dos peticiones) y reimportar una
    vela dos veces con precios distintos es un dato mal medido, no un duplicado
    inocente: se queda la ÚLTIMA leída, que es la del trozo más reciente.
    """
    por_ts: dict[int, object] = {}
    for t in trozos:
        for c in t or []:
            por_ts[int(getattr(c, "ts", 0) or 0)] = c
    return [por_ts[k] for k in sorted(por_ts)]


def gaps(candles: list, tf_seconds: int, max_gap_factor: float = 3.0) -> list[dict]:
    """Huecos sospechosos en la serie, para poder decirlo en vez de esconderlo.

    Un fin de semana es un hueco legítimo y enorme; lo que interesa son los saltos
    en pleno mercado, que suelen ser velas que el bróker no dio. Se marcan los que
    pasan de `max_gap_factor` veces la temporalidad y no caen en sábado o domingo.
    """
    import datetime as dt

    if tf_seconds <= 0 or len(candles) < 3:
        return []
    out = []
    for a, b in zip(candles, candles[1:]):
        ta, tb = int(getattr(a, "ts", 0)), int(getattr(b, "ts", 0))
        salto = tb - ta
        if salto <= tf_seconds * max_gap_factor:
            continue
        fin = dt.datetime.fromtimestamp(ta, dt.timezone.utc)
        if fin.weekday() >= 4:            # viernes en adelante: es el fin de semana
            continue
        out.append({"from_ts": ta, "to_ts": tb,
                    "faltan": int(salto / tf_seconds) - 1})
    return out
