"""Bajar el histórico del PROPIO bróker por cTrader.

Por qué existe esto teniendo Dukascopy: son dos proveedores de liquidez distintos.
Sus velas se parecen muchísimo pero no son iguales, y un stop se toca o no se toca
por décimas. Si vas a operar en cTrader, la única fuente que responde de verdad a
«¿qué habría pasado?» es cTrader.

Lo que se prueba es el troceado y el pegado, que es donde se pierden velas sin que
nadie lo note: un hueco en medio del histórico no da error — solo salen menos
operaciones en el backtest, y eso se lee como «la estrategia opera poco».
"""
import datetime as dt

from app import ctdata
from app.broker import Candle

AHORA = dt.datetime(2024, 6, 3, 12, tzinfo=dt.timezone.utc).timestamp()   # un lunes


def test_the_windows_cover_everything_asked_with_no_holes():
    """Un hueco entre dos trozos son velas que no se piden y nadie echa de menos."""
    ws = ctdata.windows("M15", 90, AHORA)
    assert ws
    assert ws[0][1] == int(AHORA * 1000)                       # empieza en ahora
    for (i1, f1), (i2, f2) in zip(ws, ws[1:]):
        assert f2 == i1, "queda un hueco entre dos peticiones"
    assert ws[-1][0] == int((AHORA - 90 * 86400) * 1000)       # y llega hasta el final


def test_it_starts_from_the_newest():
    """Si la descarga se corta, mejor tener lo reciente que un trozo de hace un año
    con un agujero hasta hoy."""
    ws = ctdata.windows("H1", 400, AHORA)
    assert ws[0][0] > ws[-1][0]


def test_smaller_timeframes_are_asked_in_smaller_bites():
    """La Open API limita por ventana de tiempo, y el límite es menor cuanto más
    fina la vela: pedir un mes de M1 de golpe devuelve un error y te quedas sin nada."""
    assert ctdata.chunk_days("M1") < ctdata.chunk_days("H1") < ctdata.chunk_days("D1")
    assert len(ctdata.windows("M1", 60, AHORA)) > len(ctdata.windows("H1", 60, AHORA))


def test_asking_for_nothing_gives_no_windows():
    assert ctdata.windows("M15", 0, AHORA) == []
    assert ctdata.windows("M15", -5, AHORA) == []


def test_an_unknown_timeframe_still_gets_a_sane_window():
    """Mejor un tamaño razonable que reventar por una temporalidad rara."""
    assert ctdata.chunk_days("M7") == 30


# ------------------------------------------------------------------- pegado

def vela(ts, close=1.0):
    return Candle(ts=ts, open=1, high=2, low=0.5, close=close, volume=1)


def test_the_overlap_between_chunks_does_not_duplicate():
    """Los bordes se solapan a propósito; contar la misma vela dos veces sería un
    dato mal medido, no un duplicado inocente."""
    a = [vela(100), vela(200), vela(300)]
    b = [vela(300), vela(400)]
    out = ctdata.merge([a, b])
    assert [c.ts for c in out] == [100, 200, 300, 400]


def test_when_a_bar_comes_twice_the_newest_chunk_wins():
    viejo = [vela(300, close=1.11)]
    nuevo = [vela(300, close=2.22)]
    assert ctdata.merge([viejo, nuevo])[0].close == 2.22


def test_merging_sorts_even_if_the_chunks_arrive_backwards():
    """Se piden del más nuevo al más viejo: sin ordenar, el backtest leería el
    tiempo hacia atrás y mediría cualquier cosa."""
    out = ctdata.merge([[vela(500)], [vela(100)], [vela(300)]])
    assert [c.ts for c in out] == [100, 300, 500]


def test_empty_chunks_do_not_break_the_merge():
    assert ctdata.merge([[], None, [vela(100)]])[0].ts == 100
    assert ctdata.merge([]) == []


# -------------------------------------------------------------------- huecos

def test_a_missing_stretch_mid_week_is_reported():
    """Un hueco no da error: solo salen menos operaciones, y eso se lee como
    «la estrategia opera poco». Hay que decirlo."""
    base = dt.datetime(2024, 6, 4, 8, tzinfo=dt.timezone.utc).timestamp()   # martes
    cs = [vela(base), vela(base + 900), vela(base + 900 * 20), vela(base + 900 * 21)]
    g = ctdata.gaps(cs, 900)
    assert len(g) == 1 and g[0]["faltan"] == 18


def test_the_weekend_is_not_reported_as_a_hole():
    """Sábado y domingo el mercado está cerrado: marcarlo sería ruido en cada serie."""
    viernes = dt.datetime(2024, 5, 31, 20, tzinfo=dt.timezone.utc).timestamp()
    lunes = dt.datetime(2024, 6, 3, 1, tzinfo=dt.timezone.utc).timestamp()
    assert ctdata.gaps([vela(viernes), vela(lunes)], 900) == []


def test_a_continuous_series_has_no_holes():
    base = dt.datetime(2024, 6, 4, 8, tzinfo=dt.timezone.utc).timestamp()
    cs = [vela(base + i * 900) for i in range(40)]
    assert ctdata.gaps(cs, 900) == []
