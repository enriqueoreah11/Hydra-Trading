"""Contexto macro: lo que mueve a los CFDs y no viene del bróker.

Lo que se prueba aquí no es que los números lleguen, es que no engañen. Un dato
macro mal presentado es peor que no tenerlo: si al analista le sueltas la curva de
tipos mientras mira BTCUSD, eso compite con lo que sí importa y el modelo no tiene
forma de saber cuál ignorar. Y si le das una tendencia histórica como si fuera una
ley, operará con una certeza que nadie tiene.
"""
from datetime import date, timedelta

from app import macro


# ------------------------------------------------------------- familias

def test_each_instrument_lands_in_its_family():
    assert macro.familia("XAUUSD") == "metal"
    assert macro.familia("XTIUSD") == "energia"
    assert macro.familia("US100") == "indice"
    assert macro.familia("USTEC") == "indice"        # el mismo con otro nombre
    assert macro.familia("EURUSD") == "forex"
    assert macro.familia("GBPJPY") == "forex"
    assert macro.familia("BTCUSD") == "cripto"


def test_a_prop_firm_suffix_does_not_change_the_family():
    """Las prop firms renombran; si el sufijo despistara, el oro dejaría de recibir
    el contexto de tipos reales sin que nadie lo note."""
    assert macro.familia("XAUUSD.raw") == "metal"
    assert macro.familia("EURUSD.r") == "forex"


# ------------------------------------------------------------ derivados

def test_the_curve_is_the_difference_not_a_level():
    d = macro.derivados({"us10y": 4.25, "us2y": 4.60})
    assert d["curva_10y_2y"] == -0.35
    assert d["curva_invertida"] is True


def test_a_normal_curve_is_not_flagged():
    assert macro.derivados({"us10y": 4.5, "us2y": 4.0})["curva_invertida"] is False


def test_a_missing_series_does_not_invent_a_curve():
    """FRED devuelve '.' los días sin dato. Restar sobre eso daría un número falso."""
    d = macro.derivados({"us10y": 4.25})
    assert d["curva_10y_2y"] is None and d["curva_invertida"] is False


def test_junk_values_become_nothing_not_zero():
    """Un cero se lee como «los tipos están a cero», que es una afirmación enorme."""
    d = macro.derivados({"us10y": ".", "vix": None, "dxy": "abc"})
    assert d["us10y"] is None and d["vix"] is None and d["dxy"] is None


# -------------------------------------------------------------- lectura

MACRO = {"us10y": 4.25, "us2y": 4.60, "us10y_real": 2.10, "vix": 17.5,
         "dxy": 121.3, "breakeven10y": 2.30}


def test_gold_gets_real_yields_and_the_dollar():
    r = macro.lectura("XAUUSD", MACRO)
    assert "tipos reales" in r["factores"] and "dólar" in r["factores"]
    assert any("2.10" in f for f in r["frases"])


def test_an_index_gets_volatility_not_real_yields():
    """Cada familia recibe lo suyo: mezclarlo todo es ruido que tapa la señal."""
    r = macro.lectura("US100", MACRO)
    assert "volatilidad" in r["factores"]
    assert "tipos reales" not in r["factores"]


def test_a_yen_pair_gets_the_bond_differential():
    r = macro.lectura("USDJPY", MACRO)
    assert "diferencial de bonos" in r["factores"]


def test_a_pair_without_yen_does_not_get_the_bond_story():
    r = macro.lectura("EURGBP", MACRO)
    assert "diferencial de bonos" not in r["factores"]


def test_crypto_gets_no_macro_instead_of_a_made_up_one():
    """Inventarle una relación a BTC con la curva de tipos sería darle al modelo una
    certeza que no existe."""
    r = macro.lectura("BTCUSD", MACRO)
    assert r["familia"] == "cripto" and r["factores"] == []
    # MACRO trae la curva invertida: tampoco esa se cuela por la puerta de atrás
    assert r["frases"] == []


def test_every_reading_carries_the_warning():
    """La frase que evita que el modelo trate una tendencia como una ley."""
    for s in ("XAUUSD", "US100", "USDJPY", "BTCUSD"):
        assert "no leyes" in macro.lectura(s, MACRO)["aviso"]


def test_the_gold_wording_says_it_is_a_tendency_that_breaks():
    frases = " ".join(macro.lectura("XAUUSD", MACRO)["frases"])
    assert "no una ley" in frases or "desacoplado" in frases


def test_with_no_macro_at_all_nothing_is_claimed():
    """Sin datos hay que callar, no rellenar con ceros."""
    r = macro.lectura("XAUUSD", {})
    assert r["frases"] == [] and r["factores"] == []


