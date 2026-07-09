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

    # --- Anthropic ---
    anthropic_api_key: str = ""
    model: str = "claude-opus-4-8"

    # --- Trading universe & cadence ---
    symbols: str = "EURUSD,XAUUSD"           # comma-separated cTrader symbol names
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
