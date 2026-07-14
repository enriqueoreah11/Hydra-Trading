"""Parámetros editables por agente (se ven y se ajustan desde la UI).

Cada agente expone un subconjunto de Settings, con etiqueta y ayuda en español,
para que el usuario entienda qué hace y pueda afinarlo. Los cambios se guardan en
data/overrides.json y se aplican en caliente sobre `settings` (sin redeploy).
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import settings

# name -> (label, help). El tipo se infiere del valor actual en settings.
_META: dict[str, tuple[str, str]] = {
    "symbols": ("Instrumentos", "Mercados que vigila (aparecen en el orbe). Nombres de cTrader separados por coma."),
    "timeframe": ("Temporalidad", "Velas que analiza: M1, M5, M15, M30, H1, H4, D1."),
    "analysis_interval_min": ("Analiza cada (min)", "Frecuencia del ciclo de análisis de mercado."),
    "min_confidence": ("Confianza mínima", "Confianza (0-100) que necesita una idea para pasar a revisión."),
    "min_risk_reward": ("Riesgo:Beneficio mínimo", "R:R mínimo para aceptar una operación."),
    "risk_per_trade_pct": ("Riesgo por operación %", "Porcentaje del balance arriesgado por trade."),
    "max_daily_loss_pct": ("Pérdida diaria máx. %", "Detiene el día al superar esta pérdida realizada."),
    "max_open_positions": ("Posiciones abiertas máx.", "Número máximo de posiciones simultáneas."),
    "equity_floor_pct": ("Piso de equity %", "Detiene todo si el balance cae bajo este % del inicial."),
    "dry_run": ("Modo papel (demo)", "Si está activo NO envía órdenes reales, solo las registra."),
    "max_correlation": ("Correlación máxima", "Bloquea apuestas redundantes muy correlacionadas (0 a 1)."),
    "max_currency_exposure_pct": ("Exposición máx. por divisa %", "Riesgo agregado máximo en una sola divisa."),
    "enable_portfolio_check": ("Revisión de portafolio", "Activa el control de correlación y exposición."),
    "overnight_interval_min": ("Revisa cada (min)", "Frecuencia de gestión de posiciones abiertas de noche."),
    "review_hour_utc": ("Hora de revisión (UTC)", "Hora a la que corre la autocrítica diaria."),
    "validate_playbook": ("Validar antes de aplicar", "Backtest contra el histórico antes de aceptar cambios de estrategia."),
    "enable_news": ("Bloqueo por noticias", "Evita abrir cerca de eventos de alto impacto."),
    "news_impact_min": ("Impacto que bloquea", "Impacto mínimo que activa el bloqueo: High, Medium o Low."),
    "news_blackout_before_min": ("Bloqueo antes (min)", "Minutos antes del evento en que no abre nuevas entradas."),
    "news_blackout_after_min": ("Bloqueo después (min)", "Minutos después del evento en que no abre."),
    "news_refresh_min": ("Refrescar calendario (min)", "Cada cuánto re-descarga el calendario económico."),
    "watchdog_interval_min": ("Vigila cada (min)", "Frecuencia de la vigilancia de salud del sistema."),
    "data_stale_alert_min": ("Alerta datos viejos (min)", "Avisa si no llegan velas frescas por este tiempo."),
    "error_burst_threshold": ("Umbral de errores", "Avisa si ocurren tantos errores en poco tiempo."),
    "heartbeat_hour_utc": ("Hora del 'sigo vivo' (UTC)", "Ping diario de que sigue operativo."),
    "enable_auditor": ("Auditor activo", "Reconcilia posiciones y detecta discrepancias."),
    "auditor_interval_min": ("Audita cada (min)", "Frecuencia de la auditoría de posiciones."),
    "auto_halt_on_discrepancy": ("Detener ante discrepancia", "Frena el trading si aparece algo sin explicar."),
    "backtest_bars": ("Historial backtest (velas)", "Profundidad de historia por símbolo."),
    "backtest_samples": ("Muestras del backtest", "Puntos de decisión evaluados por símbolo."),
    "backtest_horizon_bars": ("Horizonte backtest (velas)", "Velas hacia adelante para resolver cada trade simulado."),
}

# qué parámetros muestra/edita cada agente
PARAMS: dict[str, list[str]] = {
    "analyst": ["timeframe", "analysis_interval_min", "min_confidence", "min_risk_reward"],
    "risk_manager": ["risk_per_trade_pct", "max_daily_loss_pct", "max_open_positions", "min_risk_reward", "equity_floor_pct"],
    "executor": ["dry_run", "max_open_positions"],
    "overnight": ["overnight_interval_min"],
    "reviewer": ["review_hour_utc"],
    "architect": ["validate_playbook"],
    "sentinel": ["enable_news", "news_impact_min", "news_blackout_before_min", "news_blackout_after_min", "news_refresh_min"],
    "watchdog": ["watchdog_interval_min", "data_stale_alert_min", "error_burst_threshold", "heartbeat_hour_utc"],
    "auditor": ["enable_auditor", "auditor_interval_min", "auto_halt_on_discrepancy"],
    "validator": ["backtest_bars", "backtest_samples", "backtest_horizon_bars"],
    "portfolio": ["symbols", "enable_portfolio_check", "max_correlation", "max_currency_exposure_pct"],
}

_OPTIONS: dict[str, list[str]] = {
    "timeframe": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
    "news_impact_min": ["High", "Medium", "Low"],
}

EDITABLE = {n for names in PARAMS.values() for n in names}


def _kind(name: str) -> str:
    v = getattr(settings, name, "")
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if name == "symbols":
        return "csv"
    return "str"


def specs_for(key: str) -> list[dict]:
    out = []
    for name in PARAMS.get(key, []):
        label, help_ = _META.get(name, (name, ""))
        out.append({"name": name, "label": label, "help": help_,
                    "value": getattr(settings, name, None), "type": _kind(name),
                    "options": _OPTIONS.get(name)})
    return out


def _coerce(name: str, value):
    k = _kind(name)
    if k == "bool":
        return value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes", "on", "si", "sí")
    if k == "int":
        return int(float(value))
    if k == "float":
        return float(value)
    if name == "symbols":
        return ",".join(s.strip().upper() for s in str(value).replace(";", ",").split(",") if s.strip())
    return str(value)


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return {}


def apply_and_save(path: Path, key: str, changes: dict) -> dict:
    """Aplica en caliente los cambios de un agente y los persiste."""
    allowed = set(PARAMS.get(key, []))
    applied = {}
    for name, val in (changes or {}).items():
        if name not in allowed:
            continue
        try:
            cv = _coerce(name, val)
        except Exception:  # noqa: BLE001
            continue
        setattr(settings, name, cv)
        applied[name] = cv
    if applied:
        data = _read(path)
        data.update(applied)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return applied


def load_overrides(path: Path) -> None:
    """Al arrancar: aplica los overrides guardados sobre settings."""
    for name, val in _read(path).items():
        if name in EDITABLE:
            try:
                setattr(settings, name, _coerce(name, val))
            except Exception:  # noqa: BLE001
                pass
