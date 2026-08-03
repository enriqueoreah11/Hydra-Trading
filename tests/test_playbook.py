"""El playbook: el manual de reglas que leen el Analista y el Risk Manager.

Tenía secciones para metales, petróleo e índices y ninguna para forex ni cripto. Con
un par de divisas vigilado, el modelo leía el manual, no encontraba nada aplicable y
lo rechazaba «porque no está contemplado en el playbook» — un instrumento bien
configurado descartado por una laguna del manual, no por nada del mercado. Y sin
error en ningún sitio: solo dejaba de operar.
"""
from app.store import DEFAULT_PLAYBOOK, Store


def test_every_family_the_app_can_watch_has_its_section():
    """Si se añade una familia a la interfaz y no al playbook, vuelve el problema."""
    for titulo in ("## Metales", "## Petroleo", "## Indices", "## Forex", "## Cripto"):
        assert titulo in DEFAULT_PLAYBOOK, f"falta la sección {titulo}"


def test_it_says_out_loud_that_a_missing_section_is_not_a_reason_to_skip():
    """La regla que evita que vuelva a pasar con lo que se añada mañana."""
    bajo = DEFAULT_PLAYBOOK.lower()
    assert "no tiene seccion" in bajo
    assert "no es motivo para descartarlo" in bajo or "no se descarta por eso" in bajo


def test_the_forex_section_names_real_pairs():
    """Nombrarlos importa: el modelo busca el símbolo que tiene delante."""
    for par in ("EURUSD", "GBPJPY", "DXY"):
        assert par in DEFAULT_PLAYBOOK


def test_crypto_asks_for_wider_stops_than_the_rest():
    """Un stop de forex en BTC es ruido de diez minutos: si no se dice, se opera igual."""
    i = DEFAULT_PLAYBOOK.index("## Cripto")
    seccion = DEFAULT_PLAYBOOK[i:i + 700]
    assert "2x ATR" in seccion


def test_the_global_rules_still_apply_to_everything():
    assert "## Reglas globales" in DEFAULT_PLAYBOOK
    assert "una posicion por simbolo" in DEFAULT_PLAYBOOK.lower()


# ------------------------------------------------------- llega a tu instalación

def test_a_fresh_install_gets_the_new_playbook(tmp_path):
    s = Store(tmp_path / "b.db")
    _, texto = s.playbook()
    assert "## Forex" in texto


def test_an_existing_install_that_never_evolved_it_gets_the_update(tmp_path):
    """El caso de Krauser: ya tiene la base vieja y nunca la tocó el Architect."""
    db = tmp_path / "b.db"
    s = Store(db)
    s.db.execute("DELETE FROM playbook")
    s.db.execute("INSERT INTO playbook(ts, content, changes) VALUES(?,?,?)",
                 (0, "# Playbook v2 — viejo, sin forex", "inicial"))
    s.db.commit()
    s.db.close()

    v, texto = Store(db).playbook()
    assert "## Forex" in texto, "no adoptó la base nueva"
    assert v > 1, "tiene que quedar como versión nueva, no pisar la anterior"


def test_a_playbook_the_architect_evolved_is_never_overwritten(tmp_path):
    """Lo que aprendió el Architect vale más que la base del código: no se pisa."""
    db = tmp_path / "b.db"
    s = Store(db)
    s.save_playbook("# El mio, aprendido", "el architect lo evoluciono")
    s.db.close()

    _, texto = Store(db).playbook()
    assert texto == "# El mio, aprendido"
