# quant — ระบบ Quantitative Trading แบบ event-driven

ระบบเทรดเชิงปริมาณที่ออกแบบให้ **โค้ดกลยุทธ์ชุดเดียวรันได้ทั้ง backtest, paper และ live**
โดยสลับแค่ตัวป้อนข้อมูล (`DataHandler`) และตัวส่งคำสั่ง (`ExecutionHandler`)

## โครงสร้างโปรเจกต์

```
quant/
├── core/         events.py (Event ต่าง ๆ) + engine.py (event loop: backtest & live)
├── data/         base + historic (parquet) + loaders (yfinance) + alpaca_data (live)
├── strategy/     base + indicators + examples (4 กลยุทธ์) + registry
├── portfolio/    ติดตาม position/เงินสด, แปลง signal -> order
├── risk/         position sizing + ลิมิตความเสี่ยง
├── execution/    base + simulated (backtest) + alpaca_exec (paper/live)
├── research/     sweep (grid search) + walkforward (validation) + benchmark
├── live/         sync (reconcile กับ broker) + journal (state) + notify (alerts)
├── wealth/       config + risk_controller (4 กฎ) + waterfall (ledger) + baskets + screener
├── performance/  metrics (Sharpe, drawdown, CAGR) + กราฟ
├── runner.py     ฟังก์ชัน run_backtest() กลางที่ทุกอย่างเรียกใช้
└── settings.py   โหลด key ของ Alpaca จาก .env
scripts/          download_data, run_backtest, sweep, walkforward, compare,
                  check_alpaca, paper_trade, wealth_sim, build_baskets
notebooks/        research.ipynb (สมุดวิจัย interactive)
config/           example.yaml, wealth.yaml
```

## ติดตั้ง (Windows / PowerShell)

```powershell
cd C:\Users\Sahapob\projects\quant
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> ถ้า PowerShell บล็อกสคริปต์ activate ให้รัน
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` หนึ่งครั้ง
> (หรือเรียกตรง ๆ ผ่าน `.\.venv\Scripts\python.exe` โดยไม่ต้อง activate)

## 1) Backtest

```powershell
# ดาวน์โหลดข้อมูลเป็น parquet ลง data/
py scripts\download_data.py --symbols AAPL MSFT SPY --start 2015-01-01 --end 2024-12-31

# ดูกลยุทธ์ที่มี
py scripts\run_backtest.py --list

# รัน backtest -> ผลไปที่ results/ (equity_curve.csv, trades.csv, performance.png)
py scripts\run_backtest.py --symbols AAPL MSFT SPY --strategy sma_cross --param short_window=50 --param long_window=200
py scripts\run_backtest.py --symbols SPY --strategy rsi_reversion --param period=14 --param oversold=30
```

กลยุทธ์ตัวอย่าง: `sma_cross`, `momentum`, `rsi_reversion`, `bollinger`, `donchian`, `xs_momentum`
(เพิ่มเองได้ใน `quant/strategy/examples.py` แล้วลงทะเบียนใน `quant/strategy/registry.py`)

> backtest fill ที่ราคา **open ของแท่งถัดไป** เป็นค่าเริ่มต้น (`--fill-on next_open`) เพื่อกัน look-ahead
> ใช้ `--fill-on close` เพื่อเทียบกับแบบเดิม (มอง bias)

## 2) Research — กัน overfitting

```powershell
# Parameter sweep (+ heatmap ถ้ามี 2 พารามิเตอร์)
py scripts\sweep.py --symbols SPY --strategy sma_cross --grid short_window=20,50,100 --grid long_window=150,200,250 --metric sharpe

# Walk-forward: เลือกพารามิเตอร์บนช่วง train แล้ววัดผลบนช่วงที่ไม่เคยเห็น
py scripts\walkforward.py --symbols SPY --strategy sma_cross --grid short_window=20,50,100 --grid long_window=150,200,250 --train-years 3 --test-years 1

# เทียบทุกกลยุทธ์กับ buy & hold (ตัวตัดสินว่ามี edge จริงไหม)
py scripts\compare.py --symbols AAPL MSFT SPY GOOGL AMZN NVDA META JPM XOM JNJ KO
```

> ดูตัวเลข **out-of-sample** ที่ walk-forward รายงานเสมอ มันคือค่าที่ใกล้ความจริงที่สุด
> ตัวเลข in-sample (sweep) มักดูดีเกินจริงเพราะ fit กับข้อมูลในอดีต

## 3) Notebook วิจัย

```powershell
py -m jupyter lab notebooks\research.ipynb
```

รวมทุกอย่างไว้: โหลดข้อมูล, backtest, เทียบกลยุทธ์, heatmap, walk-forward แบบ interactive

## 4) Paper trading กับ Alpaca

