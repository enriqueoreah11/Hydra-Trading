"""El lector de CSV del bot: que no duplique, no se atragante y no invente.

Lo que se comprueba es lo que dolería en producción: leer dos veces la misma fila,
tragarse una línea a medio escribir, o quedarse mudo cuando el bot rota el archivo.
"""
from app import shadow


def write(p, text, mode="w"):
    with open(p, mode, encoding="utf-8") as fh:
        fh.write(text)


HEAD = "time,symbol,timeframe,bias,score,outcome\n"


def test_reads_only_the_new_rows(tmp_path):
    f = tmp_path / "log.csv"
    write(f, HEAD + "1700000000,EURUSD,M15,buy,0.81,alerted\n")
    rows, st = shadow.read_new(f, {})
    assert len(rows) == 1
    assert rows[0]["symbol"] == "EURUSD" and rows[0]["score"] == 0.81
    assert rows[0]["time"] == 1700000000          # los números llegan como números

    # segunda pasada sin cambios: NADA (si repitiera, el diario se llenaría de copias)
    rows2, st2 = shadow.read_new(f, st)
    assert rows2 == []

    write(f, "1700000900,XAUUSD,M15,sell,0.44,blocked:spread\n", mode="a")
    rows3, st3 = shadow.read_new(f, st2)
    assert len(rows3) == 1 and rows3[0]["symbol"] == "XAUUSD"
    assert st3["rows"] == 2


def test_a_half_written_line_waits_for_the_next_pass(tmp_path):
    f = tmp_path / "log.csv"
    write(f, HEAD + "1700000000,EURUSD,M15,buy,0.81,alerted\n1700000900,XAU")
    rows, st = shadow.read_new(f, {})
    assert len(rows) == 1                          # la fila a medias NO entra
    write(f, "USD,M15,sell,0.5,alerted\n", mode="a")
    rows2, _ = shadow.read_new(f, st)
    assert len(rows2) == 1 and rows2[0]["symbol"] == "XAUUSD"


def test_when_the_bot_rotates_the_file_it_starts_over(tmp_path):
    f = tmp_path / "log.csv"
    write(f, HEAD + "1,EURUSD,M15,buy,1,alerted\n2,EURUSD,M15,buy,2,alerted\n")
    _, st = shadow.read_new(f, {})
    write(f, HEAD + "9,GBPUSD,M5,sell,9,alerted\n")     # el bot lo empezó de cero
    rows, st2 = shadow.read_new(f, st)
    assert len(rows) == 1 and rows[0]["symbol"] == "GBPUSD"


def test_a_repeated_header_is_not_imported_as_data(tmp_path):
    f = tmp_path / "log.csv"
    write(f, HEAD + "1,EURUSD,M15,buy,1,alerted\n")
    _, st = shadow.read_new(f, {})
    write(f, HEAD + "2,EURUSD,M15,buy,2,alerted\n", mode="a")
    rows, _ = shadow.read_new(f, st)
    assert len(rows) == 1 and rows[0]["symbol"] == "EURUSD"


def test_extra_columns_are_kept_not_dropped(tmp_path):
    f = tmp_path / "log.csv"
    write(f, HEAD + "1,EURUSD,M15,buy,1,alerted,algo,mas\n")
    rows, _ = shadow.read_new(f, {})
    assert rows[0]["extra"] == ["algo", "mas"]


def test_find_logs_takes_csv_and_txt_newest_first(tmp_path):
    import os
    import time
    (tmp_path / "sub").mkdir()
    a = tmp_path / "viejo.csv"
    b = tmp_path / "sub" / "nuevo.txt"
    c = tmp_path / "no.json"
    for f in (a, b, c):
        write(f, "x\n")
    os.utime(a, (time.time() - 500, time.time() - 500))
    got = [f.name for f in shadow.find_logs(tmp_path)]
    assert got == ["nuevo.txt", "viejo.csv"]


def test_digest_counts_by_symbol_and_outcome():
    rows = [{"symbol": "EURUSD", "outcome": "alerted"},
            {"symbol": "eurusd", "outcome": "blocked:news"},
            {"Symbol Name": "XAUUSD", "status": "alerted"}]
    d = shadow.digest(rows)
    assert d["n"] == 3
    assert d["by_symbol"]["EURUSD"] == 2 and d["by_symbol"]["XAUUSD"] == 1
    assert d["by_outcome"]["alerted"] == 2


def test_ctrader_instance_folders_are_not_bot_names():
    """"3b6638ac-…-Default" es la carpeta de una instancia, no un bot."""
    assert shadow.is_instance_dir("3b6638ac-4dbb-459a-b93f-c9bb57c00c8c-Default")
    assert shadow.is_instance_dir("8EA483D3-2D26-48FF-9676-082C67AE7349-Default")
    assert not shadow.is_instance_dir("Confluence Bot")
    assert not shadow.is_instance_dir("GoldFibBot")


def test_a_label_column_in_the_row_wins():
    assert shadow.label_from_row({"bot": "Confluence Bot", "symbol": "EURUSD"}) == "Confluence Bot"
    assert shadow.label_from_row({"Bot Name": "SRC"}) == "SRC"
    # un guid dentro de la columna tampoco vale como nombre
    assert shadow.label_from_row({"instance": "3b6638ac-4dbb-459a-b93f-c9bb57c00c8c"}) == ""
    assert shadow.label_from_row({"symbol": "EURUSD"}) == ""
