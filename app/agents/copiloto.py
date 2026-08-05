"""Copiloto — contesta por voz lo que le preguntas sobre TU cuenta.

No decide ni propone nada: lee el estado y lo cuenta. Es el que te deja preguntar
"¿cómo va el oro?" mientras haces otra cosa, en vez de tener que abrir la pantalla.

La respuesta se va a OÍR, no a leer, y eso cambia cómo tiene que ser: por voz no
puedes volver atrás a releer un número. Frases cortas, cifras redondeadas y lo
importante primero.
"""
from __future__ import annotations

import json

from .. import llm

SYSTEM = """Eres el COPILOTO de un sistema de trading. Contestas EN VOZ ALTA a tu
operador sobre el estado de SU cuenta y SUS operaciones.

Reglas:
- Responde en espanol, en 1-3 frases cortas. Se va a escuchar, no a leer.
- Di solo lo que este en los datos. Si no esta, di "eso no lo tengo" y ya.
- Nada de consejos ni de opiniones sobre que hacer: no eres el analista.
- Numeros redondeados y en palabras naturales ("unos mil doscientos euros",
  "medio punto abajo"). Nada de tablas, listas ni markdown.
- Si te preguntan algo que no va del estado de la cuenta, dilo en una frase.
- Nunca digas que has hecho algo: tu no tocas nada, solo informas.
"""


async def responder(pregunta: str, estado: dict) -> str:
    user = (f"## Estado actual\n{json.dumps(estado, ensure_ascii=False, default=str)}\n\n"
            f"## Pregunta\n{pregunta}\n\nContesta en 1-3 frases para decirlas en voz alta.")
    out = await llm.ask(SYSTEM, user, role="copiloto")
    if isinstance(out, dict):
        out = out.get("text") or json.dumps(out, ensure_ascii=False)
    return str(out).strip()
