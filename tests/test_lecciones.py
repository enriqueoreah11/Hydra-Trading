"""Lo que aprende de sus resultados — y sobre todo, lo que NO se deja aprender.

El fallo caro de una memoria de resultados no es olvidar. Es aprender de más: con
seis operaciones se puede «demostrar» cualquier cosa, y una vez que esa creencia
entra en el prompt, el analista rebaja la confianza en setups buenos por culpa de
tres pérdidas que fueron ruido. Eso no da ningún error y hace daño todos los días.

Por eso casi todo lo que se prueba aquí es contención: cuánta muestra hace falta,
qué se calla, y que cada afirmación viaje con su n.
"""
import time

import pytest

from app import lecciones


def op(pnl, symbol="XAUUSD", side="buy", strategy="donchian", ts=None, state="closed"):
    return {"state": state, "pnl": pnl, "symbol": symbol, "side": side,
            "strategy": strategy, "ts": ts if ts is not None else 1767225600.0}


def muchas(n, pnl, **kw):
    # separadas una hora para que no se amontonen todas en la misma sesión
    return [op(pnl, ts=1767225600.0 + i * 3600, **kw) for i in range(n)]


# ------------------------------------------------- no aprender de la nada

def test_three_losses_are_not_a_lesson():
    """EL fallo. Tres pérdidas seguidas no son un patrón, son tres pérdidas."""
    d = lecciones.calcular([op(-50), op(-40), op(-60)])
    assert d["lecciones"] == []


def test_what_is_missing_is_reported_as_missing_not_as_nothing():
    """«No hay lección» y «no hay muestra» son cosas distintas: la segunda te dice
    que sigas midiendo, y hay que poder distinguirlas."""
    d = lecciones.calcular([op(-50), op(-40), op(-60)])
    faltas = [x for x in d["sin_muestra"] if x["dimension"] == "símbolo"]
    assert faltas and "hace falta más muestra" in faltas[0]["nota"]


def test_the_sample_floor_is_actually_enforced():
    d = lecciones.calcular(muchas(lecciones.MIN_OPS - 1, -50))
    assert d["lecciones"] == []


def test_a_consistent_loss_with_enough_sample_does_become_a_lesson():
    d = lecciones.calcular(muchas(30, -50))
    sim = [x for x in d["lecciones"] if x["dimension"] == "símbolo"]
    assert sim and sim[0]["valor"] == "XAUUSD" and sim[0]["net"] < 0


def test_a_coin_flip_is_never_called_a_lesson():
    """Muestra de sobra pero resultado plano: si esto pasara el filtro, el prompt se
    llenaría de «lecciones» que no dicen nada y taparían las que sí."""
    filas = []
    for i in range(40):
        filas.append(op(100 if i % 2 else -100, ts=1767225600.0 + i * 3600))
    d = lecciones.calcular(filas)
    assert [x for x in d["lecciones"] if x["dimension"] == "símbolo"] == []


def test_noise_is_labelled_as_not_conclusive_not_hidden():
    filas = [op(100 if i % 2 else -100, ts=1767225600.0 + i * 3600) for i in range(40)]
    d = lecciones.calcular(filas)
    sim = [x for x in d["sin_muestra"] if x["dimension"] == "símbolo"]
    assert sim and sim[0]["fuerza"] == "no concluyente"


# --------------------------------------------- cada afirmación con su n

def test_every_lesson_carries_its_sample_and_its_luck():
    """Sin esos dos números, «pierde dinero» y «ha perdido seis de nueve veces» se
    leen igual — y no son lo mismo ni de lejos."""
    d = lecciones.calcular(muchas(30, -50))
    for x in d["lecciones"]:
        assert x["n"] >= lecciones.MIN_OPS
        assert x["prob_suerte"] is not None
        assert x["win_pct"] is not None


def test_a_thin_sample_is_marked_preliminary(monkeypatch):
    d = lecciones.calcular(muchas(lecciones.MIN_OPS + 2, -80))
    sim = [x for x in d["lecciones"] if x["dimension"] == "símbolo"]
    assert sim and sim[0]["fuerza"] == "preliminar"
    assert "PRELIMINAR" in lecciones.texto(d)


def test_the_same_data_always_reads_the_same():
    """Una memoria que cambia de opinión al recargar no es una memoria. El bootstrap
    va con semilla fija justo por esto."""
    filas = muchas(25, -50)
    a = lecciones.calcular(filas)["lecciones"]
    b = lecciones.calcular(filas)["lecciones"]
    assert [x["prob_suerte"] for x in a] == [x["prob_suerte"] for x in b]


# ------------------------------------------------------------ dimensiones

