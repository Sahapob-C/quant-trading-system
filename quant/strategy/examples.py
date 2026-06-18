"""Example strategies.

All of them follow the same pattern: on each ``MarketEvent`` they look at recent
bars for every symbol and emit ``LONG`` / ``EXIT`` signals. They are long-only and
hold at most one position per symbol — the ``invested`` flag makes them fire only
on a state change, not every bar.

Treat these as templates. The engine, portfolio, and risk manager don't care which
strategy you plug in, so the interesting work is writing your own
``calculate_signals``.
"""
from __future__ import annotations

import numpy as np

from quant.core.events import EventType, SignalEvent
from quant.strategy import indicators as ind
from quant.strategy.base import Strategy


class _BaseLongOnly(Strategy):
    """Shared plumbing: per-symbol ``invested`` flags + a signal helper."""

    def __init__(self, events, data_handler, symbol_list):
        self.events = events
        self.data = data_handler
        self.symbol_list = list(symbol_list)
        self.invested = {s: False for s in self.symbol_list}

    def _emit(self, symbol, signal_type):
        ts = self.data.get_latest_bar_datetime(symbol)
        self.events.put(SignalEvent(symbol=symbol, timestamp=ts, signal_type=signal_type))

    def _series(self, symbol, field, n):
        """Last ``n`` values of ``field``; None if too few or any NaN."""
        values = self.data.get_latest_bars_values(symbol, field, n=n)
        if values is None or len(values) < n or np.isnan(values).any():
            return None
        return values

    def _closes(self, symbol, n):
        return self._series(symbol, "close", n)


class MovingAverageCrossStrategy(_BaseLongOnly):
    """Dual moving-average crossover: long when short SMA > long SMA."""

    def __init__(self, events, data_handler, symbol_list, short_window=50, long_window=200):
        super().__init__(events, data_handler, symbol_list)
        if short_window >= long_window:
            raise ValueError("short_window must be < long_window")
        self.short_window = int(short_window)
        self.long_window = int(long_window)

    def calculate_signals(self, event):
        if event.type != EventType.MARKET:
            return
        for s in self.symbol_list:
            closes = self._closes(s, self.long_window)
            if closes is None:
                continue
            short_ma = ind.sma(closes, self.short_window)
            long_ma = ind.sma(closes, self.long_window)
            if short_ma > long_ma and not self.invested[s]:
                self._emit(s, "LONG")
                self.invested[s] = True
            elif short_ma < long_ma and self.invested[s]:
                self._emit(s, "EXIT")
                self.invested[s] = False


class MomentumStrategy(_BaseLongOnly):
    """Time-series momentum with a trend filter.

    Long when the ``lookback``-period return is positive *and* price is above its
    ``trend_window`` SMA; exit when either condition breaks.
    """

    def __init__(self, events, data_handler, symbol_list, lookback=126, trend_window=200):
        super().__init__(events, data_handler, symbol_list)
        self.lookback = int(lookback)
        self.trend_window = int(trend_window)
        if self.lookback <= 0 or self.trend_window <= 0:
            raise ValueError(f"lookback and trend_window must be > 0, got lookback={self.lookback}, trend_window={self.trend_window}")

    def calculate_signals(self, event):
        if event.type != EventType.MARKET:
            return
        need = max(self.lookback + 1, self.trend_window)
        for s in self.symbol_list:
            closes = self._closes(s, need)
            if closes is None:
                continue
            momentum = ind.roc(closes, self.lookback)
            if np.isnan(momentum):
                continue
            trend = ind.sma(closes, self.trend_window)
            price = closes[-1]
            bullish = momentum > 0 and price > trend
            if bullish and not self.invested[s]:
                self._emit(s, "LONG")
                self.invested[s] = True
            elif not bullish and self.invested[s]:
                self._emit(s, "EXIT")
                self.invested[s] = False


class RSIMeanReversionStrategy(_BaseLongOnly):
    """Buy oversold, sell back to neutral.

    Long when RSI dips below ``oversold``; exit when RSI recovers above
    ``exit_level``.
    """

    def __init__(self, events, data_handler, symbol_list, period=14, oversold=30.0, exit_level=50.0):
        super().__init__(events, data_handler, symbol_list)
        self.period = int(period)
        self.oversold = float(oversold)
        self.exit_level = float(exit_level)
        if self.period <= 0:
            raise ValueError(f"period must be > 0, got {self.period}")
        if not (0 <= self.oversold < self.exit_level <= 100):
            raise ValueError(f"must have 0 <= oversold < exit_level <= 100, got oversold={self.oversold}, exit_level={self.exit_level}")

    def calculate_signals(self, event):
        if event.type != EventType.MARKET:
            return
        need = self.period * 4  # enough history for Wilder smoothing to settle
        for s in self.symbol_list:
            closes = self._closes(s, need)
            if closes is None:
                continue
            value = ind.rsi(closes, self.period)
            if np.isnan(value):
                continue
            if value < self.oversold and not self.invested[s]:
                self._emit(s, "LONG")
                self.invested[s] = True
            elif value > self.exit_level and self.invested[s]:
                self._emit(s, "EXIT")
                self.invested[s] = False


