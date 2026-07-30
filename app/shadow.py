"""Lee los CSV que escriben tus bots (el registro «shadow») sin abrirlos a mano.

Un cBot que anota cada análisis en un CSV es un diario perfecto… que nadie lee,
porque hay que ir a buscar el archivo. Esto lo recoge solo: recuerda por qué byte
se quedó en cada fichero y solo lee lo NUEVO, así puede pasar cada dos minutos sin
releer megas ni duplicar filas.

Decisiones que importan:
- se guarda el desplazamiento en BYTES, no el número de filas: el bot escribe al
  final del archivo y así no hay que volver a parsear lo ya leído.
- si el archivo ENCOGE (el bot lo rotó o lo empezó de cero), se vuelve a leer
  desde el principio en vez de quedarse mudo para siempre.
- el encabezado se guarda por archivo: cuando se leen líneas del medio ya no está.
- no se interpreta nada aquí. Cada fila se convierte en un dict {columna: valor} y
  el mapeo a columnas conocidas lo hace quien ya sabe hacerlo (_store_ctx).
"""
from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path

log = logging.getLogger("shadow")

# Extensiones que se consideran registro. El .txt entra porque hay bots que
# escriben CSV con esa extensión.
SUFFIXES = (".csv", ".txt")
MAX_ROWS_PER_PASS = 4000        # tope por pasada: un CSV enorme no bloquea el arranque


def find_logs(folder: Path) -> list[Path]:
    """Los archivos de registro de una carpeta, los más recientes primero."""
    if not folder or not folder.is_dir():
        return []
    out = [f for f in folder.rglob("*")
           if f.is_file() and f.suffix.lower() in SUFFIXES]
    out.sort(key=lambda f: -f.stat().st_mtime)
    return out


def _num(v: str):
    """'1.2345' -> float, '17' -> int, lo demás se queda como texto."""
    s = (v or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return s


def read_new(path: Path, state: dict) -> tuple[list[dict], dict]:
    """Devuelve (filas nuevas, estado actualizado) de un archivo.

    `state` es {"offset": bytes leídos, "header": [...], "rows": total}.
    """
    st = dict(state or {})
    size = path.stat().st_size
    off = int(st.get("offset") or 0)
    if size < off:                      # el archivo se rotó: se relee entero
        log.info("shadow: %s encogió (%s < %s), releo desde el principio",
                 path.name, size, off)
        off, st = 0, {"rows": st.get("rows") or 0}
    if size == off:
        return [], st

    with path.open("rb") as fh:
        fh.seek(off)
        chunk = fh.read()
    # una línea a medio escribir se deja para la próxima pasada: si no, se
    # importaría una fila truncada y eso ya no se puede arreglar (es append-only)
    cut = chunk.rfind(b"\n")
    if cut < 0:
        return [], st
    usable, off = chunk[:cut + 1], off + cut + 1
    text = usable.decode("utf-8", "replace")

    header = st.get("header")
    if not header:
        first = text.split("\n", 1)
        try:
            header = next(csv.reader(io.StringIO(first[0])))
        except StopIteration:
            return [], st
        header = [h.strip() for h in header]
        text = first[1] if len(first) > 1 else ""
        st["header"] = header

    rows: list[dict] = []
    for parts in csv.reader(io.StringIO(text)):
        if not parts or not any(p.strip() for p in parts):
            continue
        if parts[0].strip() == header[0]:      # el encabezado repetido tras rotar
            continue
        row = {header[i]: _num(v) for i, v in enumerate(parts) if i < len(header)}
        if len(parts) > len(header):           # columnas de más: no se tiran
            row["extra"] = [v for v in parts[len(header):]]
        rows.append(row)
        if len(rows) >= MAX_ROWS_PER_PASS:
            break

    st["offset"] = off
    st["rows"] = int(st.get("rows") or 0) + len(rows)
    return rows, st


def load_state(f: Path) -> dict:
    try:
        return json.loads(f.read_text()) or {}
    except Exception:  # noqa: BLE001 - primera vez, o archivo tocado a mano
        return {}


def save_state(f: Path, state: dict) -> None:
    try:
        f.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    except Exception:  # noqa: BLE001 - perder el estado solo cuesta releer
        log.warning("shadow: no pude guardar el estado", exc_info=True)


def digest(rows: list[dict]) -> dict:
    """Resumen de lo importado, para la nota de Obsidian y para la pantalla."""
    by_sym: dict[str, int] = {}
    by_out: dict[str, int] = {}
    for r in rows:
        for k, v in r.items():
            kl = str(k).lower().replace(" ", "").replace("_", "")
            if kl in ("symbol", "symbolname", "instrument", "par", "pair") and v:
                by_sym[str(v).upper()] = by_sym.get(str(v).upper(), 0) + 1
            # "reason" NO cuenta aquí: es texto libre y llenaría el resumen de
            # frases distintas, que es justo lo que un resumen no debe hacer
            elif kl in ("outcome", "status", "result", "resultado") and v:
                by_out[str(v)] = by_out.get(str(v), 0) + 1
    return {"n": len(rows),
            "by_symbol": dict(sorted(by_sym.items(), key=lambda x: -x[1])[:12]),
            "by_outcome": dict(sorted(by_out.items(), key=lambda x: -x[1])[:12])}
