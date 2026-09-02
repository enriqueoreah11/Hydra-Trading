"""Enseñarle una estrategia a trozos, y que no se invente lo que no le enseñaste.

Dos fallos, y ninguno da error:

1. Que enseñar lo de hoy borre lo de ayer. Cuando algo empieza a fallar, lo primero
   que hace falta saber es qué cambió y cuándo — y si se sobrescribe, eso no existe.
2. Que un destilado automático de los manuales entre a operar sin que nadie lo
   mire. Suena igual de bien venga del manual o se lo invente el modelo, y para
   cuando se nota lleva semanas poniendo órdenes.
"""
import asyncio

import pytest

from app import estrategia, manuales
from app.agents import destilador
from app.config import settings


@pytest.fixture(autouse=True)
def limpio(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "obsidian_vault_path", "")
    monkeypatch.setattr(settings, "estrategia_dir", "")
    yield


# ------------------------------------------------- enseñar a trozos

def test_teaching_twice_keeps_both_pieces():
    """EL punto: se va enseñando. Lo de ayer no desaparece al escribir lo de hoy."""
    estrategia.enseñar("entra en zona de 3 familias", "entradas")
    estrategia.enseñar("no operes la primera hora del lunes", "filtros")
    t = estrategia.texto()
    assert "3 familias" in t and "primera hora" in t
    assert estrategia.estado()["n_piezas"] == 2


def test_every_piece_keeps_its_date():
    """Sin fecha no se puede correlacionar un cambio de resultados con un cambio de
    estrategia, que es justo para lo que sirve tener el historial."""
    estrategia.enseñar("algo")
    p = estrategia.estado()["piezas"][0]
    assert p["ts"] and len(p["ts"]) >= 10


def test_retiring_marks_it_instead_of_deleting():
    """Borrar dejaría la estrategia sin memoria de por qué cambió."""
    estrategia.enseñar("regla vieja", "v1")
    estrategia.retirar(0, "dejó de funcionar en índices")
    assert "regla vieja" not in estrategia.texto()
    p = estrategia.estado()["piezas"][0]
    assert p["retirada"] is True and "índices" in p["motivo"]


def test_an_empty_strategy_returns_empty_not_a_heading():
    """Un encabezado con nada debajo le diría al modelo que la estrategia es no
    hacer nada — que es una instrucción muy distinta de «aún no te he enseñado»."""
    assert estrategia.texto() == ""


def test_teaching_nothing_is_refused():
    assert estrategia.enseñar("   ")["ok"] is False


# ------------------------- lo que dices tú y lo que midió la máquina

def test_machine_observations_live_in_their_own_section():
    """Mezcladas, en dos semanas no podrías distinguir lo que enseñaste de lo que
    dedujo — y para corregir, eso es lo primero que hace falta saber."""
    estrategia.enseñar("entra en zona de 3 familias")
    estrategia.observar("las de 3 familias pierden en la sesión asiática",
                        "18 ops, -4.2R")
    t = estrategia.texto()
    assert "Observaciones medidas" in t
    assert t.index("entra en zona") < t.index("Observaciones medidas")


def test_the_observation_section_says_it_is_not_a_rule():
    estrategia.enseñar("x")
    estrategia.observar("algo medido")
    assert "No son reglas" in estrategia.texto()


# --------------------------------- lo destilado no opera sin tu visto bueno

def test_a_distilled_piece_does_not_trade_until_approved():
    """EL fallo caro. Un resumen automático que entra solo acaba siendo política de
    trading que nadie escribió."""
    estrategia.enseñar("regla destilada", "Del manual: x.pdf", pendiente=True,
                       fuente="x.pdf")
    assert "regla destilada" not in estrategia.texto()
    assert estrategia.estado()["n_pendientes"] == 1


def test_approving_puts_it_to_work():
    estrategia.enseñar("regla destilada", pendiente=True)
    estrategia.aprobar(0)
    assert "regla destilada" in estrategia.texto()
    assert estrategia.estado()["n_pendientes"] == 0


def test_what_you_write_yourself_works_immediately():
    """La revisión es para lo que escribe la máquina. Lo que escribes tú ya lo
    revisaste al escribirlo."""
    estrategia.enseñar("mía")
    assert "mía" in estrategia.texto()


# ------------------------------------------- el destilador no inventa

def falso_llm(monkeypatch, salida):
    async def _ask(system, user, **kw):
        return salida
    monkeypatch.setattr(destilador.llm, "ask", _ask)


TEXTO = ("La entrada se toma cuando el precio regresa a la zona y deja una vela de "
         "rechazo con cierre por encima del nivel. Hay que ser paciente.")


def test_a_rule_whose_quote_is_not_in_the_text_is_dropped():
    """EL control. Una regla inventada suena igual de bien que una del manual: lo
    único que las separa es si la cita está de verdad en el texto."""
    import types
    salida = {"reglas": [
        {"tipo": "entrada", "regla": "entra al toque de zona con vela de rechazo",
         "cita": "deja una vela de rechazo con cierre por encima del nivel",
         "comprobable": True},
        {"tipo": "entrada", "regla": "usa siempre stop de 20 pips",
         "cita": "el stop debe ser de 20 pips", "comprobable": True}],
        "sin_reglas": False, "nota": ""}
    mp = pytest.MonkeyPatch()
    falso_llm(mp, salida)
    r = asyncio.run(destilador.destilar(TEXTO, "manual.pdf"))
    mp.undo()
    assert len(r["reglas"]) == 1
    assert len(r["descartadas"]) == 1
    assert "20 pips" not in r["reglas"][0]["regla"]


