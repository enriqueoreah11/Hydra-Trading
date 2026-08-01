"""Las herramientas de backtest expuestas por MCP.

Lo que de verdad importa comprobar aquí no es que "devuelvan algo", sino tres cosas
que harían daño en silencio: que midan sobre el MISMO archivo de velas que usa la app
(si abriera otro, Claude te daría una verdad y Hydra otra), que cuando no hay
histórico lo digan en vez de devolver un cero que parece un resultado, y que ninguna
de estas herramientas pueda tocar el mercado.
"""
import pytest

from app import mcp_server as m
from tests.test_history import trending


@pytest.fixture
def hydra(tmp_path, monkeypatch):
    """Un Hydra de mentira con su carpeta de datos propia."""
    monkeypatch.setattr(m.settings, "data_dir", str(tmp_path))
    monkeypatch.setitem(m._cdb, "db", None)
    monkeypatch.setattr(m, "_store", None)
    return tmp_path


def load(db, symbol="EURUSD", tf="M15", n=900):
    rows = [{"ts": c.ts, "open": c.open, "high": c.high, "low": c.low,
             "close": c.close, "volume": c.volume} for c in trending(n)]
    return db.add(symbol, tf, rows)


def test_it_reads_the_same_candle_file_as_the_app(hydra):
    """Un solo almacén: el que la app llama candles.db en su carpeta de datos."""
    assert m._candles_file() == hydra / "candles.db"
    load(m._candles())
    assert (hydra / "candles.db").exists()
    inv = m.data_status()
    assert inv["ok"] and inv["bars"] == 900
    assert inv["series"][0]["symbol"] == "EURUSD"


def test_without_history_it_says_so_instead_of_returning_a_zero(hydra):
    r = m.backtest_run("GBPUSD", "H1")
    assert not r["ok"] and "no hay velas" in r["error"]
    assert "disponible" in r          # y dice qué SÍ hay, para no adivinar
    o = m.backtest_optimize("GBPUSD", "H1")
    assert not o["ok"] and "no hay velas" in o["error"]


def test_a_backtest_over_stored_candles_gives_r_multiples(hydra):
    load(m._candles())
    r = m.backtest_run("eurusd", "m15", "donchian")     # minúsculas incluidas
    assert r["ok"] and r["symbol"] == "EURUSD" and r["tf"] == "M15"
    assert r["trades"] > 0 and r["bars"] == 900
    assert r["expectancy_r"] is not None
    assert r["params"], "sin params se estaría midiendo cualquier cosa"


def test_the_same_call_twice_gives_the_same_number(hydra):
    load(m._candles())
    a = m.backtest_run("EURUSD", "M15", "donchian")
    b = m.backtest_run("EURUSD", "M15", "donchian")
    assert a == b


def test_optimize_reports_both_halves_and_ranks_by_the_unseen_one(hydra):
    load(m._candles())
    r = m.backtest_optimize("EURUSD", "M15", "donchian", steps=2, horizon=40,
                            min_trades=1, top=3)
    assert r["ok"] and r["split_bar"] < r["bars"]
    for row in r["top"]:
        assert "in_sample" in row and "out_of_sample" in row
    scores = [x["score"] for x in r["top"] if x["score"] is not None]
    assert scores == sorted(scores, reverse=True)
    assert "fuera de muestra" in r["aviso"].lower()


def test_the_strategy_list_carries_its_defaults_and_ranges(hydra):
    s = m.list_strategies()
    assert "donchian" in s["estrategias"]
    assert s["por_defecto"]["donchian"]
    lo, hi = s["rangos"]["donchian"]["lookback"]
    assert lo < hi
    # el valor por defecto cae dentro del rango que se puede optimizar
    assert lo <= s["por_defecto"]["donchian"]["lookback"] <= hi


def test_none_of_these_tools_can_touch_the_market(hydra):
    """La regla del servidor MCP: lee y mide, no opera. Si alguien añade una
    herramienta que coloque órdenes, esta prueba tiene que fallar."""
    peligrosas = ("order", "close_position", "modify", "buy", "sell", "place")
    nombres = [n for n in dir(m) if not n.startswith("_")]
    assert not [n for n in nombres if any(p in n.lower() for p in peligrosas)]
