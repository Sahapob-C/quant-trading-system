"""Performance statistics and plots computed from an equity-curve DataFrame.

The input is the frame produced by ``Portfolio.equity_curve()`` — it must have a
DatetimeIndex and the columns ``total``, ``returns`` and ``equity_curve``.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

# Trading periods per year, by bar frequency. Daily bars -> 252.
PERIODS_PER_YEAR = 252


def sharpe_ratio(returns: pd.Series, periods: int = PERIODS_PER_YEAR, rf: float = 0.0) -> float:
    """Annualised Sharpe ratio of a per-period return series."""
    excess = returns - rf / periods
    std = excess.std()
    if std == 0 or np.isnan(std):
        return 0.0
    return float(np.sqrt(periods) * excess.mean() / std)


def sortino_ratio(returns: pd.Series, periods: int = PERIODS_PER_YEAR) -> float:
    downside = returns[returns < 0].std()
    if downside == 0 or np.isnan(downside):
        return 0.0
    return float(np.sqrt(periods) * returns.mean() / downside)


def drawdown_series(equity_curve: pd.Series) -> pd.Series:
    """Fractional drawdown from the running peak (<= 0)."""
    running_max = equity_curve.cummax()
    return (equity_curve - running_max) / running_max


def summary_stats(eq_df: pd.DataFrame, periods: int = PERIODS_PER_YEAR) -> Dict[str, float]:
    """Headline metrics: return, CAGR, vol, Sharpe, Sortino, max drawdown."""
    eq = eq_df["equity_curve"]
    returns = eq_df["returns"]
    n = len(eq)
    if n == 0:
        return {}

    final = float(eq.iloc[-1])
    total_return = final - 1.0
    cagr = final ** (periods / n) - 1.0 if n > 0 and final > 0 else float("nan")
    ann_vol = float(returns.std() * np.sqrt(periods))
    dd = drawdown_series(eq)
    max_dd = float(dd.min())
    # Calmar: CAGR over the worst drawdown.
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else float("nan")

    return {
        "total_return": total_return,
        "cagr": cagr,
        "ann_volatility": ann_vol,
        "sharpe": sharpe_ratio(returns, periods),
        "sortino": sortino_ratio(returns, periods),
        "max_drawdown": max_dd,
        "calmar": calmar,
        "bars": n,
        "final_equity": float(eq_df["total"].iloc[-1]),
    }


def format_stats(stats: Dict[str, float], initial_capital: float) -> str:
    """A human-readable summary block."""
    if not stats:
        return "No statistics (empty equity curve)."
    lines = [
        f"  Start equity      : {initial_capital:,.2f}",
        f"  Final equity      : {stats['final_equity']:,.2f}",
        f"  Total return      : {stats['total_return'] * 100:,.2f}%",
        f"  CAGR              : {stats['cagr'] * 100:,.2f}%",
        f"  Annual volatility : {stats['ann_volatility'] * 100:,.2f}%",
        f"  Sharpe ratio      : {stats['sharpe']:.2f}",
        f"  Sortino ratio     : {stats['sortino']:.2f}",
        f"  Max drawdown      : {stats['max_drawdown'] * 100:,.2f}%",
        f"  Calmar ratio      : {stats['calmar']:.2f}",
        f"  Bars              : {stats['bars']}",
    ]
    return "\n".join(lines)


def plot_performance(eq_df: pd.DataFrame, out_path: str, title: str = "Backtest") -> None:
    """Save an equity-curve + drawdown PNG to ``out_path``."""
    import matplotlib

    matplotlib.use("Agg")  # headless: no display needed
    import matplotlib.pyplot as plt

    eq = eq_df["equity_curve"]
    dd = drawdown_series(eq) * 100.0

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    ax1.plot(eq.index, eq.values, color="#0F6E56", linewidth=1.4)
    ax1.set_title(title)
    ax1.set_ylabel("Growth of $1")
    ax1.grid(True, alpha=0.3)

    ax2.fill_between(dd.index, dd.values, 0.0, color="#A32D2D", alpha=0.35)
    ax2.set_ylabel("Drawdown %")
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
