"""Grid bot template for B1 (active trading).

Use when capital >= 50,000 THB (Tier 2).
Simple: place buy/sell orders in a grid around midpoint.

Config in YAML:
    b1:
      enabled: true
      symbols: ["SPY", "QQQ", "IVV"]
      grid_size: 0.02        # 2% grid width
      position_size_pct: 5.0 # each tranche = 5% capital

Run via:
    py scripts/run_grid_bot.py --symbol SPY --setup-only  # dry-run
    py scripts/run_grid_bot.py --symbol SPY --exec         # live
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class GridLevel:
    price: float
    size_usd: float
    side: str  # "buy" or "sell"
    filled: bool = False
    order_id: str = ""


class GridBot:
    def __init__(
        self,
        symbol: str,
        midpoint: float,
        grid_width_pct: float = 2.0,
        levels: int = 5,
        position_size_usd: float = 500.0,
    ):
        self.symbol = symbol
        self.midpoint = midpoint
        self.grid_width = midpoint * (grid_width_pct / 100)
        self.levels = levels
        self.position_size = position_size_usd

        self._build_grid()

    def _build_grid(self) -> None:
        self.buy_levels: List[GridLevel] = []
        self.sell_levels: List[GridLevel] = []

        step = self.grid_width / self.levels
        for i in range(1, self.levels + 1):
            # Buy below midpoint
            buy_price = self.midpoint - (step * i)
            self.buy_levels.append(
                GridLevel(
                    price=buy_price,
                    size_usd=self.position_size / self.levels,
                    side="buy",
                )
            )

            # Sell above midpoint
            sell_price = self.midpoint + (step * i)
            self.sell_levels.append(
                GridLevel(
                    price=sell_price,
                    size_usd=self.position_size / self.levels,
                    side="sell",
                )
            )

    def all_levels(self) -> List[GridLevel]:
        return sorted(
            self.buy_levels + self.sell_levels, key=lambda x: x.price
        )

    def summary(self) -> str:
        lines = [
            f"GridBot {self.symbol}  midpoint=${self.midpoint:.2f}  "
            f"grid={self.grid_width:.2f}",
            f"{'Price':>10} {'Side':>6} {'Size (USD)':>12}",
            "-" * 32,
        ]
        for level in self.all_levels():
            lines.append(
                f"${level.price:>9.2f} {level.side:>6} ${level.size_usd:>11.2f}"
            )
        return "\n".join(lines)
