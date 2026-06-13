"""Run a strategy live against Alpaca paper trading.

The SAME strategy / portfolio / risk code as the backtest — only the data and
execution handlers are swapped for Alpaca ones. On startup it reconciles the
engine's book with your account (positions + cash), journals every fill, and
sends alerts.

Usage (during US market hours):
    py scripts/paper_trade.py --symbols AAPL MSFT SPY --strategy sma_cross \
        --param short_window=50 --param long_window=200 \
        --timeframe minute --poll 60

Safe dry run (warm up + sync + snapshot, then exit — never places an order):
    py scripts/paper_trade.py --symbols SPY --strategy sma_cross --setup-only

Notes:
  * --timeframe day polls once a day for a new bar; use minute to see action fast.
  * Ctrl-C to stop. ALPACA_PAPER=true in .env (the default) keeps it on fake money.
  * Set ALERT_WEBHOOK_URL in .env to also push alerts to Slack/Discord.
"""
from __future__ import annotations

import argparse
import os
import queue
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.core.engine import TradingEngine
from quant.data.alpaca_data import AlpacaDataHandler
from quant.execution.alpaca_exec import AlpacaExecutionHandler
from quant.live.journal import TradeJournal
from quant.live.notify import build_notifier
from quant.live.sync import sync_portfolio_from_broker, sync_strategy_invested
from quant.portfolio.portfolio import Portfolio
from quant.risk.risk import RiskManager
from quant.settings import use_paper
from quant.strategy.registry import build_strategy


def _parse_param(kv: str):
    if "=" not in kv:
        raise argparse.ArgumentTypeError(f"--param must be key=value, got '{kv}'")
    key, value = kv.split("=", 1)
    for cast in (int, float):
        try:
            return key, cast(value)
        except ValueError:
            continue
    return key, value


def main() -> None:
    p = argparse.ArgumentParser(description="Alpaca paper trading.")
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--strategy", default="sma_cross")
    p.add_argument("--param", action="append", type=_parse_param, default=[])
    p.add_argument("--timeframe", default="day", choices=["day", "hour", "minute"])
    p.add_argument("--warmup", type=int, default=300, help="bars of history to load on startup")
    p.add_argument("--poll", type=float, default=60.0, help="seconds between polls")
    p.add_argument("--target-pct", type=float, default=0.10)
    p.add_argument("--iterations", type=int, default=None, help="stop after N polls (default: forever)")
    p.add_argument("--state-dir", default="state", help="where to write the trade journal")
    p.add_argument("--setup-only", action="store_true",
                   help="warm up + sync + snapshot, then exit without trading")
    args = p.parse_args()

    if not use_paper():
        print("=" * 64)
        print(" WARNING: ALPACA_PAPER=false -> LIVE trading with REAL money.")
        print(" Set ALPACA_PAPER=true in .env unless you really mean it.")
        print("=" * 64)
        if input(" Type 'LIVE' to continue: ").strip() != "LIVE":
            print("Aborted.")
            return

    strategy_params = dict(args.param)
    events: "queue.Queue" = queue.Queue()
    notifier = build_notifier()
    journal = TradeJournal(args.state_dir)

    print(f"Connecting to Alpaca ({'paper' if use_paper() else 'LIVE'}) ...")
    data = AlpacaDataHandler(events, args.symbols, timeframe=args.timeframe, warmup=args.warmup)
    execution = AlpacaExecutionHandler(events)

    strategy = build_strategy(args.strategy, events, data, args.symbols, strategy_params)
    risk = RiskManager(target_pct=args.target_pct)

    def _on_fill(fill):
        journal.write_fill(fill)
        notifier.notify(
            "FILL",
            f"{fill.direction} {fill.quantity} {fill.symbol} @ {fill.fill_price:.2f}",
        )

    portfolio = Portfolio(
        events, data, args.symbols, datetime.now(),
        risk_manager=risk, on_fill=_on_fill,
    )

    # --- reconcile engine book with the broker ---
    held = sync_portfolio_from_broker(portfolio, execution.client)
    sync_strategy_invested(strategy, held)
    print(f"Synced from account: equity {portfolio.equity:,.2f} | "
          f"positions {held or '{}'}")
    journal.snapshot(portfolio.equity, dict(portfolio.current_positions), {"phase": "startup"})

    if args.setup_only:
        print("--setup-only: warm-up + sync complete, exiting without trading.")
        return

    engine = TradingEngine(events, data, strategy, portfolio, execution)

    notifier.notify("START", f"{args.strategy} on {', '.join(args.symbols)} ({args.timeframe})")
    print(f"\nTrading {args.strategy} {strategy_params or ''} | {args.timeframe} bars | "
          f"polling every {args.poll:.0f}s | Ctrl-C to stop\n")

    def _on_iteration(i):
        journal.snapshot(portfolio.equity, dict(portfolio.current_positions),
                         {"phase": "running", "iteration": i})

    n = engine.run_live(poll_interval=args.poll, max_iterations=args.iterations,
                        on_iteration=_on_iteration)

    journal.snapshot(portfolio.equity, dict(portfolio.current_positions), {"phase": "stopped"})
    notifier.notify("STOP", f"stopped after {n} polls | equity {portfolio.equity:,.2f}")


if __name__ == "__main__":
    main()
