"""Small, dependency-free technical indicators.

Each function takes a 1-D array of values (oldest first, as returned by
``DataHandler.get_latest_bars_values``) and returns the *latest* value. Keeping
them here means strategies stay readable and indicators are unit-testable on
their own.
"""
from __future__ import annotations

import numpy as np


def sma(values: np.ndarray, n: int) -> float:
    """Simple moving average of the last ``n`` values."""
    return float(np.mean(values[-n:]))


def ema(values: np.ndarray, n: int) -> float:
    """Exponential moving average (latest value)."""
    alpha = 2.0 / (n + 1.0)
    e = float(values[0])
    for v in values[1:]:
        e = alpha * float(v) + (1.0 - alpha) * e
    return e


def roc(values: np.ndarray, n: int) -> float:
    """Rate of change over ``n`` periods: ``v[-1] / v[-n-1] - 1`` (needs n+1 pts)."""
    if len(values) < n + 1 or values[-n - 1] == 0:
        return float("nan")
    return float(values[-1] / values[-n - 1] - 1.0)


def rolling_std(values: np.ndarray, n: int) -> float:
    """Sample standard deviation of the last ``n`` values."""
    return float(np.std(values[-n:], ddof=1))


def rsi(values: np.ndarray, n: int = 14) -> float:
    """Wilder's RSI (latest value). Needs at least ``n + 1`` points."""
    if len(values) < n + 1:
        return float("nan")
    deltas = np.diff(values)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = gains[:n].mean()
    avg_loss = losses[:n].mean()
    for i in range(n, len(deltas)):
        avg_gain = (avg_gain * (n - 1) + gains[i]) / n
        avg_loss = (avg_loss * (n - 1) + losses[i]) / n

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - 100.0 / (1.0 + rs))


def bollinger(values: np.ndarray, n: int = 20, k: float = 2.0):
    """Return ``(lower, mid, upper)`` Bollinger bands for the last ``n`` values."""
    mid = sma(values, n)
    sd = rolling_std(values, n)
    return mid - k * sd, mid, mid + k * sd
