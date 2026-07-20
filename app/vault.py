"""Memoria persistente estilo Obsidian.

Todo lo que Hydra aprende (revisiones diarias, cambios de playbook, hallazgos
de investigación) se guarda como notas Markdown con frontmatter YAML, tags y
[[wikilinks]] en data/vault/ (volumen persistente). El vault completo se puede
descargar en .zip desde la UI y abrirse directamente en Obsidian.
"""
from __future__ import annotations

import datetime as dt
import io
import re
import zipfile
from pathlib import Path

from .config import settings


def root() -> Path:
    p = settings.data_path / "vault"
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
