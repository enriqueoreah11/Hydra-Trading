"""Utilidades de divisas: extraer base/quote de un simbolo y correlacionar retornos.

Cubre pares FX de 6 letras (EURUSD -> EUR/USD) y metales (XAUUSD -> XAU/USD,
XAGUSD -> XAG/USD). Para simbolos no estandar devuelve el nombre completo como
'quote' y None como base, de forma que la exposicion se mide de forma conservadora.
"""
from __future__ import annotations

from .broker import Candle

_METALS = {"XAU", "XAG", "XPT", "XPD"}
_ENERGY = {"XTI", "XBR", "XNG"}                       # WTI, Brent, gas natural
# Indices bursatiles -> divisa en la que cotizan (para exposicion y blackout de noticias)
_INDICES = {
    "US100": "USD", "USTEC": "USD", "NAS100": "USD", "US30": "USD", "US500": "USD",
    "SPX500": "USD", "US2000": "USD", "USOIL": "USD", "WTI": "USD", "UKOIL": "USD",
    "DE40": "EUR", "GER40": "EUR", "EU50": "EUR", "STOXX50": "EUR", "FRA40": "EUR",
    "UK100": "GBP", "JPN225": "JPY", "JP225": "JPY", "AUS200": "AUD", "HK50": "HKD",
}


def currencies_of(symbol: str) -> tuple[str | None, str]:
    """Devuelve (base, quote). base puede ser None para simbolos no reconocidos."""
    s = symbol.upper().replace("/", "").replace(".", "")
    if s in _INDICES:
        return s, _INDICES[s]
    if len(s) == 6 and s.isalpha():
        return s[:3], s[3:]
    for pref in _METALS | _ENERGY:
        if s.startswith(pref) and len(s) >= 6:
            return pref, s[len(pref):len(pref) + 3]
    return None, s


def currency_exposure(side: str, symbol: str, risk_pct: float) -> dict[str, float]:
    """Riesgo firmado por divisa: comprar EURUSD = +riesgo EUR, -riesgo USD."""
    base, quote = currencies_of(symbol)
    sign = 1.0 if side == "buy" else -1.0
    exp: dict[str, float] = {}
    if base:
        exp[base] = exp.get(base, 0.0) + sign * risk_pct
    exp[quote] = exp.get(quote, 0.0) - sign * risk_pct
    return exp


def returns(candles: list[Candle]) -> list[float]:
    out = []
    for i in range(1, len(candles)):
        prev = candles[i - 1].close
        if prev:
            out.append((candles[i].close - prev) / prev)
    return out


def correlation(a: list[float], b: list[float]) -> float:
    """Pearson de dos series de retornos; 0 si no hay datos suficientes."""
    n = min(len(a), len(b))
    if n < 5:
        return 0.0
    a, b = a[-n:], b[-n:]
    ma = sum(a) / n
    mb = sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    denom = (va * vb) ** 0.5
    return cov / denom if denom else 0.0
