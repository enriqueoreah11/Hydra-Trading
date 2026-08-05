"""Memoria persistente en Obsidian.

Todo lo que Hydra aprende (revisiones diarias, cambios de playbook, hallazgos de
investigación, lo que dictes por voz) se guarda como notas Markdown con
frontmatter YAML, tags y [[wikilinks]].

Con `obsidian_vault_path` puesto, las notas se escriben DENTRO de tu vault y las
ves en Obsidian según se crean. Sin ella viven en data/vault y solo se ven
bajando el .zip — que es un diario, no una memoria.

La memoria va en los dos sentidos, y ahí está la diferencia:
- Hydra escribe siempre en su propia subcarpeta. Nunca toca el resto del vault.
- Hydra lee del resto del vault SOLO las notas que marques con #hydra. Sin esa
  etiqueta una nota tuya no entra en ningún prompt: lo que escribes es tuyo hasta
  que decides lo contrario, y esa decisión se toma nota a nota.
"""
from __future__ import annotations

import datetime as dt
import io
import re
import zipfile
from pathlib import Path

from .config import settings


def _obsidian() -> Path | None:
    """Tu vault, si está configurado Y existe de verdad.

    Se exige que la carpeta YA exista y no se crea nunca. Si se creara, una ruta
    mal escrita —o el vault en iCloud sin descargar todavía— haría una carpeta
    nueva en un sitio que Obsidian no conoce: las notas se escribirían sin dar
    error y no aparecerían por ningún lado.
    """
    raw = (settings.obsidian_vault_path or "").strip()
    if not raw:
        return None
    base = Path(raw).expanduser()
    return base if base.is_dir() else None


def estado() -> dict:
    """Dónde se escribe la memoria y por qué. Sin esto, «configurado» y
    «funcionando» se ven igual desde fuera."""
    raw = (settings.obsidian_vault_path or "").strip()
    base = _obsidian()
    if base is not None:
        return {"obsidian": True, "vault": str(base), "motivo": "",
                "destino": str(base / settings.obsidian_folder)}
    if raw:
        return {"obsidian": False, "vault": raw,
                "destino": str(settings.data_path / "vault"),
                "motivo": f"la carpeta «{raw}» no existe. ¿Está el vault en iCloud "
                          "sin descargar, o falta/sobra algo en la ruta?"}
    return {"obsidian": False, "vault": "",
            "destino": str(settings.data_path / "vault"),
            "motivo": "sin configurar: la memoria vive dentro de la app"}


def root() -> Path:
    """La carpeta de Hydra. Nunca es el vault entero: lo suyo va en lo suyo."""
    base = _obsidian()
    p = (base / settings.obsidian_folder) if base is not None \
        else settings.data_path / "vault"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _slug(title: str) -> str:
    s = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE).strip()
    return re.sub(r"[\s_]+", " ", s)[:80] or "nota"


def _today() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def _now_hm() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%H:%M")


def note(folder: str, title: str, body: str, tags: list[str] | None = None) -> Path:
    """Crea (o sobreescribe) una nota Markdown con frontmatter."""
    d = root() / folder
    d.mkdir(parents=True, exist_ok=True)
    fname = f"{_today()} {_slug(title)}.md"
    tag_line = ", ".join(t.strip("#") for t in (tags or []))
    fm = ("---\n"
          f"date: {_today()}\n"
          f"tags: [{tag_line}]\n"
          "origen: hydra\n"
          "---\n\n")
    path = d / fname
    path.write_text(fm + f"# {title}\n\n" + body.rstrip() + "\n", encoding="utf-8")
    _link_in_daily(folder, fname[:-3])
    return path


def _link_in_daily(folder: str, note_name: str) -> None:
    """Enlaza la nota nueva desde el diario del día (estilo daily note de Obsidian)."""
    d = root() / "Diario"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{_today()}.md"
    if not p.exists():
        p.write_text(f"---\ndate: {_today()}\ntags: [diario]\norigen: hydra\n---\n\n"
                     f"# Diario {_today()}\n\n", encoding="utf-8")
    with p.open("a", encoding="utf-8") as f:
        f.write(f"- {_now_hm()} UTC · [[{note_name}]] ({folder})\n")


def append_daily(line: str) -> None:
    """Apunta una línea suelta en el diario del día (sin nota aparte)."""
    _link_in_daily_raw(f"- {_now_hm()} UTC · {line}\n")


def _link_in_daily_raw(text: str) -> None:
    d = root() / "Diario"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{_today()}.md"
    if not p.exists():
        p.write_text(f"---\ndate: {_today()}\ntags: [diario]\norigen: hydra\n---\n\n"
                     f"# Diario {_today()}\n\n", encoding="utf-8")
    with p.open("a", encoding="utf-8") as f:
        f.write(text)


