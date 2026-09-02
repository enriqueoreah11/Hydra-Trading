"""Analizar dos días por semana y dejar las operaciones puestas.

Cambiar la cadencia parece un ajuste de calendario y no lo es: si se analiza el
domingo y se entra a mercado, se entra al precio del domingo — que casi nunca es el
de la zona que justificaba la operación. Por eso una sesión deja PENDIENTES.

Y de ahí sale el fallo que más caro cuesta y que no avisa: una orden puesta el
domingo que sigue viva tres semanas después se ejecuta en un mercado que ya no es
el que la justificó. Esa entrada no la decidió nadie.
"""
import datetime as dt

import pytest

from app import sesion


D = dt.timezone.utc


def cuando(y, m, d, h=20):
    return dt.datetime(y, m, d, h, 0, tzinfo=D)


# --------------------------------------------------------- qué días

def test_the_days_you_asked_for_are_the_days_it_runs():
    assert sesion.dias_config("sun,wed") == [2, 6]      # miércoles y domingo


def test_the_day_names_are_forgiving():
    """Va a escribirlo a mano: sunday, SUN, ' wed ' son todos el mismo día."""
    assert sesion.dias_config(" SUNDAY , wed ") == [2, 6]


def test_garbage_days_are_dropped_not_guessed():
    """Adivinar «mierco» como miércoles acertaría a veces y fallaría otras, y un
    día mal adivinado analiza cuando no toca sin que nadie lo note."""
    assert sesion.dias_config("mierco,jueves") == []


def test_no_valid_days_means_it_never_runs():
    """Y quien lo configure tiene que poder verlo antes de que pase una semana."""
    assert sesion.dias_config("") == []
    assert "no se analizará nunca" in sesion.descripcion([], 20)


def test_it_runs_on_the_configured_day_and_hour():
    dias = sesion.dias_config("sun,wed")
    assert sesion.toca_ahora(cuando(2026, 9, 6, 20), dias, 20) is True   # domingo
    assert sesion.toca_ahora(cuando(2026, 9, 9, 20), dias, 20) is True   # miércoles


def test_it_does_not_run_on_other_days_or_hours():
    dias = sesion.dias_config("sun,wed")
    assert sesion.toca_ahora(cuando(2026, 9, 7, 20), dias, 20) is False  # lunes
    assert sesion.toca_ahora(cuando(2026, 9, 6, 19), dias, 20) is False  # una hora antes


# ------------------------------------------------- la caducidad

def test_orders_expire_at_the_next_session():
    """EL punto. Una orden que sobrevive a la sesión que la justificó ya no la
    decidió nadie: la decidió el olvido."""
    dias = sesion.dias_config("sun,wed")
    dom = cuando(2026, 9, 6, 20)
    p = sesion.proxima(dom, dias, 20)
    assert p == cuando(2026, 9, 9, 20), "la de domingo debe caducar el miércoles"


def test_the_next_session_is_never_now():
    """Si devolviera «ahora», la orden nacería caducada y no se pondría ninguna."""
    dias = sesion.dias_config("sun,wed")
    dom = cuando(2026, 9, 6, 20)
    assert sesion.proxima(dom, dias, 20) > dom


def test_wednesday_orders_expire_on_sunday():
    dias = sesion.dias_config("sun,wed")
    assert sesion.proxima(cuando(2026, 9, 9, 20), dias, 20) == cuando(2026, 9, 13, 20)


def test_with_one_day_a_week_it_still_expires_in_a_week():
    dias = sesion.dias_config("sun")
    assert sesion.proxima(cuando(2026, 9, 6, 20), dias, 20) == cuando(2026, 9, 13, 20)


def test_without_days_nothing_lives_forever():
    """Sin configuración válida no hay «siguiente sesión», y aun así la orden tiene
    que caducar: para siempre es como se cuelan entradas que nadie recuerda."""
    t = sesion.caducidad(cuando(2026, 9, 6, 20), [], 20)
    assert t - cuando(2026, 9, 6, 20).timestamp() <= 7 * 86400 + 1


def test_the_expiry_is_an_epoch_the_broker_can_use():
    dias = sesion.dias_config("sun,wed")
    t = sesion.caducidad(cuando(2026, 9, 6, 20), dias, 20)
    assert isinstance(t, float) and t > 0


# ------------------------------------------------------ cómo se lee

def test_the_schedule_reads_in_spanish():
    """Se ve en pantalla: «sun,wed» no le dice nada a nadie a las siete de la tarde."""
    d = sesion.descripcion(sesion.dias_config("sun,wed"), 20)
    assert "domingo" in d and "miércoles" in d and "20:00" in d


# --------------------------------- las pendientes, del lado correcto

@pytest.mark.parametrize("side,entry,ref,sl,ok", [
    ("buy", 99.0, 100.0, 98.0, True),      # limit de compra: por debajo
    ("buy", 101.0, 100.0, 100.5, True),    # stop de compra: por encima
    ("sell", 101.0, 100.0, 102.0, True),   # limit de venta: por encima
    ("buy", 99.0, 100.0, 99.5, False),     # stop por ENCIMA de la entrada en compra
    ("sell", 101.0, 100.0, 100.5, False),  # stop por DEBAJO de la entrada en venta
])
def test_a_pending_order_refuses_an_impossible_stop(side, entry, ref, sl, ok):
    """Un stop del lado equivocado no lo rechaza siempre el bróker: a veces entra y
    la operación nace con el riesgo al revés."""
    import asyncio

    from app.broker import Broker

    class Cli:
        account_authorized = True

        async def send(self, *a, **k):
            return {"ok": True}

    b = Broker.__new__(Broker)
    b.client = Cli()
    b.account_id = 1

    async def _info(sym, acc=None):
        class I:
            symbol_id = 1
        return I()
    b.symbol_info = _info

    fut = dt.datetime.now(D).timestamp() + 86400
    coro = b.place_pending_order(symbol="X", side=side, volume_units=1000,
                                 entry=entry, stop_loss=sl, take_profit=None,
                                 expira_ts=fut, ref=ref)
    if ok:
        assert asyncio.run(coro)["ok"] is True
    else:
        with pytest.raises(ValueError):
            asyncio.run(coro)


def test_a_pending_order_refuses_an_expiry_in_the_past():
    """Sin este control se manda una orden muerta al nacer y el bróker la rechaza
    con un error que no dice por qué."""
    import asyncio

    from app.broker import Broker

    b = Broker.__new__(Broker)
    b.client = None
    b.account_id = 1
    with pytest.raises(ValueError, match="caducidad"):
        asyncio.run(b.place_pending_order(
            symbol="X", side="buy", volume_units=1000, entry=99.0, stop_loss=98.0,
            take_profit=None, expira_ts=1.0, ref=100.0))
