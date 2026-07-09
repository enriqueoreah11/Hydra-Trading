# 🐍 Medusa Trading — cerebro de trading multi-agente en la nube

Servicio 24/7 que opera tu cuenta de **cTrader** a través de la **cTrader Open API**
(OAuth2 + WebSocket). **No necesita cTrader instalado** ni en tu máquina ni en el servidor,
y corre en la nube sin que tu computadora esté prendida.

> ⚠️ **Advertencia**: esto coloca operaciones reales con dinero real si lo configuras en `live`.
> Empieza SIEMPRE en `demo` y con `DRY_RUN=true`. El trading automatizado puede perder dinero.
> Usa esto bajo tu propia responsabilidad.

## Los 6 agentes

| Agente | Rol | Cadencia |
|---|---|---|
| 🔍 **Analyst** | Lee el mercado (velas + EMA/RSI/ATR/niveles) y propone operaciones según el playbook | cada `ANALYSIS_INTERVAL_MIN` |
| 🛡️ **Risk Manager** | Calcula el tamaño de posición (*sizes*) y veta propuestas débiles (*vetoes*). Doble capa: límites duros en código + veto cualitativo LLM | por cada propuesta |
| ⚡ **Executor** | Coloca la orden de mercado con SL/TP vía Open API (o la simula en `DRY_RUN`) | por cada aprobación |
| 🌙 **Overnight** | Vigila posiciones abiertas: hold / apretar stop (nunca ampliarlo) / cerrar si la tesis murió | cada `OVERNIGHT_INTERVAL_MIN` |
| 📋 **Reviewer** | Auto-crítica diaria: qué hizo bien/mal el sistema, con evidencia del diario | diario a `REVIEW_HOUR_UTC` |
| 🏗️ **Architect** | Evoluciona el **playbook** (la estrategia) con lo aprendido. No puede tocar los límites duros de riesgo | diario, tras el Reviewer |

Todo queda registrado en un **diario** (SQLite) y el **playbook** se versiona: puedes ver cada
decisión y cada evolución de la estrategia en el dashboard web.

## Arquitectura

```
┌── nube (Docker, corre 24/7) ─────────────────────────────────────────────┐
│                                                                           │
│  Orchestrator (asyncio)                                                   │
│   ├─ ciclo de mercado ──► Analyst ─► Risk Manager ─► Executor             │
│   ├─ ciclo nocturno  ──► Overnight (posiciones vivas)                     │
│   └─ ciclo diario    ──► Reviewer ─► Architect (evoluciona playbook)      │
│                │                                                          │
│         Claude API (agentes)          SQLite (diario + playbook)          │
│                │                                                          │
│  Broker ─► CTraderClient ── wss://demo|live.ctraderapi.com:5036 (JSON)    │
│                │                                                          │
│  FastAPI :8000 ─ dashboard / OAuth / kill switch                          │
└───────────────────────────────────────────────────────────────────────────┘
```

## Puesta en marcha

### 1. Crea tu app en cTrader Open API

1. Entra a **https://openapi.ctrader.com/apps** con tu cTrader ID y crea una aplicación.
2. Registra como **Redirect URI** la URL pública de tu servicio + `/oauth/callback`
   (ej. `https://medusa.up.railway.app/oauth/callback`). Para probar local:
   `http://localhost:8000/oauth/callback`.
3. Copia el **Client ID** y **Client Secret**.

### 2. Configura

```bash
cp .env.example .env
# edita .env: CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET, CTRADER_REDIRECT_URI, ANTHROPIC_API_KEY
```

### 3. Arranca (local o nube)

```bash
docker compose up -d --build
# o sin docker:
pip install -r requirements.txt && python run.py
```

### 4. Conecta tu cuenta de cTrader (OAuth, una sola vez)

1. Abre `https://TU-DOMINIO/oauth/login` → cTrader te pedirá autorizar la app.
2. Al volver a `/oauth/callback` verás la lista de tus cuentas con su `ctidTraderAccountId`.
3. Pon ese ID en `CTRADER_ACCOUNT_ID` en `.env` y reinicia el servicio.

El access token dura ~30 días y el servicio lo **renueva solo** con el refresh token —
no tienes que volver a hacer login.

### 5. Verifica

- Dashboard: `https://TU-DOMINIO/` → estado, balance, diario, playbook.
- `GET /status`, `/positions`, `/journal`, `/playbook` (JSON).
- Kill switch: `POST /halt` / `POST /resume` (con `?token=` si definiste `DASHBOARD_TOKEN`).

Déjalo unos días en `demo` + `DRY_RUN=true`, lee las revisiones diarias del Reviewer, y solo
entonces considera `DRY_RUN=false` (sigue en demo) y mucho después `live`.

## Desplegar en la nube (sin tu máquina prendida)

Cualquier host de contenedores sirve. Necesitas: **1 proceso siempre activo + volumen persistente
para `/data` + URL pública HTTPS** (para el OAuth y el dashboard).

**Railway / Render / Fly.io** (los más simples):

1. Crea un servicio apuntando a este repositorio (todos detectan el `Dockerfile`).
2. Define las variables de `.env.example` en el panel de variables del servicio.
3. Agrega un **volumen persistente** montado en `/data` y define `DATA_DIR=/data`
   (ahí viven los tokens OAuth y la base de datos; sin volumen los pierdes en cada deploy).
4. Copia la URL pública que te den y úsala en `CTRADER_REDIRECT_URI` (+ actualiza el Redirect URI
   en tu app de cTrader).
5. Haz el paso OAuth (arriba) y reinicia.

**VPS (Hetzner, DigitalOcean, etc.)**: instala Docker, clona el repo, `docker compose up -d`,
y pon un proxy con HTTPS (Caddy/Traefik) delante del puerto 8000.

## Límites duros vs playbook

- **Límites duros** (`.env`): riesgo por operación, pérdida diaria máxima, nº de posiciones,
  confianza mínima, R:R mínimo, suelo de equity, `DRY_RUN`. Solo TÚ puedes cambiarlos.
- **Playbook** (SQLite, versionado): la estrategia que leen Analyst/Risk/Overnight.
  Es lo único que el Architect puede evolucionar, y cada versión queda guardada.

## Limitaciones conocidas (v1)

- **Tamaño de posición**: asume que la divisa de tu cuenta es la divisa cotizada del símbolo
  (cuenta USD ↔ EURUSD, XAUUSD, etc.). Para cruces tipo EURGBP con cuenta USD el tamaño será
  aproximado; mantén `RISK_PER_TRADE_PCT` bajo.
- **PnL diario** se calcula con los deals cerrados del día (grossProfit + comisión + swap).
- Un solo `ctidTraderAccountId` por instancia (levanta otra instancia para otra cuenta).
- Los agentes usan `claude-opus-4-8` por defecto (`MODEL` para cambiarlo). Costo estimado:
  con 2 símbolos y ciclos de 15 min, en el orden de unos pocos dólares al día; sube
  `ANALYSIS_INTERVAL_MIN` para reducirlo.

## Tests

```bash
pip install -r requirements.txt pytest && python -m pytest tests/ -q
```
