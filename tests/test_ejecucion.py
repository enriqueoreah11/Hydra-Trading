"""El modelo razona, el código opera.

Es el consejo de su maestro y Hydra lo incumplía en el peor sitio: el agente
nocturno devolvía un `new_stop_loss` —un número salido de un modelo de lenguaje— y
ese número se mandaba al bróker sobre una posición viva. Había un control de
dirección (solo podía apretar), que evita lo peor, pero no acota el VALOR: un stop
«apretado» a dos pips del precio pasa ese control y lo barre el primer tick.
"""
import pytest

from app import gestion


ATR = 1.0


# --------------------------------------- el stop nunca se aleja, nunca

@pytest.mark.parametrize("side,entrada,actual,precio", [
    ("buy", 100.0, 99.0, 103.0),
    ("sell", 100.0, 101.0, 97.0),
])
def test_the_stop_never_moves_away(side, entrada, actual, precio):
    s, _ = gestion.stop_objetivo(side, entrada, actual, actual, precio, ATR)
    if s is None:
        return
    assert (s > actual) if side == "buy" else (s < actual)


def test_below_one_r_nothing_moves():
    """Mover el stop antes de que la operación haya ganado nada es reducir el
    espacio que la idea necesita para desarrollarse."""
    s, motivo = gestion.stop_objetivo("buy", 100.0, 99.0, 99.0, 100.5, ATR)
    assert s is None and "todavía no toca" in motivo


def test_at_one_r_it_goes_to_break_even():
    """Dejar de poder perder en una operación que ya ganó es lo único gratis."""
    s, motivo = gestion.stop_objetivo("buy", 100.0, 99.0, 99.0, 101.0, ATR,
                                      be_en_r=1.0, trail_atr=2.0, min_atr=0.0)
    assert s is not None and s >= 100.0
    assert "break-even" in motivo


def test_the_stop_is_never_glued_to_the_price():
    """EL fallo que el control de dirección no cazaba: un stop a dos pips pasa el
    «solo aprieta» y lo barre el ruido normal del instrumento."""
    s, _ = gestion.stop_objetivo("buy", 100.0, 99.0, 99.0, 110.0, ATR,
                                 trail_atr=0.01, min_atr=0.8)
    assert s is not None
    # el epsilon es por la coma flotante: 110.0 - 109.2 da 0.7999999999999972
    assert 110.0 - s >= 0.8 * ATR - 1e-9, "dejó el stop pegado al precio"


def test_a_sell_trails_from_above():
    s, _ = gestion.stop_objetivo("sell", 100.0, 101.0, 101.0, 95.0, ATR,
                                 be_en_r=1.0, trail_atr=2.0)
    assert s is not None and 95.0 < s < 101.0


def test_without_atr_it_refuses_instead_of_guessing():
    s, motivo = gestion.stop_objetivo("buy", 100.0, 99.0, 99.0, 105.0, 0.0)
    assert s is None and "sin datos" in motivo


def test_without_the_original_risk_it_does_not_move():
    """Sin saber cuánto se arriesgó no se puede saber cuánta R lleva, y sin eso
    mover el stop es adivinar."""
    s, motivo = gestion.stop_objetivo("buy", 100.0, None, None, 105.0, ATR)
    assert s is None and "no sé cuánto riesgo" in motivo


def test_an_already_better_stop_is_left_alone():
    s, motivo = gestion.stop_objetivo("buy", 100.0, 104.0, 99.0, 105.0, ATR,
                                      trail_atr=2.0)
    assert s is None and "ya está igual o mejor" in motivo


# ------------------------- los niveles del modelo, comprobados con aritmética

def test_a_stop_on_the_wrong_side_is_refused():
    """Entra sin dar error y la operación nace con el riesgo invertido."""
    ok, why = gestion.niveles_validos("buy", 100.0, 101.0, 105.0, ATR, 1.5)
    assert ok is False and "por debajo" in why


def test_a_stop_glued_to_price_is_refused():
    """Lo barre el ruido normal antes de que la idea llegue a estar equivocada."""
    ok, why = gestion.niveles_validos("buy", 100.0, 99.9, 105.0, ATR, 1.5)
    assert ok is False and "ruido normal" in why


def test_a_stop_absurdly_far_is_refused():
    ok, why = gestion.niveles_validos("buy", 100.0, 90.0, 130.0, ATR, 1.5)
    assert ok is False and "demasiado lejos" in why


def test_a_reward_that_does_not_match_the_claim_is_refused():
    """El que más se cuela: los tres números por separado parecen razonables."""
    ok, why = gestion.niveles_validos("buy", 100.0, 98.0, 101.0, ATR, 1.5)
    assert ok is False and "beneficio/riesgo" in why


def test_the_refusal_says_not_to_move_the_stop_closer():
    """Es la reacción natural a que te rechacen por R, y es la forma más cara de
    arreglarlo: la operación pasa el filtro y muere en el ruido."""
    _, why = gestion.niveles_validos("buy", 100.0, 98.0, 101.0, ATR, 1.5)
    assert "más cara" in why


def test_good_levels_pass():
    ok, _ = gestion.niveles_validos("buy", 100.0, 98.0, 104.0, ATR, 1.5)
    assert ok is True


def test_a_sell_is_judged_by_its_own_geometry():
    assert gestion.niveles_validos("sell", 100.0, 102.0, 96.0, ATR, 1.5)[0] is True
    assert gestion.niveles_validos("sell", 100.0, 98.0, 96.0, ATR, 1.5)[0] is False


def test_without_atr_nothing_is_approved():
    """Sin ATR no se puede decir si un stop es razonable, y aprobar por defecto
    dejaría pasar justo lo que este control existe para parar."""
    ok, why = gestion.niveles_validos("buy", 100.0, 98.0, 104.0, 0.0, 1.5)
    assert ok is False and "sin ATR" in why


# ------------------------------------------------ el ajuste queda apagado

def test_deterministic_execution_is_the_default():
    from app.config import settings
    assert settings.ejecucion_determinista is True


def test_closing_by_model_is_off_by_default():
    """Cerrar por una lectura equivocada mata una operación que iba bien, y eso no
    se deshace."""
    from app.config import settings
    assert settings.permitir_cierre_por_llm is False
