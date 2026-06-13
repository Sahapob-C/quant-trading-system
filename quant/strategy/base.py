"""Base class for all strategies.

A strategy is pure decision logic: it reads bars from the data handler and emits
``SignalEvent`` objects. It never touches cash, position sizing, or the broker —
that separation is what lets the identical strategy run in backtest and live.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Strategy(ABC):
    @abstractmethod
    def calculate_signals(self, event) -> None:
        """React to a ``MarketEvent`` by putting ``SignalEvent``s on the queue."""
