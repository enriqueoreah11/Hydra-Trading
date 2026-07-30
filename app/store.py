"""SQLite persistence: journal, playbook versions, key-value state (kill switch, etc.)."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

DEFAULT_PLAYBOOK = """# Playbook v2 — metales, petroleo e indices

## Contexto
Cazamos oportunidades en ORO, PLATA, PETROLEO e INDICES de EEUU (Nasdaq, Dow, S&P).
Prioriza calidad sobre cantidad: pocas operaciones con tesis clara valen mas que muchas
mediocres. Cada mercado tiene caracter propio — usa la seccion que corresponda.

## Reglas globales (todos los mercados)
- Solo operar a favor de la tendencia dominante (precio vs EMA200 y pendiente de EMA50).
- Entrada: pullback a EMA20/EMA50 con rechazo visible, o ruptura de nivel con re-test.
- RSI14: evitar compras > 72 y ventas < 28 (no perseguir movimientos extendidos).
- Stop loss: detras del ultimo swing relevante, minimo 1x ATR14 de distancia.
- Take profit: siguiente nivel de estructura; ratio riesgo/beneficio >= 1.5.
- Nunca promediar en contra; una posicion por simbolo.

## Metales (XAUUSD, XAGUSD)
- Mejor ventana: solape Londres-NY (13:00-17:00 UTC); evitar madrugada iliquida.
- Respetan niveles redondos (oro: multiplos de 25/50; plata: 0.50/1.00) — usalos para TP.
- La plata sigue al oro con mas violencia: si el oro no confirma, no operes plata.
- Antes de datos grandes de EEUU (CPI, NFP, FOMC) son comunes los barridos de liquidez:
  no entrar en los 30 min previos (el Sentinel ademas bloquea por calendario).

## Petroleo (XTIUSD / WTI)
- Evento clave: inventarios EIA miercoles 14:30 UTC — nada de entradas nuevas cerca.
- Tendencias fuertes con reversiones bruscas: exigir estructura clara y no operar rangos.
- Sensible a titulares OPEP+ y geopolitica: si el Sentinel reporta evento, quieto.

## Indices (US100, US30, US500)
- Sesion util: 13:30-20:00 UTC (cash de NY); la primera media hora es trampa — esperar
  a que la apertura defina direccion antes de entrar.
- Gap de apertura: si abre con gap grande, esperar re-test del nivel pre-gap; no perseguir.
- Los tres indices se mueven juntos: UNA posicion de indice a la vez (el Portfolio veta
  duplicados, pero tampoco los propongas).
- El US100 (Nasdaq) es el mas volatil: stops mas anchos (>= 1.2x ATR14).

## Cuando NO operar (global)
- Sin tendencia clara (precio enredado entre EMAs).
- Velas de rango extremo recientes (noticias) — esperar estabilizacion.
- Ya existe una posicion abierta en el mismo simbolo.
- Viernes en la ultima hora de la sesion de NY (riesgo de gap de fin de semana).

