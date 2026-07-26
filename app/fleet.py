"""Flota de estrategias en paralelo, con champion congelado y revisión por LLM.

Idea: en vez de una sola estrategia que se ajusta a ciegas, corren N variantes a
la vez en papel. Cada una acumula operaciones; cada `review_every` operaciones el
revisor lee el lote y decide si ajustar algo o dejarlo igual.

Dos piezas hacen que esto sea aprender y no sobreajustar:

1. **Champion congelado.** Un arm que NUNCA cambia. Es el control científico: si
   los que se auto-corrigen no le ganan, la "mejora" era ruido.
2. **R neto de costos.** Todo se mide después de spread y comisión. Una ventaja
   bruta que el costo se come no es una ventaja.

Nada de esto toca la cuenta real: es simulación sobre velas del broker.
"""
from __future__ import annotations

import json
import logging
import time

from . import llm, strategies
from .backtest import simulate_trade
from .broker import Candle
from .store import Store

log = logging.getLogger("fleet")

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["no_change", "adjust"]},
        "confidence": {"type": "integer"},
        "reasoning": {"type": "string"},
        "changes": {"type": "object", "additionalProperties": {"type": "number"}},
    },
    "required": ["verdict", "confidence", "reasoning"],
    "additionalProperties": False,
}

SYSTEM = """Eres el revisor forense de una flota de estrategias de trading.

Recibes el resultado de un lote de operaciones de UNA estrategia y decides si
ajustar sus parámetros o dejarla igual.

Sé escéptico por defecto. La mayoría de los lotes perdedores son varianza normal,
no un fallo de los parámetros: si el edge bruto es positivo pero el neto negativo,
el problema es el COSTO, no la estrategia, y ajustar parámetros no lo arregla.
Un lote pequeño no dice nada. Ante la duda responde "no_change".

Solo responde "adjust" cuando el patrón sea claro y puedas nombrar la causa
concreta (p.ej. el stop es más corto que el ruido típico y por eso el 70% sale
por SL). Cambia como máximo 2 parámetros y muévelos poco: son ajustes finos, no
reinventos."""


def _fmt(x: float) -> str:
    return f"{x:+.3f}"


