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

    @property
    def halted(self) -> bool:
        return self.get("halted", "0") == "1"

    def set_halted(self, value: bool, reason: str = "") -> None:
        self.set("halted", "1" if value else "0")
        if reason:
            self.log("system", "halt" if value else "resume", reason)
