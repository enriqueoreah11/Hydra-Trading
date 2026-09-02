"""Destilador — convierte un manual en condiciones de entrada comprobables.

Un manual de curso está escrito para que una persona entienda. Mezcla teoría,
psicología, ejemplos, motivación y —en alguna parte— las condiciones concretas por
las que se entra. Un modelo al que le das el manual entero recibe cien párrafos de
contexto y tres frases operables, y no tiene forma de saber cuáles son cuáles.

Este agente saca solo lo operable, y con una condición que es la que hace que se
pueda confiar: **cada regla lleva la frase del manual que la sostiene**. Una regla
sin cita se descarta al llegar. Sin eso, un destilado suena igual de bien tanto si
viene del manual como si se lo inventó el modelo — y a la hora de operar dinero,
esa diferencia lo es todo.
"""
from __future__ import annotations

import json

from .. import llm

REGLAS_SCHEMA = {
    "type": "object",
    "properties": {
        "reglas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tipo": {"type": "string",
                             "enum": ["entrada", "salida", "filtro", "gestion", "riesgo"]},
                    "regla": {"type": "string"},
                    "cita": {"type": "string"},
                    "comprobable": {"type": "boolean"},
                },
                "required": ["tipo", "regla", "cita", "comprobable"],
                "additionalProperties": False,
            },
        },
        "sin_reglas": {"type": "boolean"},
        "nota": {"type": "string"},
    },
    "required": ["reglas", "sin_reglas", "nota"],
    "additionalProperties": False,
}

SYSTEM = """Eres el AGENTE DESTILADOR. Recibes un trozo de un manual de trading y
sacas de el UNICAMENTE las reglas operables, tal y como estan en el texto.

Que cuenta como regla operable: algo que un programa podria comprobar mirando el
grafico y los datos. "Se entra cuando el precio vuelve a la zona y deja una vela de
rechazo con cierre por encima" es una regla. "Hay que ser paciente y esperar la
mejor oportunidad" no lo es: es un consejo, y meterlo como regla no aporta nada
comprobable y ademas ocupa el sitio de las que si lo son.

REGLA ABSOLUTA: cada regla lleva en "cita" la frase LITERAL del texto que la
sostiene, copiada tal cual. Si no puedes citar el texto, esa regla no va. No
completes lo que el manual da por sabido, no unifiques dos ideas en una, y no
traigas nada de lo que sepas de otros sitios: lo que se destila es ESTE manual. Un
destilado que anade una condicion razonable pero que no esta escrita produce una
estrategia que el autor no reconoceria, y nadie podria saber en que momento se
desvio.

Marca "comprobable": false cuando la regla este en el texto pero dependa de algo
que un programa no puede ver (un dibujo hecho a mano, "cuando el mercado se siente
pesado"). Se guarda igual, pero marcada — hace falta saber que existe aunque no se
pueda automatizar.

Si el trozo es teoria, historia, psicologia o ejemplos sin reglas, devuelve
sin_reglas=true y una nota de una linea diciendo de que iba. Es una respuesta
correcta y frecuente: la mayor parte de un curso no son reglas.

Escribe las reglas en espanol, cortas y en imperativo, sin numerar."""


async def destilar(trozo: str, fuente: str = "") -> dict:
    user = (f"## Manual: {fuente}\n\n## Trozo\n{trozo}\n\n"
            "Saca solo las reglas operables, cada una con su cita literal.")
    out = await llm.ask(SYSTEM, user, schema=REGLAS_SCHEMA, max_tokens=4000,
                        role="destilador")
    assert isinstance(out, dict)
    # La cita se comprueba AQUI, no se le cree al modelo: una regla cuya cita no
    # esta en el texto es una regla inventada, y es justo la que hay que cazar.
    limpio, descartadas = [], []
    plano = " ".join((trozo or "").split()).lower()
    for r in out.get("reglas") or []:
        cita = " ".join(str(r.get("cita") or "").split()).lower()
        if len(cita) >= 12 and cita[:120] in plano:
            limpio.append(r)
        else:
            descartadas.append(r)
    out["reglas"] = limpio
    out["descartadas"] = descartadas
    return out


def a_markdown(reglas: list[dict], fuente: str) -> str:
    """Las reglas en el formato en el que se guardan como pieza de estrategia."""
    if not reglas:
        return ""
    por_tipo: dict[str, list[dict]] = {}
    for r in reglas:
        por_tipo.setdefault(r.get("tipo", "entrada"), []).append(r)
    orden = ["filtro", "entrada", "salida", "gestion", "riesgo"]
    out = [f"<sub>Destilado de: {fuente}</sub>", ""]
    for t in orden:
        if t not in por_tipo:
            continue
        out.append(f"**{t.capitalize()}**")
        for r in por_tipo[t]:
            marca = "" if r.get("comprobable", True) else "  _(no automatizable)_"
            out.append(f"- {r['regla']}{marca}")
            out.append(f"  <sub>«{r['cita'][:200]}»</sub>")
        out.append("")
    return "\n".join(out).strip()


def resumen(json_reglas: dict) -> str:
    return json.dumps(json_reglas, ensure_ascii=False)[:400]