class BollingerBandStrategy(_BaseLongOnly):
    """Mean-reversion on Bollinger Bands.

    Long when price closes below the lower band; exit when it returns above the
    middle band (the SMA).
    """

    def __init__(self, events, data_handler, symbol_list, window=20, num_std=2.0):
        super().__init__(events, data_handler, symbol_list)
        self.window = int(window)
        self.num_std = float(num_std)
        if self.window < 2:
            raise ValueError(f"window must be >= 2, got {self.window}")
        if self.num_std <= 0:
            raise ValueError(f"num_std must be > 0, got {self.num_std}")

    def calculate_signals(self, event):
        if event.type != EventType.MARKET:
            return
        for s in self.symbol_list:
            closes = self._closes(s, self.window)
            if closes is None:
                continue
            lower, mid, upper = ind.bollinger(closes, self.window, self.num_std)
            if np.isnan(lower) or np.isnan(mid) or np.isnan(upper):
                continue
            price = closes[-1]
            if price < lower and not self.invested[s]:
                self._emit(s, "LONG")
                self.invested[s] = True
            elif price > mid and self.invested[s]:
                self._emit(s, "EXIT")
                self.invested[s] = False


class DonchianBreakoutStrategy(_BaseLongOnly):
    """Trend-following channel breakout (turtle-style).

    Long when price closes above the highest high of the last ``entry_window``
    bars; exit when it closes below the lowest low of the last ``exit_window``
    bars. The windows exclude the current bar so the breakout is a genuine new
    extreme, not a comparison against itself.
    """

    def __init__(self, events, data_handler, symbol_list, entry_window=20, exit_window=10):
        super().__init__(events, data_handler, symbol_list)
        self.entry_window = int(entry_window)
        self.exit_window = int(exit_window)
        if self.entry_window < 1 or self.exit_window < 1:
            raise ValueError(f"entry_window and exit_window must be >= 1, got entry_window={self.entry_window}, exit_window={self.exit_window}")

    def calculate_signals(self, event):
        if event.type != EventType.MARKET:
            return
        need = max(self.entry_window, self.exit_window) + 1
        for s in self.symbol_list:
            highs = self._series(s, "high", need)
            lows = self._series(s, "low", need)
            closes = self._series(s, "close", need)
            if highs is None or lows is None or closes is None:
                continue
            price = closes[-1]
            upper = highs[-self.entry_window - 1:-1].max()  # prior highs, excl. today
            lower = lows[-self.exit_window - 1:-1].min()
            if not self.invested[s] and price > upper:
                self._emit(s, "LONG")
                self.invested[s] = True
            elif self.invested[s] and price < lower:
                self._emit(s, "EXIT")
                self.invested[s] = False


class CrossSectionalMomentumStrategy(_BaseLongOnly):
    """Relative-strength momentum: hold the strongest ``top_k`` of the universe.

    Every ``rebalance_days`` bars, rank symbols by their ``lookback`` return and
    hold the top ``top_k`` that also have positive momentum; exit the rest. This
    is the classic cross-sectional equity momentum factor.

    Tip: set the risk manager's ``target_pct`` to about ``1 / top_k`` so the
    winners are roughly equal-weighted to full investment.
    """

    def __init__(self, events, data_handler, symbol_list, lookback=126, top_k=2, rebalance_days=21):
        super().__init__(events, data_handler, symbol_list)
        self.lookback = int(lookback)
        self.top_k = int(top_k)
        self.rebalance_days = int(rebalance_days)
        if self.lookback <= 0 or self.top_k <= 0 or self.rebalance_days <= 0:
            raise ValueError(f"lookback, top_k, rebalance_days must all be > 0, got lookback={self.lookback}, top_k={self.top_k}, rebalance_days={self.rebalance_days}")
        self._bar = 0

    def calculate_signals(self, event):
        if event.type != EventType.MARKET:
            return
        self._bar += 1
        if (self._bar - 1) % self.rebalance_days != 0:  # only act on rebalance bars
            return

        scores = {}
        for s in self.symbol_list:
            closes = self._series(s, "close", self.lookback + 1)
            if closes is None:
                continue
            roc_val = ind.roc(closes, self.lookback)
            if not np.isnan(roc_val):
                scores[s] = roc_val
        if not scores:
            return

        ranked = sorted(scores, key=scores.get, reverse=True)
        winners = {s for s in ranked[: self.top_k] if scores[s] > 0}

        for s in self.symbol_list:
            want = s in winners
            if want and not self.invested[s]:
                self._emit(s, "LONG")
                self.invested[s] = True
            elif not want and self.invested[s]:
                self._emit(s, "EXIT")
                self.invested[s] = False
