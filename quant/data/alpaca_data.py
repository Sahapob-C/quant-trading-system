"""Stream live market data from Alpaca broker API.

Handles:
  - Warmup: loading historical bars on startup
  - Polling: fetching new bars at regular intervals during live trading
  - Graceful failures: returns None for missing data instead of crashing
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from quant.core.events import MarketEvent
from quant.data.base import DataHandler
from quant.settings import get_alpaca_creds


class AlpacaDataHandler(DataHandler):
    def __init__(
        self,
        events,
        symbols: List[str],
        timeframe: str = "day",
        warmup: int = 300,
    ) -> None:
        """Connect to Alpaca and stream market data.

        Args:
            events: Event queue to emit MarketEvent to.
            symbols: List of ticker symbols to track.
            timeframe: Bar frequency: "day", "hour", "minute".
            warmup: Number of historical bars to load on startup.
        """
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        self.events = events
        self.symbol_list = list(symbols)
        self.warmup = warmup
        self.timeframe_str = timeframe

        # Map timeframe string to Alpaca TimeFrame enum
        self.timeframe_map = {
            "minute": TimeFrame.Minute,
            "hour": TimeFrame.Hour,
            "day": TimeFrame.Day,
        }
        if timeframe not in self.timeframe_map:
            raise ValueError(f"timeframe must be 'minute', 'hour', or 'day', got {timeframe}")

        # Connect to Alpaca
        key, secret = get_alpaca_creds()
        self.client = StockHistoricalDataClient(key, secret)

        # Latest bar cache
        self.latest_bars: Dict[str, dict] = {s: {} for s in self.symbol_list}
        self._last_bar_time: Optional[datetime] = None
        self._warmup_done = False

        # Load warmup bars on init
        self._load_warmup()
        self._warmup_done = True

    def _load_warmup(self) -> None:
        """Load historical bars to initialize indicators."""
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        now = datetime.now(timezone.utc)
        if self.timeframe_str == "minute":
            start = now - timedelta(minutes=self.warmup)
        elif self.timeframe_str == "hour":
            start = now - timedelta(hours=self.warmup)
        else:  # day
            start = now - timedelta(days=self.warmup)

        try:
            request = StockBarsRequest(
                symbol_or_symbols=self.symbol_list,
                timeframe=self.timeframe_map[self.timeframe_str],
                start=start,
                end=now,
            )
            bars = self.client.get_stock_bars(request)

            for symbol in self.symbol_list:
                if symbol in bars.data:
                    bar_list = bars.data[symbol]
                    if bar_list:
                        latest = bar_list[-1]
                        self.latest_bars[symbol] = {
                            "datetime": latest.timestamp,
                            "open": float(latest.open),
                            "high": float(latest.high),
                            "low": float(latest.low),
                            "close": float(latest.close),
                            "volume": float(latest.volume or 0.0),
                        }
                        self._last_bar_time = latest.timestamp
        except Exception as exc:
            print(f"Warning: Warmup failed: {exc}")

    @property
    def continue_backtest(self) -> bool:
        """Always True for live trading (never stops polling)."""
        return True

    def update_bars(self) -> None:
        """Poll for new bars and emit MarketEvent if available."""
        from alpaca.data.requests import StockBarsRequest

        now = datetime.now(timezone.utc)

        try:
            request = StockBarsRequest(
                symbol_or_symbols=self.symbol_list,
                timeframe=self.timeframe_map[self.timeframe_str],
                start=now - timedelta(hours=24),  # Look back to catch any missed bars
                end=now,
            )
            bars = self.client.get_stock_bars(request)

            for symbol in self.symbol_list:
                if symbol in bars.data:
                    bar_list = bars.data[symbol]
                    if bar_list:
                        latest = bar_list[-1]
                        # Only emit if this is a new bar
                        if (
                            self._last_bar_time is None
                            or latest.timestamp > self._last_bar_time
                        ):
                            self.latest_bars[symbol] = {
                                "datetime": latest.timestamp,
                                "open": float(latest.open),
                                "high": float(latest.high),
                                "low": float(latest.low),
                                "close": float(latest.close),
                                "volume": float(latest.volume or 0.0),
                            }
                            self._last_bar_time = latest.timestamp
                            self.events.put(MarketEvent(timestamp=latest.timestamp))
        except Exception as exc:
            print(f"Warning: Failed to fetch bars: {exc}")

    def get_latest_bar_datetime(self, symbol: str) -> Optional[datetime]:
        """Return the timestamp of the latest bar for this symbol."""
        bar = self.latest_bars.get(symbol, {})
        return bar.get("datetime")

    def get_latest_bar_value(self, symbol: str, field: str) -> Optional[float]:
        """Return a field from the latest bar."""
        bar = self.latest_bars.get(symbol, {})
        value = bar.get(field)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return None
        return float(value) if value else None

    def get_latest_bars_values(
        self, symbol: str, field: str, n: int
    ) -> Optional[np.ndarray]:
        """Return the last n values of a field.

        Note: Live data doesn't cache history, so this will return None
        unless you implement a rolling buffer. For now, strategies should
        use warmup to load enough history upfront.
        """
        # TODO: Implement a rolling buffer if indicators need history during live trading
        return None
