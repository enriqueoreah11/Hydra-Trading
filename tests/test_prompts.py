"""Los prompts de los agentes: lo que se les dice y lo que no se les puede decir.

Un prompt no falla con un error. Falla dando respuestas razonables construidas sobre
una instrucción equivocada, y desde fuera se ve exactamente igual que si funcionara.
El caso concreto que motivó estas pruebas: los prompts hablaban solo de metales,
petróleo e índices. Al meter pares de forex en la lista de símbolos, el analista
seguía recibiendo «cuidado con los inventarios EIA» mirando un EURGBP, y ninguna
prueba, ningún log y ninguna pantalla lo habrían enseñado.
"""
import asyncio

import pytest

from app import macro
from app.agents import analyst, architect, overnight, reviewer, risk_manager, tester


TODOS = {"analyst": analyst.SYSTEM, "risk_manager": risk_manager.SYSTEM,
         "overnight": overnight.SYSTEM, "reviewer": reviewer.SYSTEM,
         "architect": architect.SYSTEM, "tester": tester.SYSTEM}


def plano(t: str) -> str:
    """Sin saltos de línea: lo que se comprueba es lo que dice, no cómo se envuelve.
    Una prueba que se rompe al re-ajustar un párrafo solo enseña a no tocarlo."""
    return " ".join(str(t).split())


# -------------------------------------- ningún agente casado con un mercado

@pytest.mark.parametrize("nombre", sorted(TODOS))
def test_no_agent_is_hardwired_to_one_set_of_instruments(nombre):
    """EL fallo. Si el prompt nombra los instrumentos como si fueran todos, añadir
    uno nuevo lo deja fuera en silencio: el modelo aplica las manías del mercado
    equivocado y responde con total normalidad."""
    t = plano(TODOS[nombre]).lower()
    # Nombrar un mercado como EJEMPLO está bien; declararlo como el universo, no.
    for frase in ("sistema de trading multi-agente que opera metales",
                  "especializado en metales", "operamos oro, plata, petroleo e indices"):
        assert frase not in t, f"{nombre} da por hecho qué instrumentos se operan"


def test_every_family_has_its_own_behaviour_note():
    """Cada familia recibe sus manías: si forex heredara las del oro, el analista
    esperaría reacciones que ese mercado no tiene."""
    for s, esperado in (("XAUUSD", "metal"), ("XTIUSD", "energia"), ("US100", "indice"),
                        ("EURGBP", "forex"), ("BTCUSD", "cripto")):
        assert macro.familia(s) == esperado
        assert macro.comportamiento(s) == macro.COMPORTAMIENTO[esperado]


def test_an_unknown_instrument_gets_told_not_to_assume():
    """Lo peligroso de un símbolo raro no es no saber de él: es suponerle el
    comportamiento de otro porque el nombre se parece."""
    t = plano(macro.comportamiento("XYZ123")).lower()
    assert "no le supongas" in t


def test_the_behaviour_note_reaches_the_analyst(monkeypatch):
    visto = {}

    async def _ask(system, user, **kw):
        visto["user"] = user
        return {"action": "no_trade", "direction": "none", "stop_loss": 0,
                "take_profit": 0, "confidence": 0, "thesis": "x", "invalidation": "y"}
    monkeypatch.setattr(analyst.llm, "ask", _ask)
    asyncio.run(analyst.analyze("EURGBP", "M15", {}, "pb", []))
    assert "diferencial de tipos" in visto["user"]
    assert "inventarios EIA" not in visto["user"], "le dio las manías del petróleo"


def test_gold_still_gets_gold_advice(monkeypatch):
    visto = {}

    async def _ask(system, user, **kw):
        visto["user"] = user
        return {"action": "no_trade", "direction": "none", "stop_loss": 0,
                "take_profit": 0, "confidence": 0, "thesis": "x", "invalidation": "y"}
    monkeypatch.setattr(analyst.llm, "ask", _ask)
    asyncio.run(analyst.analyze("XAUUSD", "M15", {}, "pb", []))
    assert "tipos reales" in visto["user"] and "Londres-NY" in visto["user"]


# ------------------------------------------------- disciplina del analista

