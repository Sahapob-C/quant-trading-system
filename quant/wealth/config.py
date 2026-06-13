"""Configuration for the wealth-management layer.

Recommended defaults are baked into the dataclasses below; an optional
``config/wealth.yaml`` overrides any field. Every SRS ``n%`` lives here so it can
be tuned without touching code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RiskConfig:
    position_pct: float = 5.0                 # SRS: tranche size per trade (% of capital)
    circuit_breaker_dd_pct: float = 10.0      # SRS: 24h rolling drawdown trigger
    circuit_breaker_freeze_hours: float = 24.0  # SRS: halt duration after trigger
    hard_stop_pct: float = 20.0               # SRS: per-position hard stop (given)
    trailing_retracement_pct: float = 50.0    # SRS: give back 50% of peak profit (given)
    daily_sweep_pct: float = 50.0             # SRS: % of daily profit swept to waterfall


@dataclass
class WaterfallConfig:
    tier1_min_thb: float = 10_000.0           # SRS: living-expense floor / month
    tier1_max_thb: float = 35_000.0           # SRS: living-expense cap / month
    annual_cpi_pct: float = 3.0               # realized inflation (CPI)
    inflation_buffer_pct: float = 1.0         # SRS Iron Rule: grow ABOVE CPI by this
    withholding_tax_pct: float = 30.0         # US dividend withholding (15 w/ W-8BEN treaty)
    thai_income_tax_pct: float = 0.0          # optional, on income remitted to TH


@dataclass
class FXConfig:
    usd_thb: float = 35.0                      # static fallback; real-time feed later


@dataclass
class BasketsConfig:
    # Basket 1: income with dividend-growth-rate (DGR) above inflation.
    cashflow: List[str] = field(default_factory=lambda: ["PG", "JNJ", "PEP", "KO", "MCD", "ABBV"])
    # Basket 2: mega-cap premium, high absolute DPS, single payout >= fractional min.
    drip: List[str] = field(default_factory=lambda: ["COST", "GS", "CAT", "TXN", "BLK"])
    # Basket 3: aggressive growth — LOCKED by default.
    growth: List[str] = field(default_factory=lambda: ["NVDA", "AMZN", "GOOGL", "META", "AAPL"])
    growth_locked: bool = True
    drip_min_fractional_usd: float = 1.0       # broker minimum for a fractional order
    growth_unlock_months: int = 6              # consecutive months Tier1 met before unlock


@dataclass
class AccountsConfig:
    live_capital_thb: float = 1_000.0
    paper_capital_usd: float = 100_000.0


@dataclass
class WealthConfig:
    risk: RiskConfig = field(default_factory=RiskConfig)
    waterfall: WaterfallConfig = field(default_factory=WaterfallConfig)
    fx: FXConfig = field(default_factory=FXConfig)
    baskets: BasketsConfig = field(default_factory=BasketsConfig)
    accounts: AccountsConfig = field(default_factory=AccountsConfig)


_SECTIONS = ("risk", "waterfall", "fx", "baskets", "accounts")


def load_wealth_config(path: Optional[str] = None) -> WealthConfig:
    """Start from recommended defaults; shallow-merge YAML overrides if present."""
    cfg = WealthConfig()
    if not path or not os.path.exists(path):
        return cfg

    import yaml

    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    for section in _SECTIONS:
        if section in raw and raw[section]:
            target = getattr(cfg, section)
            for key, value in raw[section].items():
                if hasattr(target, key):
                    setattr(target, key, value)
                else:
                    raise KeyError(f"Unknown config key '{section}.{key}' in {path}")
    return cfg
