"""El resumen del historial de operaciones.

Un resumen de trading engaña con una facilidad enorme y sin dar ningún error: si
cuelas las operaciones abiertas en el resultado, si sumas en bruto en vez de neto, o
si enseñas el porcentaje de aciertos sin el dinero al lado. Las tres cosas hacen que
una estrategia perdedora parezca buena, que es exactamente lo que no puede pasar.
"""
from app import tradestats


def op(pnl=None, state="closed", strategy="Confluence", symbol="XAUUSD", ts=0, lots=0.1):
    return {"state": state, "pnl": pnl, "strategy": strategy,
            "symbol": symbol, "ts": ts, "lots": lots}


def test_open_positions_never_count_as_result():
    """EL fallo que engaña: sumar el flotante que la Open API ni siquiera manda."""
    r = tradestats.summarize([op(100, ts=1), op(state="open", lots=0.5),
                              op(state="open", lots=0.3)])
    assert r["net"] == 100
    assert r["n_closed"] == 1 and r["n_open"] == 2
    assert r["open_lots"] == 0.8          # se ve lo que hay en juego, aparte


def test_the_hit_rate_never_travels_without_the_money():
    """80% de aciertos perdiendo dinero es el clásico. Las dos cifras, juntas."""
    r = tradestats.summarize([op(10, ts=1), op(10, ts=2), op(10, ts=3),
                              op(10, ts=4), op(-100, ts=5)])
    assert r["win_pct"] == 80.0
    assert r["net"] == -60.0              # y aun así se pierde


def test_the_worst_drawdown_is_not_the_worst_trade():
    """La racha es lo que de verdad se aguanta, y no sale de mirar el total."""
    r = tradestats.summarize([op(100, ts=1), op(-40, ts=2), op(-40, ts=3), op(30, ts=4)])
    assert r["net"] == 50
    assert r["worst"] == -40              # la peor operación suelta
    assert r["max_dd"] == -80             # lo que se llegó a caer desde el pico


def test_the_order_of_the_rows_does_not_change_the_drawdown():
    """Llegan desordenadas del broker; la racha se calcula por fecha, no por orden."""
    ops = [op(-40, ts=3), op(100, ts=1), op(30, ts=4), op(-40, ts=2)]
    assert tradestats.summarize(ops)["max_dd"] == -80


def test_each_strategy_is_counted_apart():
    r = tradestats.summarize([op(50, strategy="Confluence", ts=1),
                              op(-20, strategy="Confluence", ts=2),
                              op(-70, strategy="SRC", ts=3)])
    por = {g["key"]: g for g in r["by_strategy"]}
    assert por["Confluence"]["net"] == 30 and por["Confluence"]["n"] == 2
    assert por["SRC"]["net"] == -70
    assert por["Confluence"]["win_pct"] == 50.0


def test_what_hurts_the_most_goes_first():
    """Ordenado por lo que más mueve la cuenta, no alfabético: lo que duele arriba."""
    r = tradestats.summarize([op(5, strategy="pequeña", ts=1),
                              op(-500, strategy="la gorda", ts=2)])
    assert r["by_strategy"][0]["key"] == "la gorda"


def test_instruments_are_grouped_too():
    r = tradestats.summarize([op(10, symbol="XAUUSD", ts=1),
                              op(-30, symbol="EURUSD", ts=2),
                              op(5, symbol="XAUUSD", ts=3)])
    por = {g["key"]: g for g in r["by_symbol"]}
    assert por["XAUUSD"]["n"] == 2 and por["XAUUSD"]["net"] == 15
    assert por["EURUSD"]["net"] == -30


def test_an_empty_history_says_nothing_instead_of_zero():
    """Cero por ciento de aciertos sin operaciones se lee como «va fatal»."""
    r = tradestats.summarize([])
    assert r["n_closed"] == 0 and r["net"] == 0
    assert r["win_pct"] is None and r["best"] is None and r["avg_win"] is None


def test_only_open_positions_give_no_result_either():
    r = tradestats.summarize([op(state="open", lots=1.0)])
    assert r["win_pct"] is None and r["net"] == 0 and r["open_lots"] == 1.0


def test_a_missing_or_broken_pnl_is_treated_as_zero_not_as_a_crash():
    """Una fila rara del broker no puede tumbar el resumen entero."""
    r = tradestats.summarize([op(None, ts=1), {"state": "closed", "pnl": "raro"},
                              op(10, ts=2)])
    assert r["net"] == 10 and r["n_closed"] == 3


def test_rows_without_a_label_are_grouped_not_dropped():
    """Lo que abriste a mano también es dinero y tiene que aparecer."""
    r = tradestats.summarize([{"state": "closed", "pnl": -25, "ts": 1}])
    assert r["by_strategy"][0]["key"] == "—" and r["by_strategy"][0]["net"] == -25
