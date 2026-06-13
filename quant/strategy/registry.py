"""Strategy registry: build a strategy by name with optional parameter overrides.

This is what lets the CLI, parameter sweeps, walk-forward and the notebook all
refer to strategies by a short string (``"sma_cross"``) and pass params as a dict.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple, Type

from quant.strategy.base import Strategy
from quant.strategy.examples import (
    BollingerBandStrategy,
    CrossSectionalMomentumStrategy,
    DonchianBreakoutStrategy,
    MomentumStrategy,
    MovingAverageCrossStrategy,
    RSIMeanReversionStrategy,
)

# name -> (class, default params)
STRATEGIES: Dict[str, Tuple[Type[Strategy], dict]] = {
    "sma_cross": (MovingAverageCrossStrategy, {"short_window": 50, "long_window": 200}),
    "momentum": (MomentumStrategy, {"lookback": 126, "trend_window": 200}),
    "rsi_reversion": (RSIMeanReversionStrategy, {"period": 14, "oversold": 30.0, "exit_level": 50.0}),
    "bollinger": (BollingerBandStrategy, {"window": 20, "num_std": 2.0}),
    "donchian": (DonchianBreakoutStrategy, {"entry_window": 20, "exit_window": 10}),
    "xs_momentum": (CrossSectionalMomentumStrategy, {"lookback": 126, "top_k": 2, "rebalance_days": 21}),
}


def list_strategies() -> Dict[str, dict]:
    """Return ``{name: default_params}`` for everything registered."""
    return {name: dict(defaults) for name, (_, defaults) in STRATEGIES.items()}


def build_strategy(name, events, data_handler, symbol_list, params: Optional[dict] = None) -> Strategy:
    if name not in STRATEGIES:
        raise KeyError(f"Unknown strategy '{name}'. Available: {sorted(STRATEGIES)}")
    cls, defaults = STRATEGIES[name]
    merged = {**defaults, **(params or {})}
    return cls(events, data_handler, symbol_list, **merged)
