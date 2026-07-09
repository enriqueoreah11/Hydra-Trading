import time
from pathlib import Path

from app.agents.sentinel import Sentinel
from app.config import settings


def _sentinel(tmp_path: Path, events) -> Sentinel:
    s = Sentinel(tmp_path / "cal.json")
    s.events = events
    s._ever_loaded = True
    return s


def make_event(currency, impact, offset_min):
    from app.agents.sentinel import Event
    return Event(ts=time.time() + offset_min * 60, currency=currency, impact=impact, title="test")


def test_blackout_blocks_matching_currency(tmp_path):
    settings.enable_news = True
    settings.news_impact_min = "High"
    settings.news_blackout_before_min = 30
    settings.news_blackout_after_min = 15
    s = _sentinel(tmp_path, [make_event("USD", "High", 10)])  # noticia en 10 min
    assert s.blackout("EURUSD") is not None       # USD afecta a EURUSD
    assert s.blackout("AUDNZD") is None            # ni AUD ni NZD


def test_blackout_ignores_low_impact(tmp_path):
    settings.enable_news = True
    settings.news_impact_min = "High"
    s = _sentinel(tmp_path, [make_event("USD", "Low", 5)])
    assert s.blackout("EURUSD") is None


def test_blackout_outside_window(tmp_path):
    settings.enable_news = True
    settings.news_impact_min = "High"
    settings.news_blackout_before_min = 30
    s = _sentinel(tmp_path, [make_event("USD", "High", 120)])  # dentro de 2h, fuera de ventana
    assert s.blackout("EURUSD") is None


def test_blackout_after_event(tmp_path):
    settings.enable_news = True
    settings.news_impact_min = "High"
    settings.news_blackout_after_min = 15
    s = _sentinel(tmp_path, [make_event("USD", "High", -5)])  # hace 5 min
    assert s.blackout("EURUSD") is not None


def test_disabled_never_blocks(tmp_path):
    settings.enable_news = False
    s = _sentinel(tmp_path, [make_event("USD", "High", 1)])
    assert s.blackout("EURUSD") is None
    settings.enable_news = True
