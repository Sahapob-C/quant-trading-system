"""Abstract execution interface.

In a backtest this is the fill simulator; in live trading it is the Alpaca
client. Both take an ``OrderEvent`` and eventually put a ``FillEvent`` on the
queue — the portfolio cannot tell them apart.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ExecutionHandler(ABC):
    @abstractmethod
    def execute_order(self, event) -> None:
        """Receive an ``OrderEvent``. May fill now, or queue for the next bar."""

    def on_new_bar(self, event) -> None:
        """Called at the start of each new bar.

        The backtest simulator uses this to fill orders queued on the previous
        bar at the new bar's open. Live brokers fill on submit, so this is a
        no-op for them.
        """
        return None
