"""Run grid-bot for B1 (Tier 2+).

Usage (dry-run):
    py scripts/run_grid_bot.py --symbol SPY --setup-only

Usage (send to Alpaca):
    py scripts/run_grid_bot.py --symbol SPY --exec

Requires capital >= 50,000 THB (Tier 2).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.wealth.grid_bot import GridBot
from quant.wealth.portfolio_state import PortfolioState

STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "state", "portfolio.json",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid Bot for B1 (Tier 2+)")
    parser.add_argument("--symbol", required=True, help="Trade symbol (e.g. SPY)")
    parser.add_argument("--midpoint", type=float, help="Grid midpoint (default: fetch live)")
    parser.add_argument("--grid-width", type=float, default=2.0, help="Grid width % (default 2%)")
    parser.add_argument("--levels", type=int, default=5, help="Grid levels (default 5)")
    parser.add_argument("--position-size", type=float, default=500.0, help="Position size USD")
    parser.add_argument("--setup-only", action="store_true", help="Dry-run (no orders)")
    parser.add_argument("--exec", action="store_true", help="Send orders to Alpaca")

    args = parser.parse_args()

    state = PortfolioState.load(STATE_PATH)
    if state.capital_thb < 50_000:
        print(f"[!] GridBot requires Tier 2+ (>= 50k THB). You have {state.capital_thb:,.0f} THB")
        return

    # Fetch live price if not provided
    if args.midpoint is None:
        try:
            import yfinance as yf
            ticker = yf.Ticker(args.symbol)
            args.midpoint = ticker.info.get("currentPrice") or ticker.history(period="1d")["Close"].iloc[-1]
        except Exception as e:
            print(f"[!] Could not fetch {args.symbol} price: {e}")
            return

    print("=" * 56)
    print(f"  GRID BOT: {args.symbol}")
    print("=" * 56)
    print()

    bot = GridBot(
        symbol=args.symbol,
        midpoint=args.midpoint,
        grid_width_pct=args.grid_width,
        levels=args.levels,
        position_size_usd=args.position_size,
    )

    print(bot.summary())
    print()

    if args.setup_only:
        print("  (dry-run — add --exec to send orders)")
    elif args.exec:
        print("  [EXEC] Sending orders to Alpaca paper...")
        # TODO: wire to Alpaca
        print("  (not yet implemented)")

    print("=" * 56)


if __name__ == "__main__":
    main()
