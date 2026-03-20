from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest, GetPortfolioHistoryRequest
from alpaca.trading.enums import QueryOrderStatus
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame


@dataclass
class AlpacaConfig:
    key_id: str
    secret_key: str
    base_url: str
    watchlist: list[str]


def load_config() -> AlpacaConfig:
    load_dotenv()
    key_id = os.getenv("APCA_API_KEY_ID", "")
    secret_key = os.getenv("APCA_API_SECRET_KEY", "")
    base_url = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
    watchlist = [s.strip().upper() for s in os.getenv("WATCHLIST", "AAPL,MSFT,SPY,QQQ").split(",") if s.strip()]
    if not key_id or not secret_key:
        raise RuntimeError("Missing APCA_API_KEY_ID or APCA_API_SECRET_KEY")
    return AlpacaConfig(key_id=key_id, secret_key=secret_key, base_url=base_url, watchlist=watchlist)


class AlpacaGateway:
    def __init__(self, cfg: AlpacaConfig) -> None:
        self.trading = TradingClient(api_key=cfg.key_id, secret_key=cfg.secret_key, paper=True)
        self.data = StockHistoricalDataClient(api_key=cfg.key_id, secret_key=cfg.secret_key)
        self.cfg = cfg

    def account(self):
        return self.trading.get_account()

    def positions(self):
        return self.trading.get_all_positions()

    def open_orders(self):
        req = GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=200, nested=False)
        return self.trading.get_orders(filter=req)

    def recent_orders(self, limit: int = 50):
        req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=limit, nested=False)
        return self.trading.get_orders(filter=req)

    def portfolio_history(self, period: str = "1D", timeframe: str = "5Min", extended_hours: bool = True):
        req = GetPortfolioHistoryRequest(period=period, timeframe=timeframe, extended_hours=extended_hours)
        return self.trading.get_portfolio_history(history_filter=req)

    def latest_quotes(self, symbols: Iterable[str]):
        syms = sorted(set(s.upper() for s in symbols))
        if not syms:
            return {}
        req = StockLatestQuoteRequest(symbol_or_symbols=syms)
        return self.data.get_stock_latest_quote(req)

    def recent_bars(self, symbol: str, limit: int = 120):
        req = StockBarsRequest(symbol_or_symbols=symbol.upper(), timeframe=TimeFrame.Minute, limit=limit)
        return self.data.get_stock_bars(req)
