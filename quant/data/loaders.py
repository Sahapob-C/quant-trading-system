"""Download and save historical market data from free sources (yfinance).

All data is saved as parquet files for efficient loading and querying.
"""
from __future__ import annotations

import os
from typing import List, Optional

import pandas as pd
import yfinance as yf


def download_to_parquet(
    symbols: List[str],
    start: str,
    end: str,
    data_dir: str = "data",
    interval: str = "1d",
) -> List[str]:
    """Download OHLCV data from yfinance and save as parquet files.

    Args:
        symbols: List of ticker symbols (e.g., ["AAPL", "MSFT", "SPY"]).
        start: Start date (inclusive) as "YYYY-MM-DD".
        end: End date (inclusive) as "YYYY-MM-DD".
        data_dir: Directory to save {symbol}.parquet files (created if missing).
        interval: Bar frequency: "1d", "1h", "5m", "1m", etc.

    Returns:
        List of successfully downloaded symbols (subset of input).

    Example:
        saved = download_to_parquet(
            ["AAPL", "MSFT", "SPY"],
            "2015-01-01",
            "2024-12-31"
        )
        print(f"Downloaded {len(saved)} symbols")
    """
    os.makedirs(data_dir, exist_ok=True)
    saved = []

    for symbol in symbols:
        try:
            print(f"Downloading {symbol} [{start} -> {end}] ...", end=" ", flush=True)
            df = yf.download(
                symbol,
                start=start,
                end=end,
                interval=interval,
                progress=False,
            )
            if df.empty:
                print("No data")
                continue

            # Normalize column names to lowercase
            df.columns = [col.lower() for col in df.columns]
            path = os.path.join(data_dir, f"{symbol}.parquet")
            df.to_parquet(path)
            print(f"✓ ({len(df)} bars)")
            saved.append(symbol)
        except Exception as exc:
            print(f"✗ Error: {exc}")
            continue

    return saved
