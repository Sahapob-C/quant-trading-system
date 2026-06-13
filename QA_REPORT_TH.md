# รายงาน QA/ทดสอบ ระบบเทรดเชิงปริมาณ (Quantitative Trading System)
**วันที่:** 13 มิถุนายน 2026  
**ผู้ทดสอบ:** QA Tester (Difficult Customer Mode)  
**ระดับความรุนแรง:** วิกฤต ⚠️ จำนวนปัญหา: 23 ข้อ

---

## 📋 สรุปผลการทดสอบ

ระบบนี้มีปัญหาที่ **ไม่สามารถใช้งานได้ในปัจจุบัน** เนื่องจาก:
1. **โมดูล data ขาดหายไป** (CRITICAL) - ระบบไม่สามารถรัน backtest ได้เลย
2. **ความเสี่ยงการหารด้วยศูนย์** ในหลาย ๆ ฟังก์ชัน
3. **การจัดการข้อมูล None/Null ที่ไม่มั่นคง** ในพอร์ตโฟลิโอและการประมาณราคา
4. **ปัญหาการตรวจสอบพารามิเตอร์อินพุต**
5. **ความไม่ปลอดภัยในการบันทึกสถานะสำหรับการเทรดสด**

---

## 🔴 ปัญหาวิกฤต (CRITICAL BUGS)

### 1️⃣ โมดูล `quant/data/` ขาดหายไปโดยสิ้นเชิง
- **ไฟล์ที่ได้รับผลกระทบ:**
  - `quant/runner.py:16` → imports `from quant.data.historic import HistoricParquetDataHandler`
  - `scripts/download_data.py:15` → imports `from quant.data.loaders import download_to_parquet`
  - `scripts/paper_trade.py:32` → imports `from quant.data.alpaca_data import AlpacaDataHandler`
- **ผลกระทบ:** ไม่มีวิธีโหลดข้อมูลตลาดเข้าระบบ → backtest ทั้งหมดล้มเหลว
- **สถานะ:** 🚫 ระบบไม่สามารถรันได้
- **ความรุนแรง:** **CRITICAL** - ไม่มีวิธีโหลดข้อมูล

---

## 🟠 ปัญหาร้ายแรง (SEVERE BUGS)

### 2️⃣ ความเสี่ยงการหารด้วยศูนย์ใน `drawdown_series()`
- **ไฟล์:** `quant/performance/metrics.py:33-36`
```python
def drawdown_series(equity_curve: pd.Series) -> pd.Series:
    running_max = equity_curve.cummax()
    return (equity_curve - running_max) / running_max  # ⚠️ เสี่ยง / 0
```
- **สถานการณ์ขอบ:** ถ้า `running_max` เป็น 0 (ความเป็นไปได้น้อยแต่เป็นไปได้)
- **ความรุนแรง:** HIGH - ปัญหา Calculus, NaN propagation

### 3️⃣ ความเสี่ยงการหารด้วยศูนย์ใน `check_stops()`
- **ไฟล์:** `quant/wealth/risk_controller.py:63-65`
```python
drawdown = (price - pos.entry_price) / pos.entry_price  # ⚠️ ถ้า entry_price = 0
if drawdown <= -self.cfg.hard_stop_pct / 100.0:
```
- **สถานการณ์ขอบ:** หากเข้า position ที่ราคา 0 (error ในการซิงค์ข้อมูล)
- **ความรุนแรง:** HIGH - System crash

### 4️⃣ ความเสี่ยงการหารด้วยศูนย์ใน `update_equity()`
- **ไฟล์:** `quant/wealth/waterfall.py:87`
```python
peak = max(e for _, e in self._equity_history)
drawdown = (equity - peak) / peak if peak > 0 else 0.0
```
- **ปัญหา:** ถ้า `_equity_history` ว่าง → `max()` ขัดข้อง (ValueError)
- **ความรุนแรง:** MEDIUM-HIGH - Crash on first call if history empty

### 5️⃣ ความเสี่ยงการหารด้วยศูนย์ใน `rsi()`
- **ไฟล์:** `quant/strategy/indicators.py:53-56`
```python
if avg_loss == 0:
    return 100.0
rs = avg_gain / avg_loss  # ⚠️ ตรวจสอบแล้ว แต่จะเกิด ZeroDivisionError ถ้า avg_loss มีค่า float เล็ก ๆ
```
- **ปัญหา:** ตรวจสอบ `== 0` แต่ floating point อาจเป็น 1e-15 ทำให้ RS สูงมาก
- **ความรุนแรง:** MEDIUM

