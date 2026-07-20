"""Orchestrator — el cerebro que coordina los ciclos de los agentes.

Ciclos:
- market_cycle:    Sentinel(blackout) -> Analyst -> Risk Manager -> Portfolio -> Executor
- overnight_cycle: Overnight sobre posiciones abiertas
- watchdog_cycle:  salud del sistema + alertas Telegram
- auditor_cycle:   reconciliacion broker vs diario (auto-halt si es critico)
- daily_cycle:     Reviewer -> Architect -> Validator (backtest ligero) -> activa playbook
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import time

from . import constants, indicators, research, vault
from .agents import (analyst, architect, auditor, executor, overnight, portfolio,
                     reviewer, risk_manager, validator)
from .agents.sentinel import Sentinel
from .agents.watchdog import Watchdog
from .broker import Broker
from .config import settings
from .notifier import notifier
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
        self.sentinel = Sentinel(settings.data_path / "calendar.json")
        self.watchdog = Watchdog(broker, store)
        self._last_market_run = 0.0
        self._last_overnight_run = 0.0
        self._last_watchdog_run = 0.0
        self._last_auditor_run = 0.0
        self._last_daily_date = ""
        self._last_heartbeat_date = ""
        self._last_data_ts = 0.0

    # ------------------------------------------------------------ main loop

    async def run_forever(self) -> None:
        log.info("brain started (dry_run=%s, env=%s, symbols=%s)",
                 settings.dry_run, settings.ctrader_env, settings.symbol_list)
        await notifier.send(f"🐉 *Hydra* iniciado — entorno {settings.ctrader_env}, "
                            f"modo {'papel' if settings.dry_run else 'REAL'}, "
                            f"simbolos {', '.join(settings.symbol_list)}.")
        while True:
            try:
                await self._tick()
            except Exception:  # noqa: BLE001
                log.exception("tick failed")
            await asyncio.sleep(30)

    async def _tick(self) -> None:
        now = time.time()

        # el sentinel y el watchdog corren aunque no haya sesion, para poder avisar de caidas
        await self.sentinel.refresh()
        if now - self._last_watchdog_run >= settings.watchdog_interval_min * 60:
            self._last_watchdog_run = now
            try:
                await self.watchdog.check(self._last_data_ts)
            except Exception:  # noqa: BLE001
                log.exception("watchdog failed")

        if not self.broker.client.account_authorized:
            return

        if now - self._last_market_run >= settings.analysis_interval_min * 60:
            self._last_market_run = now
            await self.market_cycle()
        if now - self._last_overnight_run >= settings.overnight_interval_min * 60:
            self._last_overnight_run = now
            await self.overnight_cycle()
        if settings.enable_auditor and now - self._last_auditor_run >= settings.auditor_interval_min * 60:
            self._last_auditor_run = now
            await self.auditor_cycle()

        today = dt.datetime.now(dt.timezone.utc)
        date_s = today.strftime("%Y-%m-%d")
        if today.hour == settings.heartbeat_hour_utc and date_s != self._last_heartbeat_date:
            self._last_heartbeat_date = date_s
            await self._send_heartbeat()
        if today.hour == settings.review_hour_utc and date_s != self._last_daily_date:
            self._last_daily_date = date_s
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
        period_s = 60 * constants.TRENDBAR_PERIOD_MINUTES[settings.timeframe]
        if time.time() - candles[-1].ts > 3 * period_s:
            log.info("%s: stale data (market closed?) — skipping", symbol)
            return
        self._last_data_ts = time.time()

        # --- Sentinel: bloqueo por noticias de alto impacto ---
        event = self.sentinel.blackout(symbol)
        if event is not None:
            self.store.log("sentinel", "blackout",
                           {"event": event.title, "currency": event.currency,
                            "impact": event.impact, "event_ts": event.ts}, symbol=symbol)
            log.info("%s: bloqueado por noticia (%s %s)", symbol, event.currency, event.title)
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

        # --- Portfolio: exposicion agregada + correlacion ---
        pf = await portfolio.check(proposal, positions, self.broker)
        if not pf.approved:
            self.store.log("portfolio", "veto", {"reason": pf.reason, "proposal": proposal},
                           symbol=symbol)
            log.info("%s: portfolio VETO — %s", symbol, pf.reason)
            return

        result = await executor.execute(self.broker, self.store, proposal, decision.volume_units)
        log.info("%s: executor result %s", symbol, result.get("status"))
        await self._notify_execution(symbol, proposal, decision.volume_units, result)
        # marca la posicion recien abierta como conocida (evita falso "huerfana")
        if result.get("status") in ("placed", "simulated"):
            positions.append({"symbol": symbol, "side": proposal["direction"]})

    async def _notify_execution(self, symbol: str, proposal: dict, units: float, result: dict) -> None:
        status = result.get("status")
        arrow = "🟢 COMPRA" if proposal["direction"] == "buy" else "🔴 VENTA"
        if status == "placed":
            await notifier.send(
                f"{arrow} *{symbol}* ejecutada\nunidades: {units}\n"
                f"entrada≈ {proposal['last_close']}  SL {proposal['stop_loss']}  "
                f"TP {proposal['take_profit']}\nconfianza {proposal['confidence']}")
        elif status == "simulated":
            await notifier.send(
                f"📝 [papel] {arrow} *{symbol}* simulada — {units} unidades, "
                f"SL {proposal['stop_loss']} / TP {proposal['take_profit']}")
        elif status == "error":
            await notifier.send(f"❌ *{symbol}*: fallo al colocar orden — {result.get('error')}")

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
            await notifier.send(f"🌙 *{pos['symbol']}* cerrada por el agente nocturno — "
                                f"{action.get('reason', '')}")
        elif kind == "tighten_stop":
            new_sl = float(action.get("new_stop_loss") or 0)
            current_sl = pos.get("stop_loss")
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
            await notifier.send(f"🌙 *{pos['symbol']}* stop movido a {new_sl} (protegiendo posicion)")

    # ---------------------------------------------------------- auditor cycle

    async def auditor_cycle(self) -> None:
        positions = await self._positions_with_names()
        discrepancies = await auditor.audit(self.broker, self.store, positions)
        criticals = [d for d in discrepancies if d["severity"] == "critical"]
        if criticals:
            msg = "🚨 *Hydra AUDITORIA* discrepancias criticas:\n" + "\n".join(
                f"- {d['symbol']}: {d['issue']}" for d in criticals)
            await notifier.send(msg)
            if settings.auto_halt_on_discrepancy and not self.store.halted:
                self.store.set_halted(True, "auto-halt del auditor por discrepancia critica")
                await notifier.send("⛔ *Hydra* se DETUVO automaticamente. Revisa y usa /resume.")
        elif discrepancies:
            await notifier.send("⚠️ *Hydra auditoria*: " + "; ".join(
                f"{d['symbol']}: {d['issue']}" for d in discrepancies))

    # ------------------------------------------------------------- daily cycle

    async def daily_cycle(self) -> None:
        log.info("running daily review + architect + validator")
        entries = self.store.journal_since(_utc_midnight_epoch())
        daily_pnl = await self.broker.realized_pnl_since(_utc_midnight_epoch())
        positions = await self._positions_with_names()
        version, playbook = self.store.playbook()

        # brief de mercado (Perplexity) — se guarda en la memoria y alimenta la revisión
        brief_text = ""
        if research.available() and settings.research_daily_brief:
            try:
                brief = await research.market_brief(settings.symbol_list)
                brief_text = brief["text"]
                cites = "".join(f"\n- {c}" for c in brief.get("citations", [])[:8])
                vault.note("Investigacion", "Brief de mercado",
                           brief_text + ("\n\n## Fuentes" + cites if cites else ""),
                           tags=["investigacion", "mercado"])
                self.store.log("sentinel", "market_brief", brief_text[:1200])
            except Exception:  # noqa: BLE001 - la investigación nunca debe tumbar el ciclo
                log.warning("perplexity brief failed", exc_info=True)

        review = await reviewer.daily_review(entries, daily_pnl, positions, playbook)
        self.store.log("reviewer", "daily_review", review)
        try:
            vault.note("Revisiones", f"Revision diaria (PnL {daily_pnl:+.2f})", review,
                       tags=["revision", "aprendizaje"])
        except Exception:  # noqa: BLE001
            log.warning("vault note failed", exc_info=True)
        await notifier.send(f"📋 *Hydra revision diaria* (PnL {daily_pnl:+.2f})\n\n{review[:1500]}")

        stats = {
            "daily_pnl": daily_pnl,
            "entries_today": len(entries),
            "open_positions": len(positions),
            "playbook_version": version,
        }
        result = await architect.evolve(playbook, self.store.recent_reviews(7), stats)
        if result.get("no_change"):
            self.store.log("architect", "no_change", result["changes_summary"])
            return

        candidate = result["new_playbook_markdown"]
        vres = await validator.validate(self.broker, playbook, candidate, settings.symbol_list)
        self.store.log("validator", "result", {
            "approved": vres.approved, "detail": vres.detail,
            "current_expectancy": vres.current_expectancy,
            "candidate_expectancy": vres.candidate_expectancy})

        if not vres.approved:
            self.store.log("architect", "playbook_rejected",
                           {"changes": result["changes_summary"], "validator": vres.detail})
            await notifier.send(f"🏗️ Cambio de playbook RECHAZADO por el validador.\n{vres.detail}")
            log.info("playbook change rejected: %s", vres.detail)
            return

        new_version = self.store.save_playbook(candidate, result["changes_summary"])
        self.store.log("architect", "playbook_updated",
                       {"version": new_version, "changes": result["changes_summary"],
                        "validator": vres.detail})
        try:
            vault.note("Playbook", f"Playbook v{new_version}",
                       f"**Cambios:** {result['changes_summary']}\n\n"
                       f"**Validador:** {vres.detail}\n\n---\n\n{candidate}",
                       tags=["playbook", "aprendizaje"])
        except Exception:  # noqa: BLE001
            log.warning("vault note failed", exc_info=True)
        log.info("playbook evolved to v%s: %s", new_version, result["changes_summary"])
        await notifier.send(f"🏗️ *Playbook v{new_version}* activado.\n{result['changes_summary']}\n"
                            f"({vres.detail})")

    # ---------------------------------------------------------------- helpers

    async def _send_heartbeat(self) -> None:
        try:
            balance = None
            positions = []
            if self.broker.client.account_authorized:
                trader = await self.broker.trader()
                balance = trader["balance"]
                positions = await self.broker.positions()
            await self.watchdog.daily_heartbeat(balance, self.store.halted, len(positions))
        except Exception:  # noqa: BLE001
            log.exception("heartbeat failed")

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
