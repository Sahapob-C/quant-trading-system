"""Verify Alpaca credentials and data access before trading.

Usage:
    py scripts/check_alpaca.py

Reads keys from .env (copy .env.example first). Safe: read-only, places no orders.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.settings import get_alpaca_creds, use_paper


def main() -> None:
    key, secret = get_alpaca_creds()
    paper = use_paper()
    mode = "PAPER (fake money)" if paper else "LIVE (REAL money!)"
    print(f"Mode: {mode}\n")

    # --- account / trading API ---
    from alpaca.trading.client import TradingClient

    trading = TradingClient(key, secret, paper=paper)
    acct = trading.get_account()
    print("Account")
    print(f"  number       : {acct.account_number}")
    print(f"  status       : {acct.status}")
    print(f"  cash         : {float(acct.cash):,.2f}")
    print(f"  equity       : {float(acct.equity):,.2f}")
    print(f"  buying power : {float(acct.buying_power):,.2f}")

    positions = trading.get_all_positions()
    print(f"  open positions: {len(positions)}")
    for p in positions[:10]:
        print(f"     {p.symbol}: {p.qty} @ {float(p.avg_entry_price):.2f} "
              f"(P/L {float(p.unrealized_pl):,.2f})")

    # --- market data API ---
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    data = StockHistoricalDataClient(key, secret)
    req = StockBarsRequest(
        symbol_or_symbols=["SPY"],
        timeframe=TimeFrame.Day,
        start=datetime.now(timezone.utc) - timedelta(days=10),
        feed=DataFeed.IEX,
    )
    bars = data.get_stock_bars(req).df
    print("\nMarket data (SPY, last 3 daily bars via IEX):")
    if bars is None or bars.empty:
        print("  ! no data returned — check market-data entitlements")
    else:
        print(bars.tail(3).to_string())

    print("\nOK - credentials and data access look good.")


if __name__ == "__main__":
    main()