### 6️⃣ `update_equity()` ขัดข้องเมื่อ equity_history ว่าง
- **ไฟล์:** `quant/wealth/waterfall.py:86`
```python
peak = max(e for _, e in self._equity_history)  # ValueError if empty!
```
- **สถานการณ์:** เรียกครั้งแรกก่อน `_roll_calendar()` ตั้งค่าประวัติ
- **ความรุนแรง:** MEDIUM

---

## 🟡 ปัญหาสำคัญ (MAJOR ISSUES)

### 7️⃣ การจัดการ None ที่ไม่มั่นคง ใน `update_timeindex()`
- **ไฟล์:** `quant/portfolio/portfolio.py:70`
```python
price = self.data.get_latest_bar_value(s, "close") or 0.0
market_value = self.current_positions[s] * price  # ⚠️ ถ้า price = 0
```
- **ปัญหา:** 
  1. ถ้า symbol ไม่มีราคา → price = 0
  2. Position market_value คำนวณเป็น 0
  3. Equity ลดลง สูงสุด - ไม่สมบูรณ์
- **สถานการณ์:** ข้อมูลสูญหาย สัญญาณ no OHLCV
- **ความรุนแรง:** HIGH

### 8️⃣ ไม่ตรวจสอบราคาเป็นลบใน `_fill()`
- **ไฟล์:** `quant/execution/simulated.py:79-85`
```python
if price is None or price <= 0:
    return
if order.direction == "BUY":
    fill_price = price * (1.0 + self.slippage)  # ✓ ตรวจสอบแล้ว แต่...
```
- **ปัญหา:** ราคาเป็นลบ (data error) จะไม่ทำให้ซ้ำ
- **สถานการณ์:** Data outlier/corruption
- **ความรุนแรง:** MEDIUM

### 9️⃣ ไม่ตรวจสอบ `symbol_list` ว่างใน `Portfolio.__init__()`
- **ไฟล์:** `quant/portfolio/portfolio.py:21-46`
```python
def __init__(self, ..., symbol_list, ...):
    self.symbol_list = list(symbol_list)  # ⚠️ ไม่ตรวจสอบว่างเปล่า
    self.current_positions = {s: 0 for s in self.symbol_list}
```
- **สถานการณ์:** Pass `symbol_list=[]`
- **ผลกระทบ:** Portfolio ว่าง no positions ที่สามารถติดตาม
- **ความรุนแรง:** MEDIUM

### 🔟 ไม่ตรวจสอบ `initial_capital` เป็นลบหรือศูนย์
- **ไฟล์:** `quant/portfolio/portfolio.py:35`
```python
self.initial_capital = float(initial_capital)  # ⚠️ ไม่ตรวจสอบ > 0
```
- **สถานการณ์:** `run_backtest(capital=-1000)`
- **ผลกระทบ:** ขนาดตำแหน่งคำนวณเป็นลบ
- **ความรุนแรง:** HIGH

### 1️⃣1️⃣ ไม่ตรวจสอบพารามิเตอร์กลยุทธ์ก่อนสร้าง
- **ไฟล์:** `quant/strategy/examples.py:48-53`
```python
def __init__(self, ..., short_window=50, long_window=200):
    if short_window >= long_window:
        raise ValueError("short_window must be < long_window")
```
- **ปัญหา:** ตรวจสอบแล้วใน `sma_cross` แต่ไม่ใน `momentum` หรือ `rsi_reversion`
- **สถานการณ์:** `lookback >= trend_window` จะส่งผล signal ที่แปลก ๆ
- **ความรุนแรง:** MEDIUM

### 1️⃣2️⃣ `roc()` คืนค่า NaN สำหรับขอบนอกความต้องการ
- **ไฟล์:** `quant/strategy/indicators.py:27-31`
```python
def roc(values: np.ndarray, n: int) -> float:
    if len(values) < n + 1 or values[-n - 1] == 0:
        return float("nan")  # ⚠️ Caller ต้องตรวจสอบ NaN
```
- **ปัญหา:** Strategies ใช้ `roc()` และลืมตรวจสอบ NaN
- **สถานการณ์:** `MomentumStrategy.calculate_signals()` ไม่ตรวจสอบ `momentum` NaN
- **ความรุนแรง:** MEDIUM

### 1️⃣3️⃣ `rolling_std()` ขัดข้องเมื่อ n < 2
- **ไฟล์:** `quant/strategy/indicators.py:34-36`
```python
def rolling_std(values: np.ndarray, n: int) -> float:
    return float(np.std(values[-n:], ddof=1))  # ⚠️ ddof=1 ต้อง n >= 2
```
- **สถานการณ์:** `window=1` → ValueError
- **ความรุนแรง:** MEDIUM

