"""Screen real symbols into the three baskets using actual dividend data.

Pulls price + dividend history from Yahoo Finance and computes the metrics the
SRS cares about, so basket membership is data-driven instead of guessed:

  * Basket 1 (Cash Flow) — consistent payers whose dividend growth rate (DGR)
    outpaces inflation.
  * Basket 2 (DRIP)      — low-yield premium names with a high *absolute* dividend
    per share, where a single payout clears the broker's fractional minimum.
  * Basket 3 (Growth)    — little/no dividend, driven by price appreciation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd


@dataclass
class SymbolMetrics:
    symbol: str
    last_price: float
    annual_dividend: float    # trailing-12m dividend per share
    dividend_yield: float     # annual_dividend / last_price
    dgr: float                # CAGR of annual dividend over full years (NaN if n/a)
    years_paid: int           # calendar years with a dividend
    max_single_payout: float  # largest single payout in the last 12 months
    price_cagr: float         # price appreciation CAGR over the window


def fetch_metrics(symbol: str, years: int = 7) -> Optional[SymbolMetrics]:
    import yfinance as yf

    try:
        hist = yf.Ticker(symbol).history(period=f"{years}y", auto_adjust=True)
    except Exception:
        return None
    if hist is None or hist.empty or "Close" not in hist:
        return None

    close = hist["Close"].dropna()
    if close.empty:
        return None
    last_price = float(close.iloc[-1])

    span_years = (close.index[-1] - close.index[0]).days / 365.25
    price_cagr = (
        (last_price / float(close.iloc[0])) ** (1 / span_years) - 1
        if span_years > 0 and close.iloc[0] > 0 else float("nan")
    )

    divs = hist["Dividends"]
    divs = divs[divs > 0] if "Dividends" in hist else pd.Series(dtype=float)

    if divs.empty:
        return SymbolMetrics(symbol, last_price, 0.0, 0.0, float("nan"), 0, 0.0, price_cagr)

    cutoff_12m = close.index[-1] - pd.Timedelta(days=365)
    ttm = divs[divs.index >= cutoff_12m]
    annual_dividend = float(ttm.sum())
    max_single = float(ttm.max()) if not ttm.empty else 0.0
    dividend_yield = annual_dividend / last_price if last_price > 0 else 0.0

    by_year = divs.groupby(divs.index.year).sum()
    years_paid = int((by_year > 0).sum())

    current_year = close.index[-1].year
    full = by_year[by_year.index < current_year]
    full = full[full > 0]
    dgr = float("nan")
    if len(full) >= 2 and full.iloc[0] > 0:
        span = int(full.index[-1] - full.index[0])
        if span > 0:
            dgr = (full.iloc[-1] / full.iloc[0]) ** (1 / span) - 1

    return SymbolMetrics(
        symbol, last_price, annual_dividend, dividend_yield,
        dgr, years_paid, max_single, price_cagr,
    )


def classify(m: SymbolMetrics, fractional_min: float, inflation: float) -> str:
    """Propose a basket for one symbol from its metrics (SRS criteria)."""
    if m.years_paid == 0 or m.dividend_yield < 0.004:
        return "growth"
    if m.dividend_yield < 0.020 and m.max_single_payout >= fractional_min:
        return "drip"
    if m.years_paid >= 5 and not math.isnan(m.dgr) and m.dgr > inflation and m.dividend_yield >= 0.020:
        return "cashflow"
    return "unclassified"


def screen(symbols: List[str], years: int = 7) -> List[SymbolMetrics]:
    out = []
    for s in symbols:
        m = fetch_metrics(s, years)
        if m is not None:
            out.append(m)
    return out
