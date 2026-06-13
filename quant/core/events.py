"""Event objects that flow through the trading engine.

Every component communicates by putting :class:`Event` objects onto one shared
queue. Because the *same* event types are produced and consumed in both backtest
and live trading, a strategy written against these events runs unchanged in
either mode.

The flow for a single bar is::

    MarketEvent  -> Strategy   -> SignalEvent
    SignalEvent  -> Portfolio  -> OrderEvent
    OrderEvent   -> Execution  -> FillEvent
    FillEvent    -> Portfolio  (updates positions / cash)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    MARKET = "MARKET"
    SIGNAL = "SIGNAL"
    ORDER = "ORDER"
    FILL = "FILL"


@dataclass
class Event:
    """Base class for everything that travels on the event queue."""

    type: EventType = field(init=False)


@dataclass
class MarketEvent(Event):
    """A new bar of market data is available for every tracked symbol."""

    timestamp: datetime

    def __post_init__(self) -> None:
        self.type = EventType.MARKET


@dataclass
class SignalEvent(Event):
    """A strategy's directional view on a single symbol.

    ``signal_type`` is one of ``"LONG"``, ``"SHORT"`` or ``"EXIT"``.
    ``strength`` (0..1) is a hint the risk manager may use for sizing.
    """

    symbol: str
    timestamp: datetime
    signal_type: str
    strength: float = 1.0
    strategy_id: str = "default"

    def __post_init__(self) -> None:
        self.type = EventType.SIGNAL


@dataclass
class OrderEvent(Event):
    """An instruction for the execution handler to transact.

    ``quantity`` is always positive; the side is carried by ``direction``
    (``"BUY"`` / ``"SELL"``).
    """

    symbol: str
    timestamp: datetime
    order_type: str        # "MKT" | "LMT"
    quantity: int
    direction: str         # "BUY" | "SELL"
    limit_price: Optional[float] = None

    def __post_init__(self) -> None:
        self.type = EventType.ORDER

    def __str__(self) -> str:
        return (
            f"ORDER {self.direction} {self.quantity} {self.symbol} "
            f"[{self.order_type}]"
        )


@dataclass
class FillEvent(Event):
    """The result of an order being executed by a broker (or the simulator)."""

    timestamp: datetime
    symbol: str
    quantity: int
    direction: str         # "BUY" | "SELL"
    fill_price: float
    commission: float = 0.0
    exchange: str = "SIM"

    def __post_init__(self) -> None:
        self.type = EventType.FILL

    def __str__(self) -> str:
        return (
            f"FILL {self.direction} {self.quantity} {self.symbol} "
            f"@ {self.fill_price:.4f} (comm {self.commission:.2f})"
        )