## Notas del arquitecto
(las ira agregando el agente Architect con lo aprendido cada dia)
"""


class Store:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self._init()

    def _init(self) -> None:
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS journal(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            agent TEXT NOT NULL,
            kind TEXT NOT NULL,
            symbol TEXT,
            content TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS playbook(
            version INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            content TEXT NOT NULL,
            changes TEXT
        );
        CREATE TABLE IF NOT EXISTS kv(
            key TEXT PRIMARY KEY,
            value TEXT
        );
        -- Aprendizaje: post-mortems clasificados, hipótesis y cambios propuestos.
        -- Los escribe Claude Desktop vía MCP; los cambios NO se aplican solos:
        -- quedan en 'proposals' esperando tu aprobación desde la UI.
        CREATE TABLE IF NOT EXISTS postmortems(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            ref TEXT,                -- referencia libre (símbolo, id de operación, fecha)
            symbol TEXT,
            category TEXT NOT NULL,  -- taxonomía cerrada (ver mcp_server.CATEGORIES)
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS hypotheses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            category TEXT,           -- categoría de post-mortem que la motiva
            param TEXT,              -- parámetro que se sospecha
            description TEXT NOT NULL,
            evidence TEXT,
            occurrences INTEGER DEFAULT 0,
            status TEXT DEFAULT 'open'   -- open | promoted | rejected
        );
        -- trade_context: CÓMO SE VEÍA EL MUNDO cuando el bot decidió.
        -- No el resultado — el estado que produjo la decisión. Ese estado no es
        -- reconstruible después: el spread de ese milisegundo, los fibs que había
        -- dibujados, por qué el score dio 7 y no 5. Si no se captura aquí, se pierde.
        -- Lo escribe el Confluence Bot vía POST; ver /ingest/trade-context.
        CREATE TABLE IF NOT EXISTS trade_context(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,                -- cuándo lo recibimos
            ts_bot REAL,                     -- cuándo decidió el bot
            signal_id TEXT,                  -- Candidate.Key del bot
            broker_position_id TEXT,         -- NULL si nunca se ejecutó
            symbol TEXT, timeframe TEXT, bias TEXT,
            outcome TEXT,                    -- alerted | blocked:* | low_score | executed
            score REAL, raw_score REAL, learning_mult REAL, corr_bonus REAL,
            zone_price REAL, zone_top REAL, zone_bottom REAL, zone_width_pips REAL,
            n_confluences INTEGER, n_families INTEGER,
            dist_pips REAL, spread_pips REAL,
            regime TEXT, bot_label TEXT, build_tag TEXT,
            signals_json TEXT,               -- [{label, price, time}] — varía por estrategia
            raw_json TEXT NOT NULL           -- el payload íntegro, tal cual llegó
        );
        CREATE INDEX IF NOT EXISTS ix_tc_ts ON trade_context(ts DESC);
        CREATE INDEX IF NOT EXISTS ix_tc_sym ON trade_context(symbol, outcome);
        CREATE INDEX IF NOT EXISTS ix_tc_sig ON trade_context(signal_id);
        -- INMUTABLE de verdad: la base rechaza cualquier cambio o borrado.
        -- Una corrección entra como fila nueva, nunca modificando la original.
        CREATE TRIGGER IF NOT EXISTS tc_no_update BEFORE UPDATE ON trade_context
        BEGIN SELECT RAISE(ABORT, 'trade_context es append-only: no se puede modificar'); END;
        CREATE TRIGGER IF NOT EXISTS tc_no_delete BEFORE DELETE ON trade_context
        BEGIN SELECT RAISE(ABORT, 'trade_context es append-only: no se puede borrar'); END;

        -- Flota: N estrategias corriendo en paralelo en papel. 'frozen' marca el
        -- champion de control, que nunca se ajusta.
        CREATE TABLE IF NOT EXISTS arms(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            name TEXT NOT NULL,
            strategy TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            params TEXT NOT NULL,
            frozen INTEGER DEFAULT 0,
            is_champion INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS arm_trades(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arm_id INTEGER NOT NULL,
            bar_idx INTEGER NOT NULL,
            ts REAL NOT NULL,
            direction TEXT NOT NULL,
            entry REAL, sl REAL, tp REAL,
            r_gross REAL NOT NULL,
            r_net REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_arm_trades ON arm_trades(arm_id, id);
        CREATE TABLE IF NOT EXISTS arm_reviews(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arm_id INTEGER NOT NULL,
            ts REAL NOT NULL,
            batch INTEGER,
            verdict TEXT,
            confidence INTEGER,
            reasoning TEXT,
            applied TEXT,
            last_trade_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS proposals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            hypothesis_id INTEGER,
            changes TEXT NOT NULL,   -- JSON {param: valor_nuevo}
            rationale TEXT,
            status TEXT DEFAULT 'awaiting_approval',  -- awaiting_approval | approved | rejected
            decided_ts REAL,
            decided_note TEXT
        );
        """)
        if not self.db.execute("SELECT 1 FROM playbook LIMIT 1").fetchone():
            self.db.execute("INSERT INTO playbook(ts, content, changes) VALUES(?,?,?)",
                            (time.time(), DEFAULT_PLAYBOOK, "playbook inicial"))
        else:
            # Si solo existe el playbook inicial (el Architect nunca lo evoluciono) y el
            # playbook base del codigo cambio, adopta la nueva base como version nueva.
            rows = self.db.execute("SELECT content FROM playbook ORDER BY version").fetchall()
            if len(rows) == 1 and rows[0][0] != DEFAULT_PLAYBOOK:
                self.db.execute("INSERT INTO playbook(ts, content, changes) VALUES(?,?,?)",
                                (time.time(), DEFAULT_PLAYBOOK, "actualizacion del playbook base"))
        self.db.commit()

    # -------------------------------------------------------------- journal

    def log(self, agent: str, kind: str, content: dict | str, symbol: str | None = None) -> None:
        body = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        self.db.execute(
            "INSERT INTO journal(ts, agent, kind, symbol, content) VALUES(?,?,?,?,?)",
            (time.time(), agent, kind, symbol, body))
        self.db.commit()

    def journal_since(self, since_epoch: float, limit: int = 500) -> list[dict]:
        rows = self.db.execute(
            "SELECT ts, agent, kind, symbol, content FROM journal WHERE ts >= ? "
            "ORDER BY ts ASC LIMIT ?", (since_epoch, limit)).fetchall()
        return [{"ts": r[0], "agent": r[1], "kind": r[2], "symbol": r[3], "content": r[4]}
                for r in rows]

    def recent_journal(self, limit: int = 50) -> list[dict]:
        rows = self.db.execute(
            "SELECT ts, agent, kind, symbol, content FROM journal "
            "ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return [{"ts": r[0], "agent": r[1], "kind": r[2], "symbol": r[3], "content": r[4]}
                for r in rows]

    def recent_reviews(self, n: int = 5) -> list[dict]:
        rows = self.db.execute(
            "SELECT ts, content FROM journal WHERE agent='reviewer' AND kind='daily_review' "
            "ORDER BY ts DESC LIMIT ?", (n,)).fetchall()
        return [{"ts": r[0], "content": r[1]} for r in rows]

    # ------------------------------------------------------------- playbook

    def playbook(self) -> tuple[int, str]:
        row = self.db.execute(
            "SELECT version, content FROM playbook ORDER BY version DESC LIMIT 1").fetchone()
        return int(row[0]), row[1]

    def save_playbook(self, content: str, changes: str) -> int:
        cur = self.db.execute("INSERT INTO playbook(ts, content, changes) VALUES(?,?,?)",
                              (time.time(), content, changes))
        self.db.commit()
        return int(cur.lastrowid)

    # ------------------------------------------------------------------- kv

    def get(self, key: str, default: str | None = None) -> str | None:
        row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set(self, key: str, value: str) -> None:
        self.db.execute("INSERT INTO kv(key,value) VALUES(?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        self.db.commit()

    # ---------------------------------------------------------- trade_context

    def add_trade_context(self, row: dict, raw: dict, ts: float | None = None) -> int:
        """Guarda una captura. `ts` es CUÁNDO PASÓ, no cuándo se leyó.

        Importa para lo que se ve en pantalla: una fila de un CSV de hace tres días
        no puede contar como "analizando ahora" solo porque se acabe de importar. Si
        no llega un instante creíble, se usa el de ahora.
        """
        cols = ("ts_bot", "signal_id", "broker_position_id", "symbol", "timeframe",
                "bias", "outcome", "score", "raw_score", "learning_mult", "corr_bonus",
                "zone_price", "zone_top", "zone_bottom", "zone_width_pips",
                "n_confluences", "n_families", "dist_pips", "spread_pips",
                "regime", "bot_label", "build_tag", "signals_json")
        vals = [row.get(c) for c in cols]
        now = time.time()
        when = now
        try:
            t = float(ts or 0)
            if t > 1e11:                    # venía en milisegundos
                t /= 1000.0
            # creíble: de 2010 en adelante y no del futuro (mas de un dia)
            if 1262304000 < t < now + 86400:
                when = t
        except (TypeError, ValueError):
            pass
        cur = self.db.execute(
            f"INSERT INTO trade_context(ts,{','.join(cols)},raw_json) "
            f"VALUES(?,{','.join('?' * len(cols))},?)",
            (when, *vals, json.dumps(raw, ensure_ascii=False)))
        self.db.commit()
        return int(cur.lastrowid)

    def trade_contexts(self, limit: int = 50, symbol: str = "",
                       outcome: str = "") -> list[dict]:
        q = ("SELECT id,ts,ts_bot,signal_id,symbol,timeframe,bias,outcome,score,"
             "learning_mult,zone_price,zone_width_pips,n_confluences,dist_pips,"
             "spread_pips,regime,bot_label,signals_json FROM trade_context")
        where, args = [], []
        if symbol:
            where.append("symbol=?")
            args.append(symbol.upper())
        if outcome:
            where.append("outcome LIKE ?")
            args.append(outcome + "%")
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY id DESC LIMIT ?"
        rows = self.db.execute(q, (*args, limit)).fetchall()
        keys = ("id", "ts", "ts_bot", "signal_id", "symbol", "timeframe", "bias",
                "outcome", "score", "learning_mult", "zone_price", "zone_width_pips",
                "n_confluences", "dist_pips", "spread_pips", "regime", "bot_label",
                "signals_json")
        return [dict(zip(keys, r)) for r in rows]

    def trade_context_one(self, ctx_id: int) -> dict | None:
        """Una captura completa, con el JSON íntegro tal como llegó del bot."""
        r = self.db.execute(
            "SELECT id,ts,symbol,timeframe,outcome,score,raw_json FROM trade_context "
            "WHERE id=?", (int(ctx_id),)).fetchone()
        if not r:
            return None
        try:
            raw = json.loads(r[6] or "{}")
        except json.JSONDecodeError:
            raw = {}
        return {"id": r[0], "ts": r[1], "symbol": r[2], "timeframe": r[3],
                "outcome": r[4], "score": r[5], "raw": raw}

    def trade_context_active(self, minutes: float = 45) -> list[dict]:
        """Qué bots han ANALIZADO algo hace poco, por su etiqueta.

        Analizar deja rastro en trade_context aunque no se opere: es la señal de
        que el bot está vivo y mirando, no solo cuando abre posición.
        """
        since = time.time() - max(1.0, minutes) * 60
        rows = self.db.execute(
            "SELECT COALESCE(NULLIF(TRIM(bot_label),''),'(sin etiqueta)') AS lbl, "
            "COUNT(*), MAX(ts), "
            "SUM(CASE WHEN outcome LIKE 'alerted%' THEN 1 ELSE 0 END), "
            "GROUP_CONCAT(DISTINCT symbol) "
            "FROM trade_context WHERE ts >= ? GROUP BY lbl ORDER BY MAX(ts) DESC",
            (since,)).fetchall()
        return [{"label": r[0], "seen": int(r[1]), "last_ts": r[2],
                 "alerted": int(r[3] or 0),
                 "symbols": [s for s in (r[4] or "").split(",") if s][:6]}
                for r in rows]

    def setups(self, days: float = 30, limit: int = 40) -> list[dict]:
        """Los SETUPS acumulados: cada combinación repetida, con cómo le fue.

        Un setup no es una fila: es el patrón que se repite (instrumento +
        temporalidad + lado + qué confluencias había). Agrupando así, el diario deja
        de ser una lista infinita y empieza a decir QUÉ funciona.

        `alerted` son las que el bot dejó pasar a señal; el resto se bloqueó. Se
        muestran las dos, porque el aprendizaje está justo en las bloqueadas.
        """
        since = time.time() - max(0.1, days) * 86400
        rows = self.db.execute(
            "SELECT COALESCE(symbol,'?') s, COALESCE(timeframe,'?') tf, "
            "COALESCE(bias,'?') b, COALESCE(n_families,0) nf, "
            "COUNT(*) n, AVG(score) sc, MAX(ts) last, "
            "SUM(CASE WHEN outcome LIKE 'alerted%' THEN 1 ELSE 0 END) ok, "
            "GROUP_CONCAT(DISTINCT COALESCE(bot_label,'')) bots "
            "FROM trade_context WHERE ts >= ? "
            "GROUP BY s, tf, b, nf HAVING n >= 1 "
            "ORDER BY n DESC, last DESC LIMIT ?",
            (since, int(max(1, min(200, limit))))).fetchall()
        out = []
        for r in rows:
            n, ok = int(r[4]), int(r[7] or 0)
            out.append({"symbol": r[0], "timeframe": r[1], "bias": r[2],
                        "n_families": int(r[3] or 0), "seen": n,
                        "avg_score": round(r[5], 3) if r[5] is not None else None,
                        "last_ts": r[6], "alerted": ok, "blocked": n - ok,
                        "alerted_pct": round(ok / n * 100, 1) if n else None,
                        "bots": [x for x in (r[8] or "").split(",") if x][:4]})
        return out

    def trade_context_digest(self, hours: float = 24, symbol: str = "") -> dict:
        """Resumen digerible de lo que vio el bot, para meterlo en un prompt.

        No devuelve filas: devuelve el PATRÓN — cuántas señales, cuántas se
        bloquearon y por qué, el score medio de las que pasaron frente a las que
        no, y qué familias de confluencia aparecen. Así el Reviewer puede juzgar
        las señales RECHAZADAS, que es donde está el aprendizaje que se perdía.
        """
        since = time.time() - hours * 3600
        args: list = [since]
        where = "ts >= ?"
        if symbol:
            where += " AND symbol = ?"
            args.append(symbol.upper())

        total = self.db.execute(
            f"SELECT COUNT(*) FROM trade_context WHERE {where}", args).fetchone()[0]
        if not total:
            return {"total": 0, "hours": hours}

        by_outcome = [
            {"outcome": r[0], "n": r[1],
             "avg_score": round(r[2], 2) if r[2] is not None else None,
             "avg_confluences": round(r[3], 1) if r[3] is not None else None}
            for r in self.db.execute(
                f"SELECT outcome, COUNT(*), AVG(score), AVG(n_confluences) "
                f"FROM trade_context WHERE {where} GROUP BY outcome "
                f"ORDER BY COUNT(*) DESC", args).fetchall()]

        by_symbol = [{"symbol": r[0], "n": r[1],
                      "avg_score": round(r[2], 2) if r[2] is not None else None}
                     for r in self.db.execute(
                         f"SELECT symbol, COUNT(*), AVG(score) FROM trade_context "
                         f"WHERE {where} GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 12",
                         args).fetchall()]

        # Las que se quedaron cerca: score alto pero no se alertó. Aquí es donde
        # se ve si el filtro está demasiado apretado.
        near_miss = [
            {"symbol": r[0], "timeframe": r[1], "bias": r[2], "outcome": r[3],
             "score": r[4], "n_confluences": r[5], "spread_pips": r[6]}
            for r in self.db.execute(
                f"SELECT symbol,timeframe,bias,outcome,score,n_confluences,spread_pips "
                f"FROM trade_context WHERE {where} AND outcome NOT LIKE 'alerted%' "
                f"AND score IS NOT NULL ORDER BY score DESC LIMIT 8", args).fetchall()]

        fam: dict[str, int] = {}
        rows = self.db.execute(
            f"SELECT signals_json FROM trade_context WHERE {where} "
            f"AND signals_json IS NOT NULL ORDER BY ts DESC LIMIT 400", args).fetchall()
        for (js,) in rows:
            try:
                sigs = json.loads(js) or []
            except json.JSONDecodeError:
                continue
            seen = set()
            for sig in sigs if isinstance(sigs, list) else []:
                lbl = ""
                if isinstance(sig, dict):
                    for k in ("Label", "label", "Name", "name"):
                        if sig.get(k):
                            lbl = str(sig[k])
                            break
                else:
                    lbl = str(sig)
                # una familia cuenta una vez por señal, no una por confluencia
                key = lbl.split()[0][:14] if lbl else "?"
                if key not in seen:
                    seen.add(key)
                    fam[key] = fam.get(key, 0) + 1
        top_families = sorted(fam.items(), key=lambda kv: -kv[1])[:10]

        return {"total": int(total), "hours": hours,
                "by_outcome": by_outcome, "by_symbol": by_symbol,
                "near_miss": near_miss,
                "top_families": [{"label": k, "n": v} for k, v in top_families]}

    def trade_context_stats(self) -> dict:
        total = self.db.execute("SELECT COUNT(*) FROM trade_context").fetchone()[0]
        by_outcome = [{"outcome": r[0], "n": r[1], "avg_score": round(r[2] or 0, 2)}
                      for r in self.db.execute(
                          "SELECT outcome, COUNT(*), AVG(score) FROM trade_context "
                          "GROUP BY outcome ORDER BY COUNT(*) DESC").fetchall()]
        by_symbol = [{"symbol": r[0], "n": r[1]} for r in self.db.execute(
            "SELECT symbol, COUNT(*) FROM trade_context GROUP BY symbol "
            "ORDER BY COUNT(*) DESC LIMIT 12").fetchall()]
        row = self.db.execute("SELECT MIN(ts), MAX(ts) FROM trade_context").fetchone()
        return {"total": int(total), "by_outcome": by_outcome, "by_symbol": by_symbol,
                "first_ts": row[0], "last_ts": row[1]}

    # ------------------------------------------------------------------ flota

    def add_arm(self, name: str, strategy: str, symbol: str, timeframe: str,
                params: dict, frozen: bool = False, is_champion: bool = False) -> int:
        cur = self.db.execute(
            "INSERT INTO arms(ts,name,strategy,symbol,timeframe,params,frozen,is_champion) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (time.time(), name, strategy, symbol.upper(), timeframe.upper(),
             json.dumps(params), int(frozen), int(is_champion)))
        self.db.commit()
        return int(cur.lastrowid)

    def arms(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT id,name,strategy,symbol,timeframe,params,frozen,is_champion "
            "FROM arms ORDER BY id").fetchall()
        return [{"id": r[0], "name": r[1], "strategy": r[2], "symbol": r[3],
                 "timeframe": r[4], "params": r[5], "frozen": bool(r[6]),
                 "is_champion": bool(r[7])} for r in rows]

    def update_arm_params(self, arm_id: int, params: dict) -> None:
        self.db.execute("UPDATE arms SET params=? WHERE id=? AND frozen=0",
                        (json.dumps(params), arm_id))
        self.db.commit()

    def clear_fleet(self) -> None:
        self.db.executescript(
            "DELETE FROM arm_trades; DELETE FROM arm_reviews; DELETE FROM arms;")
        self.db.commit()

    def add_arm_trade(self, arm_id: int, bar_idx: int, ts: float, direction: str,
                      entry: float, sl: float, tp: float,
                      r_gross: float, r_net: float) -> None:
        self.db.execute(
            "INSERT INTO arm_trades(arm_id,bar_idx,ts,direction,entry,sl,tp,r_gross,r_net) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (arm_id, bar_idx, ts, direction, entry, sl, tp, r_gross, r_net))
        self.db.commit()

    def arm_last_index(self, arm_id: int) -> int:
        row = self.db.execute("SELECT MAX(bar_idx) FROM arm_trades WHERE arm_id=?",
                              (arm_id,)).fetchone()
        return int(row[0]) if row and row[0] is not None else -1

    def arm_trades(self, arm_id: int, limit: int = 40) -> list[dict]:
        rows = self.db.execute(
            "SELECT id,ts,direction,entry,sl,tp,r_gross,r_net FROM arm_trades "
            "WHERE arm_id=? ORDER BY id DESC LIMIT ?", (arm_id, limit)).fetchall()
        return [{"id": r[0], "ts": r[1], "direction": r[2], "entry": r[3], "sl": r[4],
                 "tp": r[5], "r_gross": r[6], "r_net": r[7]} for r in rows]

    def arm_trades_since_review(self, arm_id: int) -> int:
        row = self.db.execute(
            "SELECT MAX(last_trade_id) FROM arm_reviews WHERE arm_id=?", (arm_id,)).fetchone()
        last = int(row[0]) if row and row[0] is not None else 0
        row = self.db.execute(
            "SELECT COUNT(*) FROM arm_trades WHERE arm_id=? AND id>?", (arm_id, last)).fetchone()
        return int(row[0]) if row else 0

    def add_arm_review(self, arm_id: int, batch: int, verdict: str, confidence: int,
                       reasoning: str, applied: dict) -> None:
        row = self.db.execute("SELECT MAX(id) FROM arm_trades WHERE arm_id=?",
                              (arm_id,)).fetchone()
        last = int(row[0]) if row and row[0] is not None else 0
        self.db.execute(
            "INSERT INTO arm_reviews(arm_id,ts,batch,verdict,confidence,reasoning,applied,"
            "last_trade_id) VALUES(?,?,?,?,?,?,?,?)",
            (arm_id, time.time(), batch, verdict, confidence, reasoning,
             json.dumps(applied, ensure_ascii=False), last))
        self.db.commit()

    def arm_reviews(self, limit: int = 30) -> list[dict]:
        rows = self.db.execute(
            "SELECT r.ts,a.name,r.verdict,r.confidence,r.reasoning,r.applied,r.batch "
            "FROM arm_reviews r JOIN arms a ON a.id=r.arm_id "
            "ORDER BY r.id DESC LIMIT ?", (limit,)).fetchall()
        return [{"ts": r[0], "arm": r[1], "verdict": r[2], "confidence": r[3],
                 "reasoning": r[4], "applied": r[5], "batch": r[6]} for r in rows]

    def arm_stats(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT a.id,a.name,a.strategy,a.symbol,a.params,a.frozen,a.is_champion,"
            "       COUNT(t.id), COALESCE(SUM(t.r_gross),0), COALESCE(SUM(t.r_net),0),"
            "       COALESCE(SUM(CASE WHEN t.r_net>0 THEN 1 ELSE 0 END),0) "
            "FROM arms a LEFT JOIN arm_trades t ON t.arm_id=a.id "
            "GROUP BY a.id ORDER BY a.id").fetchall()
        return [{"id": r[0], "name": r[1], "strategy": r[2], "symbol": r[3],
                 "params": r[4], "frozen": bool(r[5]), "is_champion": bool(r[6]),
                 "trades": int(r[7]), "sum_gross": r[8], "sum_net": r[9],
                 "wins": int(r[10]),
                 "win_rate": (100.0 * r[10] / r[7]) if r[7] else 0.0} for r in rows]

    # ------------------------------------------------------- aprendizaje (MCP)

    def add_postmortem(self, category: str, notes: str = "", ref: str = "",
                       symbol: str | None = None) -> int:
        cur = self.db.execute(
            "INSERT INTO postmortems(ts, ref, symbol, category, notes) VALUES(?,?,?,?,?)",
            (time.time(), ref, symbol, category, notes))
        self.db.commit()
        return int(cur.lastrowid)

    def postmortem_counts(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT category, COUNT(*) FROM postmortems GROUP BY category "
            "ORDER BY COUNT(*) DESC").fetchall()
        return [{"category": r[0], "count": int(r[1])} for r in rows]

    def postmortems(self, category: str | None = None, limit: int = 100) -> list[dict]:
        if category:
            rows = self.db.execute(
                "SELECT id, ts, ref, symbol, category, notes FROM postmortems "
                "WHERE category=? ORDER BY ts DESC LIMIT ?", (category, limit)).fetchall()
        else:
            rows = self.db.execute(
                "SELECT id, ts, ref, symbol, category, notes FROM postmortems "
                "ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": r[0], "ts": r[1], "ref": r[2], "symbol": r[3],
                 "category": r[4], "notes": r[5]} for r in rows]

    def add_hypothesis(self, description: str, category: str = "", param: str = "",
                       evidence: str = "", occurrences: int = 0) -> int:
        cur = self.db.execute(
            "INSERT INTO hypotheses(ts, category, param, description, evidence, occurrences) "
            "VALUES(?,?,?,?,?,?)",
            (time.time(), category, param, description, evidence, occurrences))
        self.db.commit()
        return int(cur.lastrowid)

    def hypotheses(self, status: str | None = None, limit: int = 50) -> list[dict]:
        q = ("SELECT id, ts, category, param, description, evidence, occurrences, status "
             "FROM hypotheses")
        args: tuple = ()
        if status:
            q += " WHERE status=?"
            args = (status,)
        q += " ORDER BY ts DESC LIMIT ?"
        rows = self.db.execute(q, (*args, limit)).fetchall()
        return [{"id": r[0], "ts": r[1], "category": r[2], "param": r[3],
                 "description": r[4], "evidence": r[5], "occurrences": r[6],
                 "status": r[7]} for r in rows]

    def add_proposal(self, changes: str, rationale: str = "",
                     hypothesis_id: int | None = None) -> int:
        cur = self.db.execute(
            "INSERT INTO proposals(ts, hypothesis_id, changes, rationale) VALUES(?,?,?,?)",
            (time.time(), hypothesis_id, changes, rationale))
        self.db.commit()
        return int(cur.lastrowid)

    def proposals(self, status: str | None = "awaiting_approval", limit: int = 50) -> list[dict]:
        q = ("SELECT id, ts, hypothesis_id, changes, rationale, status, decided_ts, decided_note "
             "FROM proposals")
        args: tuple = ()
        if status:
            q += " WHERE status=?"
            args = (status,)
        q += " ORDER BY ts DESC LIMIT ?"
        rows = self.db.execute(q, (*args, limit)).fetchall()
        return [{"id": r[0], "ts": r[1], "hypothesis_id": r[2], "changes": r[3],
                 "rationale": r[4], "status": r[5], "decided_ts": r[6],
                 "decided_note": r[7]} for r in rows]

    def proposal(self, pid: int) -> dict | None:
        row = self.db.execute(
            "SELECT id, ts, hypothesis_id, changes, rationale, status FROM proposals WHERE id=?",
            (pid,)).fetchone()
        if not row:
            return None
        return {"id": row[0], "ts": row[1], "hypothesis_id": row[2], "changes": row[3],
                "rationale": row[4], "status": row[5]}

    def decide_proposal(self, pid: int, approved: bool, note: str = "") -> None:
        self.db.execute(
            "UPDATE proposals SET status=?, decided_ts=?, decided_note=? WHERE id=?",
            ("approved" if approved else "rejected", time.time(), note, pid))
        self.db.commit()

    @property
    def halted(self) -> bool:
        return self.get("halted", "0") == "1"

    def set_halted(self, value: bool, reason: str = "") -> None:
        self.set("halted", "1" if value else "0")
        if reason:
            self.log("system", "halt" if value else "resume", reason)
