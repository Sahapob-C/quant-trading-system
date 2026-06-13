"""Run a backtest end to end and write results to ./results.

Usage:
    py scripts/run_backtest.py --symbols AAPL MSFT SPY --strategy sma_cross \
        --param short_window=50 --param long_window=200

    py scripts/run_backtest.py --symbols AAPL --strategy rsi_reversion \
        --param period=14 --param oversold=25

List available strategies:
    py scripts/run_backtest.py --list

Outputs (in --out, default ./results):
    equity_curve.csv   mark-to-market book per bar
    trades.csv         every simulated fill
    performance.png    equity curve + drawdown
"""
from __future__ import annotations

import argparse
import os
import sys

# Make the `quant` package importable when run as a plain script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.performance.metrics import format_stats, plot_performance
from quant.runner import run_backtest
from quant.strategy.registry import list_strategies


def _parse_param(kv: str):
    """Parse 'key=value', coercing value to int -> float -> str."""
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
    p = argparse.ArgumentParser(description="Run a backtest.")
    p.add_argument("--symbols", nargs="+")
    p.add_argument("--start", default="2015-01-01")
    p.add_argument("--end", default="2024-12-31")
    p.add_argument("--strategy", default="sma_cross")
    p.add_argument("--param", action="append", type=_parse_param, default=[],
                   help="strategy param, e.g. --param short_window=50 (repeatable)")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--target-pct", type=float, default=0.10, help="equity per position")
    p.add_argument("--slippage-bps", type=float, default=1.0)
    p.add_argument("--fill-on", default="next_open", choices=["next_open", "close"],
                   help="next_open = realistic; close = optimistic same-bar (look-ahead)")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--out", default="results")
    p.add_argument("--list", action="store_true", help="list strategies and exit")
    args = p.parse_args()

    if args.list:
        print("Available strategies (with default params):")
        for name, defaults in list_strategies().items():
            print(f"  {name:16s} {defaults}")
        return

    if not args.symbols:
        p.error("--symbols is required (or use --list)")

    strategy_params = dict(args.param)
    print(
        f"Backtest: {', '.join(args.symbols)} | {args.start} -> {args.end} | "
        f"strategy={args.strategy} {strategy_params or ''}"
    )

    result = run_backtest(
        symbols=args.symbols,
        start=args.start,
        end=args.end,
        strategy=args.strategy,
        strategy_params=strategy_params,
        capital=args.capital,
        risk_params={"target_pct": args.target_pct},
        slippage_bps=args.slippage_bps,
        fill_on=args.fill_on,
        data_dir=args.data_dir,
    )

    if result.equity_curve.empty:
        print("No equity curve produced — check your date range / data.")
        return

    print(f"\nProcessed {result.n_bars} bars.\n")
    print(format_stats(result.stats, args.capital))

    os.makedirs(args.out, exist_ok=True)
    eq_path = os.path.join(args.out, "equity_curve.csv")
    trades_path = os.path.join(args.out, "trades.csv")
    png_path = os.path.join(args.out, "performance.png")

    result.equity_curve.to_csv(eq_path)
    result.fills.to_csv(trades_path, index=False)
    plot_performance(
        result.equity_curve, png_path,
        title=f"{'/'.join(args.symbols)}  {args.strategy} {strategy_params or ''}",
    )

    print(f"\nWrote:\n  {eq_path}\n  {trades_path}\n  {png_path}")
    print(f"Total fills: {len(result.fills)}")


if __name__ == "__main__":
    main()
