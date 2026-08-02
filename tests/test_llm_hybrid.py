"""El modo híbrido: quién piensa qué, y qué pasa cuando el cerebro local no está.

El fallo que se prueba aquí es el que no se ve: eliges híbrido para no gastar, el
Mac se duerme o cierras Ollama, y el analista deja de analizar sin decir nada. La
decisión tomada es seguir con Claude —un bot que no mira el mercado es peor que uno
que cuesta unos centavos— pero CONTÁNDOLO, porque el híbrido se eligió justamente
para no pagar y enterarse en la factura no vale.
"""
import asyncio

import pytest

from app import llm
from app.config import settings


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "hybrid")
    monkeypatch.setattr(settings, "llm_local_roles", "analyst,risk_manager,overnight,tester")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-de-mentira")
    llm.fallbacks.update({"n": 0, "last": "", "last_role": "", "last_ts": 0.0})


def claude_responde(monkeypatch, texto="respuesta de Claude"):
    """Sustituye el cliente de Anthropic: devuelve texto sin salir a la red."""
    llamadas = []

    class Bloque:
        type = "text"
        def __init__(self, t): self.text = t

    class Resp:
        stop_reason = "end_turn"
        def __init__(self, t): self.content = [Bloque(t)]

    class Msgs:
        async def create(self, **kw):
            llamadas.append(kw)
            return Resp(texto)

    class Cli:
        messages = Msgs()

    monkeypatch.setattr(llm, "client", lambda: Cli())
    return llamadas


# ------------------------------------------------------------------ el reparto

def test_the_volume_goes_local_and_the_judgement_to_claude():
    """Es TODO el sentido del híbrido: lo que corre cientos de veces al día, gratis."""
    for rol in ("analyst", "risk_manager", "overnight", "tester"):
        assert settings.brain_for(rol) == "ollama"
    for rol in ("reviewer", "architect"):
        assert settings.brain_for(rol) == "anthropic"


def test_cloud_mode_sends_everything_to_claude(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    assert settings.brain_for("analyst") == "anthropic"


def test_local_mode_sends_everything_to_ollama(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    assert settings.brain_for("architect") == "ollama"


def test_an_unknown_role_never_lands_on_the_local_brain_by_accident():
    """Un rol nuevo tiene que ir a Claude hasta que alguien lo mande a local a mano."""
    assert settings.brain_for("agente_que_no_existe") == "anthropic"
    assert settings.brain_for("") == "anthropic"


# ------------------------------------------------- cuando el local no responde

def test_if_the_local_brain_is_down_the_analysis_still_happens(monkeypatch):
    async def muerto(*a, **k):
        raise ConnectionError("Connection refused")
    monkeypatch.setattr(llm, "_ask_ollama", muerto)
    llamadas = claude_responde(monkeypatch)

    out = asyncio.run(llm.ask("sistema", "usuario", role="analyst"))
    assert out == "respuesta de Claude"       # no se cayó: el bot sigue mirando
    assert len(llamadas) == 1


def test_the_fallback_is_counted_not_silent(monkeypatch):
    """Pagar sin saberlo es el fallo caro: tiene que quedar registrado."""
    async def muerto(*a, **k):
        raise ConnectionError("Connection refused")
    monkeypatch.setattr(llm, "_ask_ollama", muerto)
    claude_responde(monkeypatch)

    asyncio.run(llm.ask("s", "u", role="analyst"))
    asyncio.run(llm.ask("s", "u", role="tester"))
    assert llm.fallbacks["n"] == 2
    assert llm.fallbacks["last_role"] == "tester"
    assert "refused" in llm.fallbacks["last"]


def test_a_working_local_brain_never_reaches_claude(monkeypatch):
    """Si no, el híbrido no ahorraría nada y nadie lo notaría."""
    async def vivo(*a, **k):
        return "respuesta local"
    monkeypatch.setattr(llm, "_ask_ollama", vivo)
    llamadas = claude_responde(monkeypatch)

    assert asyncio.run(llm.ask("s", "u", role="analyst")) == "respuesta local"
    assert llamadas == [], "se llamó a Claude teniendo el cerebro local en pie"
    assert llm.fallbacks["n"] == 0


def test_without_an_anthropic_key_it_says_what_is_missing(monkeypatch):
    """Caer a Claude sin clave daría un error de autenticación que despista."""
    monkeypatch.setattr(settings, "anthropic_api_key", "")

    async def muerto(*a, **k):
        raise ConnectionError("Connection refused")
    monkeypatch.setattr(llm, "_ask_ollama", muerto)

    with pytest.raises(RuntimeError) as e:
        asyncio.run(llm.ask("s", "u", role="analyst"))
    assert "ANTHROPIC_API_KEY" in str(e.value)
    assert "no respondió" in str(e.value)
    assert llm.fallbacks["n"] == 0            # no hubo respaldo: no se cuenta


def test_a_missing_model_also_falls_back_instead_of_dying(monkeypatch):
    """Ollama en pie pero sin el modelo descargado es el caso más común al empezar."""
    async def sin_modelo(*a, **k):
        raise RuntimeError("Ollama no tiene el modelo 'qwen3:8b'")
    monkeypatch.setattr(llm, "_ask_ollama", sin_modelo)
    claude_responde(monkeypatch)

    assert asyncio.run(llm.ask("s", "u", role="analyst")) == "respuesta de Claude"
    assert llm.fallbacks["n"] == 1
