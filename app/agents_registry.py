"""Registro central de agentes: metadatos compartidos por la UI y el endpoint /agents."""
from __future__ import annotations

from .config import settings

# key = valor del campo 'agent' en el diario (store.log)
AGENTS = [
    {"key": "analyst", "name": "Analyst", "emoji": "🔍", "ring": "core",
     "role": "Lee el mercado (velas + EMA/RSI/ATR/niveles) y propone operaciones."},
    {"key": "risk_manager", "name": "Risk Manager", "emoji": "🛡️", "ring": "core",
     "role": "Calcula el tamaño de posición y veta propuestas débiles."},
    {"key": "executor", "name": "Executor", "emoji": "⚡", "ring": "core",
     "role": "Coloca las órdenes de mercado con SL/TP (o las simula)."},
    {"key": "overnight", "name": "Overnight", "emoji": "🌙", "ring": "core",
     "role": "Vigila posiciones abiertas: mantener, apretar stop o cerrar."},
    {"key": "reviewer", "name": "Reviewer", "emoji": "📋", "ring": "core",
     "role": "Auto-crítica diaria del desempeño del sistema."},
    {"key": "architect", "name": "Architect", "emoji": "🏗️", "ring": "core",
     "role": "Evoluciona el playbook con lo aprendido."},
    {"key": "sentinel", "name": "Sentinel", "emoji": "📰", "ring": "auto",
     "role": "Bloquea entradas alrededor de noticias de alto impacto."},
    {"key": "watchdog", "name": "Watchdog", "emoji": "🩺", "ring": "auto",
     "role": "Vigila la salud del sistema y avisa por Telegram."},
    {"key": "auditor", "name": "Auditor", "emoji": "🧾", "ring": "auto",
     "role": "Reconcilia broker vs diario; puede activar el auto-halt."},
    {"key": "validator", "name": "Validator", "emoji": "🧪", "ring": "auto",
     "role": "Backtest ligero del playbook antes de activarlo."},
    {"key": "portfolio", "name": "Portfolio", "emoji": "🔗", "ring": "auto",
     "role": "Exposición agregada por divisa y correlación."},
]


def is_enabled(key: str) -> bool:
    return {
        "sentinel": settings.enable_news,
        "auditor": settings.enable_auditor,
        "validator": settings.validate_playbook,
        "portfolio": settings.enable_portfolio_check,
        "watchdog": bool(settings.telegram_bot_token and settings.telegram_chat_id),
    }.get(key, True)