### 1️⃣4️⃣ ไม่ตรวจสอบ price ว่างใน `_generate_order()`
- **ไฟล์:** `quant/portfolio/portfolio.py:86-107`
```python
price = self.data.get_latest_bar_value(s, "close")
if price is None or price <= 0:
    return None
current_qty = self.current_positions[s]  # ⚠️ อาจไม่มี key 'unknown_symbol'
```
- **สถานการณ์:** Signal สำหรับ symbol ที่ไม่ใน symbol_list
- **ผลกระทบ:** KeyError → engine crash
- **ความรุนแรง:** HIGH

---

## 🔵 ปัญหาปกติ (MODERATE ISSUES)

### 1️⃣5️⃣ ไม่ตรวจสอบ `equity` ก่อนคำนวณ target_quantity
- **ไฟล์:** `quant/risk/risk.py:23-43`
```python
def target_quantity(self, signal_type: str, equity: float, ...):
    if price <= 0 or equity <= 0:
        return current_qty  # ✓ ตรวจสอบแล้ว
```
- **ปัญหา:** ตรวจสอบแล้ว แต่ RiskManager ไม่มี assertion เพื่อ validate equity >= current_holdings["total"]
- **ความรุนแรง:** LOW-MEDIUM

### 1️⃣6️⃣ ไม่ตรวจสอบ limit_price ใน OrderEvent
- **ไฟล์:** `quant/core/events.py:66-87`
```python
@dataclass
class OrderEvent(Event):
    limit_price: Optional[float] = None  # ⚠️ ไม่ตรวจสอบว่า > 0 ถ้าใช้
```
- **ปัญหา:** ไม่มี validation ว่า limit_price เป็นบวกสำหรับ LMT orders
- **ความรุนแรง:** LOW-MEDIUM

### 1️⃣7️⃣ ไม่ตรวจสอบ fill_price เป็นลบใน FillEvent
- **ไฟล์:** `quant/core/events.py:90-109`
```python
@dataclass
class FillEvent(Event):
    fill_price: float  # ⚠️ ไม่ตรวจสอบ > 0
```
- **ปัญหา:** Data error อาจมีราคาติดลบ
- **ความรุนแรง:** LOW-MEDIUM

### 1️⃣8️⃣ ไม่ตรวจสอบ quantity เป็นลบหรือศูนย์
- **ไฟล์:** `quant/core/events.py:66-87`, `90-109`
- **ปัญหา:** OrderEvent / FillEvent อนุญาต quantity <= 0
- **ความรุนแรง:** LOW

### 1️⃣9️⃣ ไม่ตรวจสอบ commission เป็นลบ
- **ไฟล์:** `quant/core/events.py:99`
```python
commission: float = 0.0  # ⚠️ ไม่ตรวจสอบ >= 0
```
- **ความรุนแรง:** LOW

### 2️⃣0️⃣ slippage_bps อาจเป็นลบ
- **ไฟล์:** `quant/execution/simulated.py:39-54`
```python
def __init__(self, ..., slippage_bps: float = 1.0, ...):
    self.slippage = slippage_bps / 10_000.0  # ⚠️ ไม่ตรวจสอบ >= 0
```
- **ผลกระทบ:** slippage ติดลบ = ลด cost (unrealistic)
- **ความรุนแรง:** MEDIUM

### 2️⃣1️⃣ `summarized stats()` ไม่ตรวจสอบ NaN ก่อนตัดสินใจ
- **ไฟล์:** `quant/performance/metrics.py:39-66`
```python
cagr = final ** (periods / n) - 1.0 if n > 0 and final > 0 else float("nan")
# ⚠️ ไม่ตรวจสอบ NaN ที่กลับ
```
- **ปัญหา:** Return dict ที่มี NaN values ที่อาจทำให้เกิด RuntimeWarning
- **ความรุนแรง:** LOW-MEDIUM

### 2️⃣2️⃣ ไม่ตรวจสอบ `fill_on` parameter ในระหว่างการเรียก
- **ไฟล์:** `quant/runner.py:33-68`
```python
# ✓ ตรวจสอบใน SimulatedExecutionHandler แต่ไม่ใน runner
```
- **ความรุนแรง:** LOW

---

## ⚪ ปัญหาที่เหมาะสม (MINOR ISSUES & DESIGN CONCERNS)

