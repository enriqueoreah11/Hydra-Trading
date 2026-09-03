"""Una sola fuente de verdad para el precio.

El consejo de su maestro —conectar solo a la API del bróker y no mezclar feeds—
señalaba un fallo que Hydra tenía y que era peor de lo que parecía. Las velas se
guardaban con clave (símbolo, temporalidad, instante) y sin decir de dónde venían,
con INSERT OR REPLACE: bajar cTrader después de importar Dukascopy no daba dos
series, daba UNA con velas de los dos sitios pisadas entre sí.

Y eso no se nota en ningún sitio. La serie tiene el número de velas correcto, sin
huecos, con fechas seguidas. Lo único que pasa es que ese mercado no existió nunca,
y todo lo que se mida sobre él —backtests, el playbook automático, las lecciones—
es un número sobre nada.
"""
import pytest

from app.history import CandleDB


def velas(n, base=100.0, ts0=1700000000, paso=900):
    return [{"ts": ts0 + i * paso, "open": base + i, "high": base + i + 1,
             "low": base + i - 1, "close": base + i, "volume": 10} for i in range(n)]


@pytest.fixture
def db(tmp_path):
    return CandleDB(tmp_path / "c.db")


def test_the_source_is_stored(db):
    db.add("XAUUSD", "M15", velas(10), "ctrader")
    assert db.fuentes("XAUUSD", "M15") == [{"fuente": "ctrader", "velas": 10}]


def test_two_sources_are_visible_instead_of_silently_merged(db):
    """EL fallo. Antes esto daba una sola serie sin nada que lo indicara."""
    db.add("XAUUSD", "M15", velas(10), "ctrader")
    db.add("XAUUSD", "M15", velas(10, base=200.0, ts0=1700100000), "dukascopy")
    fs = {f["fuente"] for f in db.fuentes("XAUUSD", "M15")}
    assert fs == {"ctrader", "dukascopy"}
    assert db.mezclada("XAUUSD", "M15") is True


def test_one_source_is_not_flagged_as_mixed(db):
    db.add("XAUUSD", "M15", velas(10), "ctrader")
    assert db.mezclada("XAUUSD", "M15") is False


def test_asking_for_one_source_gives_only_that_one(db):
    """Es lo que permite medir sobre un mercado real en vez de sobre la mezcla."""
    db.add("XAUUSD", "M15", velas(10), "ctrader")
    db.add("XAUUSD", "M15", velas(10, base=200.0, ts0=1700100000), "dukascopy")
    ct = db.series("XAUUSD", "M15", fuente="ctrader")
    dk = db.series("XAUUSD", "M15", fuente="dukascopy")
    assert len(ct) == 10 and len(dk) == 10
    assert all(c.close < 150 for c in ct)
    assert all(c.close >= 200 for c in dk)


def test_reimporting_the_same_source_still_does_not_duplicate(db):
    """La propiedad que ya existía no se puede perder al añadir la fuente: bajar el
    histórico por trozos tiene que seguir sin duplicar ni una vela."""
    db.add("XAUUSD", "M15", velas(10), "ctrader")
    db.add("XAUUSD", "M15", velas(10), "ctrader")
    assert db.count("XAUUSD", "M15") == 10


def test_an_old_database_without_the_column_still_opens(tmp_path):
    """Su base de datos ya existe y tiene velas dentro. Si abrirla fallara, el
    arreglo le costaría el histórico que ya tiene bajado."""
    import sqlite3
    p = tmp_path / "vieja.db"
    con = sqlite3.connect(str(p))
    con.execute("""CREATE TABLE candles(symbol TEXT NOT NULL, tf TEXT NOT NULL,
        ts INTEGER NOT NULL, open REAL, high REAL, low REAL, close REAL, volume REAL,
        PRIMARY KEY(symbol, tf, ts))""")
    con.execute("INSERT INTO candles VALUES('XAUUSD','M15',1700000000,1,2,0,1,5)")
    con.commit()
    con.close()

    db = CandleDB(p)
    assert db.count("XAUUSD", "M15") == 1
    assert db.fuentes("XAUUSD", "M15") == [{"fuente": "desconocida", "velas": 1}]


def test_old_candles_are_not_silently_called_broker_data(tmp_path):
    """Lo que ya estaba guardado no se sabe de dónde vino. Marcarlo como «ctrader»
    sería inventar una procedencia, y justo eso es lo que este arreglo evita."""
    import sqlite3
    p = tmp_path / "vieja.db"
    con = sqlite3.connect(str(p))
    con.execute("""CREATE TABLE candles(symbol TEXT NOT NULL, tf TEXT NOT NULL,
        ts INTEGER NOT NULL, open REAL, high REAL, low REAL, close REAL, volume REAL,
        PRIMARY KEY(symbol, tf, ts))""")
    con.execute("INSERT INTO candles VALUES('X','M15',1,1,2,0,1,5)")
    con.commit()
    con.close()
    assert CandleDB(p).fuentes("X", "M15")[0]["fuente"] == "desconocida"


def test_an_unnamed_source_is_called_unknown_not_left_empty(db):
    db.add("X", "M15", velas(3), "")
    assert db.fuentes("X", "M15")[0]["fuente"] == "desconocida"


def test_where_it_came_from_and_who_produced_it_are_different_questions():
    """«De disco o descargado» y «quién produjo esas velas» son dos preguntas, y
    meterlas en la misma clave es como se acaba comparando «guardado» con
    «dukascopy» — que no son valores del mismo conjunto."""
    import tempfile
    from pathlib import Path

    from fastapi.testclient import TestClient

    from app.config import settings
    from app.store import Store
    from app.web import create_app

    d = tempfile.mkdtemp()
    settings.data_dir = d
    db = CandleDB(Path(d) / "candles.db")
    db.add("XAUUSD", "M15", velas(500), "dukascopy")
    c = TestClient(create_app(Store(Path(d) / "b.db"), None, None, None))
    r = c.get("/descubrir?symbol=XAUUSD&tf=M15").json()
    assert r["origen"]["fuente"] == "guardado"
    assert r["origen"]["proveedor"] == "dukascopy"


def test_a_mixed_series_warns_instead_of_measuring_the_blend():
    """Medir sobre media serie de cada sitio da un número de un mercado que no
    existió, y nada en el resultado lo delata."""
    import tempfile
    from pathlib import Path

    from fastapi.testclient import TestClient

    from app.config import settings
    from app.store import Store
    from app.web import create_app

    d = tempfile.mkdtemp()
    settings.data_dir = d
    db = CandleDB(Path(d) / "candles.db")
    db.add("XAUUSD", "M15", velas(500), "ctrader")
    db.add("XAUUSD", "M15", velas(500, base=900.0, ts0=1800000000), "dukascopy")
    c = TestClient(create_app(Store(Path(d) / "b.db"), None, None, None))
    o = c.get("/descubrir?symbol=XAUUSD&tf=M15").json()["origen"]
    assert "varias fuentes" in o["aviso"]
    assert o["proveedor"] == "ctrader", "debe preferir las velas del bróker"
