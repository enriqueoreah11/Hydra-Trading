"""Lo que va aprendiendo de sus propios resultados, para no repetir el error.

El sistema ya se auto-criticaba una vez al día y evolucionaba el playbook con esa
crítica. Pero eso es un canal lento y con pérdidas: toda una jornada comprimida en
un texto que otro agente reescribe. Lo que NO había era memoria de resultados que
llegara a la siguiente decisión — el analista abría cada ciclo sin saber que ese
mismo setup, en ese mismo símbolo, ya le había costado dinero seis veces.

Aquí está la decisión de diseño que importa: las lecciones **no se escriben, se
calculan**. Cada vez se derivan del historial real de operaciones cerradas. Si se
guardaran como frases —«el oro no funciona por la mañana»— quedarían escritas para
siempre, sin manera de saber si siguen siendo verdad, y la memoria se llenaría de
creencias caducadas que nadie puede refutar. Derivándolas, una lección que deja de
cumplirse desaparece sola en el siguiente cálculo.

Y el peligro de verdad, el que hace daño de forma silenciosa: **convertir el ruido
en regla**. Con seis operaciones se puede «aprender» cualquier cosa. Tres pérdidas
seguidas en el oro no son una lección, son tres pérdidas seguidas. Por eso:

- Por debajo de la muestra mínima no se dice nada. Se dice que falta muestra, que
  es un dato distinto de «aquí no hay nada».
- Cada lección viaja SIEMPRE con su n y con la probabilidad de que sea casualidad,
  calculada por bootstrap sobre los resultados reales. Sin ese número, «pierde
  dinero» y «ha perdido dinero seis veces de nueve» se leen igual, y no lo son.
- Nada se afirma como ley. Son evidencias con tamaño de muestra.
"""
from __future__ import annotations

import datetime as dt
import logging
import random

log = logging.getLogger("lecciones")

# Por debajo de esto no hay nada que decir: se informa de que falta muestra.
MIN_OPS = 8
# A partir de aquí la evidencia empieza a pesar. Entre una cosa y otra se enseña,
# pero marcado como preliminar.
MIN_OPS_FIABLE = 20
# Un post-mortem suelto es un mal día. Repetido tres veces es un patrón.
MIN_POSTMORTEMS = 3
# Por encima de esta probabilidad de casualidad no se llama lección a nada.
MAX_PROB_SUERTE = 0.20

_BOOTSTRAP = 2000
# Semilla fija: los mismos datos tienen que dar siempre la misma lectura. Una
# memoria que cambia de opinión al recargar no es una memoria.
SEMILLA = 20260805

AVISO = ("son evidencias con su muestra, no leyes; sirven para rebajar la confianza "
         "o pedir más confluencia, nunca para operar en contra por sí solas")


def _neto(r: dict) -> float | None:
    try:
        v = r.get("pnl")
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def sesion(ts: float) -> str:
    """En qué sesión se abrió. Las horas son UTC, como todo lo demás del sistema."""
    try:
        h = dt.datetime.fromtimestamp(float(ts), dt.timezone.utc).hour
    except (TypeError, ValueError, OSError, OverflowError):
        return "?"
    if 13 <= h < 17:
        return "solape Londres-NY"
    if 7 <= h < 13:
        return "Londres"
    if 17 <= h < 21:
        return "tarde NY"
    return "Asia/madrugada"


def dia(ts: float) -> str:
    nombres = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    try:
        return nombres[dt.datetime.fromtimestamp(float(ts), dt.timezone.utc).weekday()]
    except (TypeError, ValueError, OSError, OverflowError, IndexError):
        return "?"


