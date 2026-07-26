"""Reglas de la compuerta de aprendizaje, compartidas por el servidor MCP y la web.

Vive aparte de `mcp_server.py` a propósito: la app desplegada en Fly NO necesita
el paquete `mcp` instalado (el servidor MCP corre en tu Mac, en local).
"""
from __future__ import annotations

# Umbral mínimo de ocurrencias antes de que una categoría pueda generar hipótesis.
# Una pérdida individual casi siempre es ruido; ajustar parámetros tras cada una
# es la receta perfecta para el sobreajuste.
HYPOTHESIS_MIN_OCCURRENCES = 30

# Máximo de parámetros que una sola propuesta puede tocar. Cambiar muchos a la vez
# hace imposible saber cuál ayudó.
MAX_PARAMS_PER_PROPOSAL = 2

# Taxonomía CERRADA de post-mortems: el forense clasifica, no escribe ensayos.
# 'perdida_esperada' es la categoría más importante y la que un agente sin
# disciplina nunca usa — la mayoría de las pérdidas son parte del edge.
CATEGORIES: dict[str, str] = {
    "perdida_esperada": "Pérdida dentro del edge — el setup era válido, salió mal. RUIDO, no señal.",
    "entrada_tardia": "Entró tarde; el movimiento ya estaba hecho.",
    "sl_muy_ajustado": "El stop estaba demasiado cerca; barrido antes de que funcionara.",
    "contexto_htf_contrario": "El marco temporal mayor iba en contra.",
    "sesion_baja_liquidez": "Operó en una sesión sin volumen.",
    "noticia_no_filtrada": "Había un evento de alto impacto que no se filtró.",
    "ejecucion": "Slippage o spread se comieron el resultado.",
}