```powershell
# ครั้งแรก: คัดลอก .env.example เป็น .env แล้วใส่ paper key (ฟรีจาก app.alpaca.markets)
copy .env.example .env

# ทดสอบการเชื่อมต่อ (อ่านอย่างเดียว ไม่ส่งออเดอร์)
py scripts\check_alpaca.py

# dry run: วอร์มอัพ + ซิงค์พอร์ตจากบัญชี + snapshot แล้วออก (ไม่ส่งออเดอร์)
py scripts\paper_trade.py --symbols SPY --strategy sma_cross --setup-only

# รัน paper trading จริง (ช่วงตลาด US เปิด); ใช้ --timeframe minute เพื่อเห็นผลไว
py scripts\paper_trade.py --symbols AAPL MSFT SPY --strategy sma_cross --param short_window=50 --param long_window=200 --timeframe minute --poll 60
```

ตอนเริ่ม ระบบจะ **ซิงค์ position + เงินสดจากบัญชี Alpaca** (กันซื้อซ้ำ), บันทึกทุก fill ลง
`state/fills.jsonl`, เขียนสถานะล่าสุดที่ `state/state.json`, และแจ้งเตือนทาง console
(ตั้ง `ALERT_WEBHOOK_URL` ใน `.env` เพื่อส่งเข้า Slack/Discord ด้วย)

> `.env` ตั้ง `ALPACA_PAPER=true` เป็นค่าเริ่มต้น (เงินปลอม ปลอดภัย) — เปลี่ยนเป็น `false` ต่อเมื่อจะเทรดเงินจริงเท่านั้น

### เก็บ key อย่างปลอดภัย (1Password ฯลฯ)

ระบบอ่าน key จาก environment variable เลยใช้กับตัวจัดการ secret ได้ทันที เช่น 1Password CLI
ไม่ต้องเก็บ key เป็น plaintext ในไฟล์:

```powershell
# .env ใส่ secret reference แทนค่าจริง เช่น  ALPACA_API_KEY=op://Private/Alpaca/key
op run --env-file .env -- python scripts\paper_trade.py --symbols SPY --setup-only
```

## 5) Wealth management (income-first / waterfall)

ชั้นบริหารความมั่งคั่งที่ต่อยอดบน engine (เฟส W1 — paper, จำลองได้):

```powershell
# คัดหุ้นเข้า 3 ตะกร้าด้วยข้อมูลปันผลจริง (ตามเกณฑ์ SRS)
py scripts\build_baskets.py

# จำลอง + ตรวจสอบทั้งระบบ: 4 กฎเสี่ยง, waterfall ledger, basket lock
py scripts\wealth_sim.py
```

ค่า n% ทั้งหมด (ขนาดไม้, circuit breaker, sweep, ภาษี, FX, ตะกร้า) อยู่ใน `config/wealth.yaml`

**3 ตะกร้า** (คัดจากข้อมูลจริง — ปรับใน yaml ได้):
- **Basket 1 Cash Flow** — `PG, JNJ, PEP, KO, MCD, ABBV` (ปันผลโตเหนือเงินเฟ้อ)
- **Basket 2 DRIP** — `COST, GS, CAT, TXN, BLK` (เมกะแคป DPS สูง, ปันผล/ครั้ง ≥ $1)
- **Basket 3 Growth** — `NVDA, AMZN, GOOGL, META, AAPL` (🔒 ล็อกจนกว่า B1/B2 นิ่ง)

> เกณฑ์ fractional ใน SRS ทำงานจริง: `MSFT` ($0.91/ครั้ง) และ `AVGO` ($0.65 หลัง split) ถูกตัดออกจาก DRIP เพราะปันผล/ครั้ง < $1

## แนวคิดหลัก

ทุกอย่างสื่อสารผ่านคิวของ **Event** เดียว:

```
MarketEvent → Strategy  → SignalEvent
SignalEvent → Portfolio → OrderEvent
OrderEvent  → Execution → FillEvent
FillEvent   → Portfolio (อัปเดต position/เงินสด)
```

เพราะ backtest กับ live ใช้ Event ชนิดเดียวกัน กลยุทธ์จึงไม่ต้องแก้โค้ดเลยเมื่อย้ายไปเทรดจริง

## Roadmap

- [x] เฟส 1 — backtest engine + ข้อมูลฟรี + ตัวอย่างกลยุทธ์ + เมตริก
- [x] เฟส 2 — กลยุทธ์เพิ่ม + research (sweep, walk-forward) + notebook + Alpaca paper trading
- [x] เฟส 3 — sync position จาก Alpaca ตอนเริ่ม + trade journal/state + alerts
- [~] เฟส 4 — fill แท่งถัดไป ✅, benchmark + กลยุทธ์เพิ่ม ✅ | เหลือ: intraday, corporate actions, cost model ละเอียด
- [ ] เฟส 5 — กลยุทธ์ขั้นสูง (pairs, ML), point-in-time universe (กัน survivorship bias) + ขยายตลาด

## ข้อจำกัดที่ควรรู้ (เฟสปัจจุบัน)

- Backtest fill ที่ราคาปิดแท่งเดียวกับสัญญาณ (look-ahead เล็กน้อย) — ของจริงควร fill แท่งถัดไป
- Portfolio ตอน live เก็บบัญชีของตัวเองแยกจาก Alpaca (Alpaca คือความจริงของ position)
- กลยุทธ์ตัวอย่างเป็น long-only ตัวละ position เพื่อความเรียบง่าย
