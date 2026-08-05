"""La memoria en TU vault de Obsidian, y en los dos sentidos.

Antes de esto el vault era un diario: Hydra escribía y nadie volvía a leerlo nunca.
Memoria es que lo escrito cambie lo que pasa después.

Los dos fallos que se cuidan aquí no dan error ninguno:
1. La ruta mal puesta. Se crea la carpeta, se escriben las notas, todo va bien —
   y no aparecen en Obsidian porque están en un sitio que Obsidian no conoce.
2. Leer de más. El vault de alguien tiene su vida dentro. Barrerlo entero hacia un
   prompt manda a la nube cosas que no tienen nada que ver con esto.
"""
import pytest

from app import stt, vault
from app.config import settings


@pytest.fixture
def obsidian(tmp_path, monkeypatch):
    """Un vault como el suyo: la carpeta existe y tiene notas personales dentro."""
    v = tmp_path / "MiVault"
    (v / "Personal").mkdir(parents=True)
    (v / "Personal" / "Diario intimo.md").write_text(
        "cosas mias que no pinta nada mandar a ningun sitio", encoding="utf-8")
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "datos"))
    monkeypatch.setattr(settings, "obsidian_vault_path", str(v))
    monkeypatch.setattr(settings, "obsidian_folder", "Hydra")
    monkeypatch.setattr(settings, "obsidian_tag", "hydra")
    return v


# ------------------------------------------------------------ dónde escribe

def test_the_notes_land_inside_your_vault(obsidian):
    vault.note("Revisiones", "Revision de hoy", "salio bien")
    assert list((obsidian / "Hydra" / "Revisiones").glob("*.md")), \
        "la nota no está en el vault: en Obsidian no se vería"


def test_hydra_writes_only_in_its_own_folder(obsidian):
    """El vault es suyo. Que una revisión diaria aterrice en medio de sus notas
    personales sería invadirle la casa."""
    vault.note("Revisiones", "Revision", "x")
    vault.append_daily("algo")
    fuera = [p for p in obsidian.rglob("*.md") if "Hydra" not in p.parts]
    assert [p.name for p in fuera] == ["Diario intimo.md"]


def test_a_wrong_path_never_creates_a_folder_somewhere_else(tmp_path, monkeypatch):
    """EL fallo silencioso: si se creara, todo funcionaría y no vería una nota nunca."""
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "datos"))
    fantasma = tmp_path / "no" / "existe" / "MiVault"
    monkeypatch.setattr(settings, "obsidian_vault_path", str(fantasma))
    vault.note("Revisiones", "Revision", "x")
    assert not fantasma.exists()
    assert (tmp_path / "datos" / "vault" / "Revisiones").is_dir()


def test_a_wrong_path_is_reported_as_such(tmp_path, monkeypatch):
    """Y se dice, porque «guardado» y «guardado donde tú miras» no son lo mismo."""
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "datos"))
    monkeypatch.setattr(settings, "obsidian_vault_path", str(tmp_path / "no-existe"))
    e = vault.estado()
    assert e["obsidian"] is False and "no existe" in e["motivo"]


def test_without_configuring_anything_it_still_works(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "obsidian_vault_path", "")
    vault.note("Revisiones", "Revision", "x")
    assert (tmp_path / "vault" / "Revisiones").is_dir()
    assert vault.estado()["obsidian"] is False


def test_a_path_with_a_tilde_is_expanded(tmp_path, monkeypatch):
    """Va a copiar la ruta a mano; `~/Documents/...` es como la escribe la gente."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "MiVault").mkdir()
    monkeypatch.setattr(settings, "obsidian_vault_path", "~/MiVault")
    assert vault.estado()["obsidian"] is True


# --------------------------------------------------------------- qué lee

def test_your_personal_notes_are_never_read(obsidian):
    """Sin la etiqueta, una nota tuya no entra en ningún prompt. Ni buscándola."""
    r = vault.search("cosas mias")
    assert r == [], "se leyó una nota personal sin etiquetar"


def test_a_note_you_tag_does_get_read(obsidian):
    """Así es como decides qué comparte: nota a nota, poniendo #hydra."""
    (obsidian / "Personal" / "Sobre el oro.md").write_text(
        "#hydra\nel oro respeta el 3400 desde marzo", encoding="utf-8")
    nombres = [x["name"] for x in vault.search("oro")]
    assert "Sobre el oro" in nombres


def test_the_tag_also_works_in_the_frontmatter(obsidian):
    """Obsidian deja poner los tags arriba; quien los use así no debería quedarse
    fuera sin saber por qué."""
    (obsidian / "Personal" / "Notas.md").write_text(
        "---\ntags: [trading, hydra]\n---\n\nel petroleo se mueve raro los miercoles",
        encoding="utf-8")
    assert [x["name"] for x in vault.search("petroleo")] == ["Notas"]


def test_what_hydra_wrote_is_readable_without_any_tag(obsidian):
    """Lo suyo lo lee siempre: la etiqueta es para lo tuyo."""
    vault.note("Revisiones", "Revision del oro", "el oro fallo tres veces en el 3400")
    assert [x["name"] for x in vault.search("3400")] != []


def test_searching_for_nothing_does_not_dump_the_whole_vault(obsidian):
    (obsidian / "Personal" / "Otra.md").write_text("lo mio", encoding="utf-8")
    vault.note("Revisiones", "Una", "algo")
    assert all(x["mia"] for x in vault.search(""))


# ---------------------------------------------------- tus reglas mandan

def test_a_note_you_write_becomes_a_standing_rule(obsidian):
    """El momento en que esto deja de ser un diario: escribes y el bot obedece en
    el siguiente ciclo, sin tocar código."""
    (obsidian / "Personal" / "Mis reglas.md").write_text(
        "#hydra-reglas\n- no operes el oro los viernes por la tarde", encoding="utf-8")
    assert "viernes" in vault.instrucciones()


