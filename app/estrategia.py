"""La estrategia que TÚ enseñas, y que va creciendo.

Esto es lo que faltaba: un sitio donde ir añadiendo la estrategia a trozos, sin
que lo de ayer se pierda cuando escribes lo de hoy. No es el playbook —el playbook
lo reescribe el Arquitecto o lo genera la medición— ni son las reglas de la casa,
que son restricciones. Esto es la estrategia en sí: qué se busca y cómo se entra.

Tres decisiones que hacen que sirva para enseñar y no solo para guardar:

1. **Se AÑADE, no se reescribe.** Cada cosa que enseñas queda con su fecha y se
   queda. Si mañana explicas mejor una parte, la nueva se suma; la vieja no
   desaparece sin que tú la retires. Una estrategia que se sobrescribe sola es una
   que no puedes auditar cuando algo empieza a fallar.

2. **Lo que dices tú y lo que midió la máquina van SEPARADOS.** El sistema puede
   añadir observaciones de sus resultados, pero en su propia sección y marcadas
   como tales. Si se mezclaran, en dos semanas no podrías distinguir lo que
   enseñaste de lo que dedujo — y a la hora de corregir, eso es justo lo que hace
   falta saber.

3. **Vive también en tu Obsidian.** Puedes enseñarle desde la app o escribiendo en
   la nota; lo que esté en el vault se lee igual. Donde te resulte natural.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

log = logging.getLogger("estrategia")

NOMBRE_NOTA = "Estrategia"
# Etiqueta para enseñarle desde cualquier nota del vault, no solo desde la suya.
TAG = "hydra-estrategia"
MAX_CHARS = 12000        # cabe una estrategia larga; pasado esto se avisa, no se corta


def _archivo():
    from .config import settings
    return settings.data_path / "estrategia.json"


def _hoy() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")


def _leer() -> dict:
    try:
        d = json.loads(_archivo().read_text(encoding="utf-8"))
        if isinstance(d, dict):
            d.setdefault("nombre", "")
            d.setdefault("piezas", [])
            d.setdefault("observaciones", [])
            return d
    except Exception:  # noqa: BLE001
        pass
    return {"nombre": "", "piezas": [], "observaciones": []}


def _guardar(d: dict) -> None:
    p = _archivo()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def estado() -> dict:
    d = _leer()
    vivas = [x for x in d["piezas"]
             if not x.get("retirada") and not x.get("pendiente")]
    pend = [x for x in d["piezas"] if x.get("pendiente") and not x.get("retirada")]
    return {"nombre": d["nombre"], "n_piezas": len(vivas),
            "n_pendientes": len(pend),
            "n_retiradas": sum(1 for x in d["piezas"] if x.get("retirada")),
            "n_observaciones": len(d["observaciones"]),
            "chars": len(texto()), "max_chars": MAX_CHARS,
            "piezas": d["piezas"], "observaciones": d["observaciones"][-20:]}


def nombrar(nombre: str) -> dict:
    d = _leer()
    d["nombre"] = str(nombre or "").strip()[:60]
    _guardar(d)
    return estado()


def enseñar(texto_nuevo: str, titulo: str = "", pendiente: bool = False,
            fuente: str = "") -> dict:
    """Añade una pieza a la estrategia. Nunca pisa lo anterior.

    `pendiente=True` la deja esperando tu visto bueno y NO opera mientras tanto. Es
    lo que se usa con lo que destila la máquina de tus manuales: un resumen
    automático que entra solo acaba siendo política de trading que nadie escribió,
    y para cuando se nota ya lleva semanas operando.
    """
    t = str(texto_nuevo or "").strip()
    if not t:
        return {"ok": False, "error": "no me enseñaste nada"}
    d = _leer()
    d["piezas"].append({"ts": _hoy(), "titulo": str(titulo or "").strip()[:80],
                        "texto": t[:6000], "retirada": False,
                        "pendiente": bool(pendiente), "fuente": str(fuente or "")[:200]})
    _guardar(d)
    if not pendiente:
        _a_vault()
    return {"ok": True, **estado()}


def aprobar(indice: int) -> dict:
    """Da por buena una pieza destilada: a partir de ahí sí opera."""
    d = _leer()
    if not (0 <= indice < len(d["piezas"])):
        return {"ok": False, "error": "esa pieza no existe"}
    d["piezas"][indice]["pendiente"] = False
    d["piezas"][indice]["aprobada_ts"] = _hoy()
    _guardar(d)
    _a_vault()
    return {"ok": True, **estado()}


def retirar(indice: int, motivo: str = "") -> dict:
    """Marca una pieza como retirada. No se borra: se marca.

    Borrar dejaría la estrategia sin memoria de por qué cambió, y cuando algo
    empeora lo primero que hace falta saber es qué se quitó y cuándo.
    """
    d = _leer()
    if not (0 <= indice < len(d["piezas"])):
        return {"ok": False, "error": "esa pieza no existe"}
    d["piezas"][indice]["retirada"] = True
    d["piezas"][indice]["retirada_ts"] = _hoy()
    d["piezas"][indice]["motivo"] = str(motivo or "").strip()[:200]
    _guardar(d)
    _a_vault()
    return {"ok": True, **estado()}


def observar(texto_obs: str, evidencia: str = "") -> dict:
    """Lo que la MÁQUINA aprendió de los resultados. Sección aparte, a propósito."""
    t = str(texto_obs or "").strip()
    if not t:
        return {"ok": False, "error": "observación vacía"}
    d = _leer()
    d["observaciones"].append({"ts": _hoy(), "texto": t[:1200],
                               "evidencia": str(evidencia or "")[:600]})
    d["observaciones"] = d["observaciones"][-60:]
    _guardar(d)
    _a_vault()
    return {"ok": True, **estado()}


def _del_vault() -> list[dict]:
    """Lo que le hayas enseñado escribiendo en Obsidian en vez de en la app."""
    try:
        from . import vault
    except Exception:  # noqa: BLE001
        return []
    fuera = []
    try:
        for p in vault._tuyas(TAG):
            cuerpo = vault._sin_frontmatter(vault._leer(p)).strip()
            if cuerpo:
                fuera.append({"titulo": p.stem, "texto": cuerpo[:6000],
                              "ts": "(nota de Obsidian)", "retirada": False})
    except Exception as exc:  # noqa: BLE001
        log.info("no pude leer notas de estrategia: %s", str(exc)[:100])
    return fuera


def texto(incluir_observaciones: bool = True) -> str:
    """La estrategia entera, en el orden en que se enseñó.

    Devuelve "" cuando no hay nada. Un encabezado con una estrategia vacía debajo
    le diría al modelo que la estrategia es no hacer nada, que es una instrucción
    muy distinta de "todavía no te he enseñado".
    """
    d = _leer()
    piezas = [x for x in d["piezas"]
              if not x.get("retirada") and not x.get("pendiente")] + _del_vault()
    if not piezas:
        return ""
    out = []
    if d["nombre"]:
        out.append(f"# Estrategia: {d['nombre']}")
        out.append("")
    for i, x in enumerate(piezas, 1):
        cab = f"## {i}. {x['titulo']}" if x.get("titulo") else f"## {i}."
        out.append(f"{cab}   <sub>{x['ts']}</sub>")
        out.append(x["texto"].strip())
        out.append("")
    if incluir_observaciones and d["observaciones"]:
        out.append("## Observaciones medidas (las pone el sistema, no tú)")
        out.append("")
        out.append("No son reglas: son resultados. Están aquí para que decidas si "
                   "alguna merece convertirse en regla — esa decisión es tuya.")
        out.append("")
        for o in d["observaciones"][-12:]:
            ev = f" — {o['evidencia']}" if o.get("evidencia") else ""
            out.append(f"- <sub>{o['ts']}</sub> {o['texto']}{ev}")
    t = "\n".join(out).strip()
    if len(t) > MAX_CHARS:
        t = (t[:MAX_CHARS].rsplit("\n", 1)[0]
             + f"\n\n[...la estrategia pasa de {MAX_CHARS} caracteres y se cortó aquí. "
               "Retira las piezas que ya no uses en vez de dejar que se corte sola.]")
    return t


def _a_vault() -> None:
    """Deja la estrategia escrita en Obsidian, para poder leerla y editarla ahí."""
    try:
        from . import vault
        t = texto()
        if t:
            vault.note("Estrategia", NOMBRE_NOTA, t, tags=["estrategia", "hydra"])
    except Exception as exc:  # noqa: BLE001
        log.info("no pude escribir la estrategia en el vault: %s", str(exc)[:100])


def importar_md(md: str, titulo: str = "importado") -> dict:
    """Pega un documento entero de una vez (por ejemplo, lo que ya tengas escrito)."""
    return enseñar(md, titulo)
