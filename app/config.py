"""Central configuration. Everything comes from environment variables (.env)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- cTrader Open API ---
    ctrader_client_id: str = ""
    ctrader_client_secret: str = ""
    ctrader_redirect_uri: str = "http://localhost:8000/oauth/callback"
    ctrader_env: str = "demo"                # "demo" | "live"
    ctrader_account_id: int = 0              # ctidTraderAccountId (see dashboard after OAuth)

    # --- Llave maestra para cifrar las claves guardadas desde la UI ---
    app_secret_key: str = ""                 # pon APP_SECRET_KEY en Fly para activar la bóveda cifrada

    # --- Anthropic ---
    anthropic_api_key: str = ""
    model: str = "claude-opus-4-8"

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
    # Voz NEURAL por servidor (suena natural, como la de Claude). Requiere una API key.
    tts_provider: str = ""                   # "" (usa la del navegador) | "openai" | "elevenlabs"
    tts_api_key: str = ""                    # key de OpenAI o de ElevenLabs
    tts_speed: float = 1.06
    openai_tts_model: str = "tts-1"          # tts-1 (rápido) | tts-1-hd (más calidad)
    openai_tts_voice: str = "onyx"           # onyx=masculina grave; echo/fable/alloy también
    elevenlabs_voice_id: str = ""            # id de la voz elegida en ElevenLabs
    elevenlabs_model: str = "eleven_multilingual_v2"

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