def test_it_learns_by_session_not_only_by_symbol():
    """«El oro pierde» no es accionable. «El oro pierde en la sesión asiática» sí."""
    filas = []
    for i in range(14):                       # 02:00 UTC → Asia/madrugada
        filas.append(op(-60, ts=1767232800.0 + i * 86400))
    for i in range(14):                       # 14:00 UTC → solape
        filas.append(op(+70, ts=1767276000.0 + i * 86400))
    ses = {x["valor"] for x in lecciones.calcular(filas)["lecciones"]
           if x["dimension"] == "sesión"}
    assert "Asia/madrugada" in ses and "solape Londres-NY" in ses


def test_it_learns_by_strategy():
    filas = muchas(25, -50, strategy="ruptura") + muchas(25, +60, strategy="pullback")
    est = {x["valor"]: x["net"] for x in lecciones.calcular(filas)["lecciones"]
           if x["dimension"] == "estrategia"}
    assert est.get("ruptura", 0) < 0 < est.get("pullback", 0)


def test_asking_about_one_symbol_drops_the_symbol_dimension():
    """Comparar el oro consigo mismo no dice nada y ocuparía el sitio de lo que sí."""
    filas = muchas(25, -50, symbol="XAUUSD") + muchas(25, +60, symbol="US100")
    d = lecciones.calcular(filas, symbol="XAUUSD")
    assert d["n_cerradas"] == 25
    assert all(x["dimension"] != "símbolo" for x in d["lecciones"])


def test_open_positions_never_count():
    """La API no manda el flotante: contarlas como cero sería inventar resultados."""
    filas = muchas(25, -50) + [op(None, state="open") for _ in range(50)]
    assert lecciones.calcular(filas)["n_cerradas"] == 25


# --------------------------------------------------------- post-mortems

def test_a_single_postmortem_is_a_bad_day_not_a_pattern():
    assert lecciones.de_postmortems([{"category": "stop_muy_ajustado", "count": 1}]) == []


def test_a_repeated_postmortem_is_a_pattern():
    r = lecciones.de_postmortems([{"category": "stop_muy_ajustado", "count": 5}])
    assert r == [{"categoria": "stop_muy_ajustado", "veces": 5}]


# --------------------------------------------------------------- el texto

def test_with_nothing_learned_the_text_is_empty():
    """Un encabezado seguido de nada le diría al modelo que se miró y no se encontró.
    Lo que pasa al principio es que todavía no hay con qué mirar."""
    assert lecciones.texto(lecciones.calcular([op(-50), op(-40)])) == ""


def test_the_text_always_carries_the_warning():
    t = lecciones.texto(lecciones.calcular(muchas(30, -50)))
    assert "no leyes" in t and "nunca para operar en contra" in t


def test_the_text_says_how_many_trades_it_comes_from():
    t = lecciones.texto(lecciones.calcular(muchas(30, -50)))
    assert "30 operaciones cerradas" in t


def test_repeated_postmortems_reach_the_text():
    t = lecciones.texto(lecciones.calcular(muchas(30, -50)),
                        postmortems=[{"categoria": "entró tarde", "veces": 4}])
    assert "entró tarde" in t and "4 veces" in t


def test_the_text_does_not_grow_without_limit():
    """Va dentro del prompt de cada análisis: veinte líneas de estadística taparían
    el precio, que es lo que se está mirando."""
    filas = []
    for i in range(60):
        filas.append(op(-50, symbol=f"SYM{i % 6}", strategy=f"e{i % 5}",
                        ts=1767225600.0 + i * 3600))
    t = lecciones.texto(lecciones.calcular(filas))
    assert len(t.strip().split("\n")) <= 8


# ------------------------------------------------------- queda en el vault

# --------------------------------------------------------------- endpoint

class BrokerFalso:
    """Un bróker con historial de sobra en un símbolo y casi nada en otro."""

    class Cli:
        account_authorized = True
    client = Cli()

    async def positions(self):
        return []

    async def deals_since(self, since, max_rows=1000):
        out = []
        for i in range(30):
            out.append({"closed": True, "ts": time.time() - i * 3600, "symbol_id": 1,
                        "side": "buy", "label": "donchian", "gross": -50.0,
                        "commission": 0.0, "swap": 0.0})
        for i in range(2):
            out.append({"closed": True, "ts": time.time() - i * 3600, "symbol_id": 2,
                        "side": "sell", "label": "otra", "gross": 10.0,
                        "commission": 0.0, "swap": 0.0})
        return out

    async def symbol_name_by_id(self, sid):
        return {1: "XAUUSD", 2: "US100"}[sid]


@pytest.fixture
def cli(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.store import Store
    from app.web import create_app
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "obsidian_vault_path", "")
    return TestClient(create_app(Store(tmp_path / "brain.db"), None, BrokerFalso(), None))


def test_the_endpoint_shows_what_it_learned(cli):
    d = cli.get("/lecciones").json()
    assert d["ok"] is True
    assert any(x["dimension"] == "símbolo" and x["valor"] == "XAUUSD"
               for x in d["lecciones"])


