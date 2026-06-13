"""The four active-trading risk rules from the SRS.

  1. Position sizing   — each entry uses ``position_pct`` % of capital (tranches).
  2. 24h circuit breaker — if rolling-24h drawdown exceeds a threshold, freeze
                           all trading for a number of hours.
  3. Trailing profit stop — once profitable, exit if price gives back
                           ``trailing_retracement_pct`` % of the peak profit.
  4. Hard stop          — exit immediately if a position falls ``hard_stop_pct`` %
                           below entry.

Pure logic + state: feed it fills and prices, it tells you what to liquidate and
whether trading is frozen. The trading loop wires it to real orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List, Optional, Tuple


@dataclass
class PositionState:
    symbol: str
    entry_price: float
    quantity: float
    peak_price: float          # highest price seen since entry


class RiskController:
    def __init__(self, cfg) -> None:  # cfg: RiskConfig
        self.cfg = cfg
        self.positions: Dict[str, PositionState] = {}
        self._equity_history: List[Tuple[object, float]] = []  # (ts, equity) within 24h
        self._frozen_until = None

    # --- rule 1: position sizing -------------------------------------
    def size_quantity(self, capital: float, price: float, fractional: bool = True) -> float:
        """Shares to buy for one tranche (``position_pct`` % of capital)."""
        if price <= 0 or capital <= 0:
            return 0.0
        allocation = capital * self.cfg.position_pct / 100.0
        shares = allocation / price
        return round(shares, 6) if fractional else float(int(shares))

    # --- position bookkeeping ----------------------------------------
    def on_entry(self, symbol: str, price: float, quantity: float) -> None:
        self.positions[symbol] = PositionState(symbol, price, quantity, price)

    def on_exit(self, symbol: str) -> None:
        self.positions.pop(symbol, None)

    # --- rules 3 & 4: per-position stops -----------------------------
    def check_stops(self, prices: Dict[str, float]) -> List[Tuple[str, str]]:
        """Return ``[(symbol, reason)]`` for every position that must be liquidated."""
        to_exit: List[Tuple[str, str]] = []
        for symbol, pos in self.positions.items():
            price = prices.get(symbol)
            if price is None or price <= 0:
                continue
            pos.peak_price = max(pos.peak_price, price)

            # rule 4: hard stop (drawdown from entry)
            drawdown = (price - pos.entry_price) / pos.entry_price
            if drawdown <= -self.cfg.hard_stop_pct / 100.0:
                to_exit.append((symbol, "hard_stop"))
                continue

            # rule 3: trailing stop (give back X% of peak profit)
            peak_profit = pos.peak_price - pos.entry_price
            if peak_profit > 0:
                keep = 1.0 - self.cfg.trailing_retracement_pct / 100.0
                if (price - pos.entry_price) <= peak_profit * keep:
                    to_exit.append((symbol, "trailing_stop"))
        return to_exit

    # --- rule 2: 24h circuit breaker ---------------------------------
    def update_equity(self, ts, equity: float) -> bool:
        """Record equity; freeze trading if 24h drawdown breaches the limit.

        Returns True on the tick the breaker *triggers*.
        """
        cutoff = ts - timedelta(hours=24)
        self._equity_history.append((ts, equity))
        self._equity_history = [(t, e) for (t, e) in self._equity_history if t >= cutoff]

        peak = max(e for _, e in self._equity_history)
        drawdown = (equity - peak) / peak if peak > 0 else 0.0
        if drawdown <= -self.cfg.circuit_breaker_dd_pct / 100.0 and self._frozen_until is None:
            self._frozen_until = ts + timedelta(hours=self.cfg.circuit_breaker_freeze_hours)
            return True
        return False

    def is_frozen(self, ts) -> bool:
        if self._frozen_until is None:
            return False
        if ts >= self._frozen_until:
            self._frozen_until = None
            return False
        return True

    # --- daily profit sweep (SRS) ------------------------------------
    def split_daily_profit(self, daily_pnl: float) -> Tuple[float, float]:
        """Return ``(to_waterfall, to_reinvest)`` for a day's net profit.

        Only positive net profit is swept; losses stay in the trading pool.
        """
        if daily_pnl <= 0:
            return 0.0, daily_pnl
        sweep = daily_pnl * self.cfg.daily_sweep_pct / 100.0
        return sweep, daily_pnl - sweep
