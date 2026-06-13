"""Wealth-management layer (income-first / waterfall architecture).

Sits on top of the trading engine. Responsibilities:
  * RiskController  — the 4 active-trading risk rules (sizing, circuit breaker,
                      trailing profit stop, hard stop).
  * WaterfallLedger — route dividend + profit-sweep inflows (USD->THB, after tax)
                      into Tier 1 living expenses then Tier 2 DRIP overflow.
  * BasketRegistry  — the three segregated asset baskets + the growth lock rule.

Phase W1 is paper / fully simulatable. Real money movement is ledger-tracked and
left to a manual, approved step (never automated).
"""
