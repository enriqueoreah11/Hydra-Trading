"""Reparto a varias cuentas: que el tamaño sea el correcto en CADA una.

El fallo caro aquí es mandar el mismo lotaje a una cuenta grande y a una pequeña.
Eso no es replicar: es reventar la pequeña. Por eso el modo por defecto es
proporcional al capital y hay una prueba por cada modo.
"""
from app import mirror


def d(**kw):
    base = {"account_id": 2, "alias": "live", "enabled": True, "mode": "equity"}
    base.update(kw)
    return base


def test_proportional_to_equity_by_default():
    lots, why = mirror.size_for(d(), base_lots=1.0, base_equity=10000, dest_equity=2000)
    assert lots == 0.2                      # la quinta parte del capital, la quinta parte
    assert "proporcional" in why


def test_same_lots_when_asked():
    lots, _ = mirror.size_for(d(mode="same"), 0.37, 10000, 250)
    assert lots == 0.37                     # aunque la cuenta sea diminuta: lo pediste


def test_multiplier():
    lots, why = mirror.size_for(d(mode="mult", value=2.5), 0.4, 10000, 10000)
    assert lots == 1.0 and "x2.5" in why


def test_without_equity_it_sends_nothing_instead_of_guessing():
    lots, why = mirror.size_for(d(), 1.0, 10000, None)
    assert lots == 0.0
    assert "no mando nada" in why


def test_lots_are_rounded_and_bounded():
    assert mirror.clamp_lots(0.014999) == 0.01
    assert mirror.clamp_lots(0.0001) == 0.01          # nunca por debajo del mínimo
    assert mirror.clamp_lots(999) == 100.0
    assert mirror.clamp_lots(0) == 0.0


def test_plan_skips_the_disabled_and_marks_what_it_cannot_size():
    dests = [d(account_id=2, alias="live"),
             d(account_id=3, alias="prop", enabled=False),
             d(account_id=4, alias="sin datos")]
    rows = mirror.plan(dests, base_lots=1.0, base_equity=10000,
                       equities={2: 5000})            # de la 4 no se sabe el capital
    assert [r["account_id"] for r in rows] == [2, 4]  # la desactivada no aparece
    assert rows[0]["lots"] == 0.5 and rows[0]["skip"] is False
    assert rows[1]["lots"] == 0.0 and rows[1]["skip"] is True
    assert rows[0]["units"] == 50000


def test_a_tiny_account_gets_the_minimum_not_zero():
    """Proporcional, sí, pero por debajo del mínimo del broker no se puede operar."""
    lots, _ = mirror.size_for(d(), base_lots=1.0, base_equity=100000, dest_equity=300)
    assert lots == 0.01


def test_risk_mode_sizes_by_that_accounts_own_capital():
    """Cada cuenta arriesga LO SUYO: 1% de 5.000 con stop de 25 pips."""
    lots, why = mirror.size_for(d(mode="risk", value=1.0), base_lots=99, base_equity=100000,
                                dest_equity=5000, sl_pips=25, pip_value=10)
    assert lots == 0.2                       # 50 USD / (25 pips × 10) = 0.2 lotes
    assert "1% de 5000" in why
    # y no depende del lotaje de la principal
    lots2, _ = mirror.size_for(d(mode="risk", value=1.0), base_lots=0.01, base_equity=100000,
                               dest_equity=5000, sl_pips=25, pip_value=10)
    assert lots2 == lots


def test_risk_without_stop_sends_nothing():
    lots, why = mirror.size_for(d(mode="risk", value=1.0), 1.0, 10000, 5000, sl_pips=0)
    assert lots == 0.0 and "no mando nada" in why


def test_symbols_are_renamed_per_account():
    prop = d(suffix=".raw", symbols={"XAUUSD": "GOLD.pro"})
    assert mirror.map_symbol(prop, "EURUSD") == "EURUSD.raw"   # por sufijo
    assert mirror.map_symbol(prop, "XAUUSD") == "GOLD.pro"     # la tabla manda
    assert mirror.map_symbol(d(), "EURUSD") == "EURUSD"        # sin nada, igual


def test_symbol_filters_per_account():
    solo_fx = d(only=["EURUSD", "GBPUSD"])
    assert mirror.allowed(solo_fx, "EURUSD") and not mirror.allowed(solo_fx, "XAUUSD")
    sin_oro = d(never=["XAUUSD"])
    assert mirror.allowed(sin_oro, "EURUSD") and not mirror.allowed(sin_oro, "XAUUSD")


def test_plan_marks_a_symbol_not_allowed_and_renames_the_rest():
    dests = [d(account_id=2, mode="risk", value=0.5, suffix=".raw"),
             d(account_id=3, alias="solo fx", only=["EURUSD"])]
    rows = mirror.plan(dests, 1.0, 100000, {2: 20000, 3: 20000},
                       symbol="XAUUSD", sl_pips=50, pip_value=10)
    assert rows[0]["symbol"] == "XAUUSD.raw" and rows[0]["lots"] == 0.2
    assert rows[1]["skip"] is True and "no está permitido" in rows[1]["why"]
