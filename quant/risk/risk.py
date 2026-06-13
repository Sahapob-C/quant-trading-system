"""Position sizing and basic risk limits.

The portfolio asks the risk manager: "given this signal, how many shares should I
*target* holding?" Keeping sizing here (rather than in the strategy) means you can
change risk policy without touching strategy logic, and reuse one policy across
many strategies.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class RiskManager:
    #: Fraction of total equity to allocate to a single new position.
    target_pct: float = 0.10
    #: Hard cap on any one position as a fraction of equity.
    max_position_pct: float = 0.25
    #: Whether SHORT signals are allowed to open negative positions.
    allow_short: bool = False

    def target_quantity(
        self,
        signal_type: str,
        equity: float,
        price: float,
        current_qty: int,
    ) -> int:
        """Return the desired (signed) share count after acting on ``signal_type``."""
        if price <= 0 or equity <= 0:
            return current_qty  # cannot size meaningfully -> no change

        pct = min(self.target_pct, self.max_position_pct)
        size = math.floor((pct * equity) / price)

        if signal_type == "LONG":
            return size
        if signal_type == "EXIT":
            return 0
        if signal_type == "SHORT":
            return -size if self.allow_short else 0
        return current_qty
