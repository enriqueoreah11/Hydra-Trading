"""Explica qué hace una estrategia leyendo la configuración de su .algo.

Aviso honesto sobre el alcance: del .algo solo salen los PARÁMETROS, no el código.
La lógica va en una DLL de .NET compilada. Así que esto es una lectura informada
de la configuración, no una traducción del código — y el prompt obliga a decirlo
y a separar lo que se deduce con certeza de lo que se supone.

Sirve para lo que pidió el usuario: comprobar si el sistema entiende de verdad la
estrategia antes de intentar replicarla.
"""
from __future__ import annotations

from . import llm

SYSTEM = """Eres un ingeniero de trading que audita la configuración de un cBot de
cTrader. Te doy sus PARÁMETROS (nombre técnico, nombre visible, tipo, valor por
defecto, rango y grupo). NO tienes el código fuente: la lógica está compilada.

Escribe en español, en markdown, un análisis que sirva para que el DUEÑO del bot
compruebe si lo has entendido. Estructura obligatoria:

## Qué hace, en una frase
## Cómo decide entrar
Los filtros y confluencias que se deducen de los parámetros, con sus valores.
## Cómo gestiona el riesgo
Lotaje, stop loss, take profit, trailing, parciales, límites diarios. Cita
nombres y valores concretos.
## Cuándo NO opera
Bloqueos: noticias, spread, sesiones, horarios, límites, régimen.
## Lo que NO puedo saber de los parámetros
Sé explícito. Todo lo que sea el ALGORITMO en sí (cómo se puntúa cada
confluencia, en qué orden se evalúan, cómo se combinan) no está aquí: dilo.
## Riesgos y contradicciones que veo
Parámetros que se pisan, valores peligrosos, cosas activadas que quizá no
deberían. Sé concreto y crítico.
## Para replicarlo fuera de cTrader
Qué se podría reproducir y qué es IMPOSIBLE, y por qué.

Reglas:
- No inventes comportamientos. Si un parámetro no deja claro qué hace, dilo.
- Distingue siempre entre "esto lo dice el parámetro" y "esto supongo".
- Si un parámetro lee objetos dibujados a mano en el gráfico, avisa de que eso no
  existe fuera del escritorio de cTrader y ninguna réplica lo puede igualar.
- Nada de relleno ni elogios. El dueño necesita detectar si te has equivocado.
"""


def _compact(parsed: dict) -> str:
    """Los parámetros en texto denso: cabe en un prompt sin inflarlo."""
    lines: list[str] = []
    for g in parsed.get("groups") or []:
        lines.append(f"\n### {g['group']}")
        for p in g["params"]:
            bits = [f"{p['name']}"]
            if p.get("label") and p["label"] != p["name"]:
                bits.append(f'"{p["label"]}"')
            bits.append(f"[{p.get('type')}]")
            if p.get("enum"):
                names = list(p["enum"])
                cur = p.get("default")
                pick = names[cur] if isinstance(cur, int) and cur < len(names) else cur
                bits.append(f"= {pick} (opciones: {', '.join(names)})")
            else:
                bits.append(f"= {p.get('default')}")
            lo, hi = p.get("min"), p.get("max")
            if lo is not None and hi is not None and isinstance(hi, (int, float)) and hi < 1e300:
                bits.append(f"rango {lo}..{hi}")
            if p.get("chart_bound"):
                bits.append("<-- LEE DIBUJOS DEL GRÁFICO")
            lines.append("- " + " ".join(str(b) for b in bits))
    return "\n".join(lines)


async def explain(parsed: dict) -> str:
    chart = parsed.get("chart_bound") or []
    user = (
        f"# Bot: {parsed.get('name')}\n"
        f"Tipo: {parsed.get('kind')} · API {parsed.get('api_version')} · "
        f"{parsed.get('framework')} · compilado {parsed.get('built_at')}\n"
        f"Parámetros: {parsed.get('n_params')} en {parsed.get('n_groups')} grupos\n"
        + (f"\nATADOS AL GRÁFICO (dibujos a mano): {', '.join(chart)}\n" if chart else "")
        + "\n## Parámetros\n" + _compact(parsed)
        + "\n\nEscribe el análisis siguiendo la estructura exacta."
    )
    out = await llm.ask(SYSTEM, user, max_tokens=6000, role="architect")
    assert isinstance(out, str)
    return out