def prob_suerte(netos: list[float]) -> float:
    """Probabilidad de que un resultado así de bueno o malo salga por casualidad.

    Bootstrap sobre los resultados reales: se re-muestrea la misma cantidad de
    operaciones con reemplazo y se mira cuántas veces el signo se da la vuelta. No
    supone que las ganancias sigan ninguna campana —no la siguen: son colas
    largas— y usa exactamente los números que hubo.
    """
    n = len(netos)
    if n < 2:
        return 1.0
    total = sum(netos)
    if total == 0:
        return 1.0
    rnd = random.Random(SEMILLA)
    contra = 0
    for _ in range(_BOOTSTRAP):
        s = sum(netos[rnd.randrange(n)] for _ in range(n))
        # cuántas veces el remuestreo contradice el signo observado
        if (total < 0 and s >= 0) or (total > 0 and s <= 0):
            contra += 1
    return round(contra / _BOOTSTRAP, 3)


def evaluar(netos: list[float]) -> dict:
    """Las cuentas de un grupo, con su nivel de confianza declarado."""
    n = len(netos)
    total = round(sum(netos), 2)
    wins = sum(1 for v in netos if v > 0)
    out = {"n": n, "net": total,
           "win_pct": round(wins / n * 100, 1) if n else None,
           "avg": round(total / n, 2) if n else None,
           "prob_suerte": None, "fuerza": "sin muestra"}
    if n < MIN_OPS:
        out["nota"] = (f"solo {n} operaciones: hace falta más muestra para saber si "
                       "esto significa algo")
        return out
    out["prob_suerte"] = prob_suerte(netos)
    if out["prob_suerte"] > MAX_PROB_SUERTE:
        out["fuerza"] = "no concluyente"
        out["nota"] = (f"{n} operaciones, pero un {out['prob_suerte']*100:.0f}% de "
                       "probabilidad de que sea casualidad")
    elif n < MIN_OPS_FIABLE:
        out["fuerza"] = "preliminar"
        out["nota"] = f"{n} operaciones: apunta a algo, todavía no está asentado"
    else:
        out["fuerza"] = "asentada"
        out["nota"] = f"{n} operaciones"
    return out


def _grupos(rows: list[dict], clave) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for r in rows:
        if r.get("state") != "closed":
            continue
        v = _neto(r)
        if v is None:
            continue
        k = clave(r)
        if k in (None, "", "?"):
            continue
        out.setdefault(str(k), []).append(v)
    return out


# Cada dimensión responde a una pregunta distinta que el analista puede usar.
DIMENSIONES = (
    ("símbolo", lambda r: r.get("symbol")),
    ("estrategia", lambda r: r.get("strategy")),
    ("dirección", lambda r: r.get("side")),
    ("sesión", lambda r: sesion(r.get("ts"))),
    ("día", lambda r: dia(r.get("ts"))),
)


def calcular(rows: list[dict], symbol: str = "") -> dict:
    """Deriva las lecciones del historial. Con `symbol`, solo las de ese símbolo.

    Al filtrar por símbolo se deja fuera la dimensión "símbolo": comparar el oro
    consigo mismo no dice nada, y ocuparía el sitio de lo que sí informa.
    """
    cerradas = [r for r in rows if r.get("state") == "closed" and _neto(r) is not None]
    if symbol:
        sym = symbol.upper()
        cerradas = [r for r in cerradas if str(r.get("symbol", "")).upper() == sym]

    lecciones, flojas = [], []
    for nombre, clave in DIMENSIONES:
        if symbol and nombre == "símbolo":
            continue
        for k, netos in _grupos(cerradas, clave).items():
            ev = evaluar(netos)
            item = {"dimension": nombre, "valor": k, **ev}
            if ev["fuerza"] in ("asentada", "preliminar"):
                lecciones.append(item)
            else:
                flojas.append(item)
    # lo que más dinero mueve primero: es lo que hay que mirar antes
    lecciones.sort(key=lambda x: (-abs(x["net"]), x["dimension"]))
    flojas.sort(key=lambda x: (-x["n"], x["dimension"]))
    return {"symbol": symbol.upper() if symbol else "",
            "n_cerradas": len(cerradas), "lecciones": lecciones,
            "sin_muestra": flojas, "aviso": AVISO}