class Fleet:
    def __init__(self, store: Store, broker):
        self.store = store
        self.broker = broker

    # ------------------------------------------------------------ creación

    def seed(self, symbol: str, timeframe: str = "M15", per_strategy: int = 5) -> int:
        """Crea la flota inicial: variantes de cada estrategia + un champion
        congelado por estrategia como control."""
        made = 0
        for strat in strategies.STRATEGIES:
            base = strategies.DEFAULTS[strat]
            # champion: parámetros por defecto, CONGELADO (nunca se ajusta)
            self.store.add_arm(f"{strat}·champion", strat, symbol, timeframe,
                               base, frozen=True, is_champion=True)
            made += 1
            # variantes: mismo motor, parámetros distintos
            rng = strategies.TUNABLE[strat]
            for v in range(per_strategy - 1):
                p = dict(base)
                for k, (lo, hi) in rng.items():
                    span = hi - lo
                    # rejilla determinista: sin aleatoriedad, así es reproducible
                    p[k] = round(lo + span * ((v + 1) / per_strategy), 3)
                p = strategies.clamp(strat, p)
                self.store.add_arm(f"{strat}·v{v + 1}", strat, symbol, timeframe, p)
                made += 1
        return made

    # ------------------------------------------------------------ ejecución

    def run_arm(self, arm: dict, candles: list[Candle], horizon: int = 30,
                cost_r: float = 0.0) -> int:
        """Corre un arm sobre las velas y guarda las operaciones nuevas.

        `cost_r` es el costo de ida y vuelta (spread + comisión) expresado en R.
        Se resta de cada resultado: así todo lo que ves ya es neto.
        """
        fn = strategies.STRATEGIES.get(arm["strategy"])
        if fn is None:
            return 0
        params = json.loads(arm["params"])
        done = self.store.arm_last_index(arm["id"])
        n = 0
        for i in range(max(done + 1, 60), len(candles) - horizon):
            sig = fn(candles, params, i)
            if sig is None:
                continue
            gross = simulate_trade(candles, i, sig.direction, sig.entry,
                                   sig.sl, sig.tp, horizon)
            if gross is None:
                continue
            self.store.add_arm_trade(arm["id"], i, candles[i].ts, sig.direction,
                                     sig.entry, sig.sl, sig.tp,
                                     gross, gross - cost_r)
            n += 1
        return n

    # ------------------------------------------------------------- revisión

    async def review_arm(self, arm: dict, batch: int = 40) -> dict:
        """El revisor lee el último lote y decide. Devuelve el veredicto.

        NO aplica nada si el arm está congelado: el champion es intocable.
        """
        trades = self.store.arm_trades(arm["id"], limit=batch)
        if len(trades) < batch:
            return {"verdict": "no_change", "confidence": 0,
                    "reasoning": f"solo {len(trades)} operaciones; hacen falta {batch}. "
                                 "Un lote pequeño no dice nada.", "skipped": True}
        gross = sum(t["r_gross"] for t in trades) / len(trades)
        net = sum(t["r_net"] for t in trades) / len(trades)
        wins = [t for t in trades if t["r_net"] > 0]
        losers = [t for t in trades if t["r_net"] <= 0]
        sl_exits = [t for t in trades if t["r_gross"] <= -0.999]
        params = json.loads(arm["params"])
        user = (
            f"Estrategia: {arm['strategy']}  ·  {arm['symbol']} {arm['timeframe']}\n"
            f"Parámetros actuales: {json.dumps(params, ensure_ascii=False)}\n"
            f"Rangos permitidos: {json.dumps(strategies.TUNABLE[arm['strategy']])}\n\n"
            f"Lote de {len(trades)} operaciones:\n"
            f"- Edge BRUTO medio: {_fmt(gross)}R\n"
            f"- Edge NETO medio (tras costos): {_fmt(net)}R\n"
            f"- Costo implícito: {_fmt(gross - net)}R por operación\n"
            f"- Win rate: {100 * len(wins) / len(trades):.1f}%\n"
            f"- Salidas por stop loss: {100 * len(sl_exits) / len(trades):.1f}%\n"
            f"- Perdedor medio: {_fmt(sum(t['r_net'] for t in losers) / max(1, len(losers)))}R\n"
            f"- Ganador medio: {_fmt(sum(t['r_net'] for t in wins) / max(1, len(wins)))}R\n"
        )
        try:
            res = await llm.ask(SYSTEM, user, schema=REVIEW_SCHEMA,
                                max_tokens=1500, role="reviewer")
        except Exception as exc:  # noqa: BLE001 - la revisión nunca tumba la flota
            # sin traza: si falta la key, esto se repetiría una vez por arm
            log.warning("review failed for arm %s: %s", arm["id"], exc)
            return {"verdict": "no_change", "confidence": 0,
                    "reasoning": f"revisor no disponible: {exc}"[:200], "error": True}
        applied: dict = {}
        if res.get("verdict") == "adjust" and res.get("changes"):
            if arm["frozen"]:
                res["reasoning"] += "  [CONGELADO: es el champion de control, no se toca]"
            else:
                newp = strategies.clamp(arm["strategy"], {**params, **res["changes"]})
                applied = {k: v for k, v in newp.items() if params.get(k) != v}
                if applied:
                    self.store.update_arm_params(arm["id"], newp)
        self.store.add_arm_review(arm["id"], len(trades), res.get("verdict", "no_change"),
                                  int(res.get("confidence", 0)),
                                  str(res.get("reasoning", ""))[:1500], applied)
        return {**res, "applied": applied}

    # ---------------------------------------------------------- leaderboard

    def leaderboard(self) -> list[dict]:
        """Tabla ordenada por R neto acumulado. El champion va marcado para que
        veas de un vistazo si las variantes le están ganando de verdad."""
        rows = self.store.arm_stats()
        for r in rows:
            r["edge_net"] = (r["sum_net"] / r["trades"]) if r["trades"] else 0.0
            r["edge_gross"] = (r["sum_gross"] / r["trades"]) if r["trades"] else 0.0
            r["cost_drag"] = r["edge_gross"] - r["edge_net"]
        rows.sort(key=lambda r: r["sum_net"], reverse=True)
        champs = {r["strategy"]: r["sum_net"] for r in rows if r["is_champion"]}
        for r in rows:
            base = champs.get(r["strategy"])
            r["vs_champion"] = None if base is None or r["is_champion"] else r["sum_net"] - base
        return rows

    async def cycle(self, symbol: str = "", batch: int = 40,
                    horizon: int = 30, cost_r: float = 0.05) -> dict:
        """Un ciclo completo: alimentar todos los arms con velas nuevas y revisar
        los que ya juntaron un lote."""
        arms = self.store.arms()
        if not arms:
            return {"ok": False, "error": "la flota está vacía; créala primero"}
        cache: dict[tuple, list[Candle]] = {}
        new_trades = 0
        for a in arms:
            if symbol and a["symbol"] != symbol.upper():
                continue
            key = (a["symbol"], a["timeframe"])
            if key not in cache:
                cache[key] = await self.broker.candles(a["symbol"], a["timeframe"], 1000)
            new_trades += self.run_arm(a, cache[key], horizon, cost_r)
        reviews = []
        for a in self.store.arms():
            since = self.store.arm_trades_since_review(a["id"])
            if since >= batch:
                r = await self.review_arm(a, batch)
                reviews.append({"arm": a["name"], **{k: r[k] for k in
                                ("verdict", "confidence") if k in r}})
        return {"ok": True, "arms": len(arms), "new_trades": new_trades,
                "reviews": reviews, "ts": time.time()}