def test_a_rules_file_inside_hydra_folder_also_counts(obsidian):
    (obsidian / "Hydra").mkdir(exist_ok=True)
    (obsidian / "Hydra" / "Reglas.md").write_text("- nunca mas de dos abiertas",
                                                  encoding="utf-8")
    assert "dos abiertas" in vault.instrucciones()


def test_the_hydra_tag_alone_is_not_enough_to_command(obsidian):
    """Dejar leer una nota y dejar que mande son dos permisos distintos."""
    (obsidian / "Personal" / "Apuntes.md").write_text(
        "#hydra\n- arriesga el diez por ciento", encoding="utf-8")
    assert "diez por ciento" not in vault.instrucciones()


def test_rules_too_long_are_cut_saying_so(obsidian):
    """Cortar en silencio dejaría media regla en pie, que es peor que ninguna."""
    (obsidian / "Personal" / "Largas.md").write_text(
        "#hydra-reglas\n" + "- una regla larguisima\n" * 400, encoding="utf-8")
    txt = vault.instrucciones()
    assert len(txt) < vault._MAX_REGLAS + 200 and "cortado" in txt


def test_with_no_rules_nothing_is_sent(obsidian):
    assert vault.instrucciones() == ""


# ----------------------------------------------- qué se hace con la voz

@pytest.mark.parametrize("frase,tipo", [
    ("apunta que el oro respetó el 3400", "nota"),
    ("anota que mañana hay datos de empleo", "nota"),
    ("recuerda revisar el petróleo el miércoles", "nota"),
    ("cómo va el oro", "pregunta"),
    ("cuánto llevo ganado hoy", "pregunta"),
    ("qué tengo abierto", "pregunta"),
])
def test_speech_is_routed_by_what_it_asks_for(frase, tipo):
    assert stt.intencion(frase)["tipo"] == tipo


@pytest.mark.parametrize("frase", [
    "cierra el oro", "vende todo", "para el bot", "abre un corto en el nasdaq",
    "apaga todo", "duplica el riesgo", "reanuda el sistema",
])
def test_anything_that_moves_money_is_recognised_as_an_order(frase):
    assert stt.intencion(frase)["tipo"] == "orden"


@pytest.mark.parametrize("frase", ["para todo", "detente", "halt", "pausa el sistema"])
def test_stopping_can_be_done_by_voice_because_it_fails_safe(frase):
    """Entender «para» sin que lo hayas dicho deja el sistema quieto: molesta y se
    deshace con un botón."""
    assert stt.intencion(frase)["seguro"] is True


@pytest.mark.parametrize("frase", [
    "reanuda el sistema", "cierra el oro", "vende todo", "activa el bot",
    "abre un largo en el nasdaq",
])
def test_resuming_and_trading_need_a_button_because_they_do_not(frase):
    """Y este es el otro lado: entender «reanuda» de más pone a operar una cuenta
    que habías parado a mano, y para cuando lo ves ya hay órdenes puestas."""
    assert stt.intencion(frase)["seguro"] is False


def test_a_question_that_contains_a_verb_is_still_a_question():
    """«cómo cierra el oro hoy» es una pregunta normal: negarle la respuesta por
    llevar la palabra «cierra» dentro sería absurdo."""
    assert stt.intencion("cómo cierra el oro hoy")["tipo"] == "pregunta"


def test_the_dictated_note_drops_the_verb():
    """Se guarda lo que dijiste, no el «apunta que» con el que se lo pediste."""
    r = stt.intencion("apunta que el oro respetó el 3400")
    assert r["texto"] == "el oro respetó el 3400"


# --------------------------------------- las reglas llegan, pero acotadas

def espia(monkeypatch):
    import asyncio as _a  # noqa: F401
    from app.agents import analyst
    visto = {}

    async def _ask(system, user, **kw):
        visto["user"] = user
        return {"action": "no_trade", "direction": "none", "stop_loss": 0,
                "take_profit": 0, "confidence": 0, "thesis": "x", "invalidation": "y"}
    monkeypatch.setattr(analyst.llm, "ask", _ask)
    return analyst, visto


def test_your_rules_reach_the_analyst(monkeypatch):
    import asyncio
    analyst, visto = espia(monkeypatch)
    asyncio.run(analyst.analyze("XAUUSD", "M15", {}, "pb", [],
                                reglas="- no operes los viernes"))
    assert "viernes" in visto["user"]


def test_your_rules_can_only_tighten_never_loosen(monkeypatch):
    """Una nota escrita de madrugada —«sube el riesgo al cinco por ciento»— no puede
    saltarse los límites que existen justo para las madrugadas."""
    import asyncio
    analyst, visto = espia(monkeypatch)
    asyncio.run(analyst.analyze("XAUUSD", "M15", {}, "pb", [], reglas="- algo"))
    assert "solo pueden RESTRINGIR" in visto["user"]
    assert "IGNORALA" in visto["user"]


def test_your_rules_come_before_the_playbook(monkeypatch):
    """Si van detrás, el modelo las lee como una coletilla del playbook en vez de
    como lo que mandan."""
    import asyncio
    analyst, visto = espia(monkeypatch)
    asyncio.run(analyst.analyze("XAUUSD", "M15", {}, "pb", [], reglas="MARCA-REGLA"))
    assert visto["user"].index("MARCA-REGLA") < visto["user"].index("Playbook vigente")


def test_with_no_rules_no_empty_section_appears(monkeypatch):
    import asyncio
    analyst, visto = espia(monkeypatch)
    asyncio.run(analyst.analyze("XAUUSD", "M15", {}, "pb", []))
    assert "Reglas de la casa" not in visto["user"]
