"""The three segregated asset baskets and the growth lock rule.

  * Basket 1 (Cash Flow) — income with dividend growth > inflation.
  * Basket 2 (DRIP)      — mega-cap premium, high absolute DPS.
  * Basket 3 (Growth)    — locked until Baskets 1 & 2 hit their primary targets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Basket:
    name: str
    symbols: List[str]
    purpose: str
    locked: bool = False


class BasketRegistry:
    def __init__(self, cfg) -> None:  # cfg: BasketsConfig
        self.cashflow = Basket("cashflow", list(cfg.cashflow), "income, DGR > inflation")
        self.drip = Basket("drip", list(cfg.drip), "mega-cap premium, high DPS")
        self.growth = Basket("growth", list(cfg.growth), "aggressive growth", locked=cfg.growth_locked)
        self.drip_min_fractional_usd = cfg.drip_min_fractional_usd
        self.growth_unlock_months = cfg.growth_unlock_months
        self._tier1_met_streak = 0

    # ------------------------------------------------------------------
    def active_symbols(self) -> List[str]:
        """Symbols the system is allowed to allocate to right now."""
        syms = list(self.cashflow.symbols) + list(self.drip.symbols)
        if not self.growth.locked:
            syms += list(self.growth.symbols)
        return syms

    def can_allocate(self, basket_name: str) -> bool:
        if basket_name == "growth":
            return not self.growth.locked
        return basket_name in ("cashflow", "drip")

    def drip_eligible(self, dividend_usd: float) -> bool:
        """A single dividend payout must clear the broker's fractional minimum."""
        return dividend_usd >= self.drip_min_fractional_usd

    # ------------------------------------------------------------------
    def review_growth_lock(self, tier1_target_met: bool) -> bool:
        """Unlock growth after Tier 1 has been met for ``growth_unlock_months`` in a row.

        Returns True if growth is (now) unlocked.
        """
        if not self.growth.locked:
            return True
        if tier1_target_met:
            self._tier1_met_streak += 1
            if self._tier1_met_streak >= self.growth_unlock_months:
                self.growth.locked = False
        else:
            self._tier1_met_streak = 0
        return not self.growth.locked
