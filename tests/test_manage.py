"""Gestión de posiciones: que proteja, que no afloje y que no abra nada.

El fallo caro aquí no es dejar de mover un stop: es MOVERLO HACIA ATRÁS. Eso
convierte una pérdida acotada en una abierta, así que hay una prueba por cada forma
en la que podría pasar.
"""
from app import botpolicy, manage


def pos(**kw):
    base = {"position_id": 1, "symbol": "EURUSD", "side": "BUY", "entry_price": 1.1000,
            "volume_units": 100000, "stop_loss": 1.0950, "take_profit": None}
    base.update(kw)
    return base


POL = {"breakeven": {"on": True, "trigger_pips": 20, "offset_pips": 2},
       "trailing": {"on": True, "start_pips": 40, "distance_pips": 15},
       "partials": [{"pct": 50, "trigger_pips": 30, "on": True}]}


def test_does_nothing_before_the_trigger():
    assert manage.plan(pos(), POL, 1.1010) == []          # +10 pips: aún no


def test_breakeven_moves_the_stop_to_entry_plus_offset():
    acts = manage.plan(pos(), POL, 1.1025)                # +25 pips
    assert [a["action"] for a in acts] == ["amend_sl"]
    assert abs(acts[0]["stop_loss"] - 1.1002) < 1e-9      # entrada + 2 pips
    assert "break-even" in acts[0]["reason"]


def test_partial_fires_once_and_not_again():
    acts = manage.plan(pos(), POL, 1.1035)                # +35 pips
    part = [a for a in acts if a["action"] == "close_partial"]
    assert part and part[0]["units"] == 50000
    again = manage.plan(pos(), POL, 1.1040, done={"p1"})
    assert not [a for a in again if a["action"] == "close_partial"]


def test_trailing_wins_when_it_protects_more():
    acts = manage.plan(pos(), POL, 1.1060, done={"p1"})   # +60 pips
    sl = [a for a in acts if a["action"] == "amend_sl"][0]
    assert abs(sl["stop_loss"] - 1.1045) < 1e-9           # 15 pips por debajo
    assert "trailing" in sl["reason"]


def test_never_moves_the_stop_backwards():
    """El caso que arruina cuentas: el precio baja y el trailing propone peor stop."""
    p = pos(stop_loss=1.1045)                             # ya protegido en +45
    acts = manage.plan(p, POL, 1.1050)                    # trailing daria 1.1035
    assert [a for a in acts if a["action"] == "amend_sl"] == []


def test_sell_side_is_mirrored():
    p = pos(side="SELL", entry_price=1.1000, stop_loss=1.1050)
    acts = manage.plan(p, POL, 1.0975)                    # +25 pips a favor
    sl = [a for a in acts if a["action"] == "amend_sl"][0]
    assert abs(sl["stop_loss"] - 1.0998) < 1e-9           # entrada − 2 pips
    # y en venta, "mejor" es MÁS BAJO
    assert sl["stop_loss"] < p["stop_loss"]


def test_it_never_proposes_opening_anything():
    for price in (1.0900, 1.1000, 1.1100, 1.2000):
        for a in manage.plan(pos(), POL, price):
            assert a["action"] in ("amend_sl", "close_partial", "close")


def test_jpy_and_gold_use_their_own_pip():
    assert manage.pip_size("USDJPY") == 0.01
    assert manage.pip_size("XAUUSD") == 0.1
    assert manage.pip_size("US500") == 1.0
    # +25 pips en USDJPY son 25 céntimos, no 0.0025
    p = pos(symbol="USDJPY", entry_price=150.00, stop_loss=149.50)
    acts = manage.plan(p, POL, 150.25)
    assert abs([a for a in acts if a["action"] == "amend_sl"][0]["stop_loss"] - 150.02) < 1e-9


# ------------------------------------------------ lectura de la politica del .algo

def algo(*names_defaults):
    return {"groups": [{"group": "g", "params": [
        {"name": n, "label": n, "type": "?", "default": v} for n, v in names_defaults]}]}


def test_policy_read_from_typical_bot_parameters():
    pol = botpolicy.from_params(algo(
        ("UseBreakEven", True), ("BreakEvenTriggerPips", 18), ("BreakEvenOffsetPips", 1),
        ("UseTrailing", True), ("TrailingStartPips", 35), ("TrailingDistancePips", 12),
        ("UsePartialClose", True), ("PartialClosePct", 40), ("PartialClosePips", 25),
        ("StopLossPips", 60), ("TakeProfitPips", 120)))
    assert pol["breakeven"] == {"on": True, "trigger_pips": 18.0, "offset_pips": 1.0}
    assert pol["trailing"]["distance_pips"] == 12.0 and pol["trailing"]["start_pips"] == 35.0
    assert pol["partials"][0]["pct"] == 40.0 and pol["partials"][0]["trigger_pips"] == 25.0
    assert pol["sl_pips"] == 60.0 and pol["tp_pips"] == 120.0
    assert pol["usable"] is True
    assert pol["source"]["be_trigger"] == "BreakEvenTriggerPips"   # auditable


def test_switch_off_means_off():
    pol = botpolicy.from_params(algo(("UseBreakEven", False), ("BreakEvenTriggerPips", 18)))
    assert pol["breakeven"]["on"] is False
    assert manage.plan(pos(), pol, 1.1030) == []


def test_absurd_limits_are_not_taken_as_values():
    """cTrader usa 2147483647 como 'sin límite': tomarlo daría un trailing imposible."""
    pol = botpolicy.from_params(algo(("UseTrailing", True),
                                     ("TrailingDistancePips", 2147483647)))
    assert pol["trailing"]["distance_pips"] is None
    assert manage.plan(pos(), pol, 1.1500) == []


def test_management_params_it_cannot_map_are_reported():
    pol = botpolicy.from_params(algo(("TrailingWeirdMagicMode", 3), ("UseBreakEven", True),
                                     ("BreakEvenTriggerPips", 10)))
    assert "TrailingWeirdMagicMode" in pol["unmapped"]


def test_explain_says_plainly_when_there_is_nothing_to_do():
    txt = " ".join(manage.explain(botpolicy.from_params(algo(("Lots", 0.1)))))
    assert "no se tocará nada" in txt
