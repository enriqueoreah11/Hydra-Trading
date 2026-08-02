"""Subir el .cbotset: los valores que TÚ usas, no los de fábrica.

Lo que se prueba aquí es el fallo que no avisa. El .algo trae los valores por
defecto; si tu bot lleva el break-even a 12 pips y el .algo dice 20, Hydra movía el
stop a 20 sin dar ningún error. Nadie lo nota hasta que mira una operación cerrada
y no le cuadra.

También se prueba lo contrario: que subir el preset de OTRO bot se detecte, porque
eso deja una gestión con números inventados y tampoco salta nada.
"""
import pytest

from app import botpolicy, cbotset


# ---------------------------------------------------------------- leer el archivo

XML_CLASICO = """<?xml version="1.0" encoding="utf-8"?>
<ParametersRoot>
  <Parameters>
    <Parameter Name="UseBreakEven" Value="true" />
    <Parameter Name="BreakEvenPips" Value="12" />
    <Parameter Name="Riesgo" Value="1,5" />
    <Parameter Name="Comentario" Value="mi bot" />
  </Parameters>
</ParametersRoot>"""

XML_POR_TEXTO = """<Settings>
  <Parameter Name="BreakEvenPips">12</Parameter>
  <Parameter Name="UseBreakEven">true</Parameter>
</Settings>"""

XML_POR_ETIQUETA = """<Settings><BreakEvenPips>12</BreakEvenPips>
  <UseBreakEven>true</UseBreakEven></Settings>"""

JSON_LISTA = """{"Parameters":[{"Name":"UseBreakEven","Value":"true"},
                               {"Name":"BreakEvenPips","Value":"12"}]}"""

JSON_PLANO = """{"UseBreakEven": true, "BreakEvenPips": 12}"""


@pytest.mark.parametrize("texto", [XML_CLASICO, XML_POR_TEXTO, XML_POR_ETIQUETA,
                                   JSON_LISTA, JSON_PLANO])
def test_every_known_shape_gives_the_same_values(texto):
    """cTrader lo ha guardado de varias formas según la versión. Todas valen."""
    v = cbotset.parse(texto)["values"]
    assert v["BreakEvenPips"] == 12
    assert v["UseBreakEven"] is True


def test_numbers_arrive_as_numbers_not_as_text():
    """Si llegaran como texto, comparar con el valor por defecto diría «cambiado»
    en todos y no se sabría qué tocaste de verdad."""
    v = cbotset.parse(XML_CLASICO)["values"]
    assert v["Riesgo"] == 1.5                 # coma decimal incluida
    assert isinstance(v["BreakEvenPips"], int)
    assert v["Comentario"] == "mi bot"        # el texto se queda texto


def test_a_file_that_is_not_a_preset_says_so():
    for basura in (b"", "hola que tal", "<Settings></Settings>", "{}"):
        with pytest.raises(cbotset.CbotsetError):
            cbotset.parse(basura)


def test_broken_files_do_not_return_an_empty_dict():
    """Devolver {} se leería como «este bot no tiene nada configurado»."""
    with pytest.raises(cbotset.CbotsetError) as e:
        cbotset.parse('{"Parameters": [')
    assert "no pude leer" in str(e.value)


def test_the_wrapper_tags_are_not_taken_as_parameters():
    v = cbotset.parse(XML_CLASICO)["values"]
    assert "Parameters" not in v and "ParametersRoot" not in v


def test_a_utf8_bom_does_not_break_it():
    """Windows y cTrader escriben el BOM; con él, el JSON no empieza por '{'."""
    assert cbotset.parse(b"\xef\xbb\xbf" + JSON_PLANO.encode())["n"] == 2


# ------------------------------------------------- meterlos en los del .algo

def bot(*pares):
    return {"groups": [{"name": "G", "params": [
        {"name": n, "default": d} for n, d in pares]}]}


def test_your_values_land_on_the_right_parameters():
    p = bot(("UseBreakEven", "false"), ("BreakEvenPips", 20))
    r = cbotset.apply_to(p, {"UseBreakEven": True, "BreakEvenPips": 12})
    params = p["groups"][0]["params"]
    assert params[1]["value"] == 12
    assert params[1]["default"] == 20, "el de fábrica se pisó: ya no se puede comparar"
    assert r["n_matched"] == 2 and r["n_unmatched"] == 0


def test_it_reports_exactly_what_you_changed():
    """Es lo único que deja ver de un vistazo si el preset es el que creías."""
    p = bot(("UseBreakEven", True), ("BreakEvenPips", 20))
    r = cbotset.apply_to(p, {"UseBreakEven": True, "BreakEvenPips": 12})
    assert [c["name"] for c in r["changed"]] == ["BreakEvenPips"]
    assert r["changed"][0]["default"] == 20 and r["changed"][0]["value"] == 12


def test_the_preset_of_another_bot_is_flagged():
    """Sin esto se gestionarían posiciones con los números de otro robot."""
    p = bot(("UseBreakEven", True), ("BreakEvenPips", 20))
    r = cbotset.apply_to(p, {"OtraCosa": 1, "YOtra": 2, "UseBreakEven": False})
    assert r["suspect"], "no avisó de que casi nada casaba"
    assert set(r["unmatched"]) == {"OtraCosa", "YOtra"}


def test_names_match_even_with_spaces_or_case_differences():
    p = bot(("Break Even Pips", 20))
    r = cbotset.apply_to(p, {"breakevenpips": 12})
    assert r["n_matched"] == 1
    assert p["groups"][0]["params"][0]["value"] == 12


# ------------------------------------------------- y que la GESTIÓN los use

def test_the_policy_manages_with_your_number_not_the_factory_one():
    """EL punto de todo esto. Con el de fábrica, el stop se mueve donde no toca."""
    p = bot(("UseBreakEven", "true"), ("BreakEvenTriggerPips", 20))
    assert botpolicy.from_params(p)["breakeven"]["trigger_pips"] == 20

    cbotset.apply_to(p, {"BreakEvenTriggerPips": 12})
    assert botpolicy.from_params(p)["breakeven"]["trigger_pips"] == 12


def test_without_a_preset_nothing_changes():
    """Quien no suba su .cbotset tiene que seguir exactamente igual que antes."""
    p = bot(("UseBreakEven", "true"), ("BreakEvenTriggerPips", 20))
    antes = botpolicy.from_params(p)
    cbotset.apply_to(p, {})
    assert botpolicy.from_params(p) == antes


def test_turning_something_off_in_your_preset_turns_it_off_in_the_policy():
    """Un false tuyo tiene que ganar: si no, Hydra gestionaría algo que apagaste."""
    p = bot(("UseBreakEven", "true"), ("BreakEvenTriggerPips", 20))
    assert botpolicy.from_params(p)["breakeven"]["on"] is True
    cbotset.apply_to(p, {"UseBreakEven": False})
    assert botpolicy.from_params(p)["breakeven"]["on"] is False
