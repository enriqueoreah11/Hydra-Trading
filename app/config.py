"""Central configuration. Everything comes from environment variables (.env)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- cTrader Open API ---
    # Carpeta donde viven tus .algo (la que sincronizas con GitHub y el VPS).
    # Si se pone, Hydra la escanea y no hay que subir nada a mano.
    algo_dir: str = ""
    # carpeta donde tus bots escriben sus CSV de análisis (registro "shadow")
    shadow_dir: str = ""
    # Si la carpeta de los .algo es un repo, se hace `git pull` sola antes de cada
    # relectura: los ajustes que se hagan fuera (otra conversación, otro equipo)
    # llegan sin pulsar nada. Un fallo de red no para nada: se sigue con lo de disco.
    algo_auto_pull: bool = True

    ctrader_client_id: str = ""
    ctrader_client_secret: str = ""
    ctrader_redirect_uri: str = "http://localhost:8000/oauth/callback"
    ctrader_env: str = "demo"                # "demo" | "live"
    ctrader_account_id: int = 0              # ctidTraderAccountId (see dashboard after OAuth)

    # --- Llave maestra para cifrar las claves guardadas desde la UI ---
    app_secret_key: str = ""                 # pon APP_SECRET_KEY en Fly para activar la bóveda cifrada

    # --- Anthropic ---
    anthropic_api_key: str = ""
    # Modelo por defecto. Sonnet 5 da un balance costo/calidad para el análisis rutinario.
    # Opus 4.8 es ~5-10x más caro; Haiku 4.5 es ~20-30x más barato. Cambia desde la UI (Sistema).
    model: str = "claude-sonnet-5"

    # --- Cerebro local (Ollama) ---
    # Con "ollama" el análisis corre en TU máquina: gratis, ilimitado y sin API key.
    # Es lo que hace sostenible revisar cada lote de operaciones. Requiere Ollama
    # corriendo en local (ollama.com) y el modelo descargado (ollama pull qwen3).
    #   "anthropic" = todo en la nube · "ollama" = todo local
    #   "hybrid"    = el volumen en local, el juicio con Claude (recomendado)
    llm_provider: str = "anthropic"          # "anthropic" | "ollama" | "hybrid"
    # En modo híbrido, estos roles corren en local (son los de alta frecuencia:
    # el analista solo ya hace ~576 llamadas al día). El resto —reviewer y
    # architect, que deciden cómo evoluciona la estrategia— van con Claude,
    # porque corren pocas veces al día y ahí el criterio sí vale lo que cuesta.
    # El copiloto va en local a propósito: contestar "¿cómo va el oro?" veinte veces
    # al día no justifica una llamada de pago cada vez, y solo lee lo que ya hay.
    llm_local_roles: str = "analyst,risk_manager,overnight,tester,copiloto"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"           # el de la talacha
    ollama_timeout_s: float = 180.0
    # Ventana de contexto. Ollama por defecto usa una MUY corta y recorta el
    # prompt en silencio; el playbook + el snapshot de mercado no caben ahí.
    # 16k va sobrado y en 96 GB de RAM unificada ni se siente.
    ollama_num_ctx: int = 16384

    @property
    def local_roles(self) -> set[str]:
        return {r.strip() for r in self.llm_local_roles.split(",") if r.strip()}

    def brain_for(self, role: str) -> str:
        """Qué cerebro le toca a este rol: 'ollama' o 'anthropic'."""
        if self.llm_provider == "ollama":
            return "ollama"
        if self.llm_provider == "hybrid" and role in self.local_roles:
            return "ollama"
        return "anthropic"

    # --- Perplexity (investigación web) ---
    perplexity_api_key: str = ""             # activa el agente investigador (noticias/contexto)
    perplexity_model: str = "sonar"          # "sonar" es el económico; "sonar-pro" el potente
    research_daily_brief: bool = True        # un brief de mercado al día, guardado en la memoria

    # --- Quién toca la cuenta ---
    # El modelo razona; el código opera. Con esto activo, los stops de las
    # posiciones abiertas los calcula `gestion.py` con aritmética sobre precio,
    # entrada y ATR — no un número salido de un modelo de lenguaje. La opinión del
    # agente nocturno se sigue guardando (sirve para revisar si habría acertado),
    # pero no llega al bróker.
    ejecucion_determinista: bool = True
    gestion_be_en_r: float = 1.0             # a break-even al llegar a +1R
    gestion_trail_atr: float = 2.0           # arrastre a N x ATR del precio
    gestion_min_atr: float = 0.8             # nunca más cerca del precio que esto
    # Un "cerrar" del modelo NO cierra: avisa. Cerrar por una lectura equivocada
    # mata una operación que iba bien, y eso no se deshace.
    permitir_cierre_por_llm: bool = False

    # --- Cadencia: cuándo se analiza y se ponen las operaciones ---
    # "continua": se analiza cada `analysis_interval_min` minutos, todos los días.
    # "sesiones": se analiza SOLO los días de `sesion_dias`, a la hora fijada, y se
    #             dejan órdenes PENDIENTES en las zonas con caducidad hasta la
    #             siguiente sesión. La zona se toca cuando se toca, no cuando la miras.
    cadencia: str = "continua"               # "continua" | "sesiones"
    sesion_dias: str = "sun,wed"             # días de análisis (nombres en inglés, 3 letras)
    sesion_hora_utc: int = 20                # hora UTC de la sesión
    # Caducidad de las pendientes. Por defecto se calcula sola: hasta la siguiente
    # sesión. Una orden que sobrevive a la sesión que la justificó ya no la decidió
    # nadie.
    sesion_max_ordenes: int = 6              # tope por sesión: sin él, una sesión buena abre todo

    # --- La estrategia que enseñas tú ---
    # Con esto activo, el analista aplica TU estrategia (la que vas escribiendo en
    # Sistema → Estrategia o en tu Obsidian) en vez del playbook.
    estrategia_activa: bool = False
    estrategia_label: str = "50cal"          # etiqueta con la que se abren sus órdenes
    # Carpeta con tus manuales del curso. La app corre en TU Mac, así que puede
    # leer iCloud directamente — pero solo lo que esté DESCARGADO: un archivo que
    # solo vive en la nube no se puede abrir aunque se vea en Finder.
    # Ej: "/Users/tu-usuario/Library/Mobile Documents/com~apple~CloudDocs/Trading"
    estrategia_dir: str = ""

    # --- Cómo se decide qué operar ---
    # "manual": el playbook lo escribes tú (o lo evoluciona el Arquitecto desde las
    #           revisiones diarias). Es una creencia: puede estar bien o estar viejo,
    #           y mirándolo no se distingue.
    # "auto":   el playbook lo escribe la MEDICIÓN. Cada día se prueban las estrategias
    #           sobre tu histórico, se puntúa fuera de muestra y con coste, y lo que
    #           sobrevive es lo único que se opera. Lo que no sobrevive desaparece solo.
    playbook_mode: str = "manual"            # "manual" | "auto"
    descubrir_steps: int = 3                 # valores por parámetro (3 = 3^n combinaciones)
    descubrir_horizon: int = 60              # velas máximas que dura una operación medida
    descubrir_split: float = 0.7             # 70% para buscar, 30% para comprobar
    # Spread + comisión estimados en múltiplos de R. Un backtest a coste cero miente
    # hacia arriba. Súbelo si tu bróker es caro: las cifras bajarán, y serán las tuyas.
    coste_r: float = 0.05

    # --- Macro (lo que mueve a los CFDs y no viene del bróker) ---
    # FRED (Reserva Federal de St. Louis): tipos nominales y reales, VIX e índice
    # dólar. Gratis, pero pide una clave gratuita en fred.stlouisfed.org. Sin clave
    # el macro sigue funcionando solo con el posicionamiento de la CFTC, que no
    # necesita clave ninguna.
    fred_api_key: str = ""
    macro_enabled: bool = True               # apagarlo deja al analista solo con el precio

    # --- Trading universe & cadence ---
    # Principales metales, energia e indices. OJO: el nombre exacto depende del broker
    # (Nasdaq puede ser US100/USTEC/NAS100; el WTI puede ser XTIUSD/USOIL/WTI).
    # Ajusta con el secreto SYMBOLS si tu broker usa otros nombres.
    symbols: str = "XAUUSD,XAGUSD,XTIUSD,US100,US30,US500"
    timeframe: str = "M15"                   # M1,M5,M15,M30,H1,H4,D1
    analysis_interval_min: int = 15
    overnight_interval_min: int = 30
    review_hour_utc: int = 21                # daily reviewer + architect run at this UTC hour

    # --- Hard risk limits (NOT editable by the Architect agent) ---
    dry_run: bool = True                     # True = paper mode, logs orders instead of sending
    risk_per_trade_pct: float = 1.0          # % of balance risked per trade
    max_daily_loss_pct: float = 3.0          # stop trading for the day beyond this realized loss
    max_open_positions: int = 3
    min_confidence: int = 65                 # analyst confidence needed to even reach risk review
    min_risk_reward: float = 1.5
    equity_floor_pct: float = 80.0           # halt if balance < this % of initial balance

    # --- Sentinel (economic-calendar news blackout) ---
    enable_news: bool = True
    news_url: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    news_impact_min: str = "High"            # High | Medium | Low — minimum impact that blocks
    news_blackout_before_min: int = 30       # no new entries this many min BEFORE an event
    news_blackout_after_min: int = 15        # ...and this many min AFTER
    news_refresh_min: int = 180              # re-fetch the calendar every N minutes
    # Panel de calendario embebido en el dashboard (p.ej. widget de Financial Juice / TradingView).
    # Pega aqui la URL del widget/iframe de tu calendario para verlo dentro de la app.
    calendar_embed_url: str = ""

    # --- Voz (JARVIS) ---
    voice_enabled: bool = True               # muestra el control de voz en el dashboard
    owner_name: str = "Krauser"              # cómo te llama la app por voz (p.ej. Enrique, Krauser, jefe)
    owner_lang: str = "mix"                  # idioma: "es" | "en" | "mix" (español con términos de trading en inglés)
    # Voz NEURAL por servidor (suena natural, como la de Claude). Requiere una API key.
    # La voz de Hydra es Voicebox y punto. Los proveedores de pago (OpenAI,
    # ElevenLabs) siguen en el código por si algún día hacen falta, pero no se
    # ofrecen: elegir entre cuatro voces no aportaba nada y cada opción era una
    # forma más de acabar sin voz sin saber por qué.
    tts_provider: str = "voicebox"           # "" (navegador) | "voicebox"
    # Voicebox: estudio de voz LOCAL (Kokoro/Qwen3-TTS). Gratis, sin API key y sin
    # internet. Requiere la app abierta: el servidor corre dentro de ella.
    voicebox_url: str = "http://127.0.0.1:17493"
    voicebox_profile: str = "Jarvis"         # nombre del perfil de voz en Voicebox
    voicebox_timeout_s: float = 120.0
    tts_api_key: str = ""                    # key de OpenAI o de ElevenLabs
    tts_speed: float = 1.06
    openai_tts_model: str = "tts-1"          # tts-1 (rápido) | tts-1-hd (más calidad)
    openai_tts_voice: str = "onyx"           # onyx=masculina grave; echo/fable/alloy también
    elevenlabs_voice_id: str = ""            # id de la voz elegida en ElevenLabs
    elevenlabs_model: str = "eleven_multilingual_v2"

    # --- Memoria en Obsidian ---
    # Vacío = la memoria vive dentro de la app (data/vault) y solo se ve bajándola
    # en .zip. Con la ruta de TU vault puesta, las notas se escriben directamente
    # ahí: las ves en Obsidian según se crean, y lo que tú escribas puede volver al
    # cerebro. Ejemplo: /Users/tu-usuario/Documents/MiVault
    obsidian_vault_path: str = ""
    obsidian_folder: str = "Hydra"           # subcarpeta suya dentro del vault
    # Del resto del vault solo se lee lo que marques con #hydra. Lo tuyo es tuyo:
    # sin esa etiqueta, una nota no entra nunca en un prompt.
    obsidian_tag: str = "hydra"

    # --- Oídos (voz -> texto) ---
    # El mismo Voicebox que habla trae Whisper dentro y lo expone en /transcribe.
    # Todo local: el audio no sale del Mac y no hace falta ninguna clave.
    stt_enabled: bool = True
    stt_model: str = "whisper-turbo"          # turbo va sobrado para dictar en español
    stt_timeout_s: float = 60.0

    # --- Watchdog + Telegram notifier ---
    telegram_bot_token: str = ""             # from @BotFather; empty = notifications disabled
    telegram_chat_id: str = ""               # your chat id (see README)
    watchdog_interval_min: int = 5
    data_stale_alert_min: int = 20           # alert if no fresh candles for this long (market open)
    error_burst_threshold: int = 5           # alert if this many errors within the window
    heartbeat_hour_utc: int = 8              # one "estoy vivo" ping per day at this UTC hour

    # --- Auditor / reconciler ---
    enable_auditor: bool = True
    auditor_interval_min: int = 20
    auto_halt_on_discrepancy: bool = True    # halt trading if an unexplained discrepancy appears

    # --- Playbook validator (backtest gate for the Architect) ---
    validate_playbook: bool = True
    backtest_bars: int = 700                 # history depth per symbol (más = más robusto)
    backtest_samples: int = 24               # decision points sampled per symbol (LLM cost driver)
    backtest_horizon_bars: int = 30          # bars ahead to resolve each simulated trade

    # --- Portfolio risk / correlation ---
    enable_portfolio_check: bool = True
    max_currency_exposure_pct: float = 2.0   # max aggregate risk% on a single currency
    max_correlation: float = 0.7             # block a redundant, highly-correlated same-direction bet

    # --- Web dashboard ---
    web_host: str = "0.0.0.0"
    web_port: int = 8000
    dashboard_token: str = ""                # if set, required as ?token= for /halt & /resume

    # --- Storage ---
    data_dir: str = "./data"

    @property
    def symbol_list(self) -> list[str]:
        return [s.strip().upper() for s in self.symbols.split(",") if s.strip()]

    @property
    def ws_url(self) -> str:
        host = "live.ctraderapi.com" if self.ctrader_env == "live" else "demo.ctraderapi.com"
        return f"wss://{host}:5036"

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
