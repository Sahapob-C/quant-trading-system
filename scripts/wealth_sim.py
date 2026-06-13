"""Simulate and self-check the wealth-management layer (Phase W1, paper).

Exercises the four risk rules on synthetic prices, runs ~14 months of inflows
through the waterfall ledger, and demonstrates the basket lock rule. Doubles as a
test: it asserts the key outcomes and prints PASS markers.

    py scripts/wealth_sim.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.wealth.baskets import BasketRegistry
from quant.wealth.config import load_wealth_config
from quant.wealth.risk_controller import RiskController
from quant.wealth.waterfall import FXConverter, WaterfallLedger

CFG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "wealth.yaml")


def hr(title):
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    assert ok, label


def demo_risk(cfg):
    hr("1) RISK ENGINE - 4 rules")
    rc = RiskController(cfg.risk)

    # Rule 1: position sizing (5% of 100k at $100 = 50 shares)
    qty = rc.size_quantity(capital=100_000, price=100.0, fractional=False)
    print(f"  sizing: 5% of $100,000 @ $100 -> {qty} shares")
    check("position sizing = 50", qty == 50)

    # Rule 3: trailing 50% profit retracement
    rc.on_entry("AAPL", price=100.0, quantity=50)
    e1 = rc.check_stops({"AAPL": 110.0})          # peak profit 10, no exit yet
    e2 = rc.check_stops({"AAPL": 104.0})          # gave back to +4 (<= 50% of 10) -> exit
    print(f"  trailing: peak $110 then $104 -> {e2}")
    check("no exit at the peak", e1 == [])
    check("trailing stop fires after 50% give-back", ("AAPL", "trailing_stop") in e2)
    rc.on_exit("AAPL")

    # Rule 4: hard stop at -20%
    rc.on_entry("XYZ", price=100.0, quantity=50)
    e3 = rc.check_stops({"XYZ": 79.0})            # -21% -> hard stop
    print(f"  hard stop: entry $100 -> $79 (-21%) -> {e3}")
    check("hard stop fires at -20%", ("XYZ", "hard_stop") in e3)
    rc.on_exit("XYZ")

    # Rule 2: 24h circuit breaker
    t0 = datetime(2026, 6, 12, 9, 0)
    trig0 = rc.update_equity(t0, 100_000)
    trig1 = rc.update_equity(t0 + timedelta(hours=1), 89_000)   # -11% in 24h -> trip
    print(f"  circuit breaker: 100k -> 89k in 1h -> triggered={trig1}")
    check("not triggered at first reading", not trig0)
    check("breaker trips on -11% / 24h", trig1)
    check("frozen 10h later", rc.is_frozen(t0 + timedelta(hours=10)))
    check("unfrozen after 24h freeze", not rc.is_frozen(t0 + timedelta(hours=26)))

    # Daily profit sweep
    sweep, reinvest = rc.split_daily_profit(1_000.0)
    print(f"  daily sweep: $1,000 profit -> waterfall ${sweep:.0f}, reinvest ${reinvest:.0f}")
    check("sweep 50% of positive profit", (sweep, reinvest) == (500.0, 500.0))
    check("no sweep on a losing day", rc.split_daily_profit(-200.0) == (0.0, -200.0))


def demo_waterfall(cfg):
    hr("2) WATERFALL LEDGER - 14 months of inflows")
    ledger = WaterfallLedger(cfg.waterfall, FXConverter(cfg.fx.usd_thb))

    print("  monthly: $1,000 gross dividend (30% WHT) + $400 profit sweep | FX 35")
    months = [(2026, m) for m in range(1, 13)] + [(2027, 1), (2027, 2)]
    for (y, m) in months:
        ledger.inflow(datetime(y, m, 15), "dividend", 1_000.0)
        ledger.inflow(datetime(y, m, 28), "profit_sweep", 400.0)

    s = ledger.summary()
    print(f"  cap this year (was 35,000)       : {s['current_cap_thb']:,.0f} THB")
    print(f"  Tier-1 living expense (this mo)  : {s['tier1_this_month_thb']:,.0f} THB")
    print(f"  Tier-1 paid out (lifetime)       : {s['tier1_paid_total_thb']:,.0f} THB")
    print(f"  Tier-2 DRIP bucket (waiting)     : {s['drip_bucket_thb']:,.0f} THB")
    print(f"  Tier-2 DRIP total (lifetime)     : {s['tier2_total_thb']:,.0f} THB")

    # First month: $700 net div = 24,500 THB; $400 sweep = 14,000 THB; fills 35,000 cap, 3,500 overflow.
    jan = ledger.entries[1]  # the Jan profit_sweep entry
    check("Jan sweep tops Tier-1 to the 35k cap", abs(jan.to_tier1_thb - 10_500) < 1e-6)
    check("Jan overflow to DRIP = 3,500", abs(jan.to_tier2_thb - 3_500) < 1e-6)
    check("Tier-1 floor (10k) met", ledger.tier1_target_met())
    # 12 months of 2026 overflow at 3,500 each = 42,000 before 2027.
    check("DRIP lifetime grew past 2026 total", s["tier2_total_thb"] > 42_000)
    # Year rollover grows the cap 4% above inflation: 35,000 -> 36,400.
    check("Iron Rule grew the cap to 36,400 in 2027", abs(s["current_cap_thb"] - 36_400) < 1.0)

    drained = ledger.drain_drip_bucket()
    print(f"  draining DRIP bucket -> {drained:,.0f} THB to buy fractional shares")
    check("draining empties the bucket", ledger.drip_bucket_thb == 0.0)


def demo_baskets(cfg):
    hr("3) ASSET BASKETS - segregation + growth lock")
    reg = BasketRegistry(cfg.baskets)

    print(f"  Basket 1 (cashflow): {reg.cashflow.symbols}")
    print(f"  Basket 2 (drip)    : {reg.drip.symbols}")
    print(f"  Basket 3 (growth)  : {reg.growth.symbols}  locked={reg.growth.locked}")
    print(f"  active (allocatable) symbols: {reg.active_symbols()}")

    n_cf, n_dr, n_gr = len(reg.cashflow.symbols), len(reg.drip.symbols), len(reg.growth.symbols)
    check("growth starts locked", reg.growth.locked)
    check("growth excluded from active set", len(reg.active_symbols()) == n_cf + n_dr)
    check("cannot allocate to growth while locked", not reg.can_allocate("growth"))
    check("dividend $0.50 below fractional min -> ineligible", not reg.drip_eligible(0.50))
    check("dividend $5.00 eligible for DRIP", reg.drip_eligible(5.00))

    # Unlock only after Tier-1 met for `growth_unlock_months` consecutive months.
    for i in range(cfg.baskets.growth_unlock_months - 1):
        reg.review_growth_lock(tier1_target_met=True)
    check("still locked before the required streak", reg.growth.locked)
    reg.review_growth_lock(tier1_target_met=True)  # final month
    print(f"  after {cfg.baskets.growth_unlock_months} months of Tier-1 met -> growth locked={reg.growth.locked}")
    check("growth unlocks after the streak", not reg.growth.locked)
    check("growth now in active set", len(reg.active_symbols()) == n_cf + n_dr + n_gr)


def main():
    cfg = load_wealth_config(CFG_PATH)
    print(f"Loaded config from {CFG_PATH}")
    demo_risk(cfg)
    demo_waterfall(cfg)
    demo_baskets(cfg)
    hr("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
