# Quant Trading System — Claude Code Configuration

> **Rule hierarchy**: Global `~/.claude/CLAUDE.md` always takes priority. This file extends global rules — it may add project-specific detail but may never override or contradict global rules.

## ADHD Framework (Divergent Thinking)

**Location**: `C:\Users\Sahapob\.claude\adhd\`

**When to use ADHD:**
- ✓ Designing new trading strategies
- ✓ Debugging complex market behaviors
- ✓ Testing multiple approaches to the same problem
- ✓ Need creative/divergent solutions

**When NOT to use:**
- ✗ Simple bugs or syntax fixes
- ✗ Routine code reviews
- ✗ Straightforward implementations

**How to trigger:**
```
"Use ADHD thinking for..." 
"Create 3 divergent approaches to..."
"Brainstorm strategy ideas using..."
```

---

## Project Structure

```
quant-trading-system/
├── quant/              # Main Python package
│   ├── strategy/       # Strategy implementations (including ADHD-generated)
│   ├── data/           # Data handlers
│   └── execution/      # Execution handlers
├── notebooks/          # Backtesting notebooks
├── scripts/            # Utility scripts (run_backtest.py)
├── adhd/               # → Symlink to global ADHD framework
└── config/             # Configuration files
```

---

## ADHD Output Integration

When ADHD generates strategies:
1. Output goes to `quant/strategy/adhd_strategies.py`
2. Each strategy includes docstring, parameters, signals
3. Ready for backtest via `scripts/run_backtest.py`

---

## Preferences

- Answer in Thai
- Include both ideas AND implementation
- Always provide backtest instructions
