"""Cada cierre revisado y clasificado, sin buscarle causa a lo que no la tiene.

El riesgo de automatizar esto no es clasificar mal: es clasificar DE MÁS. Una
estrategia con ventaja pierde el 40% de las veces sin que nada esté roto. Un
sistema que le encuentra una causa a cada pérdida acaba cambiando reglas por ruido
— y así es exactamente como se rompe una estrategia que funcionaba.
"""
import pytest

from app import cierres


def op(**kw):
    base = {"symbol": "XAUUSD", "ts": 1, "strategy": "50cal", "r": -1.0,
            "max_favor_r": 0.2, "velas": 20}
    base.update(kw)
    return base


# ------------------------------------------ el sesgo correcto: ruido

def test_a_plain_loss_is_noise_not_a_defect():
    """EL punto. Sin este sesgo, el sistema cambia la estrategia cada semana por
    pérdidas que eran el coste normal de tenerla."""
    r = cierres.clasificar(op())
    assert r["categoria"] == "perdida_esperada"
    assert "no hay nada" in r["nota"]


def test_a_winner_has_nothing_to_diagnose():
    r = cierres.clasificar(op(r=2.0))
    assert r["gano"] is True and r["categoria"] is None


def test_all_losses_being_noise_says_do_not_touch_anything():
    res = cierres.resumen([cierres.clasificar(op()) for _ in range(10)])
    assert "nada que arreglar" in res["lectura"]


# --------------------------------- lo que sí se sabe por aritmética

def test_a_trade_that_gave_back_more_than_1r_is_a_tight_stop():
    """Si llegó a ir 1.5R a favor y acabó en el stop, el stop estaba donde el ruido
    lo alcanza. Eso no es opinión, es resta."""
    r = cierres.clasificar(op(max_favor_r=1.5))
    assert r["categoria"] == "sl_muy_ajustado" and r["seguro"] is True


def test_a_trade_that_died_in_three_bars_entered_late():
    r = cierres.clasificar(op(velas=2, max_favor_r=0.0))
    assert r["categoria"] == "entrada_tardia"


def test_an_unfiltered_news_event_is_named():
    r = cierres.clasificar(op(), {"noticia_alto_impacto": True})
    assert r["categoria"] == "noticia_no_filtrada"


def test_the_spread_eating_the_edge_is_named():
    r = cierres.clasificar(op(), {"spread_r": 0.3})
    assert r["categoria"] == "ejecucion"


def test_a_poor_session_is_flagged_but_not_as_certain():
    """Operar de madrugada y perder puede ser causa o coincidencia; marcarlo como
    seguro invitaría a prohibir una sesión por dos casos."""
    r = cierres.clasificar(op(), {"sesion": "Asia/madrugada"})
    assert r["categoria"] == "sesion_baja_liquidez" and r["seguro"] is False


def test_the_tight_stop_check_beats_the_session_one():
    """Si llegó a ir a favor, la sesión no fue el problema — el stop sí. Con el
    orden al revés se archivaría como «mala hora» y el stop seguiría igual."""
    r = cierres.clasificar(op(max_favor_r=1.8), {"sesion": "Asia/madrugada"})
    assert r["categoria"] == "sl_muy_ajustado"


# ------------------------------------- lo que falta se dice, no se rellena

def test_missing_data_is_declared_not_assumed():
    """Sin `max_favor_r` no se puede saber si el stop estuvo mal. Suponerlo daría
    un diagnóstico con la misma pinta que uno real."""
    r = cierres.clasificar({"symbol": "X", "r": -1.0})
    assert "max_favor_r" in r["faltan_datos"]
    assert r["categoria"] == "perdida_esperada"


# ------------------------------------------ un caso no es un patrón

def test_one_occurrence_is_not_a_pattern():
    """Cambiar una regla por un caso suelto es cambiarla por ruido con nombre."""
    lote = [cierres.clasificar(op()) for _ in range(9)]
    lote.append(cierres.clasificar(op(max_favor_r=1.5)))
    res = cierres.resumen(lote)
    assert "todavía no es un patrón" in res["lectura"]


def test_something_repeated_is_a_pattern():
    lote = [cierres.clasificar(op()) for _ in range(5)]
    lote += [cierres.clasificar(op(max_favor_r=1.5)) for _ in range(4)]
    res = cierres.resumen(lote)
    assert "ya es un patrón" in res["lectura"]
    assert res["categorias"]["sl_muy_ajustado"] == 4


def test_the_summary_says_what_share_was_just_noise():
    lote = [cierres.clasificar(op()) for _ in range(8)]
    lote += [cierres.clasificar(op(max_favor_r=1.5)) for _ in range(2)]
    assert cierres.resumen(lote)["pct_ruido"] == 80.0


def test_a_batch_of_only_winners_has_nothing_to_say():
    res = cierres.resumen([cierres.clasificar(op(r=1.0)) for _ in range(5)])
    assert res["perdidas"] == 0 and "sin pérdidas" in res["lectura"]


def test_the_categories_are_the_ones_the_system_already_uses():
    """Inventar categorías nuevas dejaría los post-mortems viejos incomparables."""
    from app.mcp_gate import CATEGORIES
    for t in ({"max_favor_r": 1.5}, {"velas": 2, "max_favor_r": 0.0}, {}):
        c = cierres.clasificar(op(**t))["categoria"]
        assert c is None or c in CATEGORIES
