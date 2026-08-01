"""Guarda el histórico de velas que descargues, y lo lee para hacer backtest.

Por qué en local y no pidiéndoselo a un servicio cada vez: un backtest tiene que dar
EL MISMO resultado hoy y dentro de tres meses. Una fuente remota cambia, limita las
peticiones y no se puede auditar; un archivo tuyo, no. Además así puedes probar diez
mil combinaciones sin que nadie te corte.

El formato de los CSV varía mucho (columnas en inglés o español, fecha en segundos,
en milisegundos o en texto), así que aquí se reconoce lo común y se dice claramente
lo que no se ha podido leer, en vez de importar basura silenciosamente.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import re
import sqlite3
from pathlib import Path

from .broker import Candle

# nombre de columna (normalizado) -> campo
_COLS = {
    "time": "ts", "timestamp": "ts", "date": "ts", "datetime": "ts", "fecha": "ts",
    "localtime": "ts", "gmttime": "ts", "opentime": "ts",
    "open": "open", "apertura": "open", "o": "open",
    "high": "high", "maximo": "high", "max": "high", "h": "high",
    "low": "low", "minimo": "low", "min": "low", "l": "low",
    "close": "close", "cierre": "close", "c": "close", "price": "close",
    "volume": "volume", "vol": "volume", "tickvolume": "volume", "volumen": "volume",
}

_TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800,
               "H1": 3600, "H4": 14400, "D1": 86400, "W1": 604800}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def parse_ts(v) -> float | None:
    """Segundos, milisegundos o fecha en texto — todo acaba en segundos epoch."""
    if v is None or v == "":
        return None
    s = str(v).strip()
    try:
        f = float(s)
        if f > 1e16:            # nanosegundos
            return f / 1e9
        if f > 1e12:            # milisegundos
            return f / 1000.0
        if f > 1e10:            # microsegundos raros
            return f / 1e6
        return f                # segundos
    except ValueError:
        pass
    s = s.replace("/", "-").replace("T", " ").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d-%m-%Y",
                "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return dt.datetime.strptime(s[:26], fmt).replace(
                tzinfo=dt.timezone.utc).timestamp()
        except ValueError:
            continue
    return None


def parse_csv(text: str) -> tuple[list[dict], dict]:
    """Devuelve (velas, informe). El informe dice qué se leyó y qué se descartó."""
    rows: list[dict] = []
    info = {"lines": 0, "skipped": 0, "columns": {}, "error": ""}
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        reader = csv.reader(io.StringIO(text), dialect)
    except csv.Error:
        reader = csv.reader(io.StringIO(text))
    header = None
    for parts in reader:
        if not parts or not any(str(p).strip() for p in parts):
            continue
        if header is None:
            mapped = {i: _COLS.get(_norm(p)) for i, p in enumerate(parts)}
            if any(v == "ts" for v in mapped.values()) and \
               sum(1 for v in mapped.values() if v in ("open", "high", "low", "close")) >= 4:
                header = mapped
                info["columns"] = {parts[i]: v for i, v in mapped.items() if v}
                continue
            # sin encabezado reconocible: se asume el orden clásico
            header = {0: "ts", 1: "open", 2: "high", 3: "low", 4: "close", 5: "volume"}
            info["columns"] = {"(sin encabezado)": "ts,open,high,low,close,volume"}
        info["lines"] += 1
        row: dict = {}
        for i, p in enumerate(parts):
            f = header.get(i)
            if not f:
                continue
            if f == "ts":
                row["ts"] = parse_ts(p)
            else:
                try:
                    row[f] = float(str(p).replace(",", "."))
                except ValueError:
                    row[f] = None
        if not row.get("ts") or any(row.get(k) is None for k in ("open", "high", "low", "close")):
            info["skipped"] += 1
            continue
        row.setdefault("volume", 0.0)
        rows.append(row)
    if not rows and not info["error"]:
        info["error"] = ("no reconocí ninguna vela: hacen falta columnas de fecha y "
                         "open/high/low/close")
    return rows, info


def infer_tf(rows: list[dict]) -> str:
    """La temporalidad, del hueco más repetido entre velas. Menos fiable a ojo que
    contarlo, y equivocarse aquí desalinea todo el backtest."""
    if len(rows) < 3:
        return ""
    gaps: dict[int, int] = {}
    for a, b in zip(rows, rows[1:]):
        g = int(abs(b["ts"] - a["ts"]))
        if g:
            gaps[g] = gaps.get(g, 0) + 1
    if not gaps:
        return ""
    common = max(gaps.items(), key=lambda x: x[1])[0]
    best, diff = "", None
    for name, secs in _TF_SECONDS.items():
        d = abs(secs - common)
        if diff is None or d < diff:
            best, diff = name, d
    return best if diff is not None and diff <= max(1, common * 0.2) else ""


class CandleDB:
    """Las velas viven en su propio archivo: son muchas y no deben competir con el
    diario ni engordar la copia de seguridad del cerebro."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS candles(
            symbol TEXT NOT NULL, tf TEXT NOT NULL, ts INTEGER NOT NULL,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            PRIMARY KEY(symbol, tf, ts))""")
        self.db.commit()

    def add(self, symbol: str, tf: str, rows: list[dict]) -> int:
        """Inserta o REEMPLAZA por (símbolo, temporalidad, instante).

        Reimportar el mismo archivo no duplica ni una vela: la clave lo impide. Es lo
        que permite bajar el histórico por trozos sin llevar la cuenta a mano.
        """
        if not rows:
            return 0
        sym, t = symbol.upper(), tf.upper()
        before = self.count(sym, t)
        self.db.executemany(
            "INSERT OR REPLACE INTO candles(symbol,tf,ts,open,high,low,close,volume) "
            "VALUES(?,?,?,?,?,?,?,?)",
            [(sym, t, int(r["ts"]), r["open"], r["high"], r["low"], r["close"],
              r.get("volume") or 0) for r in rows])
        self.db.commit()
        return self.count(sym, t) - before

    def count(self, symbol: str, tf: str) -> int:
        return int(self.db.execute(
            "SELECT COUNT(*) FROM candles WHERE symbol=? AND tf=?",
            (symbol.upper(), tf.upper())).fetchone()[0])

    def series(self, symbol: str, tf: str, limit: int = 200000) -> list[Candle]:
        rows = self.db.execute(
            "SELECT ts,open,high,low,close,volume FROM candles "
            "WHERE symbol=? AND tf=? ORDER BY ts LIMIT ?",
            (symbol.upper(), tf.upper(), int(limit))).fetchall()
        return [Candle(ts=r[0], open=r[1], high=r[2], low=r[3], close=r[4],
                       volume=r[5] or 0) for r in rows]

    def inventory(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT symbol, tf, COUNT(*), MIN(ts), MAX(ts) FROM candles "
            "GROUP BY symbol, tf ORDER BY symbol, tf").fetchall()
        return [{"symbol": r[0], "tf": r[1], "bars": int(r[2]),
                 "from_ts": r[3], "to_ts": r[4]} for r in rows]

    def drop(self, symbol: str, tf: str = "") -> int:
        if tf:
            cur = self.db.execute("DELETE FROM candles WHERE symbol=? AND tf=?",
                                  (symbol.upper(), tf.upper()))
        else:
            cur = self.db.execute("DELETE FROM candles WHERE symbol=?",
                                  (symbol.upper(),))
        self.db.commit()
        return cur.rowcount
