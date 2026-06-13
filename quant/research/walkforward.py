"""Walk-forward validation.

The honest way to test a strategy with tunable parameters: repeatedly pick the
best params on a *training* window, then measure performance on the *next,
unseen* window. Stitching those out-of-sample (OOS) windows together gives an
equity curve you never fitted to — much closer to what live trading would feel
like, and a strong defence against overfitting.

    train(3y) -> test(1y) -> roll forward -> train(3y) -> test(1y) -> ...
"""
from __future__ import annotations

from typing import Dict, Sequence

import pandas as pd

from quant.performance.metrics import summary_stats
from quant.research.sweep import run_sweep
from quant.runner import run_backtest


def _generate_windows(start, end, train_years: int, test_years: int):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    windows = []
    train_start = start
    while True:
        train_end = train_start + pd.DateOffset(years=train_years)
        test_start = train_end
        test_end = min(test_start + pd.DateOffset(years=test_years), end)
        if test_start >= end:
            break
        windows.append((train_start, train_end, test_start, test_end))
        train_start = train_start + pd.DateOffset(years=test_years)
    return windows


def _curve_from_total(total: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"total": total})
    df["returns"] = df["total"].pct_change().fillna(0.0)
    df["equity_curve"] = (1.0 + df["returns"]).cumprod()
    return df


def walk_forward(
    symbols,
    start,
    end,
    strategy: str,
    param_grid: Dict[str, Sequence],
    train_years: int = 3,
    test_years: int = 1,
    metric: str = "sharpe",
    maximize: bool = True,
    data_dir: str = "data",
    **common,
) -> Dict:
    """Run walk-forward optimisation.

    Returns a dict with:
      * ``windows``  — one row per window (chosen params + OOS metrics)
      * ``combined`` — stitched OOS equity curve DataFrame
      * ``overall``  — summary stats of the combined OOS curve
    """
    windows = _generate_windows(start, end, train_years, test_years)
    rows = []
    oos_returns = []

    for (tr_s, tr_e, te_s, te_e) in windows:
        sweep_df = run_sweep(symbols, tr_s, tr_e, strategy, param_grid, data_dir=data_dir, **common)
        if sweep_df.empty or metric not in sweep_df.columns:
            continue
        sweep_df = sweep_df.dropna(subset=[metric])
        if sweep_df.empty:
            continue

        best = sweep_df.sort_values(metric, ascending=not maximize).iloc[0]
        best_params = {k: best[k] for k in param_grid.keys()}

        # Re-run from the train start (so indicators warm up) through the test end,
        # then evaluate only the OOS slice.
        res = run_backtest(
            symbols=symbols, start=tr_s, end=te_e, strategy=strategy,
            strategy_params=best_params, data_dir=data_dir, **common,
        )
        eq = res.equity_curve
        oos = eq.loc[(eq.index >= te_s) & (eq.index <= te_e)]
        if oos.empty:
            continue

        oos_curve = _curve_from_total(oos["total"])
        oos_stats = summary_stats(oos_curve)

        row = {
            "train_start": tr_s.date(), "train_end": tr_e.date(),
            "test_start": te_s.date(), "test_end": te_e.date(),
        }
        row.update({f"best_{k}": v for k, v in best_params.items()})
        row.update({f"oos_{k}": oos_stats.get(k) for k in
                    ("total_return", "cagr", "sharpe", "max_drawdown")})
        rows.append(row)
        oos_returns.append(oos_curve["returns"])

    summary = pd.DataFrame(rows)

    combined = None
    overall: Dict = {}
    if oos_returns:
        all_ret = pd.concat(oos_returns).sort_index()
        all_ret = all_ret[~all_ret.index.duplicated(keep="first")]
        combined = pd.DataFrame({"returns": all_ret})
        combined["equity_curve"] = (1.0 + combined["returns"]).cumprod()
        combined["total"] = 100_000.0 * combined["equity_curve"]
        overall = summary_stats(combined)

    return {"windows": summary, "combined": combined, "overall": overall}
