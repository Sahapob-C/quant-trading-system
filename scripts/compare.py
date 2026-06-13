"""Compare every strategy against a buy-and-hold benchmark.

Usage:
    py scripts/compare.py --symbols AAPL MSFT SPY GOOGL AMZN NVDA META JPM XOM JNJ \
        --start 2015-01-01 --end 2024-12-31

Prints a ranked table and saves results/compare.png (equity curves + benchmark).

Note on fairness: the benchmark is ~100% invested; the example strategies hold
cash much of the time (target_pct per position), so raw return is NOT directly
comparable. Judge edge by SHARPE and MAX DRAWDOWN, not headline return.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from quant.research.benchmark import buy_and_hold
from quant.runner import run_backtest
from quant.strategy.registry import list_strategies


def main() -> None:
    p = argparse.ArgumentParser(description="Compare strategies vs buy-and-hold.")
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--start", default="2015-01-01")
    p.add_argument("--end", default="2024-12-31")
    p.add_argument("--strategies", nargs="+", default=None, help="subset (default: all)")
    p.add_argument("--target-pct", type=float, default=0.10)
    p.add_argument("--fill-on", default="next_open", choices=["next_open", "close"])
    p.add_argument("--slippage-bps", type=float, default=1.0,
                   help="per-trade cost proxy in basis points (5 = 0.05%)")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--out", default="results")
    args = p.parse_args()

    names = args.strategies or list(list_strategies().keys())
    metrics = ("total_return", "cagr", "ann_volatility", "sharpe", "max_drawdown", "calmar")

    rows, curves = [], {}

    # Benchmark first.
    bench = buy_and_hold(args.symbols, args.start, args.end, args.data_dir)
    from quant.performance.metrics import summary_stats
    bstats = summary_stats(bench)
    curves["Buy & Hold"] = bench["equity_curve"]
    rows.append({"strategy": "Buy & Hold", **{m: bstats.get(m) for m in metrics}, "n_fills": 0})
    bench_sharpe = bstats.get("sharpe", float("nan"))

    for name in names:
        res = run_backtest(
            symbols=args.symbols, start=args.start, end=args.end, strategy=name,
            risk_params={"target_pct": args.target_pct}, fill_on=args.fill_on,
            slippage_bps=args.slippage_bps, data_dir=args.data_dir,
        )
        if res.equity_curve.empty:
            continue
        curves[name] = res.equity_curve["equity_curve"]
        rows.append({"strategy": name, **{m: res.stats.get(m) for m in metrics},
                     "n_fills": len(res.fills)})

    table = pd.DataFrame(rows).set_index("strategy")
    table["beats_B&H_sharpe"] = table["sharpe"] > bench_sharpe
    table = table.sort_values("sharpe", ascending=False)

    pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
    print(f"\n{', '.join(args.symbols)} | {args.start} -> {args.end} | "
          f"fill_on={args.fill_on} | target_pct={args.target_pct}\n")
    print(table.to_string())
    print("\n(Sharpe & max_drawdown are the fair comparison - see header note.)")

    # Overlay plot.
    os.makedirs(args.out, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.figure(figsize=(12, 6))
    for label, c in curves.items():
        style = dict(linewidth=2.2, color="black") if label == "Buy & Hold" else dict(linewidth=1.3)
        plt.plot(c.index, c.values, label=label, **style)
    plt.legend(); plt.title("Strategies vs Buy & Hold"); plt.ylabel("Growth of $1")
    plt.grid(alpha=0.3)
    png = os.path.join(args.out, "compare.png")
    plt.savefig(png, dpi=120, bbox_inches="tight")
    plt.close()

    table.to_csv(os.path.join(args.out, "compare.csv"))
    print(f"\nWrote {png} and {os.path.join(args.out, 'compare.csv')}")


if __name__ == "__main__":
    main()
