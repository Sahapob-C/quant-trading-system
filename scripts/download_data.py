"""Download historical OHLCV data into ./data as parquet.

Usage:
    py scripts/download_data.py --symbols AAPL MSFT SPY --start 2015-01-01 --end 2024-12-31
"""
from __future__ import annotations

import argparse
import os
import sys

# Make the `quant` package importable when run as a plain script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.data.loaders import download_to_parquet


def main() -> None:
    p = argparse.ArgumentParser(description="Download OHLCV data to parquet.")
    p.add_argument("--symbols", nargs="+", required=True, help="Tickers, e.g. AAPL MSFT SPY")
    p.add_argument("--start", default="2015-01-01")
    p.add_argument("--end", default="2024-12-31")
    p.add_argument("--interval", default="1d", help="1d, 1h, 1wk, ...")
    p.add_argument("--data-dir", default="data")
    args = p.parse_args()

    print(f"Downloading {len(args.symbols)} symbol(s) [{args.start} -> {args.end}] ...")
    saved = download_to_parquet(
        args.symbols, args.start, args.end, args.data_dir, interval=args.interval
    )
    print(f"\nDone. Saved {len(saved)}/{len(args.symbols)} symbol(s) to {args.data_dir}/")


if __name__ == "__main__":
    main()
