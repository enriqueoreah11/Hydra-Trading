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


# Cómo nombra Dukascopy sus exportaciones:
#   EURUSD_Candlestick_15_M_BID_01.01.2024-31.12.2024.csv
# y cómo lo nombra casi todo el mundo:
#   EURUSD_M15.csv, eurusd-m15-2024.csv, XAUUSD H1.csv
_DUKA = re.compile(r"^([A-Za-z0-9./]+)[_ -]candlestick[_ -](\d+)[_ -]([mhdw])", re.I)
_PLAIN = re.compile(r"^([A-Za-z0-9./]{3,12})[ _-]+(m|h|d|w)\s*(\d+)", re.I)
_PLAIN2 = re.compile(r"^([A-Za-z0-9./]{3,12})[ _-]+(\d+)\s*(m|h|d|w)\b", re.I)


def from_filename(name: str) -> tuple[str, str]:
    """(símbolo, temporalidad) deducidos del nombre del archivo, o ("", "").

    Se deduce, no se adivina: si el nombre no lo dice claro se devuelve vacío y que lo
    ponga el usuario. Importar EURUSD como si fuera XAUUSD no se detecta luego.
    """
    base = str(name or "").rsplit("/", 1)[-1]
    base = base.rsplit(".", 1)[0] if "." in base else base
    m = _DUKA.match(base)
    if m:
        sym, n, unit = m.group(1), m.group(2), m.group(3).upper()
        return sym.replace(".", "").upper(), f"{unit}{int(n)}"
    m = _PLAIN.match(base)
    if m:
        return m.group(1).replace(".", "").upper(), f"{m.group(2).upper()}{int(m.group(3))}"
    m = _PLAIN2.match(base)
    if m:
        return m.group(1).replace(".", "").upper(), f"{m.group(3).upper()}{int(m.group(2))}"
    return "", ""


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
        # De DONDE salio cada vela. Sin esto, dos fuentes para el mismo simbolo se
        # pisaban vela a vela (la clave primaria no las distingue) y quedaba una
        # serie mitad de un sitio y mitad de otro, sin nada que lo indicara. Eso es
        # peor que no tener datos: se mide sobre una serie que no existio nunca.
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(candles)")}
        if "fuente" not in cols:
            self.db.execute("ALTER TABLE candles ADD COLUMN fuente TEXT DEFAULT ''")
        self.db.commit()

    def add(self, symbol: str, tf: str, rows: list[dict],
            fuente: str = "ctrader") -> int:
        """Inserta o REEMPLAZA por (símbolo, temporalidad, instante).

        Reimportar el mismo archivo no duplica ni una vela: la clave lo impide. Es lo
        que permite bajar el histórico por trozos sin llevar la cuenta a mano.

        `fuente` dice de dónde salió. Importa mucho más de lo que parece: los datos
        de Dukascopy y los de tu bróker NO son los mismos —distinto feed, distintos
        cierres, distintas mechas— y antes se pisaban vela a vela sin dejar rastro.
        Una estrategia medida sobre media serie de cada sitio da un número que no
        corresponde a ningún mercado real.
        """
        if not rows:
            return 0
        sym, t, f = symbol.upper(), tf.upper(), (fuente or "desconocida").lower()
        before = self.count(sym, t)
        self.db.executemany(
            "INSERT OR REPLACE INTO candles(symbol,tf,ts,open,high,low,close,volume,fuente) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            [(sym, t, int(r["ts"]), r["open"], r["high"], r["low"], r["close"],
              r.get("volume") or 0, f) for r in rows])
        self.db.commit()
        return self.count(sym, t) - before

    def fuentes(self, symbol: str, tf: str) -> list[dict]:
        """Qué fuentes hay mezcladas en esa serie, y cuántas velas pone cada una."""
        rows = self.db.execute(
            "SELECT COALESCE(NULLIF(fuente,''),'desconocida'), COUNT(*) FROM candles "
            "WHERE symbol=? AND tf=? GROUP BY 1 ORDER BY 2 DESC",
            (symbol.upper(), tf.upper())).fetchall()
        return [{"fuente": r[0], "velas": int(r[1])} for r in rows]

    def mezclada(self, symbol: str, tf: str) -> bool:
        return len(self.fuentes(symbol, tf)) > 1

    def count(self, symbol: str, tf: str) -> int:
        return int(self.db.execute(
            "SELECT COUNT(*) FROM candles WHERE symbol=? AND tf=?",
            (symbol.upper(), tf.upper())).fetchone()[0])

    def series(self, symbol: str, tf: str, limit: int = 200000,
               fuente: str = "") -> list[Candle]:
        """Las velas de una serie. Con `fuente`, SOLO las de esa procedencia.

        Sin filtrar devuelve todo lo que haya, que es lo correcto cuando hay una
        sola fuente. Cuando hay varias, quien mida debe elegir una: `mezclada()` lo
        dice, y medir sobre la mezcla es medir sobre un mercado que no existió.
        """
        if fuente:
            rows = self.db.execute(
                "SELECT ts,open,high,low,close,volume FROM candles "
                "WHERE symbol=? AND tf=? AND COALESCE(NULLIF(fuente,''),'desconocida')=? "
                "ORDER BY ts LIMIT ?",
                (symbol.upper(), tf.upper(), fuente.lower(), int(limit))).fetchall()
            return [Candle(ts=r[0], open=r[1], high=r[2], low=r[3], close=r[4],
                           volume=r[5] or 0) for r in rows]
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
