"""Screen a candidate pool into the three baskets, with the SRS metrics shown.

    py scripts/build_baskets.py

Prints a metrics table + a recommended membership list for each basket. Review
it, then paste the picks into config/wealth.yaml (we keep the human in the loop
for what the portfolio actually holds).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.wealth.config import load_wealth_config
from quant.wealth.screener import classify, screen

CFG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "wealth.yaml")

# Diversified large-cap candidate pool (income / premium / growth).
POOL = [
    "KO", "PG", "JNJ", "PEP", "MCD", "CL", "KMB", "ABBV", "ABT", "ITW",
    "MMM", "HD", "LOW", "CAT", "CVX", "XOM", "O", "T", "VZ",
    "AVGO", "COST", "UNH", "LMT", "BLK", "GS", "TXN", "AMGN", "MSFT",
    "NVDA", "AMZN", "META", "GOOGL", "AAPL",
]


def main() -> None:
    cfg = load_wealth_config(CFG_PATH)
    fractional_min = cfg.baskets.drip_min_fractional_usd
    inflation = (cfg.waterfall.annual_cpi_pct + cfg.waterfall.inflation_buffer_pct) / 100.0

    print(f"Screening {len(POOL)} candidates "
          f"(fractional_min=${fractional_min:.2f}, inflation hurdle={inflation*100:.1f}%) ...\n")
    metrics = screen(POOL)

    for m in metrics:
        m.basket = classify(m, fractional_min, inflation)  # type: ignore[attr-defined]

    metrics.sort(key=lambda m: (m.basket, -m.dividend_yield))

    head = f"{'sym':6}{'price':>9}{'annDiv':>8}{'yield%':>8}{'DGR%':>8}{'yrs':>5}{'maxPay':>8}{'priceCAGR%':>12}  basket"
    print(head)
    print("-" * len(head))
    for m in metrics:
        dgr = "  n/a" if m.dgr != m.dgr else f"{m.dgr*100:6.1f}"
        pc = "  n/a" if m.price_cagr != m.price_cagr else f"{m.price_cagr*100:8.1f}"
        print(f"{m.symbol:6}{m.last_price:9.2f}{m.annual_dividend:8.2f}{m.dividend_yield*100:8.2f}"
              f"{dgr:>8}{m.years_paid:5d}{m.max_single_payout:8.2f}{pc:>12}  {m.basket}")

    def pick(basket, key, n):
        items = [m for m in metrics if m.basket == basket]
        items.sort(key=key, reverse=True)
        return [m.symbol for m in items[:n]]

    cashflow = pick("cashflow", lambda m: (0 if m.dgr != m.dgr else m.dgr, m.dividend_yield), 6)
    drip = pick("drip", lambda m: m.annual_dividend, 5)
    growth = pick("growth", lambda m: (0 if m.price_cagr != m.price_cagr else m.price_cagr), 5)

    print("\nRecommended baskets:")
    print(f"  cashflow (DGR > inflation)        : {cashflow}")
    print(f"  drip (high DPS, payout >= ${fractional_min:.0f}) : {drip}")
    print(f"  growth (price appreciation)       : {growth}")
    print("\nPaste these into config/wealth.yaml -> baskets:")


if __name__ == "__main__":
    main()
