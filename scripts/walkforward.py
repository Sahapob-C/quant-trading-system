"""Walk-forward validation: optimise on training windows, score on unseen ones.

Usage:
    py scripts/walkforward.py --symbols SPY --strategy sma_cross \
        --grid short_window=20,50,100 --grid long_window=150,200,250 \
        --train-years 3 --test-years 1 --metric sharpe
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.performance.metrics import format_stats, plot_performance
from quant.research.walkforward import walk_forward


def _parse_grid(spec: str):
    if "=" not in spec:
        raise argparse.ArgumentTypeError(f"--grid must be key=v1,v2,..., got '{spec}'")
    key, values = spec.split("=", 1)
    out = []
    for v in values.split(","):
        v = v.strip()
        for cast in (int, float):
            try:
                out.append(cast(v))
                break
            except ValueError:
                continue
        else:
            out.append(v)
    return key, out


def main() -> None:
    p = argparse.ArgumentParser(description="Walk-forward validation.")
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--start", default="2015-01-01")
    p.add_argument("--end", default="2024-12-31")
    p.add_argument("--strategy", default="sma_cross")
    p.add_argument("--grid", action="append", type=_parse_grid, default=[], required=True)
    p.add_argument("--train-years", type=int, default=3)
    p.add_argument("--test-years", type=int, default=1)
    p.add_argument("--metric", default="sharpe")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--target-pct", type=float, default=0.10)
    p.add_argument("--slippage-bps", type=float, default=1.0,
                   help="per-trade cost proxy in basis points (5 = 0.05%)")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--out", default="results")
    args = p.parse_args()

    grid = dict(args.grid)
    print(f"Walk-forward {args.strategy} on {', '.join(args.symbols)} | "
          f"train {args.train_years}y / test {args.test_years}y | select by {args.metric}\n")

    out = walk_forward(
        args.symbols, args.start, args.end, args.strategy, grid,
        train_years=args.train_years, test_years=args.test_years, metric=args.metric,
        data_dir=args.data_dir, capital=args.capital,
        risk_params={"target_pct": args.target_pct}, slippage_bps=args.slippage_bps,
    )

    windows = out["windows"]
    if windows.empty:
        print("No walk-forward windows produced — widen the date range or shrink windows.")
        return

    print("Per-window out-of-sample results (params chosen on each training window):\n")
    print(windows.to_string(index=False))

    if out["overall"]:
        print("\nStitched out-of-sample performance (the honest number):")
        print(format_stats(out["overall"], args.capital))

    os.makedirs(args.out, exist_ok=True)
    windows.to_csv(os.path.join(args.out, "walkforward_windows.csv"), index=False)
    if out["combined"] is not None and not out["combined"].empty:
        out["combined"].to_csv(os.path.join(args.out, "walkforward_oos_curve.csv"))
        plot_performance(
            out["combined"], os.path.join(args.out, "walkforward_oos.png"),
            title=f"{'/'.join(args.symbols)} {args.strategy} — out-of-sample (walk-forward)",
        )
        print(f"\nWrote results to {args.out}/ (walkforward_windows.csv, walkforward_oos.png, ...)")


if __name__ == "__main__":
    main()
