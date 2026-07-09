"""Orchestrator — el cerebro que coordina los ciclos de los agentes.

Ciclos:
- market_cycle: cada ANALYSIS_INTERVAL_MIN -> Analyst -> Risk Manager -> Executor
- overnight_cycle: cada OVERNIGHT_INTERVAL_MIN -> Overnight sobre posiciones abiertas
- daily_cycle: a REVIEW_HOUR_UTC -> Reviewer -> Architect
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import time

from . import constants, indicators
from .agents import analyst, architect, executor, overnight, reviewer, risk_manager
from .broker import Broker
from .config import settings
from .store import Store

log = logging.getLogger("brain")


def _utc_midnight_epoch() -> float:
    now = dt.datetime.now(dt.timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.timestamp()


class Brain:
    def __init__(self, broker: Broker, store: Store):
        self.broker = broker
        self.store = store
        self._last_market_run = 0.0
        self._last_overnight_run = 0.0
        self._last_daily_date = ""

    # ------------------------------------------------------------ main loop

    async def run_forever(self) -> None:
        log.info("brain started (dry_run=%s, env=%s, symbols=%s)",
                 settings.dry_run, settings.ctrader_env, settings.symbol_list)
        while True:
            try:
                await self._tick()
            except Exception:  # noqa: BLE001
                log.exception("tick failed")
            await asyncio.sleep(30)

    async def _tick(self) -> None:
        if not self.broker.client.account_authorized:
            return
        now = time.time()
        if now - self._last_market_run >= settings.analysis_interval_min * 60:
            self._last_market_run = now
            await self.market_cycle()
        if now - self._last_overnight_run >= settings.overnight_interval_min * 60:
            self._last_overnight_run = now
            await self.overnight_cycle()
        today = dt.datetime.now(dt.timezone.utc)
        if today.hour == settings.review_hour_utc and today.strftime("%Y-%m-%d") != self._last_daily_date:
            self._last_daily_date = today.strftime("%Y-%m-%d")
            await self.daily_cycle()

    # ----------------------------------------------------------- market cycle

    async def market_cycle(self) -> None:
        if self.store.halted:
            log.info("halted — skipping market cycle")
            return
        _, playbook = self.store.playbook()
        trader = await self.broker.trader()
        balance = trader["balance"]
        self._remember_initial_balance(balance)
        positions = await self._positions_with_names()
        daily_pnl = await self.broker.realized_pnl_since(_utc_midnight_epoch())

        for symbol in settings.symbol_list:
            try:
                await self._analyze_symbol(symbol, playbook, balance, daily_pnl, positions)
            except Exception:  # noqa: BLE001
                log.exception("market cycle failed for %s", symbol)

    async def _analyze_symbol(self, symbol: str, playbook: str, balance: float,
                              daily_pnl: float, positions: list[dict]) -> None:
        candles = await self.broker.candles(symbol, settings.timeframe, count=200)
        if len(candles) < 60:
            return
        # market likely closed if the last bar is stale (weekend, holiday)
        period_s = 60 * constants.TRENDBAR_PERIOD_MINUTES[settings.timeframe]
        if time.time() - candles[-1].ts > 3 * period_s:
            log.info("%s: stale data (market closed?) — skipping", symbol)
            return

        market = indicators.snapshot(candles)
        proposal = await analyst.analyze(symbol, settings.timeframe, market, playbook, positions)
        self.store.log("analyst", "analysis", proposal, symbol=symbol)

        if proposal["action"] != "propose":
            return
        log.info("%s: analyst proposes %s (confidence %s)",
                 symbol, proposal["direction"], proposal["confidence"])

        info = await self.broker.symbol_info(symbol)
        decision = await risk_manager.review(
            proposal=proposal, balance=balance,
            initial_balance=self._initial_balance(balance),
            daily_realized_pnl=daily_pnl, open_positions=positions,
            info=info, halted=self.store.halted, playbook=playbook)
        self.store.log("risk_manager", "decision",
                       {"approved": decision.approved, "reason": decision.reason,
                        "volume_units": decision.volume_units, "proposal": proposal},
                       symbol=symbol)
        if not decision.approved:
            log.info("%s: risk manager VETO — %s", symbol, decision.reason)
            return

        result = await executor.execute(self.broker, self.store, proposal, decision.volume_units)
        log.info("%s: executor result %s", symbol, result.get("status"))

    # --------------------------------------------------------- overnight cycle

    async def overnight_cycle(self) -> None:
        positions = await self._positions_with_names()
        if not positions:
            return
        symbols = sorted({p["symbol"] for p in positions})
        markets: dict[str, dict] = {}
        for s in symbols:
            try:
                candles = await self.broker.candles(s, settings.timeframe, count=100)
                if candles:
                    markets[s] = indicators.snapshot(candles)
            except Exception:  # noqa: BLE001
                log.exception("overnight: failed to fetch %s", s)

        recent = self.store.recent_journal(limit=40)
        journal_context = json.dumps(
            [e for e in recent if e["agent"] in ("analyst", "executor")], ensure_ascii=False)

        result = await overnight.watch(positions, markets, journal_context)
        self.store.log("overnight", "watch", result)

        for action in result.get("actions", []):
            pid = int(action["position_id"])
            pos = next((p for p in positions if p["position_id"] == pid), None)
            if pos is None:
                continue
            try:
                await self._apply_overnight_action(action, pos)
            except Exception:  # noqa: BLE001
                log.exception("overnight action failed: %s", action)

    async def _apply_overnight_action(self, action: dict, pos: dict) -> None:
        kind = action["action"]
        if kind == "hold":
            return
        if settings.dry_run:
            self.store.log("overnight", f"{kind}_simulated", action, symbol=pos["symbol"])
            return
        if kind == "close":
            await self.broker.close_position(pos["position_id"], pos["volume_units"])
            self.store.log("overnight", "position_closed", action, symbol=pos["symbol"])
        elif kind == "tighten_stop":
            new_sl = float(action.get("new_stop_loss") or 0)
            current_sl = pos.get("stop_loss")
            # only ever tighten, never widen the risk
            ok = (
                new_sl > 0 and (
                    current_sl is None
                    or (pos["side"] == "buy" and new_sl > current_sl)
                    or (pos["side"] == "sell" and new_sl < current_sl)
                )
            )
            if not ok:
                self.store.log("overnight", "tighten_rejected", action, symbol=pos["symbol"])
                return
            await self.broker.amend_position_sltp(pos["position_id"], new_sl, pos.get("take_profit"))
            self.store.log("overnight", "stop_tightened", action, symbol=pos["symbol"])

    # ------------------------------------------------------------- daily cycle

    async def daily_cycle(self) -> None:
        log.info("running daily review + architect")
        entries = self.store.journal_since(_utc_midnight_epoch())
        daily_pnl = await self.broker.realized_pnl_since(_utc_midnight_epoch())
        positions = await self._positions_with_names()
        version, playbook = self.store.playbook()

        review = await reviewer.daily_review(entries, daily_pnl, positions, playbook)
        self.store.log("reviewer", "daily_review", review)

        stats = {
            "daily_pnl": daily_pnl,
            "entries_today": len(entries),
            "open_positions": len(positions),
            "playbook_version": version,
        }
        result = await architect.evolve(playbook, self.store.recent_reviews(7), stats)
        if result.get("no_change"):
            self.store.log("architect", "no_change", result["changes_summary"])
        else:
            new_version = self.store.save_playbook(
                result["new_playbook_markdown"], result["changes_summary"])
            self.store.log("architect", "playbook_updated",
                           {"version": new_version, "changes": result["changes_summary"]})
            log.info("playbook evolved to v%s: %s", new_version, result["changes_summary"])

    # ---------------------------------------------------------------- helpers

    async def _positions_with_names(self) -> list[dict]:
        positions = await self.broker.positions()
        for p in positions:
            p["symbol"] = await self.broker.symbol_name_by_id(p["symbol_id"])
        return positions

    def _remember_initial_balance(self, balance: float) -> None:
        if self.store.get("initial_balance") is None:
            self.store.set("initial_balance", str(balance))

    def _initial_balance(self, fallback: float) -> float:
        raw = self.store.get("initial_balance")
        return float(raw) if raw else fallback