def test_the_endpoint_publishes_its_own_thresholds(cli):
    """Para poder discutirle el criterio hay que poder verlo: si no, «esto no es una
    lección» suena a capricho."""
    m = cli.get("/lecciones").json()["minimos"]
    assert m["muestra"] == lecciones.MIN_OPS and m["fiable"] == lecciones.MIN_OPS_FIABLE


def test_the_endpoint_filters_by_symbol(cli):
    d = cli.get("/lecciones?symbol=US100").json()
    assert d["n_cerradas"] == 2 and d["lecciones"] == []


def test_without_a_broker_it_says_so_instead_of_showing_nothing(tmp_path, monkeypatch):
    """«Sin historial» y «sin lecciones» se ven igual en pantalla, y no son lo mismo."""
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.store import Store
    from app.web import create_app
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    c = TestClient(create_app(Store(tmp_path / "b.db"), None, None, None))
    d = c.get("/lecciones").json()
    assert d["ok"] is False and d["error"]


def test_what_it_learns_is_written_to_the_memory(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "obsidian_vault_path", "")
    lecciones.guardar(lecciones.calcular(muchas(30, -50)))
    notas = list((tmp_path / "vault" / "Aprendizajes").glob("*.md"))
    assert notas and "30" in notas[0].read_text(encoding="utf-8")


def test_the_note_shows_what_is_still_being_measured(tmp_path, monkeypatch):
    """Para que se vea que está midiendo aunque todavía no concluya nada — si no,
    una nota vacía se lee como «esto no funciona»."""
    from app.config import settings
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "obsidian_vault_path", "")
    lecciones.guardar(lecciones.calcular([op(-50), op(-40)]))
    txt = list((tmp_path / "vault" / "Aprendizajes").glob("*.md"))[0].read_text(encoding="utf-8")
    assert "Sin muestra suficiente" in txt and "NO son lecciones" in txt


def test_it_reaches_the_analyst_prompt(monkeypatch):
    """Sin esto todo lo anterior es un informe bonito que nadie lee en el momento
    que importa, que es justo cuando va a decidir."""
    import asyncio
    from app.agents import analyst
    visto = {}

    async def _ask(system, user, **kw):
        visto["user"] = user
        return {"action": "no_trade", "direction": "none", "stop_loss": 0,
                "take_profit": 0, "confidence": 0, "thesis": "x", "invalidation": "y"}
    monkeypatch.setattr(analyst.llm, "ask", _ask)
    txt = lecciones.texto(lecciones.calcular(muchas(30, -50)))
    asyncio.run(analyst.analyze("XAUUSD", "M15", {}, "pb", [], aprendido=txt))
    assert "30 operaciones cerradas" in visto["user"]
    assert "nunca es motivo para operar" in visto["user"]
    assert "fijate en el tamano antes que en el signo" in visto["user"]


def test_with_nothing_learned_no_empty_section_is_added(monkeypatch):
    import asyncio
    from app.agents import analyst
    visto = {}

    async def _ask(system, user, **kw):
        visto["user"] = user
        return {"action": "no_trade", "direction": "none", "stop_loss": 0,
                "take_profit": 0, "confidence": 0, "thesis": "x", "invalidation": "y"}
    monkeypatch.setattr(analyst.llm, "ask", _ask)
    asyncio.run(analyst.analyze("XAUUSD", "M15", {}, "pb", []))
    assert "te ha costado dinero" not in visto["user"]


def test_the_architect_is_told_to_trust_the_numbers_over_the_story(monkeypatch):
    """El arquitecto es donde una lección se vuelve norma permanente. Si el relato
    de un día pesa más que las cuentas, ahí se escriben reglas por casualidades."""
    import asyncio
    from app.agents import architect
    visto = {}

    async def _ask(system, user, **kw):
        visto["user"] = user
        return {"no_change": True, "changes_summary": "x", "new_playbook_markdown": ""}
    monkeypatch.setattr(architect.llm, "ask", _ask)
    asyncio.run(architect.evolve("pb", [], {}, aprendido="MARCA"))
    assert visto["user"].index("MARCA") < visto["user"].index("Revisiones diarias")
    assert "no por lo\nque sugiera el relato de un dia suelto" in visto["user"]


def test_the_note_is_rewritten_not_piled_up(tmp_path, monkeypatch):
    """Acumulando quedaría un montón de frases de distintas épocas contradiciéndose,
    sin forma de saber cuál sigue en pie."""
    from app.config import settings
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "obsidian_vault_path", "")
    lecciones.guardar(lecciones.calcular(muchas(30, -50)))
    lecciones.guardar(lecciones.calcular(muchas(30, +70)))
    notas = list((tmp_path / "vault" / "Aprendizajes").glob("*.md"))
    assert len(notas) == 1
    assert "gana" in notas[0].read_text(encoding="utf-8")
