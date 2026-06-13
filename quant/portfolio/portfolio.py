"""The book: tracks positions and cash, turns signals into sized orders.

Responsibilities:
  * ``update_signal`` — a strategy signal arrives; ask the risk manager how big
    the position should be and emit an ``OrderEvent`` for the difference.
  * ``update_fill``  — an order executed; update share counts, cash, commission.
  * ``update_timeindex`` — a new bar closed; snapshot mark-to-market equity so we
    can build an equity curve afterwards.
"""
from __future__ import annotations

from typing import Callable, List, Optional

import pandas as pd

from quant.core.events import EventType, OrderEvent
from quant.risk.risk import RiskManager


class Portfolio:
    def __init__(
        self,
        events,
        data_handler,
        symbol_list,
        start_date,
        initial_capital: float = 100_000.0,
        risk_manager: Optional[RiskManager] = None,
        on_fill: Optional[Callable] = None,
    ) -> None:
        self.events = events
        self.data = data_handler
        self.symbol_list = list(symbol_list)
        self.start_date = pd.Timestamp(start_date)
        self.initial_capital = float(initial_capital)
        self.risk = risk_manager or RiskManager()
        # Optional hook fired after every fill (live trading: journal + alert).
        self.on_fill = on_fill

        # Live state.
        self.current_positions = {s: 0 for s in self.symbol_list}
        self.current_holdings = {s: 0.0 for s in self.symbol_list}
        self.current_holdings["cash"] = self.initial_capital
        self.current_holdings["commission"] = 0.0
        self.current_holdings["total"] = self.initial_capital
        self.equity = self.initial_capital  # latest mark-to-market total

        # History (built up bar by bar).
        self.all_positions: List[dict] = []
        self.all_holdings: List[dict] = []
        self.fills: List[dict] = []

    # ------------------------------------------------------------------
    def update_timeindex(self, event=None) -> None:
        """Snapshot positions and mark-to-market holdings for the latest bar."""
        latest_dt = self.data.get_latest_bar_datetime(self.symbol_list[0])

        positions = {"datetime": latest_dt}
        for s in self.symbol_list:
            positions[s] = self.current_positions[s]
        self.all_positions.append(positions)

        holdings = {
            "datetime": latest_dt,
            "cash": self.current_holdings["cash"],
            "commission": self.current_holdings["commission"],
        }
        total = self.current_holdings["cash"]
        for s in self.symbol_list:
            price = self.data.get_latest_bar_value(s, "close") or 0.0
            market_value = self.current_positions[s] * price
            holdings[s] = market_value
            total += market_value
        holdings["total"] = total
        self.all_holdings.append(holdings)
        self.equity = total

    # ------------------------------------------------------------------
    def update_signal(self, signal) -> None:
        if signal.type != EventType.SIGNAL:
            return
        order = self._generate_order(signal)
        if order is not None:
            self.events.put(order)

    def _generate_order(self, signal) -> Optional[OrderEvent]:
        s = signal.symbol
        price = self.data.get_latest_bar_value(s, "close")
        if price is None or price <= 0:
            return None

        current_qty = self.current_positions[s]
        target_qty = self.risk.target_quantity(
            signal.signal_type, self.equity, price, current_qty
        )
        delta = target_qty - current_qty
        if delta == 0:
            return None

        direction = "BUY" if delta > 0 else "SELL"
        return OrderEvent(
            symbol=s,
            timestamp=signal.timestamp,
            order_type="MKT",
            quantity=abs(int(delta)),
            direction=direction,
        )

    # ------------------------------------------------------------------
    def update_fill(self, fill) -> None:
        if fill.type != EventType.FILL:
            return

        fill_dir = 1 if fill.direction == "BUY" else -1
        self.current_positions[fill.symbol] += fill_dir * fill.quantity

        cost = fill_dir * fill.fill_price * fill.quantity
        self.current_holdings["commission"] += fill.commission
        self.current_holdings["cash"] -= cost + fill.commission
        self.current_holdings["total"] -= cost + fill.commission

        self.fills.append(
            {
                "datetime": fill.timestamp,
                "symbol": fill.symbol,
                "direction": fill.direction,
                "quantity": fill.quantity,
                "fill_price": fill.fill_price,
                "commission": fill.commission,
            }
        )

        if self.on_fill is not None:
            self.on_fill(fill)

    # ------------------------------------------------------------------
    def equity_curve(self) -> pd.DataFrame:
        """Build the equity-curve DataFrame from the recorded holdings."""
        df = pd.DataFrame(self.all_holdings)
        if df.empty:
            return df
        df = df.set_index("datetime").sort_index()
        df["returns"] = df["total"].pct_change().fillna(0.0)
        df["equity_curve"] = (1.0 + df["returns"]).cumprod()
        return df

    def fills_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.fills)
