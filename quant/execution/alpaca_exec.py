"""Live / paper order execution via Alpaca.

Submits market orders through Alpaca's trading API, waits briefly for the fill,
then emits a ``FillEvent`` so the portfolio updates exactly as it does in a
backtest. Defaults to **paper** trading (see ``.env`` / ``ALPACA_PAPER``).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd

from quant.core.events import EventType, FillEvent
from quant.execution.base import ExecutionHandler
from quant.settings import get_alpaca_creds, use_paper


class AlpacaExecutionHandler(ExecutionHandler):
    def __init__(self, events, paper: bool | None = None, poll_timeout: float = 20.0, poll_interval: float = 1.0):
        from alpaca.trading.client import TradingClient

        self.events = events
        self.paper = use_paper() if paper is None else paper
        key, secret = get_alpaca_creds()
        self.client = TradingClient(key, secret, paper=self.paper)
        self.poll_timeout = poll_timeout
        self.poll_interval = poll_interval

    def execute_order(self, event) -> None:
        if event.type != EventType.ORDER:
            return

        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        side = OrderSide.BUY if event.direction == "BUY" else OrderSide.SELL
        request = MarketOrderRequest(
            symbol=event.symbol,
            qty=event.quantity,
            side=side,
            time_in_force=TimeInForce.DAY,
        )

        try:
            order = self.client.submit_order(request)
        except Exception as exc:
            print(f"! submit_order failed for {event.symbol}: {exc}")
            return

        filled = self._await_fill(order.id)
        if filled is None or not filled.filled_avg_price:
            print(f"! {event.symbol} {event.direction} x{event.quantity} not filled within "
                  f"{self.poll_timeout:.0f}s (market closed?)")
            return

        fill_price = float(filled.filled_avg_price)
        qty = int(float(filled.filled_qty))
        ts = pd.Timestamp(filled.filled_at or datetime.now(timezone.utc))

        self.events.put(
            FillEvent(
                timestamp=ts, symbol=event.symbol, quantity=qty,
                direction=event.direction, fill_price=fill_price,
                commission=0.0, exchange="ALPACA",
            )
        )
        print(f"  FILLED {event.direction} {qty} {event.symbol} @ {fill_price:.2f}")

    def _await_fill(self, order_id):
        from alpaca.trading.enums import OrderStatus

        deadline = time.time() + self.poll_timeout
        while time.time() < deadline:
            order = self.client.get_order_by_id(order_id)
            if order.status == OrderStatus.FILLED:
                return order
            if order.status in (OrderStatus.CANCELED, OrderStatus.REJECTED, OrderStatus.EXPIRED):
                return None
            time.sleep(self.poll_interval)
        # Last look: accept a partial fill if any quantity went through.
        order = self.client.get_order_by_id(order_id)
        if order.filled_qty and float(order.filled_qty) > 0:
            return order
        return None
