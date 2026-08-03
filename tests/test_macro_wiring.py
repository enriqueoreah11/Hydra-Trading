"""Que el macro llegue al cerebro sin mentir y sin costar una llamada por ciclo.

Tres cosas se rompen fácil aquí y ninguna da error:
1. Pedir FRED en cada análisis (6 símbolos × cada 15 min) para recibir el mismo
   número que publican una vez al día.
2. Guardar el último dato bueno y seguir sirviéndolo días después como si fuera de
   ahora. Un VIX de anteayer al lado del precio de ahora se lee como el de ahora.
3. Colar el macro como si fuera una señal de entrada. Es contexto que resta, no
   un motivo para abrir.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app import macro
from app.agents import analyst
from app.config import settings
from app.store import Store
from app.web import create_app


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    macro.reset_cache()
    monkeypatch.setattr(settings, "fred_api_key", "clave-de-prueba")
    monkeypatch.setattr(settings, "macro_enabled", True)
    yield
    macro.reset_cache()


def reloj(monkeypatch, t):
    """El tiempo mandado a mano: probar una caché con sleeps sería una prueba lenta
    y encima frágil."""
    monkeypatch.setattr(macro, "_ahora", lambda: t)


def fred_que_cuenta(monkeypatch, datos=None, veces=None):
    veces = veces if veces is not None else []

    async def _f(_key, **kw):
        veces.append(1)
        return dict(datos if datos is not None else {"us10y": 4.2, "vix": 16.0})
    monkeypatch.setattr(macro, "fetch_fred", _f)
    return veces


# ----------------------------------------------------------------- caché

def test_the_same_series_is_not_asked_twice_in_a_row(monkeypatch):
    """FRED publica una vez al día; pedirlo cada 15 min por símbolo es tirar llamadas."""
    veces = fred_que_cuenta(monkeypatch)
    reloj(monkeypatch, 1000.0)
    d1, _ = asyncio.run(macro.series())
    d2, _ = asyncio.run(macro.series())
    assert d1 == d2 and d1["us10y"] == 4.2
    assert len(veces) == 1, "se volvió a pedir teniendo el dato fresco"


def test_after_the_ttl_it_does_ask_again(monkeypatch):
    veces = fred_que_cuenta(monkeypatch)
    reloj(monkeypatch, 1000.0)
    asyncio.run(macro.series())
    reloj(monkeypatch, 1000.0 + macro._TTL_FRED + 1)
    asyncio.run(macro.series())
    assert len(veces) == 2


def test_a_failure_is_not_retried_on_every_call(monkeypatch):
    """Si FRED está caído, reintentarlo seis veces cada 15 min añade seis esperas de
    red a cada ciclo de análisis por un dato que no va a venir."""
    veces = fred_que_cuenta(monkeypatch, datos={})
    reloj(monkeypatch, 1000.0)
    for _ in range(5):
        assert asyncio.run(macro.series())[0] == {}
    assert len(veces) == 1


def test_after_the_failure_window_it_tries_again(monkeypatch):
    """Caído no es caído para siempre: tiene que recuperarse solo."""
    veces = fred_que_cuenta(monkeypatch, datos={})
    reloj(monkeypatch, 1000.0)
    asyncio.run(macro.series())
    fred_que_cuenta(monkeypatch, datos={"us10y": 4.0}, veces=veces)
    reloj(monkeypatch, 1000.0 + macro._TTL_FALLO + 1)
    assert asyncio.run(macro.series())[0]["us10y"] == 4.0


def test_a_stale_value_is_served_but_its_age_comes_with_it(monkeypatch):
    """Mientras el hueco sea de horas, el dato viejo vale MÁS que ninguno — pero solo
    si va acompañado de cuándo se tomó."""
    fred_que_cuenta(monkeypatch)
    reloj(monkeypatch, 1000.0)
    asyncio.run(macro.series())

    async def caido(_key, **kw):
        return {}
    monkeypatch.setattr(macro, "fetch_fred", caido)
    reloj(monkeypatch, 1000.0 + 5 * 3600)
    datos, edad = asyncio.run(macro.series())
    assert datos["us10y"] == 4.2
    assert edad == pytest.approx(5 * 3600)


def test_a_value_too_old_is_dropped_instead_of_passed_off_as_current(monkeypatch):
    """EL fallo silencioso: el VIX de anteayer puesto junto al precio de ahora no se
    lee como viejo, se lee como el VIX de ahora."""
    fred_que_cuenta(monkeypatch)
    reloj(monkeypatch, 1000.0)
    asyncio.run(macro.series())

    async def caido(_key, **kw):
        return {}
    monkeypatch.setattr(macro, "fetch_fred", caido)
    reloj(monkeypatch, 1000.0 + macro._MAX_EDAD + 1)
    datos, _ = asyncio.run(macro.series())
    assert datos == {}, "sirvió un dato de más de un día como si fuera de ahora"


def test_turning_macro_off_asks_for_nothing(monkeypatch):
    veces = fred_que_cuenta(monkeypatch)
    monkeypatch.setattr(settings, "macro_enabled", False)
    assert asyncio.run(macro.series())[0] == {}
    assert asyncio.run(macro.contexto("XAUUSD"))["frases"] == []
    assert veces == []


# ------------------------------------------------------------------- COT

def cot_que_cuenta(monkeypatch, filas, veces=None):
    veces = veces if veces is not None else []

    async def _c(sym, **kw):
        veces.append(sym)
        return list(filas)
    monkeypatch.setattr(macro, "fetch_cot", _c)
    return veces


FILAS = [{"report_date_as_yyyy_mm_dd": "2026-01-06",
          "noncomm_positions_long_all": "200000",
          "noncomm_positions_short_all": "80000"}]


def test_a_symbol_without_a_cftc_contract_costs_no_call(monkeypatch):
    veces = cot_que_cuenta(monkeypatch, FILAS)
    assert asyncio.run(macro.cot("GBPNZD")) is None
    assert veces == []


def test_the_positioning_is_cached_per_symbol(monkeypatch):
    """Es un dato SEMANAL: pedirlo cada quince minutos no lo hace más nuevo."""
    veces = cot_que_cuenta(monkeypatch, FILAS)
    reloj(monkeypatch, 500.0)
    asyncio.run(macro.cot("XAUUSD"))
    asyncio.run(macro.cot("XAUUSD"))
    asyncio.run(macro.cot("EURUSD"))
    assert veces == ["XAUUSD", "EURUSD"]


# -------------------------------------------------------------- el texto

def test_with_nothing_to_say_the_text_is_empty(monkeypatch):
    """Sin datos hay que callarse. Un encabezado «Contexto macro:» seguido de nada
    le dice al modelo que miró y no encontró, que no es lo que pasó."""
    fred_que_cuenta(monkeypatch, datos={})
    assert macro.texto(asyncio.run(macro.contexto("XAUUSD"))) == ""


def test_the_text_carries_the_warning_not_just_the_numbers(monkeypatch):
    fred_que_cuenta(monkeypatch, datos={"us10y_real": 2.1, "dxy": 120.0})
    t = macro.texto(asyncio.run(macro.contexto("XAUUSD")))
    assert "2.10" in t and "no leyes" in t


def test_the_text_says_when_the_data_is_hours_old(monkeypatch):
    """Si no lo dice el texto, no lo sabe el modelo: el JSON de edad no llega."""
    fred_que_cuenta(monkeypatch, datos={"us10y_real": 2.1})
    reloj(monkeypatch, 1000.0)
    asyncio.run(macro.series())

    async def caido(_key, **kw):
        return {}
    monkeypatch.setattr(macro, "fetch_cot", caido)
    monkeypatch.setattr(macro, "fetch_fred", caido)
    reloj(monkeypatch, 1000.0 + 6 * 3600)
    t = macro.texto(asyncio.run(macro.contexto("XAUUSD")))
    assert "hace 6 h" in t


def test_crypto_gets_an_empty_block_not_the_yield_curve(monkeypatch):
    """Soltarle la curva de tipos al análisis de BTC es ruido que compite con lo que
    sí importa, y el modelo no tiene forma de saber cuál ignorar."""
    fred_que_cuenta(monkeypatch, datos={"us10y": 4.2, "us2y": 4.5, "vix": 18.0})
    assert macro.texto(asyncio.run(macro.contexto("BTCUSD"))) == ""


# ------------------------------------------------------- llega al analista

def espia_llm(monkeypatch):
    visto = {}

    async def _ask(system, user, **kw):
        visto["user"] = user
        return {"action": "no_trade", "direction": "none", "stop_loss": 0,
                "take_profit": 0, "confidence": 0, "thesis": "x", "invalidation": "y"}
    monkeypatch.setattr(analyst.llm, "ask", _ask)
    return visto


def test_the_macro_reaches_the_analyst_prompt(monkeypatch):
    visto = espia_llm(monkeypatch)
    asyncio.run(analyst.analyze("XAUUSD", "M15", {"last_close": 2000}, "pb", [],
                                macro_ctx="Tipo real a 10 años en 2.10%."))
    assert "2.10" in visto["user"]


def test_the_macro_is_framed_as_context_not_as_a_signal(monkeypatch):
    """Sin este encuadre, un modelo que ve «tipos reales subiendo» acaba proponiendo
    cortos de oro sin que el precio haya dicho nada."""
    visto = espia_llm(monkeypatch)
    asyncio.run(analyst.analyze("XAUUSD", "M15", {}, "pb", [], macro_ctx="algo"))
    assert "NO es una senal de entrada" in visto["user"]
    assert "NUNCA es por si solo motivo" in visto["user"]


def test_the_macro_goes_after_the_price_not_before(monkeypatch):
    """El orden importa: primero el precio. Puesto delante, el modelo construye la
    tesis desde el macro y luego busca en el gráfico lo que la confirme."""
    visto = espia_llm(monkeypatch)
    asyncio.run(analyst.analyze("XAUUSD", "M15", {"last_close": 2000}, "pb", [],
                                macro_ctx="MARCA-MACRO"))
    assert visto["user"].index("Snapshot de mercado") < visto["user"].index("MARCA-MACRO")


def test_with_no_macro_no_empty_section_is_added(monkeypatch):
    visto = espia_llm(monkeypatch)
    asyncio.run(analyst.analyze("XAUUSD", "M15", {}, "pb", []))
    assert "Contexto macro" not in visto["user"]


# --------------------------------------------------------------- endpoint

@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    return TestClient(create_app(Store(tmp_path / "brain.db"), None, None, None))


def test_the_endpoint_says_whether_the_key_is_there(cli, monkeypatch):
    """Sin esto, «no hay macro» y «hay macro pero está caído» se ven igual desde fuera."""
    fred_que_cuenta(monkeypatch)
    assert cli.get("/macro").json()["fred_key"] is True
    monkeypatch.setattr(settings, "fred_api_key", "")
    d = cli.get("/macro").json()
    assert d["fred_key"] is False and "sin clave de FRED" in d["aviso"]


def test_the_endpoint_explains_what_is_missing_on_purpose(cli, monkeypatch):
    """Él preguntó por las opciones FX. Callarlo se leería como que ya está metido."""
    fred_que_cuenta(monkeypatch)
    assert "DTCC" in cli.get("/macro").json()["opciones_fx"]


def test_the_endpoint_shows_the_reading_for_one_symbol(cli, monkeypatch):
    fred_que_cuenta(monkeypatch, datos={"us10y_real": 2.1, "dxy": 120.0})
    cot_que_cuenta(monkeypatch, FILAS)
    d = cli.get("/macro?symbol=XAUUSD").json()
    assert d["familia"] == "metal" and "tipos reales" in d["factores"]
    assert "2.10" in d["texto"]
