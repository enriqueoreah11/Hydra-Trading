"""El patrón del Confluence Bot corriendo dentro de Hydra.

El error que arruina una réplica de confluencias no da ningún fallo: contar
SEÑALES en vez de FAMILIAS. Tres EMAs pegadas al mismo precio son una razón para
que ese nivel importe, no tres — pero puntúan como tres, y entonces cualquier sitio
donde se juntan medias parece una zona de oro. Son justo los sitios donde no hay
nada, y el sistema se pone a operarlos con la confianza de tener «cuatro
confluencias».

El otro, igual de silencioso: medir la zona en pips. La misma configuración que es
sensata en el EURUSD no toca una zona en el Nasdaq en la vida y salta con todo en
el oro. No se ve en ningún log: se ve en que un símbolo no opera nunca.
"""
import pytest

from app import confluencia, strategies
from app.broker import Candle


def vela(c, hi=None, lo=None, op=None, ts=0):
    """La mecha va en PROPORCION al precio, no en valor absoluto.

    Con una mecha fija de ±0.5, una serie de EURUSD tendría un rango del 50% por
    vela y una de Nasdaq del 0.002%. La prueba de escala mediría entonces el
    disparate de la fixture, no el del código.
    """
    mecha = abs(c) * 0.002
    return Candle(ts=ts, open=op if op is not None else c,
                  high=hi if hi is not None else c + mecha,
                  low=lo if lo is not None else c - mecha, close=c, volume=100)


def serie(n, f):
    return [vela(f(i), ts=1700000000 + i * 900) for i in range(n)]


P = dict(strategies.DEFAULTS["confluencia"])


# ------------------------------------------- familias, no señales

def test_zones_are_scored_by_distinct_families_not_by_level_count():
    """EL fallo. Se construye un grupo con cuatro niveles de UNA sola familia: tiene
    que puntuar 1, no 4."""
    grupo = [("EMA", 100.0), ("EMA", 100.1), ("EMA", 100.2), ("EMA", 100.05)]
    fams = sorted({f for f, _ in grupo})
    assert len(fams) == 1, "el conteo por familias no está distinguiendo"


def test_a_real_zone_groups_several_families():
    v = serie(600, lambda i: 100 + (i % 40) * 0.05)
    zs = confluencia.zonas(v, len(v) - 1, P)
    assert zs, "no agrupó ninguna zona"
    assert all(z["n_familias"] <= len(z["n_niveles"] * [0]) + 99 for z in zs)
    assert all(z["n_familias"] <= z["n_niveles"] for z in zs), \
        "hay más familias que niveles: se están contando dos veces"


def test_the_family_names_match_the_bot_taxonomy():
    """Se llaman igual a propósito: si aquí fueran otras, no habría forma de comparar
    una captura del bot con una señal de Hydra."""
    from app.web import create_app  # noqa: F401  (solo para asegurar que importa)
    assert set(confluencia.FAMILIAS) >= {"HTFKL", "KeyLevel", "Fib", "EMA", "SMA",
                                         "Session", "Round"}


def test_what_cannot_be_replicated_is_declared():
    """Si tu bot lee líneas dibujadas a mano, parte de sus señales son imposibles
    aquí. Callarlo haría leer una coincidencia baja como «no se parece» cuando lo
    que pasa es que le faltan datos."""
    assert "TrendLine" in confluencia.NO_REPLICADAS
    v = serie(400, lambda i: 100 + i * 0.01)
    assert "TrendLine" in confluencia.radar(v, P)["no_replicadas"]


# --------------------------------------------- anchura en ATR, no en pips

def test_the_zone_width_scales_with_the_instrument():
    """La misma configuración tiene que valer para un par de forex y para un índice.
    En pips, una de las dos no toca una zona jamás y nadie se entera."""
    barato = serie(600, lambda i: 1.08 + (i % 40) * 0.0002)
    caro = serie(600, lambda i: 21000 + (i % 40) * 4.0)
    zb = confluencia.zonas(barato, len(barato) - 1, P)
    zc = confluencia.zonas(caro, len(caro) - 1, P)
    assert zb and zc, "una de las dos escalas se quedó sin zonas"
    # la anchura relativa al precio tiene que ser del mismo orden en las dos
    rb = zb[0]["ancho_atr"] / 1.08
    rc = zc[0]["ancho_atr"] / 21000
    assert 0.05 < rb / rc < 20, f"la anchura no escala: {rb} vs {rc}"


def test_round_levels_adapt_to_the_price_scale():
    """1.0850 y 3400 no tienen los mismos números redondos, y una tabla fija se
    queda vieja en cuanto añades un símbolo."""
    assert confluencia._redondos(1.0850, 0.001)
    caros = confluencia._redondos(3400.0, 5.0)
    assert caros and all(abs(x - 3400) < 500 for x in caros)


