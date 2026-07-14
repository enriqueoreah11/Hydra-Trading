"""High-level broker operations on top of the raw cTrader client."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from . import constants as c
from .ctrader import CTraderClient

log = logging.getLogger("broker")

# Cada bróker nombra los índices/materias primas distinto. Estos son grupos de
# nombres equivalentes: si pedimos uno y no existe, probamos los demás del grupo.
# (Todo se compara sin símbolos ni separadores: "US Tech 100" -> "USTECH100".)
_ALIAS_GROUPS: list[list[str]] = [
    ["US100", "USTEC", "NAS100", "NASDAQ100", "NASDAQ", "USTECH100", "USTEC100", "NDX", "USNAS100"],
    ["US30", "DJ30", "DOW", "DOW30", "WS30", "US30USD", "USADOW", "DJIA"],
    ["US500", "SPX500", "SP500", "SPX", "US500USD", "USSPX500", "SPXUSD"],
    ["XAUUSD", "GOLD", "XAUUSD"],
    ["XAGUSD", "SILVER", "XAGUSD"],
    ["XTIUSD", "USOIL", "WTI", "OIL", "CRUDE", "USCRUDE", "WTIUSD", "OILUSD"],
    ["XBRUSD", "UKOIL", "BRENT", "BRENTUSD", "UKOUSD"],
    ["US2000", "US2000", "RUSSELL2000", "RUT", "US2000USD"],
    ["DE40", "GER40", "DAX", "DAX40", "GER30", "DE30", "DEU40"],
    ["UK100", "FTSE100", "FTSE", "UK100GBP"],
    ["JP225", "JPN225", "NIKKEI", "NIKKEI225", "JP225USD"],
]


def _norm(s: str) -> str:
    return "".join(ch for ch in s.upper() if ch.isalnum())


_ALIAS_LOOKUP: dict[str, list[str]] = {}
for _grp in _ALIAS_GROUPS:
    _keys = [_norm(x) for x in _grp]
    for _k in _keys:
        _ALIAS_LOOKUP.setdefault(_k, []).extend(k for k in _keys if k != _k)


@dataclass
class SymbolInfo:
    symbol_id: int
    name: str
    digits: int
    pip_position: int
    lot_size_units: float      # units per lot
    min_volume_units: float
    step_volume_units: float
    max_volume_units: float


@dataclass
class Candle:
    ts: int          # epoch seconds (bar open)
    open: float
    high: float
    low: float
    close: float
    volume: float


class Broker:
    def __init__(self, client: CTraderClient, account_id: int):
        self.client = client
        self.account_id = account_id
        self._symbols_by_name: dict[str, int] = {}
        self._symbol_info: dict[int, SymbolInfo] = {}
        self._money_digits = 2

    # ------------------------------------------------------------- accounts

    async def list_accounts(self, access_token: str) -> list[dict]:
        res = await self.client.send(c.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ,
                                     {"accessToken": access_token})
        return res.get("ctidTraderAccount", [])

    async def trader(self) -> dict:
        res = await self.client.send(c.TRADER_REQ, {"ctidTraderAccountId": self.account_id})
        t = res.get("trader", {})
        md = int(t.get("moneyDigits", 2))
        self._money_digits = md
        return {
            "balance": float(t.get("balance", 0)) / (10 ** md),
            "currency": t.get("depositAssetId"),
            "leverage": t.get("leverageInCents", 0) / 100 if t.get("leverageInCents") else None,
            "raw": t,
        }

    # -------------------------------------------------------------- symbols

    async def _load_symbols(self) -> None:
        res = await self.client.send(c.SYMBOLS_LIST_REQ, {"ctidTraderAccountId": self.account_id})
        for s in res.get("symbol", []):
            self._symbols_by_name[str(s["symbolName"]).upper()] = int(s["symbolId"])

    async def symbol_id(self, name: str) -> int:
        if not self._symbols_by_name:
            await self._load_symbols()
        sid = self._symbols_by_name.get(name.upper())
        if sid is None:
            # tolerante al formato del broker: EUR/USD, EURUSD.i, EURUSD-RAW, etc.
            key = _norm(name)
            norm = {_norm(nm): s for nm, s in self._symbols_by_name.items()}
            sid = norm.get(key)
            # alias entre brokers: US100 <-> USTEC, XAUUSD <-> GOLD, XTIUSD <-> USOIL, etc.
            if sid is None:
                for alt in _ALIAS_LOOKUP.get(key, []):
                    sid = norm.get(alt)
                    if sid is not None:
                        break
            # último recurso: coincidencia por prefijo (EURUSD -> EURUSD.i)
            if sid is None:
                for candidate in [key, *_ALIAS_LOOKUP.get(key, [])]:
                    for nk, s in norm.items():
                        if nk.startswith(candidate):
                            sid = s
                            break
                    if sid is not None:
                        break
        if sid is None:
            raise ValueError(f"symbol {name!r} not found on this account")
        return sid

    def symbol_names(self) -> list[str]:
        return sorted(self._symbols_by_name.keys())

    async def symbol_info(self, name: str) -> SymbolInfo:
        sid = await self.symbol_id(name)
        if sid not in self._symbol_info:
            res = await self.client.send(c.SYMBOL_BY_ID_REQ, {
                "ctidTraderAccountId": self.account_id, "symbolId": [sid]})
            s = (res.get("symbol") or [{}])[0]
            # volumes on the wire are in cents of units
            self._symbol_info[sid] = SymbolInfo(
                symbol_id=sid,
                name=name.upper(),
                digits=int(s.get("digits", 5)),
                pip_position=int(s.get("pipPosition", 4)),
                lot_size_units=float(s.get("lotSize", 10_000_000)) / 100,
                min_volume_units=float(s.get("minVolume", 100_000)) / 100,
                step_volume_units=float(s.get("stepVolume", 100_000)) / 100,
                max_volume_units=float(s.get("maxVolume", 1_000_000_000)) / 100,
            )
        return self._symbol_info[sid]

    # -------------------------------------------------------------- candles

    async def candles(self, symbol: str, timeframe: str, count: int = 200) -> list[Candle]:
        sid = await self.symbol_id(symbol)
        period = c.TRENDBAR_PERIOD[timeframe]
        minutes = c.TRENDBAR_PERIOD_MINUTES[timeframe]
        now_ms = int(time.time() * 1000)
        frm = now_ms - int(count * 2.5) * minutes * 60_000  # extra margin for weekends
        res = await self.client.send(c.GET_TRENDBARS_REQ, {
            "ctidTraderAccountId": self.account_id,
            "fromTimestamp": frm,
            "toTimestamp": now_ms,
            "period": period,
            "symbolId": sid,
            "count": count,
        })
        out: list[Candle] = []
        for tb in res.get("trendbar", []):
            low = float(tb.get("low", 0))
            d_open = float(tb.get("deltaOpen", 0))
            d_high = float(tb.get("deltaHigh", 0))
            d_close = float(tb.get("deltaClose", 0))
            close = (low + d_close) / c.PRICE_SCALE if d_close else None
            out.append(Candle(
                ts=int(tb.get("utcTimestampInMinutes", 0)) * 60,
                open=(low + d_open) / c.PRICE_SCALE,
                high=(low + d_high) / c.PRICE_SCALE,
                low=low / c.PRICE_SCALE,
                close=close if close is not None else (low + d_open) / c.PRICE_SCALE,
                volume=float(tb.get("volume", 0)),
            ))
        out.sort(key=lambda x: x.ts)
        return out[-count:]

    # ------------------------------------------------------------- positions

    async def positions(self) -> list[dict]:
        res = await self.client.send(c.RECONCILE_REQ, {"ctidTraderAccountId": self.account_id})
        out = []
        for p in res.get("position", []):
            td = p.get("tradeData", {})
            out.append({
                "position_id": int(p.get("positionId", 0)),
                "symbol_id": int(td.get("symbolId", 0)),
                "side": c.TRADE_SIDE_NAME.get(int(td.get("tradeSide", 0)), "?"),
                "volume_units": float(td.get("volume", 0)) / 100,
                "entry_price": float(p.get("price", 0)),
                "stop_loss": float(p["stopLoss"]) if p.get("stopLoss") else None,
                "take_profit": float(p["takeProfit"]) if p.get("takeProfit") else None,
                "swap": float(p.get("swap", 0)) / (10 ** self._money_digits),
                "open_ts": int(td.get("openTimestamp", 0)) // 1000,
                "label": td.get("label", ""),
            })
        return out

    async def symbol_name_by_id(self, symbol_id: int) -> str:
        if not self._symbols_by_name:
            await self._load_symbols()
        for name, sid in self._symbols_by_name.items():
            if sid == symbol_id:
                return name
        return str(symbol_id)

    # ---------------------------------------------------------------- orders

    async def place_market_order(self, symbol: str, side: str, volume_units: float,
                                 stop_loss: float, take_profit: float | None,
                                 entry_ref: float, label: str = "brain") -> dict:
        """Market order with SL/TP expressed as *relative* distances (required by the API)."""
        info = await self.symbol_info(symbol)
        payload: dict = {
            "ctidTraderAccountId": self.account_id,
            "symbolId": info.symbol_id,
            "orderType": c.ORDER_TYPE_MARKET,
            "tradeSide": c.TRADE_SIDE[side],
            "volume": int(round(volume_units * 100)),
            "label": label[:100],
            # market orders take relative SL/TP: distance from execution price, scaled 1e5
            "relativeStopLoss": int(round(abs(entry_ref - stop_loss) * c.PRICE_SCALE)),
        }
        if take_profit is not None:
            payload["relativeTakeProfit"] = int(round(abs(take_profit - entry_ref) * c.PRICE_SCALE))
        log.info("placing order: %s", payload)
        return await self.client.send(c.NEW_ORDER_REQ, payload)

    async def amend_position_sltp(self, position_id: int, stop_loss: float | None,
                                  take_profit: float | None) -> dict:
        payload: dict = {"ctidTraderAccountId": self.account_id, "positionId": position_id}
        if stop_loss is not None:
            payload["stopLoss"] = stop_loss
        if take_profit is not None:
            payload["takeProfit"] = take_profit
        return await self.client.send(c.AMEND_POSITION_SLTP_REQ, payload)

    async def close_position(self, position_id: int, volume_units: float) -> dict:
        return await self.client.send(c.CLOSE_POSITION_REQ, {
            "ctidTraderAccountId": self.account_id,
            "positionId": position_id,
            "volume": int(round(volume_units * 100)),
        })

    # ----------------------------------------------------------------- deals

    async def realized_pnl_since(self, since_epoch: float) -> float:
        """Sum of realized gross profit + commission of deals since a timestamp."""
        res = await self.client.send(c.DEAL_LIST_REQ, {
            "ctidTraderAccountId": self.account_id,
            "fromTimestamp": int(since_epoch * 1000),
            "toTimestamp": int(time.time() * 1000),
            "maxRows": 1000,
        })
        total = 0.0
        md = self._money_digits
        for d in res.get("deal", []):
            cp = d.get("closePositionDetail")
            if cp:
                total += float(cp.get("grossProfit", 0)) / (10 ** md)
                total += float(cp.get("commission", 0)) / (10 ** md)
                total += float(cp.get("swap", 0)) / (10 ** md)
        return total
