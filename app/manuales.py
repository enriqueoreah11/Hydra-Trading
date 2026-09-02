"""Tus manuales del curso, leídos desde la carpeta donde los tienes.

Esto corre en TU Mac, así que puede leer tu iCloud directamente: no hay que subir
nada ni copiar nada a ningún sitio. Se apunta la carpeta y se lee de ahí.

Lo que NO se hace, y es la decisión importante: volcar los manuales enteros en el
prompt. Tres meses de curso son cientos de páginas de contexto, ejemplos, teoría y
motivación. Metido tal cual, eso no enseña una estrategia — la entierra: el modelo
recibe cien párrafos sobre psicología del trading y tres frases con las condiciones
de entrada, y no tiene forma de saber cuáles importan.

Lo que se hace es DESTILAR: sacar del manual las condiciones concretas y
comprobables, cada una con la frase del manual que la sostiene. Una regla sin cita
se tira. Y lo destilado no entra a operar hasta que tú lo apruebas, porque un
resumen automático que se cuela sin revisar acaba siendo política de trading que
nadie escribió.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger("manuales")

EXTENSIONES = {".pdf", ".md", ".markdown", ".txt", ".rtf", ".docx"}
MAX_BYTES = 40 * 1024 * 1024
# Trozo que se manda a destilar de una vez. Ni tan corto que parta una regla por la
# mitad, ni tan largo que el modelo tenga que elegir qué mirar.
TROZO = 12000
SOLAPE = 800          # para que una regla a caballo entre dos trozos no se pierda


def carpeta() -> Path | None:
    from .config import settings
    raw = (settings.estrategia_dir or "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser()
    return p if p.is_dir() else None


def estado() -> dict:
    from .config import settings
    raw = (settings.estrategia_dir or "").strip()
    c = carpeta()
    if c is not None:
        return {"ok": True, "carpeta": str(c), "motivo": ""}
    if raw:
        return {"ok": False, "carpeta": raw,
                "motivo": f"no encuentro «{raw}». Si está en iCloud, ábrela una vez en "
                          "Finder para que se descargue: los archivos que solo están "
                          "en la nube no se pueden leer"}
    return {"ok": False, "carpeta": "",
            "motivo": "sin configurar: dime en qué carpeta tienes los manuales"}


def listar() -> list[dict]:
    """Qué hay en la carpeta, sin leer nada todavía."""
    c = carpeta()
    if c is None:
        return []
    out = []
    for p in sorted(c.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in EXTENSIONES:
            continue
        try:
            n = p.stat().st_size
        except OSError:
            continue
        out.append({"nombre": p.name, "rel": str(p.relative_to(c)),
                    "tipo": p.suffix.lower().lstrip("."), "bytes": n,
                    "grande": n > MAX_BYTES})
    return out


def _texto_pdf(p: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        r = PdfReader(str(p))
        return "\n\n".join((pg.extract_text() or "") for pg in r.pages)
    except Exception as exc:  # noqa: BLE001
        log.info("no pude leer %s: %s", p.name, str(exc)[:100])
        return ""


def _texto_docx(p: Path) -> str:
    """Un .docx es un zip con XML dentro: se lee sin librería extra."""
    import xml.etree.ElementTree as ET
    import zipfile
    try:
        with zipfile.ZipFile(p) as z:
            xml = z.read("word/document.xml")
    except Exception:  # noqa: BLE001
        return ""
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError:
        return ""
    partes = []
    for par in raiz.iter(f"{ns}p"):
        txt = "".join(t.text or "" for t in par.iter(f"{ns}t"))
        if txt.strip():
            partes.append(txt)
    return "\n".join(partes)


def extraer(rel: str) -> dict:
    """El texto de un manual. Dice por qué si no puede."""
    c = carpeta()
    if c is None:
        return {"ok": False, "error": estado()["motivo"], "texto": ""}
    p = (c / rel).resolve()
    try:
        dentro = p.is_relative_to(c.resolve())
    except (OSError, ValueError):
        dentro = False
    if not dentro or not p.is_file():
        return {"ok": False, "error": "ese archivo no está en la carpeta", "texto": ""}
    if p.stat().st_size > MAX_BYTES:
        return {"ok": False, "texto": "",
                "error": f"{p.name} pesa más de {MAX_BYTES // 1024 // 1024} MB"}
    ext = p.suffix.lower()
    if ext == ".pdf":
        t = _texto_pdf(p)
    elif ext == ".docx":
        t = _texto_docx(p)
    else:
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {"ok": False, "error": str(exc)[:120], "texto": ""}
    t = re.sub(r"\n{4,}", "\n\n\n", t or "").strip()
    if not t:
        # Un PDF escaneado es una imagen: no tiene texto que extraer, y decir
        # "vacío" haría pensar que el archivo está mal.
        return {"ok": False, "texto": "",
                "error": f"{p.name} no tiene texto extraíble. Si es un PDF escaneado "
                         "(fotos de páginas), hace falta pasarle un OCR antes"}
    return {"ok": True, "texto": t, "chars": len(t), "nombre": p.name}


def trozos(texto: str, tam: int = TROZO, solape: int = SOLAPE) -> list[str]:
    """Parte el manual en trozos con solape.

    El solape no es un detalle: una condición de entrada que caiga justo en el
    corte se perdería entera, y no habría forma de notarlo — el resultado sería una
    estrategia a la que le falta una regla, que es peor que una que falta entera.
    """
    t = (texto or "").strip()
    if not t:
        return []
    if len(t) <= tam:
        return [t]
    out, i = [], 0
    while i < len(t):
        corte = t[i:i + tam]
        # cortar por párrafo cuando se pueda: partir una frase confunde al destilador
        if i + tam < len(t):
            j = corte.rfind("\n\n")
            if j > tam // 2:
                corte = corte[:j]
        out.append(corte.strip())
        i += max(1, len(corte) - solape)
    return [x for x in out if x]