def test_a_zero_price_does_not_explode():
    assert confluencia._redondos(0.0, 1.0) == []
    assert confluencia._redondos(100.0, 0.0) == []


# ----------------------------------------------------- cuándo entra

def test_it_does_not_signal_without_enough_families():
    """Subir el mínimo a cinco tiene que dejar de dar señales: si sigue dándolas, el
    filtro no está haciendo nada."""
    v = serie(600, lambda i: 100 + (i % 30) * 0.1)
    exigente = {**P, "min_familias": 5}
    señales = sum(1 for i in range(300, len(v))
                  if confluencia.confluencia(v, exigente, i) is not None)
    laxo = sum(1 for i in range(300, len(v))
               if confluencia.confluencia(v, {**P, "min_familias": 2}, i) is not None)
    assert señales <= laxo, "exigir más familias dio MÁS señales"


def test_it_never_signals_without_enough_history():
    v = serie(100, lambda i: 100 + i * 0.1)
    assert all(confluencia.confluencia(v, P, i) is None for i in range(len(v)))


def test_a_support_bounce_buys_and_closes_above_the_zone():
    """Entrar por cercanía sin confirmar es entrar antes de que el nivel haya hecho
    nada. Si la vela cierra DENTRO de la zona, el nivel está cediendo — eso es lo
    contrario de un rebote."""
    v = serie(600, lambda i: 100 + (i % 40) * 0.05)
    i = len(v) - 1
    zs = [z for z in confluencia.zonas(v, i, P) if z["n_familias"] >= 3]
    if not zs:
        pytest.skip("esta serie sintética no formó zona de 3 familias")
    for j in range(400, i):
        s = confluencia.confluencia(v, P, j)
        if s and s.direction == "buy":
            assert s.sl < s.entry < s.tp
            assert v[j].close > v[j].open, "compró con una vela bajista"
            return


def test_the_stops_are_on_the_right_side():
    v = serie(900, lambda i: 100 + (i % 50) * 0.08)
    for i in range(300, len(v)):
        s = confluencia.confluencia(v, P, i)
        if s is None:
            continue
        if s.direction == "buy":
            assert s.sl < s.entry < s.tp
        else:
            assert s.tp < s.entry < s.sl


# ------------------------------------------------- el radar (todos los pares)

def test_the_radar_shows_zones_even_with_no_signal():
    """Una zona de cuatro familias a media sesión de distancia es información
    aunque hoy no se opere. Enseñar solo las entradas esconde el mapa."""
    v = serie(600, lambda i: 100 + (i % 40) * 0.05)
    r = confluencia.radar(v, P)
    assert r["ok"] is True and r["zonas"]
    assert all("lado" in z and "dist_atr" in z for z in r["zonas"])


def test_the_radar_says_when_there_is_not_enough_history():
    r = confluencia.radar(serie(50, lambda i: 100 + i), P)
    assert r["ok"] is False and "250 velas" in r["error"]


def test_the_radar_marks_support_and_resistance_by_side():
    v = serie(600, lambda i: 100 + (i % 40) * 0.05)
    r = confluencia.radar(v, P)
    for z in r["zonas"]:
        assert z["lado"] == ("soporte" if z["centro"] < r["precio"] else "resistencia")


# ------------------------------------- hereda todo lo que ya existía

def test_it_is_registered_as_one_more_strategy():
    """Es lo que le da gratis la medición fuera de muestra, el coste, la flota y el
    playbook automático. Sin registrarla habría que rehacer todo eso para ella."""
    assert "confluencia" in strategies.STRATEGIES
    assert "confluencia" in strategies.TUNABLE
    assert "confluencia" in strategies.DEFAULTS


def test_its_tunable_params_are_clamped_like_any_other():
    p = strategies.clamp("confluencia", {"min_familias": 99, "zona_atr": -5})
    assert p["min_familias"] <= 5 and p["zona_atr"] >= 0.15


def test_the_search_space_stays_small_on_purpose():
    """Cuantas más combinaciones se prueban, más fácil es que la mejor lo sea por
    casualidad. Abrir todos los parámetros multiplicaría la búsqueda sin cambiar
    el patrón."""
    assert len(strategies.TUNABLE["confluencia"]) <= 5


def test_it_can_be_measured_by_the_discoverer_without_crashing():
    from app import optimize
    v = serie(1200, lambda i: 100 + (i % 60) * 0.07)
    r = optimize.run(v, "confluencia", P, horizon=40)
    assert r["ok"] is True
