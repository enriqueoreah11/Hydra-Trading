"""Que encuentre entradas solo — y sobre todo, que no se invente ninguna.

Un buscador de estrategias es una máquina de auto-engaño. Le das histórico y
siempre, SIEMPRE, encuentra algo: con doscientas combinaciones la mejor luce bien
aunque no haya nada que encontrar. Si eso pasa el filtro, el sistema se pone a
operar una casualidad con dinero de verdad y encima con la confianza de que "está
medido".

Casi todo lo que se prueba aquí es el filtro: qué se rechaza y por qué.
"""
import pytest

from app import descubridor
from app.broker import Candle


def velas(n, patron):
    """Velas sintéticas: `patron(i)` da el cierre. El rango se construye alrededor."""
    out = []
    for i in range(n):
        c = float(patron(i))
        out.append(Candle(ts=1700000000 + i * 900, open=c, high=c + 1.0,
                          low=c - 1.0, close=c, volume=100))
    return out


def res(trades, esperanza, dd=-1.0, win=50.0):
    return {"ok": True, "trades": trades, "expectancy_r": esperanza,
            "win_pct": win, "max_dd_r": dd, "total_r": round(esperanza * trades, 2)}


# ------------------------------------------------------ el filtro, uno a uno

def test_a_thin_out_of_sample_is_rejected():
    """Con cinco operaciones no se mide nada, luzca lo que luzca."""
    v = descubridor.evaluar(res(200, 0.5), res(5, 1.2))
    assert v["vale"] is False and "5 operaciones" in v["motivo"]


def test_a_tiny_edge_is_eaten_by_costs():
    """0.03R de ventaja no es una ventaja: es el spread de un lado."""
    v = descubridor.evaluar(res(200, 0.30), res(60, 0.08))
    assert v["vale"] is False and "spread" in v["motivo"]


def test_the_cost_is_actually_subtracted():
    """EL error clásico del backtest: sin coste, todo funciona."""
    v = descubridor.evaluar(res(200, 0.50), res(60, 0.40), coste_r=0.05)
    assert v["esperanza_oos"] == 0.35
    assert v["coste_r"] == 0.05


def test_a_curve_fit_is_caught_by_the_gap():
    """Dentro 1.0R y fuera 0.2R no es una estrategia con mal día: es una
    combinación ajustada al ruido de la primera mitad."""
    v = descubridor.evaluar(res(200, 1.0), res(40, 0.25))
    assert v["vale"] is False and "ajustada al ruido" in v["motivo"]


def test_an_unbearable_drawdown_is_rejected_even_if_it_ends_up_positive():
    """El saldo final no es lo único: nadie aguanta una racha que triplica lo que
    va a ganar, y una estrategia que no se aguanta no se opera."""
    v = descubridor.evaluar(res(200, 0.40), res(40, 0.35, dd=-40.0))
    assert v["vale"] is False and "por el camino" in v["motivo"]


def test_something_that_survives_everything_is_accepted():
    v = descubridor.evaluar(res(200, 0.60), res(40, 0.45, dd=-4.0))
    assert v["vale"] is True and v["esperanza_oos"] == 0.40
    assert v["total_r_oos"] == 16.0


def test_the_verdict_always_explains_itself():
    """«No pasó» sin motivo es indistinguible de un fallo del sistema."""
    for v in (descubridor.evaluar(res(200, 0.5), res(3, 1.0)),
              descubridor.evaluar(res(200, 0.5), res(40, 0.01)),
              descubridor.evaluar(res(200, 0.6), res(40, 0.45))):
        assert v["motivo"]


# -------------------------------------------------- sobre velas de verdad

def test_pure_noise_yields_nothing():
    """EL caso que importa. Velas sin ninguna estructura: si de aquí sale un setup,
    el filtro no sirve para nada y el sistema operaría ruido creyendo que mide."""
    import random
    rnd = random.Random(7)
    precio = [100.0]
    for _ in range(1500):
        precio.append(max(1.0, precio[-1] + rnd.gauss(0, 0.5)))
    d = descubridor.descubrir(velas(len(precio), lambda i: precio[i]), "RUIDO", steps=2)
    assert d["hallazgos"] == [], f"encontró ventaja en ruido puro: {d['hallazgos']}"


