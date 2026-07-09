"""SQLite persistence: journal, playbook versions, key-value state (kill switch, etc.)."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

DEFAULT_PLAYBOOK = """# Playbook v1 — estrategia base

## Contexto
Opera tendencia en los timeframes configurados. Prioriza calidad sobre cantidad:
pocas operaciones con tesis clara valen mas que muchas mediocres.

## Setup permitido
- Solo operar a favor de la tendencia dominante (precio vs EMA200 y pendiente de EMA50).
- Entrada: pullback a EMA20/EMA50 o ruptura de nivel con re-test.
- RSI: evitar compras con RSI14 > 72 y ventas con RSI14 < 28.
- Stop loss: detras del ultimo swing relevante, minimo 1x ATR14 de distancia.
- Take profit: siguiente nivel de estructura; ratio riesgo/beneficio >= 1.5.

## Cuando NO operar
- Sin tendencia clara (precio enredado entre EMAs).
- Velas de rango extremo recientes (noticias) — esperar estabilizacion.
- Ya existe una posicion abierta en el mismo simbolo.

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
        """)
        if not self.db.execute("SELECT 1 FROM playbook LIMIT 1").fetchone():
            self.db.execute("INSERT INTO playbook(ts, content, changes) VALUES(?,?,?)",
                            (time.time(), DEFAULT_PLAYBOOK, "playbook inicial"))
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

    @property
    def halted(self) -> bool:
        return self.get("halted", "0") == "1"

    def set_halted(self, value: bool, reason: str = "") -> None:
        self.set("halted", "1" if value else "0")
        if reason:
            self.log("system", "halt" if value else "resume", reason)
