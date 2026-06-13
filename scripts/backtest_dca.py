"""Backtest DCA strategy on historical data (2023–2026).

Simple DCA: buy equal-weight baskets monthly with $30 (1,050 THB).
Compare: final equity vs buy-and-hold SPY.

    py scripts/backtest_dca.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Symbols from B3 + B4
SYMBOLS = ["AAPL", "NVDA", "GOOGL", "MSFT", "AMZN", "OKLO", "NNE", "SMR", "CEG", "VST"]


def load_data(symbol: str) -> pd.DataFrame | None:
    path = os.path.join(DATA_DIR, f"{symbol}.parquet")
    if not os.path.exists(path):
        return None
    df = pd.read_parquet(path)
    df = df.sort_index()
    return df


def backtest_dca(monthly_usd: float = 30.0) -> dict:
    """Simulate monthly DCA purchases across 10 symbols."""
    dfs = {}
    for sym in SYMBOLS:
        df = load_data(sym)
        if df is None:
            print(f"  ⚠ {sym} not found")
            continue
        dfs[sym] = df

    if not dfs:
        print("  ERROR: no data files found")
        return {}

    # Get common date range
    min_date = max(df.index.min() for df in dfs.values())
    max_date = min(df.index.max() for df in dfs.values())
    print(f"  Date range: {min_date.date()} -> {max_date.date()}")

    # Monthly DCA loop
    holdings = {sym: 0.0 for sym in dfs.keys()}
    per_sym = monthly_usd / len(dfs)

    current_date = min_date
    month_count = 0

    while current_date <= max_date:
        # Find first trading day >= current_date for each symbol
        for sym, df in dfs.items():
            mask = df.index >= current_date
            if mask.any():
                close_price = df.loc[mask].iloc[0]["close"]
                shares = per_sym / close_price
                holdings[sym] += shares

        month_count += 1
        current_date += timedelta(days=30)

    # Final equity at max_date
    final_equity = 0.0
    for sym, df in dfs.items():
        close_price = df.iloc[-1]["close"]
        final_equity += holdings[sym] * close_price

    # Buy-and-hold SPY for comparison
    spy_df = load_data("SPY")
    if spy_df is not None:
        spy_df = spy_df[(spy_df.index >= min_date) & (spy_df.index <= max_date)]
        spy_start = spy_df.iloc[0]["close"]
        spy_end = spy_df.iloc[-1]["close"]
        spy_return = (spy_end / spy_start - 1) * 100
    else:
        spy_return = None

    total_invested = per_sym * len(dfs) * month_count
    dca_return = (final_equity / total_invested - 1) * 100 if total_invested > 0 else 0

    return {
        "months": month_count,
        "total_invested": total_invested,
        "final_equity": final_equity,
        "dca_return_pct": dca_return,
        "spy_return_pct": spy_return,
        "holdings": holdings,
    }


def main() -> None:
    print("=" * 56)
    print("  BACKTEST: DCA Strategy (2023–2026)")
    print("=" * 56)
    print(f"  Monthly: ${30:.2f} -> {10} symbols (equal weight)")
    print()

    result = backtest_dca(monthly_usd=30.0)

    if result:
        print(f"  Period: {result['months']} months")
        print(f"  Total invested: ${result['total_invested']:,.2f}")
        print(f"  Final equity: ${result['final_equity']:,.2f}")
        print(f"  DCA return: {result['dca_return_pct']:.2f}%")
        if result["spy_return_pct"] is not None:
            print(f"  SPY return: {result['spy_return_pct']:.2f}%")
            if result["dca_return_pct"] > result["spy_return_pct"]:
                print(f"  [OK] DCA beat SPY by {result['dca_return_pct'] - result['spy_return_pct']:.2f}%")
            else:
                print(f"  [!] SPY beat DCA by {result['spy_return_pct'] - result['dca_return_pct']:.2f}%")
        print()
        print("  Holdings (shares):")
        for sym, qty in result["holdings"].items():
            print(f"    {sym}: {qty:.4f}")

    print("=" * 56)


if __name__ == "__main__":
    main()
