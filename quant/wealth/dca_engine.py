"""DCA engine — splits an available amount across active baskets and symbols.

Usage (paper / simulation — no real orders):
    engine = DCAEngine(cfg, tier_engine)
    plan = engine.plan(available_thb=500.0, capital_thb=1_000.0, fx=35.0)
    for leg in plan:
        print(leg)   # symbol, usd_amount, basket

For live execution wire ``execute()`` to an Alpaca handler.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import List

from quant.wealth.tier_engine import TierEngine


@dataclass
class DCALeg:
    basket: str
    symbol: str
    usd_amount: float
    thb_amount: float
    note: str = ""


@dataclass
class DCAPlan:
    timestamp: str
    capital_thb: float
    available_thb: float
    tier: int
    legs: List[DCALeg]

    def total_usd(self) -> float:
        return sum(l.usd_amount for l in self.legs)

    def summary(self) -> str:
        lines = [
            f"DCA Plan  tier={self.tier}  capital={self.capital_thb:,.0f} THB"
            f"  deploy={self.available_thb:,.0f} THB ({self.total_usd():.2f} USD)",
            f"{'Basket':<6} {'Symbol':<8} {'THB':>8} {'USD':>8}",
            "-" * 36,
        ]
        for leg in self.legs:
            lines.append(
                f"{leg.basket:<6} {leg.symbol:<8} {leg.thb_amount:>8.2f} {leg.usd_amount:>8.4f}"
            )
        return "\n".join(lines)


# Default basket symbol lists (override via config).
DEFAULT_SYMBOLS = {
    "b0": [],                                           # cash only — no buy orders
    "b1": [],                                           # live trading — handled by bot
    "b2": ["COST", "GS", "CAT", "TXN", "BLK"],        # high-DPS DRIP
    "b3": ["AAPL", "NVDA", "GOOGL", "MSFT", "AMZN"],  # quality growth
    "b4": ["OKLO", "NNE", "SMR", "CEG", "VST"],        # passion / SMR moonshot
}


class DCAEngine:
    def __init__(
        self,
        tier_engine: TierEngine,
        symbols: dict | None = None,
        fx_usd_thb: float = 35.0,
    ):
        self._te = tier_engine
        self._symbols = {**DEFAULT_SYMBOLS, **(symbols or {})}
        self.fx = fx_usd_thb

    def plan(self, available_thb: float, capital_thb: float) -> DCAPlan:
        spec = self._te.current_tier(capital_thb)
        legs: List[DCALeg] = []

        for basket, weight in spec.weights.items():
            syms = self._symbols.get(basket, [])
            if not syms:
                continue
            basket_thb = available_thb * weight
            per_sym_thb = basket_thb / len(syms)
            for sym in syms:
                legs.append(
                    DCALeg(
                        basket=basket,
                        symbol=sym,
                        usd_amount=round(per_sym_thb / self.fx, 4),
                        thb_amount=round(per_sym_thb, 2),
                    )
                )

        return DCAPlan(
            timestamp=datetime.utcnow().isoformat(),
            capital_thb=capital_thb,
            available_thb=available_thb,
            tier=spec.tier,
            legs=legs,
        )

    def save_plan(self, plan: DCAPlan, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(plan)) + "\n")
