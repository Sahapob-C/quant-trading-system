"""Reusable backtest wiring.

One function builds the whole event-driven stack, runs it, and returns the
results. The CLI script, parameter sweeps, walk-forward and the notebook all call
this so there is exactly one definition of "what a backtest is".
"""
from __future__ import annotations

import queue
from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from quant.core.engine import TradingEngine
from quant.data.historic import HistoricParquetDataHandler
from quant.execution.simulated import SimulatedExecutionHandler, zero_commission
from quant.performance.metrics import summary_stats
from quant.portfolio.portfolio import Portfolio
from quant.risk.risk import RiskManager
from quant.strategy.registry import build_strategy


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame
    stats: dict
    fills: pd.DataFrame
    portfolio: Portfolio
    n_bars: int


def run_backtest(
    symbols,
    start,
    end,
    strategy: str = "sma_cross",
    strategy_params: Optional[dict] = None,
    capital: float = 100_000.0,
    risk_params: Optional[dict] = None,
    slippage_bps: float = 1.0,
    commission: Optional[Callable[[int, float], float]] = None,
    fill_on: str = "next_open",
    data_dir: str = "data",
) -> BacktestResult:
    events: "queue.Queue" = queue.Queue()

    data = HistoricParquetDataHandler(events, data_dir, symbols, start=start, end=end)
    strat = build_strategy(strategy, events, data, symbols, strategy_params)
    risk = RiskManager(**(risk_params or {}))
    portfolio = Portfolio(events, data, symbols, start, initial_capital=capital, risk_manager=risk)
    execution = SimulatedExecutionHandler(
        events, data, slippage_bps=slippage_bps,
        commission=commission or zero_commission, fill_on=fill_on,
    )
    engine = TradingEngine(events, data, strat, portfolio, execution)

    n_bars = engine.run_backtest()
    eq = portfolio.equity_curve()
    stats = summary_stats(eq) if not eq.empty else {}

    return BacktestResult(
        equity_curve=eq,
        stats=stats,
        fills=portfolio.fills_dataframe(),
        portfolio=portfolio,
        n_bars=n_bars,
    )
