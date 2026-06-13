"""Parameter sweep: run one backtest per parameter combination.

Returns a tidy DataFrame (one row per combo, columns = params + metrics) that you
can sort, filter, or pivot into a heatmap. Useful for *seeing the shape* of a
strategy's parameter space — but beware: the best in-sample cell is usually
partly luck. Confirm it with walk-forward before believing it.
"""
from __future__ import annotations

import itertools
from typing import Dict, List, Sequence

import pandas as pd

from quant.runner import run_backtest


def run_sweep(
    symbols,
    start,
    end,
    strategy: str,
    param_grid: Dict[str, Sequence],
    data_dir: str = "data",
    **common,
) -> pd.DataFrame:
    """Cartesian-product sweep over ``param_grid`` ({param: [values, ...]})."""
    keys: List[str] = list(param_grid.keys())
    rows = []

    for combo in itertools.product(*(param_grid[k] for k in keys)):
        params = dict(zip(keys, combo))
        try:
            res = run_backtest(
                symbols=symbols, start=start, end=end, strategy=strategy,
                strategy_params=params, data_dir=data_dir, **common,
            )
        except Exception as exc:  # a bad combo shouldn't kill the whole sweep
            rows.append({**params, "error": str(exc)})
            continue
        row = dict(params)
        row.update(res.stats)
        row["n_fills"] = len(res.fills)
        rows.append(row)

    return pd.DataFrame(rows)
