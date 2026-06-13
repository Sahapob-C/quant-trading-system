"""Personal portfolio CLI — 5-Basket Adaptive System.

Commands
--------
status              Show current tier, capital, next-tier target
deposit <amount>    Record a cash deposit (THB)
dca <amount>        Plan a DCA run with <amount> THB
dca <amount> --exec Execute the plan via Alpaca paper (paper mode)

Examples
--------
    py scripts/portfolio.py status
    py scripts/portfolio.py deposit 1000
    py scripts/portfolio.py dca 500
    py scripts/portfolio.py dca 500 --exec
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.wealth.dca_engine import DCAEngine
from quant.wealth.portfolio_state import PortfolioState
from quant.wealth.tier_engine import TierEngine

STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "state", "portfolio.json",
)
DCA_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "state", "dca_log.jsonl",
)

TIER_NAMES = {
    0: "Tier 0 - Accumulation (B3 + B4)",
    1: "Tier 1 - Growth + DRIP (B2 + B3 + B4)",
    2: "Tier 2 - Full Active (B1 + B2 + B3 + B4)",
    3: "Tier 3 - Complete System (B0 + B1 + B2 + B3 + B4)",
}

BASKET_DESC = {
    "b0": "Fortress  (cash reserve 1 yr)",
    "b1": "Cash Flow (active trading bot)",
    "b2": "DRIP      (high-dividend reinvest)",
    "b3": "Growth    (quality DCA, long-term)",
    "b4": "Passion   (moonshot DCA, SMR/tech)",
}


def cmd_status(state: PortfolioState, te: TierEngine) -> None:
    spec = te.current_tier(state.capital_thb)
    nxt = te.thb_to_next_tier(state.capital_thb)

    print("=" * 56)
    print("  PORTFOLIO STATUS")
    print("=" * 56)
    print(f"  Capital         : {state.capital_thb:>10,.2f} THB")
    print(f"  FX              : {state.fx_usd_thb:.1f} THB/USD")
    print(f"  Capital (USD)   : {state.capital_thb / state.fx_usd_thb:>10,.2f} USD")
    print(f"  DCA runs done   : {state.dca_count}")
    print(f"  Deposits made   : {len(state.deposits)}")
    print()
    print(f"  Current Tier    : {spec.tier} — {TIER_NAMES[spec.tier]}")
    print()
    print("  Active baskets + weights:")
    for b, w in spec.weights.items():
        print(f"    {b}  {w*100:.0f}%  {BASKET_DESC.get(b, '')}")
    print()
    if nxt > 0:
        print(f"  Next tier unlock: +{nxt:,.0f} THB needed")
    else:
        print("  You are at the top tier!")
    print("=" * 56)


def cmd_deposit(state: PortfolioState, amount: float) -> None:
    state.deposit(amount, note="manual deposit")
    state.save(STATE_PATH)
    print(f"  Deposited {amount:,.2f} THB -> capital now {state.capital_thb:,.2f} THB")


def cmd_dca(
    state: PortfolioState,
    te: TierEngine,
    amount: float,
    execute: bool = False,
) -> None:
    engine = DCAEngine(tier_engine=te, fx_usd_thb=state.fx_usd_thb)
    plan = engine.plan(available_thb=amount, capital_thb=state.capital_thb)

    print(plan.summary())
    print()

    engine.save_plan(plan, DCA_LOG_PATH)

    if execute:
        executed_count = _execute_alpaca(plan, state)
        state.record_dca(deployed_thb=amount)
        state.save(STATE_PATH)
        print(f"  Executed {executed_count} orders via Alpaca paper.")
    else:
        print("  (dry-run — add --exec to send orders to Alpaca paper)")


def cmd_project(state: PortfolioState, te: TierEngine, monthly: float) -> None:
    print("=" * 56)
    print("  TIER PROJECTION")
    print("=" * 56)
    print(f"  Current capital: {state.capital_thb:,.2f} THB")
    print(f"  Monthly deposit: {monthly:,.2f} THB")
    print()

    capital = state.capital_thb
    month = 0
    for tier_spec in te._tiers[1:]:  # skip tier 0
        months_to_tier = (tier_spec.min_thb - capital) / monthly if monthly > 0 else float("inf")
        print(f"  Tier {tier_spec.tier} @ {tier_spec.min_thb:>8,.0f} THB: in {months_to_tier:>5.1f} months")
    print("=" * 56)


def _execute_alpaca(plan, state: PortfolioState) -> int:
    executed = 0
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        from quant.settings import get_alpaca_creds, use_paper

        key, secret = get_alpaca_creds()
        paper = use_paper()
        client = TradingClient(key, secret, paper=paper)

        for leg in plan.legs:
            if leg.basket in ("b0", "b1"):
                continue  # cash/bot — no buy orders
            if leg.usd_amount < 1.0:
                print(f"    SKIP {leg.symbol}: ${leg.usd_amount:.4f} (< $1 min)")
                continue  # Alpaca minimum
            req = MarketOrderRequest(
                symbol=leg.symbol,
                notional=round(leg.usd_amount, 2),
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )
            order = client.submit_order(req)
            print(f"    ORDER {leg.symbol}: ${leg.usd_amount:.4f}  id={order.id}")
            executed += 1
    except ImportError:
        print("  alpaca-py not installed — pip install alpaca-py")
    except Exception as exc:
        print(f"  Alpaca error: {exc}")
    return executed


def main() -> None:
    parser = argparse.ArgumentParser(description="5-Basket Adaptive Portfolio")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("status", help="Show tier + capital")

    dep = sub.add_parser("deposit", help="Record a cash deposit (THB)")
    dep.add_argument("amount", type=float)
    dep.add_argument("--note", default="", help="Optional note")

    dca = sub.add_parser("dca", help="Plan / execute a DCA run (THB)")
    dca.add_argument("amount", type=float)
    dca.add_argument("--exec", dest="execute", action="store_true",
                     help="Send orders to Alpaca paper")

    proj = sub.add_parser("project", help="Estimate when you'll reach next tier")
    proj.add_argument("--monthly", type=float, default=2000.0,
                      help="Monthly deposit amount (THB)")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    state = PortfolioState.load(STATE_PATH)
    te = TierEngine()

    if args.cmd == "status":
        cmd_status(state, te)
    elif args.cmd == "deposit":
        cmd_deposit(state, args.amount)
        if args.note:
            state.deposits[-1].note = args.note
            state.save(STATE_PATH)
    elif args.cmd == "dca":
        cmd_dca(state, te, args.amount, execute=args.execute)
    elif args.cmd == "project":
        cmd_project(state, te, args.monthly)


if __name__ == "__main__":
    main()
