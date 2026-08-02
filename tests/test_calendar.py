"""El calendario extendido: que salga ENTERO.

El fallo que se prueba aquí no da error ni se ve raro: la lista llega recortada y
los últimos días aparecen vacíos. Desde fuera parece que esa semana no tenía datos,
que es exactamente la conclusión equivocada antes de un jueves de tipos.
"""
import datetime as dt
import json

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.store import Store
from app.web import create_app


def semana(n_por_dia=40, dias=7):
    """Una semana cargada de verdad: más eventos de los que cabían en el tope viejo."""
    ahora = dt.datetime.now(dt.timezone.utc)
    ccy = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
    out = []
    for d in range(dias):
        for i in range(n_por_dia):
            t = ahora + dt.timedelta(days=d, hours=1 + (i % 20), minutes=(i % 4) * 15)
            out.append({"title": f"dato {d}-{i}", "country": ccy[i % len(ccy)],
                        "date": t.isoformat().replace("+00:00", "Z"),
                        "impact": ["High", "Medium", "Low"][i % 3],
                        "forecast": "1.0%", "previous": "0.9%"})
    return out


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    # sin red: la fuente falla y se sirve el archivo cacheado, que es el camino real
    # cuando ForexFactory nos limita
    monkeypatch.setattr(settings, "news_url", "http://127.0.0.1:1/nada.json")
    (tmp_path / "calendar.json").write_text(json.dumps(semana()))
    # la caché del calendario vive dentro de create_app, así que cada app arranca
    # con la suya: no hay estado que limpiar entre pruebas
    return TestClient(create_app(Store(tmp_path / "brain.db"), None, None, None))


def test_the_whole_week_comes_back_not_the_first_hundred_and_twenty(cli):
    d = cli.get("/calendar").json()
    assert d["total"] == len(d["events"])
    assert d["total"] > 120, "se está recortando: los últimos días se perderían"


def test_every_day_of_the_week_is_represented(cli):
    """Que no falte el último día es justo lo que rompía el tope."""
    ev = cli.get("/calendar").json()["events"]
    dias = {dt.datetime.fromtimestamp(e["ts"], dt.timezone.utc).date() for e in ev}
    assert len(dias) >= 7


def test_no_currency_is_filtered_out(cli):
    """La extendida NO hereda el filtro de sesión: tienen que venir todas."""
    ev = cli.get("/calendar").json()["events"]
    assert {e["currency"] for e in ev} >= {"USD", "EUR", "GBP", "JPY",
                                          "AUD", "CAD", "CHF", "NZD"}


def test_no_impact_is_filtered_out(cli):
    ev = cli.get("/calendar").json()["events"]
    assert {e["impact"] for e in ev} == {"High", "Medium", "Low"}


def test_events_come_in_time_order(cli):
    ev = cli.get("/calendar").json()["events"]
    assert [e["ts"] for e in ev] == sorted(e["ts"] for e in ev)


def test_the_ones_that_touch_your_symbols_are_marked(cli):
    """`watched` es lo que resalta la fila; marcar de más o de menos engaña igual."""
    ev = cli.get("/calendar").json()["events"]
    mias = set()
    for s in settings.symbol_list:
        mias |= {s[:3], s[3:6]}
    for e in ev:
        assert e["watched"] == (e["currency"] in mias)


def test_past_events_are_not_shown(cli):
    """Un dato de ayer arriba del todo hace perder el de dentro de una hora."""
    ahora = dt.datetime.now(dt.timezone.utc).timestamp()
    for e in cli.get("/calendar").json()["events"]:
        assert e["ts"] > ahora - 3700
