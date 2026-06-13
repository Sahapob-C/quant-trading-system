"""Tier engine — reads portfolio capital and decides which baskets are active.

Tier 0  :  0 – 5,000 THB   → B3 Growth (60%) + B4 Passion (40%)
Tier 1  :  5k – 50k THB    → B2 DRIP (35%) + B3 (45%) + B4 (20%)
Tier 2  : 50k – 500k THB   → B1 Trading (20%) + B2 (30%) + B3 (35%) + B4 (15%)
Tier 3  : 500k+ THB        → Full system — all baskets incl. building B0 Fortress

Baskets auto-activate when capital crosses a threshold.  No manual switch needed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class TierSpec:
    tier: int
    min_thb: float
    max_thb: float          # math.inf for the top tier
    active_baskets: List[str]
    weights: Dict[str, float]   # must sum to 1.0


# Canonical tier definitions (edit via config if desired).
TIERS: List[TierSpec] = [
    TierSpec(
        tier=0,
        min_thb=0,
        max_thb=5_000,
        active_baskets=["b3", "b4"],
        weights={"b3": 0.60, "b4": 0.40},
    ),
    TierSpec(
        tier=1,
        min_thb=5_000,
        max_thb=50_000,
        active_baskets=["b2", "b3", "b4"],
        weights={"b2": 0.35, "b3": 0.45, "b4": 0.20},
    ),
    TierSpec(
        tier=2,
        min_thb=50_000,
        max_thb=500_000,
        active_baskets=["b1", "b2", "b3", "b4"],
        weights={"b1": 0.20, "b2": 0.30, "b3": 0.35, "b4": 0.15},
    ),
    TierSpec(
        tier=3,
        min_thb=500_000,
        max_thb=float("inf"),
        active_baskets=["b0", "b1", "b2", "b3", "b4"],
        weights={"b0": 0.10, "b1": 0.20, "b2": 0.25, "b3": 0.30, "b4": 0.15},
    ),
]


class TierEngine:
    def __init__(self, tiers: List[TierSpec] | None = None):
        self._tiers = tiers or TIERS

    def current_tier(self, capital_thb: float) -> TierSpec:
        for spec in reversed(self._tiers):
            if capital_thb >= spec.min_thb:
                return spec
        return self._tiers[0]

    def active_baskets(self, capital_thb: float) -> List[str]:
        return self.current_tier(capital_thb).active_baskets

    def weights(self, capital_thb: float) -> Dict[str, float]:
        return self.current_tier(capital_thb).weights

    def next_tier(self, capital_thb: float) -> TierSpec | None:
        spec = self.current_tier(capital_thb)
        for t in self._tiers:
            if t.tier == spec.tier + 1:
                return t
        return None

    def thb_to_next_tier(self, capital_thb: float) -> float:
        nxt = self.next_tier(capital_thb)
        if nxt is None:
            return 0.0
        return max(0.0, nxt.min_thb - capital_thb)