def list_notes() -> list[dict]:
    out = []
    r = root()
    for p in sorted(r.rglob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        rel = p.relative_to(r)
        out.append({"path": str(rel), "folder": str(rel.parent) if str(rel.parent) != "." else "",
                    "name": p.stem, "mtime": int(p.stat().st_mtime),
                    "size": p.stat().st_size})
    return out


def read_note(rel: str) -> str:
    r = root()
    p = (r / rel).resolve()
    if not str(p).startswith(str(r.resolve())) or not p.is_file():
        raise FileNotFoundError(rel)
    return p.read_text(encoding="utf-8")


# ------------------------------------------------------ leer (la otra mitad)

# Notas tuyas que valen como instrucción permanente para el analista. Etiqueta
# aparte de #hydra: una cosa es dejar que lea una nota y otra que la obedezca.
REGLAS_TAG = "hydra-reglas"
_MAX_REGLAS = 2000


def _sin_frontmatter(texto: str) -> str:
    if texto.startswith("---"):
        partes = texto.split("---", 2)
        if len(partes) == 3:
            return partes[2].lstrip()
    return texto


def _tags(texto: str) -> set[str]:
    """Etiquetas de la nota, del frontmatter y del cuerpo."""
    out = set()
    if texto.startswith("---"):
        cab = texto.split("---", 2)[1] if len(texto.split("---", 2)) == 3 else ""
        m = re.search(r"^tags:\s*\[(.*?)\]", cab, re.MULTILINE)
        if m:
            out |= {t.strip().strip("#").lower() for t in m.group(1).split(",") if t.strip()}
        for m in re.finditer(r"^\s*-\s*([\w/-]+)\s*$", cab, re.MULTILINE):
            out.add(m.group(1).strip("#").lower())
    out |= {m.group(1).lower() for m in re.finditer(r"#([\w/-]+)", _sin_frontmatter(texto))}
    return out


def _leer(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _mias() -> list[Path]:
    return sorted(root().rglob("*.md"))


def _tuyas(tag: str) -> list[Path]:
    """Notas TUYAS, de cualquier parte del vault, marcadas con la etiqueta.

    Sin etiqueta no se devuelve nada. Recorrer el vault entero y meterlo en un
    prompt mandaría a la nube cosas que no tienen nada que ver con esto.
    """
    base = _obsidian()
    if base is None:
        return []
    mio = root().resolve()
    fuera = []
    for p in base.rglob("*.md"):
        try:
            if p.resolve().is_relative_to(mio):
                continue
        except OSError:
            continue
        if tag.lower() in _tags(_leer(p)):
            fuera.append(p)
    return sorted(fuera)


def search(q: str = "", limit: int = 8) -> list[dict]:
    """Busca en la memoria: lo escrito por Hydra y lo tuyo marcado con #hydra."""
    tag = (settings.obsidian_tag or "hydra").strip().lstrip("#")
    terminos = [t for t in re.split(r"\s+", q.lower().strip()) if len(t) > 2]
    out = []
    for p, mio in [(x, True) for x in _mias()] + [(x, False) for x in _tuyas(tag)]:
        texto = _leer(p)
        if not texto:
            continue
        bajo = texto.lower()
        hits = sum(bajo.count(t) for t in terminos) if terminos else 0
        if terminos and not hits:
            continue
        out.append({"name": p.stem, "mia": mio, "hits": hits,
                    "path": p.name if not mio else str(p.relative_to(root())),
                    "extracto": _sin_frontmatter(texto)[:400].strip()})
    out.sort(key=lambda x: (-x["hits"], x["name"]))
    return out[:limit]


def instrucciones() -> str:
    """Tus reglas permanentes, las que escribes tú en Obsidian.

    Es la memoria funcionando de verdad: escribes una nota con #hydra-reglas y el
    analista la lee en el siguiente ciclo, sin tocar código ni reiniciar nada.
    """
    trozos = []
    for p in _tuyas(REGLAS_TAG) + [root() / "Reglas.md"]:
        if not p.is_file():
            continue
        cuerpo = _sin_frontmatter(_leer(p)).strip()
        if cuerpo:
            trozos.append(f"[{p.stem}]\n{cuerpo}")
    txt = "\n\n".join(trozos).strip()
    if len(txt) > _MAX_REGLAS:
        # Cortar en silencio dejaría media regla en pie, que es peor que ninguna.
        txt = (txt[:_MAX_REGLAS].rsplit("\n", 1)[0]
               + f"\n\n[...cortado: tus reglas pasan de {_MAX_REGLAS} caracteres; "
                 "recórtalas para que entren enteras]")
    return txt


def export_zip() -> bytes:
    buf = io.BytesIO()
    r = root()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in r.rglob("*.md"):
            z.write(p, arcname=str(Path("HydraVault") / p.relative_to(r)))
    return buf.getvalue()


def stats() -> dict:
    notes = list(root().rglob("*.md"))
    return {"notes": len(notes),
            "bytes": sum(p.stat().st_size for p in notes)}
