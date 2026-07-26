# Hydra en local + Claude Desktop (sin API, sin gastar tokens)

## La dirección del flujo

Hydra **no puede** mandarle un mensaje a una conversación de Claude Desktop.
Claude Desktop es un cliente, no un servidor: no expone endpoint ni acepta
llamadas entrantes. Lo que sí existe es lo inverso — **MCP**:

```
❌  Hydra           →  pregunta  →  Claude Desktop
✅  Claude Desktop  →  lee/escribe →  Hydra (servidor MCP local)
```

Tú abres Claude Desktop, dices *"revisa Hydra"*, y Claude llama las herramientas.
Cero tokens de la API: usa tu suscripción.

## 1. Corre Hydra en local

```bash
cd ~/Hydra-Trading
pip install -r requirements.txt
python run.py            # http://localhost:8000
```

## 2. Instala el SDK de MCP

```bash
pip install "mcp>=1.2.0"
```

## 3. Conecta Claude Desktop

Edita `~/Library/Application Support/Claude/claude_desktop_config.json`
(en Mac; créalo si no existe) y pon la ruta **absoluta** de tu carpeta:

```json
{
  "mcpServers": {
    "hydra": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/Users/TU_USUARIO/Hydra-Trading",
      "env": { "DATA_DIR": "./data" }
    }
  }
}
```

Reinicia Claude Desktop. Debe aparecer el conector **hydra** con sus herramientas.

## 4. Los cuatro roles (un Proyecto por rol, mismo servidor MCP)

No uses conversaciones sueltas — pierdes trazabilidad y cada una empieza sin
memoria. Crea un **Proyecto** de Claude por rol, todos conectados a este servidor,
y pon estas instrucciones en cada uno:

| Rol | Instrucción del proyecto |
|---|---|
| **Forense** | *Clasificas pérdidas usando `get_categories` y `record_postmortem`. NO propones cambios. La mayoría de las pérdidas son `perdida_esperada` — úsala sin miedo.* |
| **Estratega** | *Lees métricas y abres hipótesis (`open_hypothesis`) y propuestas (`propose_change`) solo cuando una categoría superó el umbral.* |
| **Auditor** | *Tu trabajo es ser hostil: demuestra que la mejora observada es ruido. Solo lectura. Calcula si la muestra es suficiente.* |
| **Dueño (tú)** | *Apruebas o rechazas en la app: Sistema → Propuestas.* |

La separación **Estratega / Auditor** es lo que evita el sobreajuste.

## 5. Lo que el servidor NUNCA hace

- No coloca órdenes, no mueve stops, no cambia lotaje. Eso queda en tu mano.
- No aplica cambios de parámetros: `propose_change` los deja en
  `awaiting_approval` y tú decides en **Sistema → Propuestas**.
- No deja abrir hipótesis con menos de 30 post-mortems en esa categoría.
  Una pérdida suelta es ruido, no señal.
- Máximo 2 parámetros por propuesta: si cambias muchos a la vez, no se puede
  saber cuál funcionó.

## Herramientas disponibles

**Lectura:** `get_status`, `get_playbook`, `get_parameters`, `get_categories`,
`query_journal`, `get_metrics`, `list_postmortems`, `list_hypotheses`,
`list_proposals`, `get_market`.

**Escritura (con compuerta):** `record_postmortem`, `open_hypothesis`,
`propose_change`.

## Autonomía real sin API (opcional)

Claude Code se autentica con tu suscripción y se puede invocar por cron:

```bash
claude -p "Corre el ciclo de post-mortem de Hydra" --output-format json
```

Un `launchd` los domingos a las 22:00 le da el ciclo semanal autónomo. Ojo:
consume cuota de la suscripción, así que no lo corras muy seguido.
