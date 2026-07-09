"""Validator — puerta de calidad para el playbook que propone el Architect.

Antes de activar una nueva version del playbook, la prueba contra las ultimas semanas
de velas historicas: reproduce puntos de decision muestreados, corre al Analista con el
playbook candidato y con el vigente, y simula el resultado de cada operacion en multiplos
de R. Si el candidato rinde claramente peor que el vigente, se RECHAZA el cambio.

Es una validacion LIGERA (muestreo, no cada vela) para acotar coste de LLM: el Analista
usa el LLM, asi que el coste crece con BACKTEST_SAMPLES x nº simbolos x 2 playbooks.
No sustituye a un backtest riguroso; sirve como red de seguridad contra cambios malos.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .. import backtest, indicators
from ..broker import Broker
from ..config import settings
from . import analyst

log = logging.getLogger("validator")

WARMUP = 60
MARGIN = 0.1   # el candidato puede ser hasta 0.1R peor sin ser rechazado


@dataclass
class ValidationResult:
    approved: bool
    current_expectancy: float
    candidate_expectancy: float
    trades_current: int
    trades_candidate: int
    detail: str
    per_symbol: list[dict] = field(default_factory=list)


async def _expectancy(broker: Broker, symbols: list[str], playbook: str) -> tuple[float, int]:
    r_multiples: list[float] = []
    for symbol in symbols:
        try:
            candles = await broker.candles(symbol, settings.timeframe, count=settings.backtest_bars)
        except Exception:  # noqa: BLE001
            log.warning("validator: no se pudieron traer velas de %s", symbol, exc_info=True)
            continue
        if len(candles) < WARMUP + settings.backtest_horizon_bars + 5:
            continue
        idxs = backtest.sample_indices(len(candles), settings.backtest_samples,
                                       WARMUP, settings.backtest_horizon_bars)
        for i in idxs:
            hist = candles[:i + 1]
            market = indicators.snapshot(hist)
            try:
                proposal = await analyst.analyze(symbol, settings.timeframe, market, playbook, [])
            except Exception:  # noqa: BLE001
                continue
            if proposal.get("action") != "propose":
                continue
            r = backtest.simulate_trade(
                candles, i, proposal["direction"], hist[-1].close,
                float(proposal["stop_loss"]), float(proposal["take_profit"]),
                settings.backtest_horizon_bars)
            if r is not None:
                r_multiples.append(r)
    if not r_multiples:
        return 0.0, 0
    return sum(r_multiples) / len(r_multiples), len(r_multiples)


async def validate(broker: Broker, current_playbook: str,
                   candidate_playbook: str, symbols: list[str]) -> ValidationResult:
    if not settings.validate_playbook:
        return ValidationResult(True, 0, 0, 0, 0, "validacion desactivada")

    cur_exp, cur_n = await _expectancy(broker, symbols, current_playbook)
    cand_exp, cand_n = await _expectancy(broker, symbols, candidate_playbook)

    # sin evidencia suficiente del candidato -> aprobar con nota (no penalizar por falta de trades)
    if cand_n < 3:
        return ValidationResult(
            True, cur_exp, cand_exp, cur_n, cand_n,
            "muestras insuficientes del candidato; se aprueba con cautela")

    approved = cand_exp >= cur_exp - MARGIN
    detail = (f"expectancy candidato={cand_exp:+.2f}R ({cand_n} trades) vs "
              f"vigente={cur_exp:+.2f}R ({cur_n} trades) — "
              f"{'APROBADO' if approved else 'RECHAZADO'}")
    log.info("validator: %s", detail)
    return ValidationResult(approved, cur_exp, cand_exp, cur_n, cand_n, detail)