def de_postmortems(counts: list[dict]) -> list[dict]:
    """Errores ya diagnosticados que se repiten. Uno suelto es un mal día."""
    out = []
    for c in counts or []:
        try:
            n = int(c.get("count") or 0)
        except (TypeError, ValueError):
            continue
        if n >= MIN_POSTMORTEMS:
            out.append({"categoria": str(c.get("category") or "?"), "veces": n})
    return sorted(out, key=lambda x: -x["veces"])


def _frase(x: dict) -> str:
    signo = "pierde" if x["net"] < 0 else "gana"
    txt = (f"{x['dimension']} «{x['valor']}»: {signo} {abs(x['net']):.2f} en {x['n']} "
           f"operaciones ({x['win_pct']}% acierto, media {x['avg']:+.2f})")
    if x.get("prob_suerte") is not None:
        txt += f", probabilidad de casualidad {x['prob_suerte']*100:.0f}%"
    if x["fuerza"] == "preliminar":
        txt += " — PRELIMINAR"
    return txt


def texto(datos: dict, postmortems: list[dict] | None = None, max_items: int = 6) -> str:
    """Lo aprendido, en prosa, para el prompt del analista. Vacío si no hay nada.

    Un encabezado seguido de nada le diría al modelo que se miró y no se encontró,
    y lo que pasa casi siempre al principio es que todavía no hay con qué mirar.
    """
    if not datos:
        return ""
    lineas = [_frase(x) for x in (datos.get("lecciones") or [])[:max_items]]
    for p in (postmortems or []):
        lineas.append(f"error ya diagnosticado «{p['categoria']}»: {p['veces']} veces")
    if not lineas:
        return ""
    cab = f"Lo aprendido de {datos.get('n_cerradas', 0)} operaciones cerradas"
    if datos.get("symbol"):
        cab += f" de {datos['symbol']}"
    return (f"{cab} — {AVISO}:\n" + "\n".join(f"- {x}" for x in lineas))


# ------------------------------------------------------------ a la memoria

def guardar(datos: dict, postmortems: list[dict] | None = None) -> int:
    """Escribe lo aprendido en el vault, para poder auditarlo en Obsidian.

    Se reescribe entera en cada cálculo, a propósito: la nota tiene que reflejar la
    evidencia de HOY. Si se fuera acumulando, acabaría siendo un montón de frases
    contradictorias de distintas épocas sin forma de saber cuál sigue en pie.
    """
    from . import vault

    lec = datos.get("lecciones") or []
    flojas = datos.get("sin_muestra") or []
    cuerpo = [f"De **{datos.get('n_cerradas', 0)}** operaciones cerradas.",
              "", f"> {AVISO}", ""]
    if lec:
        cuerpo.append("## Con evidencia")
        cuerpo += [f"- {_frase(x)}" for x in lec]
    else:
        cuerpo.append("## Con evidencia\n\nTodavía ninguna: falta historial.")
    if postmortems:
        cuerpo.append("\n## Errores que se repiten")
        cuerpo += [f"- **{p['categoria']}** · {p['veces']} veces" for p in postmortems]
    if flojas:
        cuerpo.append("\n## Sin muestra suficiente")
        cuerpo.append("Esto NO son lecciones todavía. Se listan para que se vea qué "
                      "se está midiendo y cuánto falta.")
        cuerpo += [f"- {x['dimension']} «{x['valor']}»: {x['n']} ops, "
                   f"{x['net']:+.2f} — {x.get('nota', '')}" for x in flojas[:20]]
    try:
        vault.note("Aprendizajes", "Lo que funciona y lo que no",
                   "\n".join(cuerpo), tags=["aprendizajes", "hydra"])
    except Exception as exc:  # noqa: BLE001
        log.info("no pude guardar los aprendizajes: %s", str(exc)[:120])
        return 0
    return len(lec)