def test_it_says_how_many_combinations_it_tried():
    """Con doscientos intentos, la mejor sale bien por casualidad. Que ese número
    no se vea es lo que convierte una búsqueda en una promesa."""
    d = descubridor.descubrir(velas(900, lambda i: 100 + i * 0.01), "X", steps=2)
    assert d["combinaciones_probadas"] > 0
    assert "combinaciones" in d["aviso"]


def test_too_little_history_is_not_the_same_as_no_edge():
    """Los dos acaban en una lista vacía y piden cosas opuestas: sin ventaja es «no
    operes esto»; sin histórico es «bájate más velas». Confundirlos deja un símbolo
    apagado para siempre por un problema de datos."""
    d = descubridor.descubrir(velas(100, lambda i: 100 + i), "X", steps=2)
    assert d["hallazgos"] == [] and d["sin_datos"] is True
    assert "no se ha mirado" in d["aviso"]
    assert all("velas y hay 100" in x["motivo"] for x in d["descartes"])


def test_a_trending_market_does_produce_something():
    """El otro lado: si el filtro rechazara TODO tampoco serviría. Una tendencia
    limpia y sostenida tiene que dejar pasar alguna estrategia de tendencia."""
    v = velas(2000, lambda i: 100 + i * 0.05)
    d = descubridor.descubrir(v, "TENDENCIA", steps=2)
    assert d["hallazgos"], "no dejó pasar nada ni en una tendencia perfecta"


# --------------------------------------------------- el playbook que escribe

def test_the_generated_playbook_forbids_inventing_setups():
    """Sin esta frase, un modelo con velas delante siempre encuentra una historia.
    Es lo único que separa «operar lo medido» de «operar lo que le parezca»."""
    pb = descubridor.a_playbook({"XAUUSD": {"hallazgos": [
        {"estrategia": "donchian", "params": {"lookback": 20}, "esperanza_oos": 0.4,
         "ops_oos": 30, "win_pct_oos": 45.0, "dd_oos": -3.0}], "velas": 2000,
        "combinaciones_probadas": 27}})
    assert "no_trade" in pb and "No inventes setups" in pb


def test_symbols_with_no_edge_are_listed_as_such():
    """Callarlos dejaría al analista sin saber si están sin mirar o mirados y
    descartados — y esas dos cosas piden lo contrario."""
    pb = descubridor.a_playbook({
        "XAUUSD": {"hallazgos": [{"estrategia": "donchian", "params": {},
                                  "esperanza_oos": 0.4, "ops_oos": 30,
                                  "win_pct_oos": 45.0, "dd_oos": -3.0}]},
        "US100": {"hallazgos": [], "descartes": [{"motivo": "nada pasó los mínimos"}]}})
    assert "sin ventaja medible" in pb and "US100" in pb
    assert "no se opera" in pb.lower()


def test_the_playbook_declares_the_cost_it_assumed():
    """Si su spread es peor, las cifras están infladas y tiene que poder verlo."""
    pb = descubridor.a_playbook({}, coste_r=0.08)
    assert "0.08" in pb


def test_the_playbook_says_what_it_does_not_know():
    pb = descubridor.a_playbook({})
    assert "no sabe" in pb and "noticias" in pb


def test_the_numbers_travel_with_every_rule():
    """Una regla sin su muestra al lado se lee como una ley."""
    pb = descubridor.a_playbook({"XAUUSD": {"hallazgos": [
        {"estrategia": "donchian", "params": {"lookback": 20}, "esperanza_oos": 0.42,
         "ops_oos": 31, "win_pct_oos": 45.0, "dd_oos": -3.0}]}})
    assert "0.42R" in pb and "31 operaciones" in pb and "fuera de muestra" in pb


def test_with_nothing_found_the_analyst_text_is_empty():
    """Un encabezado vacío le diría al analista que se miró y no había nada, cuando
    lo que pasa es que no hay con qué mirar todavía."""
    assert descubridor.texto({"symbol": "X", "hallazgos": []}) == ""
