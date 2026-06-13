"""Persistent trade journal + state snapshots for live trading.

Fills are appended to ``state/fills.jsonl`` (one JSON object per line — easy to
tail, grep, or load into pandas). The latest book is written to
``state/state.json`` so you can inspect what the engine thinks it holds, and so a
future restart can reconcile against the broker.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone


class TradeJournal:
    def __init__(self, directory: str = "state"):
        self.dir = directory
        os.makedirs(self.dir, exist_ok=True)
        self.fills_path = os.path.join(self.dir, "fills.jsonl")
        self.state_path = os.path.join(self.dir, "state.json")

    def write_fill(self, fill) -> None:
        record = {
            "timestamp": str(getattr(fill, "timestamp", "")),
            "symbol": fill.symbol,
            "direction": fill.direction,
            "quantity": fill.quantity,
            "fill_price": fill.fill_price,
            "commission": getattr(fill, "commission", 0.0),
            "exchange": getattr(fill, "exchange", ""),
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(self.fills_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    def snapshot(self, equity: float, positions: dict, extra: dict | None = None) -> None:
        state = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "equity": equity,
            "positions": positions,
        }
        if extra:
            state.update(extra)
        with open(self.state_path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, default=str)