def test_the_analyst_is_warned_that_a_chart_always_has_a_story():
    """Es la instrucción que más dinero ahorra: delante de un gráfico siempre se
    puede construir un argumento, y encontrarlo no es haber encontrado un setup."""
    t = plano(analyst.SYSTEM).lower()
    assert "siempre se puede construir una historia" in t
    assert "no_trade" in t


def test_the_analyst_may_not_use_data_it_was_not_given():
    """Rellenar un hueco con «lo que suele pasar» produce una tesis coherente y
    falsa, que es la peor combinación posible."""
    t = plano(analyst.SYSTEM).lower()
    assert "no supongas" in t and "nunca para rellenarlo" in t


def test_the_analyst_is_told_what_calibrated_actually_means():
    """«Calibrada» sin definir no significa nada. Con la definición, el número que
    devuelve se puede comprobar después contra los resultados."""
    assert "de cada 100 propuestas con 70" in plano(analyst.SYSTEM)


def test_the_analyst_may_not_shrink_the_stop_to_make_the_numbers_work():
    """Mover el stop para que salga la R es la forma más cara de equivocarse: la
    operación aprueba el filtro y muere en el ruido."""
    assert "salgan las cuentas" in plano(analyst.SYSTEM)


def test_a_refusal_has_to_say_what_was_missing():
    """Un no_trade mudo no se puede revisar, y sin revisarlo no hay forma de saber
    si el filtro está demasiado apretado."""
    assert "di en una frase QUE falto" in plano(analyst.SYSTEM)


# ---------------------------------------------- disciplina del resto

def test_the_risk_manager_knows_its_two_errors_do_not_cost_the_same():
    t = plano(risk_manager.SYSTEM)
    assert "no cuestan lo mismo" in t and "veta" in t.lower()


def test_the_risk_manager_catches_the_same_bet_twice_in_forex():
    """Largo EURUSD y corto USDCHF es una posición con dos nombres, y el chequeo por
    correlación no siempre la ve."""
    assert "USDCHF" in plano(risk_manager.SYSTEM)


def test_the_risk_manager_must_say_which_datum_motivated_the_veto():
    assert "no se puede revisar" in plano(risk_manager.SYSTEM)


def test_the_overnight_may_never_widen_a_stop():
    t = plano(overnight.SYSTEM)
    assert "Ampliar un stop" in t and "jamas dar mas margen" in t


def test_the_overnight_is_told_not_to_close_just_because_it_is_losing():
    """Cerrar en rojo antes de la invalidación convierte una estrategia con ventaja
    en una que pierde poco muchas veces — y cada cierre suelto parece prudente."""
    t = plano(overnight.SYSTEM)
    assert "Cerrar solo porque va en perdida" in t
    assert "pierde poco muchas veces" in t


def test_the_reviewer_is_told_one_day_is_not_a_pattern():
    assert "no da para detectar ningun patron" in plano(reviewer.SYSTEM)


def test_the_reviewer_may_answer_that_there_is_nothing_to_change():
    """Sin este permiso explícito, un revisor inventa una recomendación cada día y
    el playbook se llena de cambios que nadie pidió."""
    assert "sin cambios, hace falta mas muestra" in plano(reviewer.SYSTEM)


def test_the_architect_knows_its_rules_outlive_the_day_that_caused_them():
    t = plano(architect.SYSTEM)
    assert "se queda anos" in t and "el de quitar es bajo" in t


def test_the_architect_must_attach_evidence_to_every_rule():
    assert "no se puede revisar despues" in plano(architect.SYSTEM)


def test_the_architect_may_not_leave_a_traded_symbol_without_a_section():
    """Un símbolo sin sección se lee como «no operar» sin que nadie lo haya decidido."""
    assert "sin seccion se lee como" in plano(architect.SYSTEM)


def test_the_tester_may_not_improve_the_strategy_it_is_measuring():
    """Si la corrige por el camino, lo que se mide no es la estrategia del usuario y
    no hay forma de notarlo en el resultado."""
    t = plano(tester.SYSTEM)
    assert "ni las mejores" in t and "no será" in t


def test_the_tester_refuses_on_ambiguity_instead_of_guessing():
    t = plano(tester.SYSTEM)
    assert "ambiguas" in t and "convierte la" in t
