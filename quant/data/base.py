"""Abstract base class for all data sources.

Every data handler must implement these methods so that the engine, strategies,
and execution handlers can work identically whether backtesting or trading live.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

import numpy as np


class DataHandler(ABC):
    """Abstract interface for market data sources.

    Concrete implementations must handle:
      - Loading/streaming bars for a symbol list
      - Returning current/historical bar values
      - Signaling when more data is available (backtest) or polling (live)
    """

    @property
    @abstractmethod
    def continue_backtest(self) -> bool:
        """Whether more bars are available. Used by engine.run_backtest() loop."""

    @abstractmethod
    def update_bars(self) -> None:
        """Fetch next bar(s) and put MarketEvent(s) on the event queue."""

    @abstractmethod
    def get_latest_bar_datetime(self, symbol: str) -> Optional[datetime]:
        """Return the timestamp of the most recent bar for ``symbol``.

        Returns None if symbol has no data yet.
        """

    @abstractmethod
    def get_latest_bar_value(self, symbol: str, field: str) -> Optional[float]:
        """Return the latest value of a field (open, high, low, close, volume, etc).

        Returns None if:
          - Symbol has no data loaded yet
          - Field doesn't exist (typo)
          - Bar data is corrupt / missing

        Never raises an exception.
        """

    @abstractmethod
    def get_latest_bars_values(
        self, symbol: str, field: str, n: int
    ) -> Optional[np.ndarray]:
        """Return the last ``n`` values of ``field`` for ``symbol`` as a 1-D array.

        Returns None if:
          - Not enough bars are available (len < n)
          - Symbol has no data yet
          - Any bar in the window has NaN/missing data

        Values are ordered oldest-first: [bar[t-n+1], ..., bar[t]]
        """
