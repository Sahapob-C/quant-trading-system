"""Parameter sweep over a grid, ranked by a chosen metric.

Usage:
    py scripts/sweep.py --symbols SPY --strategy sma_cross \
        --grid short_window=20,50,100 --grid long_window=150,200,250 --metric sharpe

A 2-parameter grid also writes a heatmap to results/sweep_heatmap.png.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.research.sweep import run_sweep


def _parse_grid(spec: str):
    """'key=1,2,3' -> ('key', [1, 2, 3]) with int/float coercion."""
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


def _heatmap(df, keys, metric, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pivot = df.pivot_table(index=keys[0], columns=keys[1], values=metric)
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(pivot.values, aspect="auto", cmap="viridis", origin="lower")
    ax.set_xticks(range(len(pivot.columns)), [str(c) for c in pivot.columns])
    ax.set_yticks(range(len(pivot.index)), [str(i) for i in pivot.index])
    ax.set_xlabel(keys[1])
    ax.set_ylabel(keys[0])
    ax.set_title(f"{metric} across {keys[0]} x {keys[1]}")
    for (i, j), val in zip([(i, j) for i in range(pivot.shape[0]) for j in range(pivot.shape[1])],
                           pivot.values.flatten()):
        if val == val:  # not NaN
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    color="white", fontsize=8)
    fig.colorbar(im, ax=ax, label=metric)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(description="Parameter sweep.")
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--start", default="2015-01-01")
    p.add_argument("--end", default="2024-12-31")
    p.add_argument("--strategy", default="sma_cross")
    p.add_argument("--grid", action="append", type=_parse_grid, default=[], required=True,
                   help="param grid, e.g. --grid short_window=20,50,100 (repeatable)")
    p.add_argument("--metric", default="sharpe")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--target-pct", type=float, default=0.10)
    p.add_argument("--data-dir", default="data")
    p.add_argument("--out", default="results")
    p.add_argument("--top", type=int, default=15)
    args = p.parse_args()

    grid = dict(args.grid)
    n_combos = 1
    for v in grid.values():
        n_combos *= len(v)
    print(f"Sweeping {args.strategy} on {', '.join(args.symbols)} | "
          f"{n_combos} combos | ranking by {args.metric}\n")

    df = run_sweep(
        args.symbols, args.start, args.end, args.strategy, grid,
        data_dir=args.data_dir, capital=args.capital,
        risk_params={"target_pct": args.target_pct},
    )

    if args.metric in df.columns:
        df = df.sort_values(args.metric, ascending=False)

    cols = list(grid.keys()) + [c for c in
                ("sharpe", "cagr", "total_return", "max_drawdown", "n_fills")
                if c in df.columns]
    with_pct = df.copy()
    print(with_pct[cols].head(args.top).to_string(index=False))

    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, "sweep.csv")
    df.to_csv(csv_path, index=False)
    print(f"\nWrote {csv_path}")

    keys = list(grid.keys())
    if len(keys) == 2 and args.metric in df.columns:
        png = os.path.join(args.out, "sweep_heatmap.png")
        _heatmap(df, keys, args.metric, png)
        print(f"Wrote {png}")


if __name__ == "__main__":
    main()
