"""Buy-and-hold benchmark — the bar every strategy must clear.

Equal-dollar buy-and-hold of the universe at the start date (no rebalancing).
If a strategy can't beat this on a risk-adjusted basis, it isn't adding value.
"""
from __future__ import annotations

import os

import pandas as pd

from quant.performance.metrics import summary_stats


def buy_and_hold(symbols, start, end, data_dir: str = "data") -> pd.DataFrame:
    """Return an equity-curve DataFrame (total / returns / equity_curve)."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    norm = []
    for s in symbols:
        df = pd.read_parquet(os.path.join(data_dir, f"{s}.parquet"))
        df.columns = [str(c).lower() for c in df.columns]
        close = df["close"].sort_index()
        close = close[(close.index >= start) & (close.index <= end)]
        if close.empty:
            continue
        norm.append((close / close.iloc[0]).rename(s))

    prices = pd.concat(norm, axis=1).dropna()
    # Equal-dollar at t0: portfolio value = mean of each name's growth factor.
    equity = prices.mean(axis=1)

    out = pd.DataFrame({"equity_curve": equity})
    out["returns"] = out["equity_curve"].pct_change().fillna(0.0)
    out["total"] = 100_000.0 * out["equity_curve"]
    return out


def benchmark_stats(symbols, start, end, data_dir: str = "data") -> dict:
    return summary_stats(buy_and_hold(symbols, start, end, data_dir))
