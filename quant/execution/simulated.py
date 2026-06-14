"""Backtest fill simulator.

By default (``fill_on="next_open"``) an order received on bar *t* is held and
filled at the **open of bar t+1** — this matches reality (you decide after a bar
closes, and trade on the next session) and removes the look-ahead bias of filling
at the very close that produced the signal.

Set ``fill_on="close"`` to reproduce the (optimistic) same-bar-close behaviour,
which is handy for measuring how much that bias was flattering your results.

Fills are nudged by a slippage assumption (buys a touch higher, sells a touch
lower) and charged a commission. Defaults model a commission-free US equity
broker with a tiny slippage buffer — tune them to your broker.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from quant.core.events import EventType, FillEvent, OrderEvent
from quant.execution.base import ExecutionHandler


class PerShareCommission:
    """Interactive-Brokers-style commission: per share with a per-order floor."""

    def __init__(self, per_share: float = 0.005, min_per_order: float = 1.0):
        self.per_share = per_share
        self.min_per_order = min_per_order

    def __call__(self, quantity: int, price: float) -> float:
        return max(self.min_per_order, self.per_share * quantity)


def zero_commission(quantity: int, price: float) -> float:
    return 0.0


class SimulatedExecutionHandler(ExecutionHandler):
    def __init__(
        self,
        events,
        data_handler,
        slippage_bps: float = 1.0,
        commission: Optional[Callable[[int, float], float]] = None,
        fill_on: str = "next_open",
    ) -> None:
        if fill_on not in ("next_open", "close"):
            raise ValueError("fill_on must be 'next_open' or 'close'")
        if slippage_bps < 0:
            raise ValueError(f"slippage_bps cannot be negative, got {slippage_bps}")
        self.events = events
        self.data = data_handler
        self.slippage = slippage_bps / 10_000.0
        self.commission_model = commission or zero_commission
        self.fill_on = fill_on
        self._pending: List[OrderEvent] = []

    # ------------------------------------------------------------------
    def execute_order(self, event) -> None:
        if event.type != EventType.ORDER:
            return
        if self.fill_on == "close":
            # Legacy: fill immediately at this bar's close.
            self._fill(event, self.data.get_latest_bar_value(event.symbol, "close"))
        else:
            # Realistic: wait and fill at the next bar's open.
            self._pending.append(event)

    def on_new_bar(self, event) -> None:
        """Fill everything queued on the previous bar at this bar's open."""
        if not self._pending:
            return
        pending, self._pending = self._pending, []
        for order in pending:
            price = self.data.get_latest_bar_value(order.symbol, "open")
            if price is None:  # rare gaps: fall back to close
                price = self.data.get_latest_bar_value(order.symbol, "close")
            self._fill(order, price)

    # ------------------------------------------------------------------
    def _fill(self, order: OrderEvent, price) -> None:
        if price is None or price <= 0:
            return
        if order.direction == "BUY":
            fill_price = price * (1.0 + self.slippage)
        else:
            fill_price = price * (1.0 - self.slippage)

        commission = self.commission_model(order.quantity, fill_price)
        ts = self.data.get_latest_bar_datetime(order.symbol)

        self.events.put(
            FillEvent(
                timestamp=ts,
                symbol=order.symbol,
                quantity=order.quantity,
                direction=order.direction,
                fill_price=fill_price,
                commission=commission,
                exchange="SIM",
            )
        )
