"""Load historical OHLCV data from parquet files.

Expects one parquet file per symbol in the data directory:
    data/AAPL.parquet, data/MSFT.parquet, etc.

Each file must have a DatetimeIndex (timestamps) and columns:
    open, high, low, close, volume
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from quant.core.events import MarketEvent
from quant.data.base import DataHandler


class HistoricParquetDataHandler(DataHandler):
    def __init__(
        self,
        events,
        data_dir: str,
        symbols: List[str],
        start: str,
        end: str,
    ) -> None:
        """Load parquet files from data_dir for the given symbol list and date range.

        Args:
            events: Event queue to emit MarketEvent to when bars are available.
            data_dir: Directory containing {symbol}.parquet files (default: "data").
            symbols: List of ticker symbols to load.
            start: Start date (inclusive) as "YYYY-MM-DD" or Timestamp.
            end: End date (inclusive) as "YYYY-MM-DD" or Timestamp.
        """
        self.events = events
        self.data_dir = data_dir
        self.symbol_list = list(symbols)
        self.start = pd.Timestamp(start)
        self.end = pd.Timestamp(end)

        # Load all parquet files into DataFrames, aligned to same dates.
        self.data: Dict[str, pd.DataFrame] = {}
        self._load_data()

        # Track current bar index (same for all symbols).
        self._bar_index = 0
        self._dates: List[pd.Timestamp] = []
        if self.data:
            self._dates = sorted(set().union(*[df.index for df in self.data.values()]))
            self._dates = [d for d in self._dates if self.start <= d <= self.end]

        # Cache latest bar for each symbol.
        self.latest_bars: Dict[str, dict] = {s: {} for s in self.symbol_list}

    def _load_data(self) -> None:
        """Load parquet files; skip missing symbols with a warning."""
        for symbol in self.symbol_list:
            path = os.path.join(self.data_dir, f"{symbol}.parquet")
            if not os.path.exists(path):
                print(f"Warning: {path} not found (skipping {symbol})")
                continue
            try:
                df = pd.read_parquet(path)
                # Ensure DatetimeIndex
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                self.data[symbol] = df
            except Exception as exc:
                print(f"Error loading {symbol}: {exc}")

    @property
    def continue_backtest(self) -> bool:
        """Whether there are more bars to process."""
        return self._bar_index < len(self._dates)

    def update_bars(self) -> None:
        """Emit a MarketEvent for the next bar (same timestamp for all symbols)."""
        if not self.continue_backtest:
            return

        bar_date = self._dates[self._bar_index]
        self._bar_index += 1

        # Cache the bar for all symbols at this timestamp.
        for symbol in self.symbol_list:
            if symbol not in self.data:
                self.latest_bars[symbol] = {}
                continue
            df = self.data[symbol]
            if bar_date not in df.index:
                self.latest_bars[symbol] = {}
                continue
            row = df.loc[bar_date]
            self.latest_bars[symbol] = {
                "datetime": bar_date,
                "open": float(row.get("open")),
                "high": float(row.get("high")),
                "low": float(row.get("low")),
                "close": float(row.get("close")),
                "volume": float(row.get("volume", 0.0)),
            }

        # Emit a market event for this bar.
        self.events.put(MarketEvent(timestamp=bar_date))

    def get_latest_bar_datetime(self, symbol: str) -> Optional[datetime]:
        """Return the timestamp of the latest cached bar for this symbol."""
        bar = self.latest_bars.get(symbol, {})
        return bar.get("datetime")

    def get_latest_bar_value(self, symbol: str, field: str) -> Optional[float]:
        """Return a field from the latest bar (open, high, low, close, volume)."""
        bar = self.latest_bars.get(symbol, {})
        value = bar.get(field)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return None
        return float(value) if value else None

    def get_latest_bars_values(
        self, symbol: str, field: str, n: int
    ) -> Optional[np.ndarray]:
        """Return the last n values of a field as a 1-D array (oldest first).

        Returns None if not enough bars available or any bar has missing data.
        """
        if symbol not in self.data or self._bar_index == 0:
            return None

        df = self.data[symbol]
        # Get the last bar_index bars (from current date, going back).
        end_index = min(self._bar_index, len(df))
        start_index = max(0, end_index - n)
        if end_index - start_index < n:
            return None

        subset = df.iloc[start_index:end_index]
        if field not in subset.columns:
            return None

        values = subset[field].values
        # Check for NaN or missing values
        if np.isnan(values).any():
            return None

        return values.astype(float)
