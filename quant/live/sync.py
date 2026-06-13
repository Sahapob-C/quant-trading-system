"""Reconcile the engine's in-memory book with the broker at startup.

Without this, the engine starts at a clean slate while your Alpaca account may
already hold positions — so it could try to buy something you already own, or
mis-size orders. Syncing makes the broker the source of truth.
"""
from __future__ import annotations

from typing import Dict


def sync_portfolio_from_broker(portfolio, trading_client) -> Dict[str, int]:
    """Seed cash, positions and equity from the live account.

    Returns ``{symbol: qty}`` for every position the account currently holds.
    """
    account = trading_client.get_account()
    positions = trading_client.get_all_positions()

    portfolio.current_holdings["cash"] = float(account.cash)

    for s in portfolio.symbol_list:
        portfolio.current_positions[s] = 0

    held: Dict[str, int] = {}
    for p in positions:
        qty = int(float(p.qty))
        held[p.symbol] = qty
        if p.symbol in portfolio.current_positions:
            portfolio.current_positions[p.symbol] = qty

    # Trust the broker's own equity figure (it includes untracked symbols too).
    portfolio.equity = float(account.equity)
    portfolio.current_holdings["total"] = float(account.equity)
    return held


def sync_strategy_invested(strategy, held_symbols: Dict[str, int]) -> None:
    """If the strategy keeps per-symbol ``invested`` flags, align them to holdings."""
    invested = getattr(strategy, "invested", None)
    if invested is None:
        return
    for s in invested:
        invested[s] = held_symbols.get(s, 0) != 0
