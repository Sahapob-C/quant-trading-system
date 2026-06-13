"""Persistent portfolio state — capital, deposits, DCA history.

Stored as JSON in state/portfolio.json (gitignored).
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import List


@dataclass
class DepositRecord:
    timestamp: str
    amount_thb: float
    note: str = ""


@dataclass
class PortfolioState:
    capital_thb: float = 1_000.0
    fx_usd_thb: float = 35.0
    deposits: List[DepositRecord] = field(default_factory=list)
    dca_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # ---- persistence -------------------------------------------------------

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "PortfolioState":
        if not os.path.exists(path):
            return cls()
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        raw["deposits"] = [DepositRecord(**d) for d in raw.get("deposits", [])]
        obj = cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})
        return obj

    # ---- mutations ---------------------------------------------------------

    def deposit(self, amount_thb: float, note: str = "") -> None:
        self.capital_thb += amount_thb
        self.deposits.append(
            DepositRecord(
                timestamp=datetime.utcnow().isoformat(),
                amount_thb=amount_thb,
                note=note,
            )
        )
        self._touch()

    def record_dca(self, deployed_thb: float) -> None:
        self.dca_count += 1
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.utcnow().isoformat()