# ------------------------------------------------------------------ COT

def fila(fecha, largo, corto):
    return {"report_date_as_yyyy_mm_dd": fecha,
            "noncomm_positions_long_all": str(largo),
            "noncomm_positions_short_all": str(corto)}


def semanas(n, largo=lambda i: 100000, corto=lambda i: 80000, desde="2025-01-07"):
    """n informes semanales seguidos, como los publica la CFTC (martes)."""
    d0 = date.fromisoformat(desde)
    return [fila((d0 + timedelta(weeks=i)).isoformat(), largo(i), corto(i))
            for i in range(n)]


def test_the_net_position_is_long_minus_short():
    r = macro.cot_resumen([fila("2026-01-06", 200000, 80000)])
    assert r["ok"] and r["neto"] == 120000


def test_an_extreme_is_measured_against_its_own_history():
    """«Mucho» no significa nada suelto: 120k es extremo en un mercado y normal en
    otro. Por eso se mide en percentil de su propia serie."""
    filas = semanas(60, largo=lambda i: 100000 + i * 1000)
    filas.append(fila("2026-06-02", 500000, 50000))       # disparado
    r = macro.cot_resumen(filas)
    assert r["extremo"] is True and r["percentil"] == 100.0


def test_a_middling_position_is_not_called_extreme():
    """Con historia de sobra, lo que decide es dónde cae DENTRO de ella. Aquí la
    última semana está a media tabla, así que no hay nada que avisar."""
    filas = semanas(60, largo=lambda i: 100000 + (i % 20) * 5000)   # neto 20k..115k
    filas.append(fila("2026-06-02", 148000, 80000))                 # neto 68k: en medio
    r = macro.cot_resumen(filas)
    assert r["historia_suficiente"] is True     # no se salva por falta de datos
    assert 25 < r["percentil"] < 75
    assert r["extremo"] is False


def test_a_short_history_is_reported_as_such_and_not_judged():
    """Con veinte semanas, «extremo» solo querría decir «lo más alto de los últimos
    cinco meses». Eso no es un extremo, y presentarlo como tal es el engaño."""
    filas = semanas(20)
    filas.append(fila("2025-06-03", 900000, 10000))       # dispardísimo
    r = macro.cot_resumen(filas)
    assert r["ok"] is True                       # el dato se da...
    assert r["extremo"] is False                 # ...pero sin veredicto
    assert r["historia_suficiente"] is False
    assert "hace falta mas historia" in r["lectura"]
    assert str(r["semanas"]) in r["lectura"]     # dice cuánta hay, no «pocas»


def test_the_reading_never_says_where_the_price_goes():
    """Un posicionamiento masificado NO es una señal direccional. Decirlo así sería
    el error caro: operar en contra de la multitud porque sí."""
    filas = semanas(60)
    filas.append(fila("2026-06-02", 900000, 10000))
    r = macro.cot_resumen(filas)
    assert r["extremo"] is True
    assert "no dice a dónde va el precio" in r["lectura"]
    assert "nunca para cronometrar" in r["aviso"]


def test_the_order_of_the_rows_does_not_matter():
    """La CFTC los devuelve del más nuevo al más viejo; el «último» tiene que ser el
    de la fecha más reciente, no el primero de la lista."""
    filas = [fila("2026-02-01", 500000, 50000), fila("2026-01-01", 100000, 90000)]
    assert macro.cot_resumen(filas)["fecha"] == "2026-02-01"


def test_no_data_says_so_instead_of_returning_zeros():
    assert macro.cot_resumen([])["ok"] is False
    assert macro.cot_resumen([{"report_date_as_yyyy_mm_dd": "2026-01-01"}])["ok"] is False


# -------------------------------------------------- lo que NO se promete

def test_fx_options_are_documented_as_missing_not_silently_skipped():
    """El efecto es real y él preguntó por él: callarlo se leería como que no existe
    o, peor, como que ya está metido."""
    n = macro.OPCIONES_FX_NOTA.lower()
    assert "dtcc" in n and "no hay fuente" in n


def test_without_a_fred_key_it_returns_nothing_instead_of_failing():
    import asyncio
    assert asyncio.run(macro.fetch_fred("")) == {}


def test_a_symbol_with_no_cftc_contract_asks_for_nothing():
    """No todo lo que operas cotiza en Chicago; pedirlo sería una llamada tirada."""
    import asyncio
    assert asyncio.run(macro.fetch_cot("GBPNZD")) == []
