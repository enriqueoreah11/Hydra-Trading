"""Dukascopy: la URL, el decodificado y la agregación a velas.

Se prueba sin red: se fabrica un archivo bi5 igual que el suyo (LZMA + registros de
20 bytes) y se comprueba que sale exactamente lo que se metió. Si el divisor de
decimales o el mes 0-11 estuvieran mal, aquí se ve — y son los dos fallos que hacen
que te descargues datos que parecen buenos y no lo son.
"""
import datetime as dt
import lzma
import struct

from app import dukascopy as dk


def bi5(ticks):
    """(ms, ask, bid, askVol, bidVol) -> archivo bi5 como el de Dukascopy."""
    raw = b"".join(struct.pack(">IIIff", *t) for t in ticks)
    return lzma.compress(raw)


def test_the_month_is_zero_based():
    """Enero es 00. Es EL error clásico: con 01 te traes febrero."""
    u = dk.url_for("EURUSD", dt.datetime(2024, 1, 2, 10))
    assert u.endswith("/EURUSD/2024/00/02/10h_ticks.bi5")
    u2 = dk.url_for("eurusd", dt.datetime(2024, 12, 31, 23))
    assert u2.endswith("/EURUSD/2024/11/31/23h_ticks.bi5")


def test_digits_per_family():
    assert dk.digits_for("EURUSD") == 5
    assert dk.digits_for("USDJPY") == 3        # los del yen llevan 3
    assert dk.digits_for("XAUUSD") == 3
    assert dk.digits_for("USA500IDXUSD") == 2


def test_decoding_gives_back_the_prices_and_the_absolute_time():
    hour = dt.datetime(2024, 1, 2, 10, tzinfo=dt.timezone.utc).timestamp()
    raw = bi5([(0, 110123, 110120, 1.0, 2.0),        # 1.10123 / 1.10120
               (1500, 110130, 110125, 1.0, 1.0)])
    ticks = dk.decode(raw, hour, digits=5)
    assert len(ticks) == 2
    assert abs(ticks[0]["ask"] - 1.10123) < 1e-9
    assert abs(ticks[0]["bid"] - 1.10120) < 1e-9
    assert ticks[0]["ts"] == hour                     # ms 0 = principio de la hora
    assert ticks[1]["ts"] == hour + 1.5


def test_the_wrong_divisor_would_be_caught():
    hour = 0
    raw = bi5([(0, 110123, 110120, 1.0, 1.0)])
    assert dk.decode(raw, hour, digits=3)[0]["ask"] == 110.123   # otra escala, visible


def test_a_broken_or_empty_file_does_not_explode():
    assert dk.decode(b"", 0, 5) == []
    assert dk.decode(b"esto no es lzma", 0, 5) == []


def test_ticks_become_candles_with_the_mid_price():
    # las velas se alinean al reloj (múltiplos de la temporalidad desde epoch), no al
    # primer tick: por eso el instante de partida es divisible entre 60
    hour = 1000020
    ticks = [{"ts": hour + s, "bid": b, "ask": a, "vol": 1}
             for s, b, a in [(0, 1.0, 1.002), (10, 1.010, 1.012),
                             (20, 0.990, 0.992), (70, 1.004, 1.006)]]
    cs = dk.to_candles(ticks, 60)                     # velas de un minuto
    assert len(cs) == 2
    c = cs[0]
    assert abs(c["open"] - 1.001) < 1e-9              # (1.000 + 1.002) / 2
    assert abs(c["high"] - 1.011) < 1e-9
    assert abs(c["low"] - 0.991) < 1e-9
    assert abs(c["close"] - 0.991) < 1e-9
    assert c["volume"] == 3                           # los tres ticks del minuto
    assert cs[1]["ts"] - cs[0]["ts"] == 60


def test_weekends_are_not_requested():
    # sábado 6 y domingo 7 de enero de 2024
    hs = dk.hours_between(dt.datetime(2024, 1, 5, 22), dt.datetime(2024, 1, 8, 2))
    days = {h.day for h in hs}
    assert 6 not in days and 7 not in days
    assert 5 in days and 8 in days


def test_no_ticks_no_candles():
    assert dk.to_candles([], 60) == []
    assert dk.to_candles([{"ts": 1, "bid": 1, "ask": 1, "vol": 0}], 0) == []


def test_resume_starts_at_the_last_stored_bar_not_after_it():
    """La última vela guardada pudo quedarse a medias: se vuelve a pedir su hora."""
    last = dt.datetime(2024, 1, 2, 10, 30, tzinfo=dt.timezone.utc).timestamp()
    now = dt.datetime(2024, 1, 2, 13, 5, tzinfo=dt.timezone.utc).timestamp()
    hs = dk.resume_hours(last, 900, now)
    # incluida la hora de la última vela Y la hora en curso: la que está a medias se
    # vuelve a pedir en la siguiente pasada y se sobreescribe con la completa
    assert [h.hour for h in hs] == [10, 11, 12, 13]


def test_resume_stops_when_there_is_nothing_new():
    now = dt.datetime(2024, 1, 2, 10, 20, tzinfo=dt.timezone.utc).timestamp()
    assert dk.resume_hours(now, 900, now) == []
    assert dk.resume_hours(0, 900, now) == []          # sin nada guardado, no adivina


def test_resume_works_in_batches_when_you_are_months_behind():
    last = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc).timestamp()
    now = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc).timestamp()
    hs = dk.resume_hours(last, 900, now, max_hours=100)
    assert len(hs) == 100                              # por tandas, no mil de golpe
