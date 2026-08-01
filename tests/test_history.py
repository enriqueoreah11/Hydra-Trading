"""Importar tu histórico y hacer backtest con él.

Lo que se comprueba es lo que arruinaría un backtest sin que se note: fechas mal
interpretadas, filas basura coladas, velas duplicadas al reimportar, y una
optimización que se ajusta al ruido y nadie te avisa.
"""
import math

from app import history, optimize, strategies
from app.broker import Candle


def test_timestamps_in_every_format_end_in_seconds():
    assert history.parse_ts("1700000000") == 1700000000
    assert history.parse_ts("1700000000000") == 1700000000        # milisegundos
    assert history.parse_ts("2023-11-14 22:13:20") == 1700000000
    assert history.parse_ts("2023-11-14") == 1699920000
    assert history.parse_ts("14-11-2023 22:13") == 1699999980
    assert history.parse_ts("") is None and history.parse_ts("hola") is None


def test_reads_a_normal_csv_with_headers():
    txt = ("time,open,high,low,close,volume\n"
           "1700000000,1.1,1.2,1.05,1.15,100\n"
           "1700000900,1.15,1.25,1.1,1.2,120\n")
    rows, info = history.parse_csv(txt)
    assert len(rows) == 2 and info["skipped"] == 0
    assert rows[0]["open"] == 1.1 and rows[1]["close"] == 1.2


def test_reads_spanish_headers_and_semicolons():
    txt = ("fecha;apertura;maximo;minimo;cierre;volumen\n"
           "2023-11-14 22:13:20;1,1;1,2;1,05;1,15;100\n")
    rows, _ = history.parse_csv(txt)
    assert len(rows) == 1 and rows[0]["high"] == 1.2      # coma decimal incluida


def test_a_file_without_headers_uses_the_classic_order():
    rows, info = history.parse_csv("1700000000,1.1,1.2,1.05,1.15,100\n")
    assert len(rows) == 1 and rows[0]["low"] == 1.05


def test_broken_rows_are_counted_not_imported():
    txt = ("time,open,high,low,close\n"
           "1700000000,1.1,1.2,1.05,1.15\n"
           "esto,no,es,una,vela\n"
           "1700000900,,,,\n")
    rows, info = history.parse_csv(txt)
    assert len(rows) == 1 and info["skipped"] == 2       # se dice cuántas se cayeron


def test_a_file_that_is_not_candles_says_so():
    rows, info = history.parse_csv("nombre,edad\nana,33\n")
    assert rows == [] and "no reconocí" in info["error"]


def test_timeframe_is_inferred_from_the_gaps():
    rows = [{"ts": 1700000000 + i * 900} for i in range(10)]
    assert history.infer_tf(rows) == "M15"
    rows_h1 = [{"ts": 1700000000 + i * 3600} for i in range(10)]
    assert history.infer_tf(rows_h1) == "H1"


def test_reimporting_the_same_file_does_not_duplicate(tmp_path):
    db = history.CandleDB(tmp_path / "c.db")
    rows = [{"ts": 1700000000 + i * 900, "open": 1, "high": 2, "low": 0.5,
             "close": 1.5, "volume": 1} for i in range(50)]
    assert db.add("EURUSD", "M15", rows) == 50
    assert db.add("EURUSD", "M15", rows) == 0            # ni una de más
    assert db.count("EURUSD", "M15") == 50
    inv = db.inventory()
    assert inv[0]["bars"] == 50 and inv[0]["symbol"] == "EURUSD"


def test_the_series_comes_back_in_order(tmp_path):
    db = history.CandleDB(tmp_path / "c.db")
    db.add("X", "M15", [{"ts": 300, "open": 3, "high": 3, "low": 3, "close": 3},
                        {"ts": 100, "open": 1, "high": 1, "low": 1, "close": 1},
                        {"ts": 200, "open": 2, "high": 2, "low": 2, "close": 2}])
    assert [c.ts for c in db.series("X", "M15")] == [100, 200, 300]


# ------------------------------------------------------------------ backtest

def trending(n=600, step=0.0005):
    """Subida con retrocesos. En las velas de impulso el cierre TOCA el máximo, como
    en el mercado real: si el máximo siempre fuera mayor que el cierre, una ruptura de
    canal no podría dispararse nunca y la prueba mediría un motor mudo."""
    out, price = [], 1.0
    for i in range(n):
        up = bool(i % 7)
        price += step * (1 if up else -3)
        hi = price if up else price + 0.001
        lo = price - 0.001 if up else price
        out.append(Candle(ts=i * 900, open=price - step * (1 if up else -3),
                          high=hi, low=lo, close=price, volume=1))
    return out


def test_a_backtest_needs_enough_history():
    r = optimize.run(trending(50), "donchian", strategies.DEFAULTS["donchian"])
    assert not r["ok"] and "velas" in r["error"]


def test_a_backtest_gives_the_same_result_twice():
    cs = trending()
    a = optimize.run(cs, "donchian", strategies.DEFAULTS["donchian"])
    b = optimize.run(cs, "donchian", strategies.DEFAULTS["donchian"])
    assert a == b                                        # sin azar: reproducible
    assert a["ok"] and a["trades"] > 0
    assert a["expectancy_r"] is not None and math.isfinite(a["expectancy_r"])


def test_it_does_not_stack_overlapping_trades():
    """Una posición a la vez: si no, se mediría algo que el bot no hace.

    Se comprueba sobre las operaciones REALES que tomó: cada entrada tiene que ser
    posterior a la salida de la anterior. Contar solo el total no serviría, porque una
    operación que salta el stop enseguida libera el hueco legítimamente.
    """
    cs = trending()
    r = optimize.run(cs, "donchian", strategies.DEFAULTS["donchian"], horizon=60)
    det = r["trades_detail"]
    assert det, "sin operaciones no se prueba nada"
    for a, b in zip(det, det[1:]):
        assert b["bar"] > a["exit"], f"solapadas: entra en {b['bar']} y la otra sale en {a['exit']}"
        assert a["exit"] - a["bar"] <= 60                 # nunca más allá del horizonte


def test_the_grid_stays_inside_the_allowed_ranges():
    combos = optimize.grid("ema_trend", steps=3)
    lo_f, hi_f = strategies.TUNABLE["ema_trend"]["ema_fast"]
    assert combos and all(lo_f <= c["ema_fast"] <= hi_f for c in combos)
    assert all(float(c["ema_fast"]).is_integer() for c in combos)   # velas enteras


def test_optimize_scores_out_of_sample_and_warns():
    cs = trending(900)
    r = optimize.optimize(cs, "donchian", steps=2, horizon=40, min_trades=1, top=3)
    assert r["ok"] and r["combos"] >= 2
    assert r["split_bar"] < r["bars"]                    # hay tramo sin ver
    assert "fuera de muestra" in r["aviso"].lower()
    for row in r["top"]:
        assert "in_sample" in row and "out_of_sample" in row
    # ordenado por el resultado FUERA de muestra, no por el de dentro
    scores = [x["score"] for x in r["top"] if x["score"] is not None]
    assert scores == sorted(scores, reverse=True)


def test_combinations_with_too_few_trades_are_discarded():
    cs = trending(900)
    r = optimize.optimize(cs, "donchian", steps=2, horizon=40, min_trades=10000)
    assert r["evaluated"] == 0 and r["top"] == []
