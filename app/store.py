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
