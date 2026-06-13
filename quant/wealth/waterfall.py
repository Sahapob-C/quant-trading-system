"""Waterfall cash-flow engine (ledger).

Inflows (net dividends + daily profit sweeps) arrive in USD, are taxed and
converted to THB, then routed by priority:

  Tier 1  Living expenses  — accumulate up to a monthly cap (10k-35k THB),
          which grows each year ABOVE realized inflation (the "Iron Rule").
  Tier 2  DRIP overflow    — everything past the cap goes to a bucket that buys
          fractional shares in the DRIP basket.

This is an accounting ledger only: it computes and records allocations to the
THB cent. Physically moving money out of the broker is a separate, manual step.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import List, Optional


@dataclass
class FXConverter:
    usd_thb: float = 35.0

    def to_thb(self, usd: float) -> float:
        return usd * self.usd_thb


@dataclass
class TaxModel:
    withholding_pct: float = 30.0   # US dividend withholding
    thai_income_pct: float = 0.0    # optional, on remitted income

    def net_dividend_usd(self, gross_usd: float) -> float:
        return gross_usd * (1.0 - self.withholding_pct / 100.0)

    def net_after_thai_thb(self, thb: float) -> float:
        return thb * (1.0 - self.thai_income_pct / 100.0)


@dataclass
class LedgerEntry:
    timestamp: object
    source: str          # "dividend" | "profit_sweep"
    gross_usd: float
    net_usd: float
    thb: float
    to_tier1_thb: float
    to_tier2_thb: float
    note: str = ""


class WaterfallLedger:
    def __init__(self, cfg, fx: Optional[FXConverter] = None) -> None:  # cfg: WaterfallConfig
        self.cfg = cfg
        self.fx = fx or FXConverter()
        self.tax = TaxModel(cfg.withholding_tax_pct, cfg.thai_income_tax_pct)

        self.entries: List[LedgerEntry] = []
        self.tier1_balance_thb = 0.0     # accumulated this month (paid out as living expenses)
        self.drip_bucket_thb = 0.0       # Tier 2 waiting to buy fractional shares
        self.tier1_paid_total_thb = 0.0  # lifetime living-expense allocations
        self.tier2_total_thb = 0.0       # lifetime DRIP allocations

        self.current_min_thb = cfg.tier1_min_thb
        self.current_cap_thb = cfg.tier1_max_thb
        self._month = None               # (year, month)
        self._year = None

    # ------------------------------------------------------------------
    def _roll_calendar(self, ts) -> None:
        ym = (ts.year, ts.month)
        if self._month is None:
            self._month, self._year = ym, ts.year
            return
        if ym != self._month:
            # New month: this month's living-expense accrual is considered paid out.
            self.tier1_paid_total_thb += self.tier1_balance_thb
            self.tier1_balance_thb = 0.0
            self._month = ym
        if ts.year != self._year:
            # Iron Rule: grow living-expense floor & cap above realized inflation.
            growth = (self.cfg.annual_cpi_pct + self.cfg.inflation_buffer_pct) / 100.0
            self.current_min_thb *= 1.0 + growth
            self.current_cap_thb *= 1.0 + growth
            self._year = ts.year

    # ------------------------------------------------------------------
    def inflow(self, ts, source: str, gross_usd: float, note: str = "") -> LedgerEntry:
        """Process one inflow; returns the ledger entry it created."""
        self._roll_calendar(ts)

        if source == "dividend":
            net_usd = self.tax.net_dividend_usd(gross_usd)   # withholding applied
        else:
            net_usd = gross_usd                              # profit sweep already realized

        thb = self.fx.to_thb(net_usd)
        if source == "profit_sweep":
            thb = self.tax.net_after_thai_thb(thb)

        room = max(0.0, self.current_cap_thb - self.tier1_balance_thb)
        to_tier1 = min(thb, room)
        to_tier2 = thb - to_tier1

        self.tier1_balance_thb += to_tier1
        self.drip_bucket_thb += to_tier2
        self.tier2_total_thb += to_tier2

        entry = LedgerEntry(ts, source, gross_usd, net_usd, thb, to_tier1, to_tier2, note)
        self.entries.append(entry)
        return entry

    # ------------------------------------------------------------------
    def tier1_target_met(self) -> bool:
        """Has this month's living-expense floor been reached?"""
        return self.tier1_balance_thb >= self.current_min_thb

    def drain_drip_bucket(self) -> float:
        """Take everything in the Tier 2 bucket (to buy fractional shares)."""
        amount = self.drip_bucket_thb
        self.drip_bucket_thb = 0.0
        return amount

    def summary(self) -> dict:
        return {
            "entries": len(self.entries),
            "tier1_this_month_thb": round(self.tier1_balance_thb, 2),
            "tier1_paid_total_thb": round(self.tier1_paid_total_thb, 2),
            "drip_bucket_thb": round(self.drip_bucket_thb, 2),
            "tier2_total_thb": round(self.tier2_total_thb, 2),
            "current_min_thb": round(self.current_min_thb, 2),
            "current_cap_thb": round(self.current_cap_thb, 2),
        }