def test_a_quote_that_is_in_the_text_survives_reformatting():
    """El texto viene de un PDF: los saltos de línea y los espacios dobles no
    pueden decidir si una regla es válida."""
    mp = pytest.MonkeyPatch()
    falso_llm(mp, {"reglas": [{"tipo": "entrada", "regla": "x",
                               "cita": "deja una  vela de rechazo\ncon cierre",
                               "comprobable": True}],
                   "sin_reglas": False, "nota": ""})
    r = asyncio.run(destilador.destilar(TEXTO, "m.pdf"))
    mp.undo()
    assert len(r["reglas"]) == 1


def test_a_chunk_with_only_theory_is_a_valid_answer():
    """La mayor parte de un curso no son reglas. Forzar una salida de cada trozo
    llenaría la estrategia de consejos disfrazados de condiciones."""
    mp = pytest.MonkeyPatch()
    falso_llm(mp, {"reglas": [], "sin_reglas": True, "nota": "psicología del trading"})
    r = asyncio.run(destilador.destilar("Hay que dominar las emociones.", "m.pdf"))
    mp.undo()
    assert r["reglas"] == [] and r["sin_reglas"] is True


def test_the_distiller_is_told_never_to_complete_the_manual():
    t = " ".join(destilador.SYSTEM.split())
    assert "frase LITERAL" in t and "no puedes citar el texto, esa regla no va" in t
    assert "no completes lo que el manual da por sabido" in t.lower()


def test_non_automatable_rules_are_kept_but_marked():
    """«Cuando el mercado se siente pesado» no se puede programar, pero hace falta
    saber que existe: si desaparece, la estrategia parece completa y no lo está."""
    md = destilador.a_markdown(
        [{"tipo": "entrada", "regla": "entra si el mercado se siente pesado",
          "cita": "c", "comprobable": False}], "m.pdf")
    assert "no automatizable" in md


# --------------------------------------------------- leer los manuales

def test_chunks_overlap_so_a_rule_on_the_seam_is_not_lost():
    """Una condición de entrada que caiga justo en el corte se perdería entera y no
    habría forma de notarlo: la estrategia saldría con una regla de menos."""
    t = ("párrafo\n\n" * 400) + "LA REGLA CLAVE"
    ts = manuales.trozos(t, tam=2000, solape=500)
    assert len(ts) > 1
    for a, b in zip(ts, ts[1:]):
        assert a[-100:] in (a + b), "no hay solape entre trozos"


def test_a_short_manual_is_one_chunk():
    assert len(manuales.trozos("corto")) == 1


def test_an_empty_manual_gives_no_chunks():
    assert manuales.trozos("   ") == []


def test_a_missing_folder_is_explained_not_just_empty(monkeypatch, tmp_path):
    """iCloud es el caso real: la carpeta se ve en Finder pero no está descargada."""
    monkeypatch.setattr(settings, "estrategia_dir", str(tmp_path / "no-existe"))
    e = manuales.estado()
    assert e["ok"] is False and "iCloud" in e["motivo"]


def test_only_document_files_are_listed(monkeypatch, tmp_path):
    (tmp_path / "manual.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "notas.md").write_text("hola")
    (tmp_path / "captura.png").write_bytes(b"x")
    monkeypatch.setattr(settings, "estrategia_dir", str(tmp_path))
    nombres = {x["nombre"] for x in manuales.listar()}
    assert nombres == {"manual.pdf", "notas.md"}


def test_a_file_outside_the_folder_is_refused(monkeypatch, tmp_path):
    """Sin esto, un '../..' leería cualquier cosa del disco."""
    monkeypatch.setattr(settings, "estrategia_dir", str(tmp_path))
    r = manuales.extraer("../../etc/passwd")
    assert r["ok"] is False and "no está en la carpeta" in r["error"]


def test_a_scanned_pdf_says_it_needs_ocr(monkeypatch, tmp_path):
    """«Vacío» haría pensar que el archivo está roto. Lo que pasa es que son fotos."""
    (tmp_path / "escaneado.pdf").write_bytes(b"%PDF-1.4 sin texto")
    monkeypatch.setattr(settings, "estrategia_dir", str(tmp_path))
    r = manuales.extraer("escaneado.pdf")
    assert r["ok"] is False and "OCR" in r["error"]


def test_markdown_is_read_directly(monkeypatch, tmp_path):
    (tmp_path / "reglas.md").write_text("# Entradas\n\nzona de 3 familias",
                                        encoding="utf-8")
    monkeypatch.setattr(settings, "estrategia_dir", str(tmp_path))
    r = manuales.extraer("reglas.md")
    assert r["ok"] is True and "3 familias" in r["texto"]