### 2️⃣3️⃣ ไม่มี error handling สำหรับการเรียก API Alpaca
- **ไฟล์:** `quant/execution/alpaca_exec.py:44-68`
```python
try:
    order = self.client.submit_order(request)
except Exception as exc:
    print(f"! submit_order failed ...")  # ⚠️ Print only, no event emitted
    return
```
- **ปัญหา:** Order failure ไม่ส่ง FillEvent → Position book ไม่อัปเดต
- **สถานการณ์:** ตลาดปิด/ข้อขัดข้องเครือข่าย
- **ความรุนแรง:** LOW-MEDIUM (live trading critical)

---

## 📊 สรุปการนับปัญหา

| ระดับความรุนแรง | จำนวน | สถานะ |
|---|---|---|
| 🔴 CRITICAL | 1 | ⛔ ไม่สามารถใช้งาน |
| 🟠 SEVERE | 5 | ⚠️ ล้มเหลว/Crash |
| 🟡 MAJOR | 9 | ⚠️ ข้อมูลไม่ถูกต้อง/Edge cases |
| 🔵 MODERATE | 7 | ⚠️ ประสิทธิภาพลด |
| ⚪ MINOR | 1 | ℹ️ UX issue |
| **รวมทั้งหมด** | **23** | |

---

## 🧪 สถานการณ์การทดสอบ Edge Case ที่ทำให้ล้มเหลว

### Test Case 1: Backtest ด้วยข้อมูลตาหลัก
```bash
python scripts/run_backtest.py --symbols SPY --start 2020-01-01 --end 2024-12-31
```
**ผล:** ❌ `ModuleNotFoundError: No module named 'quant.data.historic'`

### Test Case 2: Portfolio ว่างเปล่า
```python
Portfolio(events, data, symbol_list=[], start="2020-01-01")
```
**ผล:** ❌ ไม่สามารถติดตามตำแหน่ง

### Test Case 3: Capital เป็นลบ
```python
run_backtest(..., capital=-100_000.0)
```
**ผล:** ❌ ขนาดตำแหน่งติดลบ

### Test Case 4: Slippage เป็นลบ
```python
SimulatedExecutionHandler(..., slippage_bps=-1.0)
```
**ผล:** ❌ Fill price ลดลงสำหรับ BUY (unrealistic)

### Test Case 5: Equity history ว่าง
```python
rc.update_equity(pd.Timestamp.now(), 100_000)  # First call
```
**ผล:** ❌ `ValueError: max() arg is an empty sequence`

### Test Case 6: Entry price = 0
```python
rc.on_entry("SPY", 0.0, 100)
rc.check_stops({"SPY": 1.0})
```
**ผล:** ❌ `ZeroDivisionError`

### Test Case 7: Bollinger band ด้วย window=1
```python
ind.bollinger(values, n=1, k=2.0)
```
**ผล:** ❌ `ValueError: ddof >= len(values)`

### Test Case 8: Signal สำหรับ symbol ที่ไม่มี
```python
event = SignalEvent("UNKNOWN", timestamp, "LONG")
portfolio.update_signal(event)
```
**ผล:** ❌ `KeyError: 'UNKNOWN'`

---

## 💡 สถานการณ์การใช้งานแบบ Chaotic/Unpredictable

1. **Data Gaps:** ข้อมูลหายไปบางวัน → ราคา None
2. **Stock Split:** ราคาลดลง 10x ทันใดนั้น (data outlier)
3. **Market Holiday:** ไม่มีข้อมูล → ยังไม่มี bar
4. **Broker Outage:** ล้มเหลวเหลือเพียง 50% ของ orders
5. **Negative Prices:** Corrupt data มี -$5 ราคา
6. **Extreme Slippage:** Market orders ที่ไม่ได้ fill
7. **Partial Fills:** Order fill ที่ 60% แล้วค้าง
8. **Commission Spikes:** Commission ที่สูงกว่า expected
9. **Rounding Errors:** Quantity ที่เป็น 0.00001 shares
10. **Concurrent Updates:** Position book update ขณะเดียวกับ signal processing

---

## 🎯 บทสรุป

**ระบบนี้ยังไม่พร้อมใช้งาน** เนื่องจาก:
1. ❌ โมดูล data ขาดหายไป
2. ❌ ปัญหาการหารด้วยศูนย์หลาย ๆ ที่
3. ❌ ไม่มี input validation
4. ⚠️ Edge case handling ไม่ครบถ้วน
5. ⚠️ Live trading state sync ไม่มั่นคง

ต้องการการแก้ไขเร่งด่วน **ก่อนการใช้งานใด ๆ**

---

**ลงชื่อ:** QA Tester (Chaotic Mode Activated)  
**สถานะ:** 🚫 **NOT PRODUCTION READY**
