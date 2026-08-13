# PROJECT.md — Gold Swing AI (Gold Trader)

**Location:** `Desktop/Gold Trader`  
**Product name:** Gold Swing AI  
**Folder name:** Gold Trader  
**Current phase:** **11.12 — SLVONUSD Instrument + Silver Theme (complete)** · **11.12.1 Live Paper UI (research)**  
**Next phase:** **Blocked** — Phase 12 still NO-GO for **PAXGUSD**; **SLVONUSD** starts its own Phase 12 gate from scratch (not yet evaluated). Monitor PAXGUSD per [docs/monitoring-checklist.md](docs/monitoring-checklist.md)  
**Last updated:** 2026-08-13

---

## 1. Project overview

Gold Swing AI is a **production-oriented decision-support / quantitative research platform** for **PAXGUSD** and **SLVONUSD** (both Delta Exchange India live perpetuals).

It analyzes market data, detects technical + Smart Money Concepts (SMC) structure, scores multi-timeframe bias, generates **BUY / SELL / WAIT / NO TRADE** signals (rule + optional ML filter), and sizes risk via an instrument-aware risk engine.

### What it is
- Market analysis and decision-support system
- Research platform for swing setups on **PAXGUSD** and **SLVONUSD** (independent tracks — never blended)
- Desktop-first terminal UI with gold / silver instrument themes

### What it is NOT (yet)
- Automatic real-money trade execution
- A broker bot
- A guaranteed profit system

> Real broker execution is only considered after backtesting, paper trading, and validation (Phase 12–13+). Each instrument is gated on its own evidence.

---

## 2. Primary goals

1. Ingest and validate OHLCV market data  
2. Compute causal technical indicators  
3. Detect SMC structures (BOS, CHoCH, FVG, OB, liquidity, etc.)  
4. Combine multi-timeframe context (1D → 4H → 1H → 15M)  
5. Rule-based + ML-filtered signals, risk sizing, backtest  
6. Always allow **WAIT / NO TRADE** when conditions are unclear  

**Priority order:**  
Correctness → Data quality → Backtesting → Risk → ML validation → UI

---

## 3. Technology stack

| Layer | Stack |
|-------|--------|
| Frontend | React, TypeScript, Vite, Tailwind CSS, TradingView Lightweight Charts |
| Backend | Python, FastAPI, Pydantic, Pandas, NumPy |
| TA | Custom causal indicators (Phase 3) |
| SMC | Custom deterministic detectors (Phase 4) |
| Database | PostgreSQL (configured; default store can be in-memory for local) |
| Cache | Redis (optional, Docker) |
| Tests | Pytest (backend), Vitest (frontend) |
| Infra | Docker, docker-compose |

---

## 4. High-level architecture

```
Market Data (real free-tier)  ← Phase 11.5
  → Data Validation
  → Historical Storage
  → Chart Visualization          ← Phase 2
  → Technical Indicators         ← Phase 3
  → SMC Detection Engine         ← Phase 4
  → Multi-Timeframe Analysis     ← Phase 5
  → Rule-Based Strategy Engine   ← Phase 6
  → Backtesting                  ← Phase 7
  → ML Dataset / Features        ← Phase 8
  → ML Training & Validation     ← Phase 9
  → Combined Signal (Rule + ML)  ← Phase 10
  → Risk / Position Sizing       ← Phase 11
  → Real Market Data Migration   ← Phase 11.5
  → Strategy Recalibration       ← Phase 11.6 (NO-GO)
  → Diagnosis Review             ← Phase 11.7 (no rewrite; NO-GO)
  → Candle-Level ML Labeling     ← Phase 11.8 (research; weak skill)
  → Liquidity Sweep Investigation← Phase 11.9 (inconclusive; no rule change)
  → Trading Session Overlay      ← Phase 11.10 (UI/reference only)
  → Post-Fix Backtest Re-Run     ← Phase 11.11 (NO-GO stands)
  → SLVONUSD + Silver Theme      ← Phase 11.12
  → Live Paper UI (browser)      ← Phase 11.12.1 (research only; not Phase 12 GO)
  → Paper Trading + Alerts       ← Phase 12 (blocked for PAXGUSD; SLVONUSD unevaluated)
  → Production Hardening
```

Components are loosely coupled. UI must not hide trading logic.

---

## 5. Project folder structure

```
Gold Trader/
├── frontend/                 # React + Vite dashboard
│   └── src/
│       ├── components/       # Dashboard, chart, AppHeader, Live Paper, risk, ML pages
│       └── lib/              # API client, EMA, chart adapters, paperTrade, theme
├── backend/                  # FastAPI application
│   └── app/
│       ├── api/              # health, market, ta, smc, mtf, strategy, risk, ml…
│       ├── core/             # config, logging, errors, database
│       ├── market/           # provider, real_provider, validator, repository, service
│       ├── ta/               # indicators, structure, engine
│       ├── smc/              # BOS/CHoCH/FVG/OB/liquidity/dealing range
│       ├── mtf/              # sync, bias engine, MultiTimeframeAnalyzer
│       ├── strategy/         # rule-based signal engine
│       ├── risk/             # Instrument registry (PAXGUSD, SLVONUSD) + RiskEngine
│       ├── ml/               # dataset, train, combined filter
│       └── models/           # SQLAlchemy OHLCV model
├── backend/scripts/          # backfill_market_data, validate_phase_11_5
├── data/sample/              # Sample / fixture notes
├── data/historical/          # Real OHLCV CSV snapshots (Phase 11.5)
├── database/init/            # Postgres bootstrap SQL
├── docs/                     # Detailed technical docs
├── docker/                   # Dockerfiles + nginx
├── docker-compose.yml
├── .env / .env.example
├── README.md
└── PROJECT.md                # This file
```

---

## 6. Phase status (roadmap)

| Phase | Name | Status |
|-------|------|--------|
| 0 | Project Foundation | **COMPLETE** |
| 1 | Market Data Engine | **COMPLETE** |
| 2 | Market Chart / Dashboard | **COMPLETE** |
| 3 | Technical Analysis Engine | **COMPLETE** |
| 4 | SMC Engine | **COMPLETE** |
| 5 | Multi-Timeframe Analysis | **COMPLETE** |
| 6 | Rule-Based Trading Strategy | **COMPLETE** |
| 7 | Backtesting Engine | **COMPLETE** |
| 8 | ML Dataset + Feature Engineering | **COMPLETE** |
| 9 | ML Model Training & Validation | **COMPLETE** |
| 10 | ML + Strategy Combined Signal Engine | **COMPLETE** |
| 11 | Risk Management + Position Sizing | **COMPLETE** |
| 11.5 | Real Market Data Migration | **COMPLETE** |
| 11.6 | Strategy Recalibration on Real Data | **COMPLETE — NO-GO** |
| 11.7 | Diagnosis Review + Conditional Rule Revision | **COMPLETE — no rewrite; NO-GO** |
| 11.8 | Candle-Level ML Labeling | **COMPLETE — research; weak skill** |
| 11.9 | Liquidity Sweep Investigation | **COMPLETE — inconclusive; no rule change** |
| 11.10 | Trading Session Overlay | **COMPLETE** |
| 11.10.1 | DST-Aware Session Windows | **COMPLETE** |
| 11.11 | Post-Fix Backtest Re-Run (SL geometry) | **COMPLETE — NO-GO stands** |
| 11.12 | SLVONUSD Instrument + Silver Theme | **COMPLETE** |
| 11.12.1 | Live Paper Trades UI (client-side) | **COMPLETE** — research only; does **not** clear Phase 12 |
| 12 | Paper Trading + Live Monitoring + Alerts | **BLOCKED** (PAXGUSD NO-GO; SLVONUSD not yet gated) |
| 13 | Production Hardening & Deployment | Pending |

See [docs/roadmap.md](docs/roadmap.md) for full phase descriptions.

---

## 7. What each completed phase delivered

### Phase 0 — Foundation
- React + FastAPI + Docker scaffolds
- Central env config, logging, error handlers
- Health endpoints, gold-theme dashboard shell
- Docs: architecture, roadmap, data-model

### Phase 1 — Market Data
- `MarketDataProvider` abstraction + mock provider (now test-only)
- Timeframes: **15m, 30m, 1h, 4h, 1d** (30m added in Phase 11.5)
- Normalized OHLCV schema + validation
- In-memory + PostgreSQL repositories
- API: `/api/market/status`, `/ohlcv`, `/ingest`, `/seed`

### Phase 2 — Chart
- Candlestick chart (zoom / pan / crosshair / OHLC)
- Timeframe selector
- EMA 20 / 50 / 100 / 200 overlays (toggleable)
- Auto-seed when store empty

### Phase 3 — Technical Analysis
- Causal EMA, RSI, MACD, ADX, ATR, Bollinger
- Swing High/Low + HH/HL/LH/LL (confirmation lag)
- `TechnicalAnalysisEngine` + `GET /api/ta/analyze`
- Dashboard TA snapshot

### Phase 4 — SMC
- BOS, CHoCH (state machine), FVG lifecycle, Order Blocks
- Demand/Supply, liquidity pools, sweeps, premium/discount/eq
- `GET /api/smc/analyze` + chart overlays + SMC Analysis panel
- Rules: `docs/smc-rules.md`

### Phase 5 — Multi-Timeframe
- Closed-candle sync (no unfinished HTF candles)
- `BiasEngine` (−100…+100, configurable weights)
- `MultiTimeframeAnalyzer` + `GET /api/mtf/analyze`
- Dashboard Multi-Timeframe panel

### Phase 6 — Rule-Based Signal Engine
- Isolated `backend/app/strategy/` consuming TA + SMC + MTF
- BUY / SELL / WAIT / NO_TRADE with scoring thresholds
- Entry zone, structural SL, TP + RR validation
- Explanation engine, setup lifecycle, dedup, expiration
- `GET /api/strategy/analyze` + history
- Signal Card + Signal History UI
- Strategy version `1.0.0` (no ML / no broker)

### Phase 7 — Backtesting
- Historical measurement of Phase 6 strategy
- Equity curve, trades, win rate, drawdown, expectancy
- Cost/slippage inputs; research-only UI page

### Phase 8 — ML Dataset
- Causal feature/label pipeline (no look-ahead)
- Train / validation / test chronological splits
- Dataset build API + ML Dataset UI page

### Phase 9 — ML Training & Validation
- Model lab (logistic / RF / GB baselines)
- Validation-first selection; held-out test reporting
- Research-only metrics (not production trade authority)

### Phase 10 — Combined Signal
- Rule + optional ML filter modes
- `GET /api/combined/analyze`, compare RULE_ONLY vs ML_FILTER
- Combined Signal panel on dashboard

### Phase 11 — Risk Management (PAXGUSD)
- Instrument-aware RiskEngine + position sizing
- Margin / cost / daily-loss / consecutive-loss guards
- FIXED_1R vs RISK_PERCENT backtest modes
- Risk API + Risk & Position dashboard panel + Risk Management page
- **No** live orders, API keys, or profitability claims

### Phase 11.5 — Real Market Data Migration
- `RealMarketDataProvider` (**Delta India** primary for PAXGUSD + optional Twelve Data for XAUUSD)
- `PAXGUSD` symbol verified against Delta `GET /v2/products` (listed live perpetual)
- Default `MARKET_DATA_PROVIDER=delta_india`; mock only with `ALLOW_MOCK_DATA=true` (pytest)
- **30m** timeframe end-to-end (enum, MTF hierarchy 1D→4H→1H→30M→15M, chart selector, ML `htf_30m_bias`)
- Historical backfill script + `POST /api/market/backfill` (5 timeframes)
- Docs: [docs/market-data.md](docs/market-data.md), [docs/multi-timeframe.md](docs/multi-timeframe.md)

### Phase 11.6 — Strategy Recalibration on Real Data (**NO-GO**)
- Max-window Delta backfill reused (~16k 15m bars); expanded Phase 7 baseline
- Diagnosed Phase 10 zero-trade as warmup-after-slice measurement bug; fixed eval bounds
- TRAIN/VAL-only recalibration candidate (vol penalty 8→5) **rejected** — worsened ALL, no TEST help
- Explicit **NO-GO** for Phase 12 — see [docs/phase-11.6-recalibration-results.md](docs/phase-11.6-recalibration-results.md)

### Phase 11.7 — Diagnosis Review (**no structural rewrite; NO-GO**)
- Plain-language review of *why* 11.6 failed: win rate **and** realized R:R weak; sample too thin for surgery
- Decision gate: **do not** rewrite Phase 6 confluence on n≈34 / TEST n=6
- Docs: [docs/phase-11.7-diagnosis-review.md](docs/phase-11.7-diagnosis-review.md)

### Phase 11.8 — Candle-Level ML Labeling (**research; weak skill**)
- Triple-barrier labels (`N=8`, `k=1.0×ATR(14)`) on **full** Delta history (~16 294 rows), not UI `bar_limit=220`
- Stored under `data/ml_datasets_candle/` — Phase 8 trade-outcome datasets untouched
- Retrained logistic / RF / GB; held-out TEST beats majority by only ~2.7pp accuracy — **not wired** to Phase 6/10
- Docs: [docs/ml-labeling.md](docs/ml-labeling.md), [docs/phase-11.8-candle-ml-results.md](docs/phase-11.8-candle-ml-results.md)

### Phase 11.9 — Liquidity Sweep Investigation (**inconclusive; no rule change**)
- Quantified sweep as score-gap vs sole blocker on real PAXGUSD TRAIN+VAL
- Base rate of reclaim sweeps is low on quiet gold; lookback widen no-op; 15m fallback hurt VAL expectancy
- **No** live Phase 6 / SMC change
- Docs: [docs/phase-11.9-liquidity-sweep-investigation.md](docs/phase-11.9-liquidity-sweep-investigation.md)
- Script: `backend/scripts/phase_11_9_liquidity_sweep.py`

### Phase 11.10 — Trading Session Overlay (**UI / reference only**)
- Session windows (Asia / London / New York / London+NY Overlap) defined once in `backend/app/core/sessions.py` (IST labels, UTC computation)
- `GET /api/market/sessions` (+ `/tag`) — display/reference; does **not** feed strategy / combined / risk
- Chart: toggleable semi-transparent session bands on **15m / 30m / 1h** only (hidden on 4h/1d)
- Dashboard: session reference table + live “active now” indicator
- Docs: [docs/trading-sessions.md](docs/trading-sessions.md)

### Phase 11.10.1 — DST-Aware Session Windows
- London / New York use local 08:00–17:00 via `zoneinfo` (`Europe/London`, `America/New_York`) per candle date
- Overlap derived as London ∩ New York (no separate fixed UTC constant)
- Asia remains fixed UTC (no Japanese DST)
- Historical chart bars use that bar’s DST state; live “active now” follows today’s offsets
- Docs: [docs/trading-sessions.md](docs/trading-sessions.md) updated

### Phase 11.11 — Post-Fix Backtest Re-Run (**NO-GO stands**)
- Re-ran Phase 11.6 methodology on the same 16 382×15m PAXGUSD window after Path B `_stop_loss` fix
- Only variable: entry-anchored SL; thresholds / sweep logic unchanged
- ALL expectancy essentially flat (+0.072R → +0.070R) while trades 34→53 and max DD ~5.4%→~11.4%
- Held-out TEST flips −0.39R (n=6) → +0.41R (n=9) — too thin to trust
- SL-geometry unblocks are real and frequent at signal level; filled subset is mixed W/L — bug was not a hidden edge filter
- Docs: [docs/phase-11.11-post-fix-backtest.md](docs/phase-11.11-post-fix-backtest.md)
- Script: `backend/scripts/phase_11_11_post_fix_backtest.py`

### Phase 11.12 — SLVONUSD Instrument + Silver Theme
- Verified **SLVONUSD** live perpetual on Delta India `GET /v2/products` (contract_value `0.1`, tick `0.01`, funding 8h, position limit 62 000)
- `RealMarketDataProvider` (delta_india) supports **PAXGUSD + SLVONUSD** as separate series
- Instrument registry + risk sizing use SLVONUSD’s own spec (not PAXGUSD’s)
- Historical backfill writes `data/historical/SLVONUSD_{tf}.csv` — never merged with PAXGUSD
- UI symbol tabs: `PAXGUSD | SLVONUSD` (XAUUSD tab removed)
- Token-level **silver** theme when SLVONUSD is selected — see [docs/theming.md](docs/theming.md)
- Engines remain symbol-parameterized; each instrument is an **independent research track** with its own Phase 12 gate (SLVONUSD not yet evaluated; PAXGUSD NO-GO is not inherited)
- Docs: [docs/market-data.md](docs/market-data.md), [docs/theming.md](docs/theming.md)

### Phase 11.12.1 — Live Paper Trades UI (**research only; not Phase 12**)
- Frontend page **Live Paper** (`LivePaperTradePage`) auto-picks live strategy BUY/SELL for the selected symbol
- Size fixed at **1 PAXG** (1000 × 0.001) or **1 SLVON** (10 × 0.1); tracks SL / TP1 vs live ticker; closes on hit
- Persistence: browser `localStorage` key `gold-swing-paper-trades-v1` — **no** broker, **no** backend order API
- Engine: `frontend/src/lib/paperTrade.ts` (Vitest-covered)
- **Idempotency / anti-spam (2026-08-13):**
  - Atomic open/close against localStorage (close by trade id once)
  - `consumedKeys` blocks re-opening the same signal / same entry·SL·TP levels after close
  - Refuse open if market price is already past SL or TP (stops TP→reopen loops)
  - History load dedupes by trade id **and** fingerprint (same levels + close minute)
- Shared sticky `AppHeader` for all pages; live chart forming-candle + countdown remain separate chart polish
- Does **not** unlock Phase 12 GO, alerts, or live monitoring product scope

---

## 8. API reference (current)

Base URL (dev): `http://localhost:8000`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | App metadata / phase |
| GET | `/api/health` | Liveness |
| GET | `/api/ready` | Readiness |
| GET | `/api/market/status` | Provider/store counts + health |
| GET | `/api/market/ohlcv` | Query bars |
| GET | `/api/market/sessions` | Session defs + active now (Phase 11.10 display) |
| GET | `/api/market/sessions/tag` | Tag one UTC timestamp with session(s) |
| POST | `/api/market/ingest` | Fetch → validate → store |
| POST | `/api/market/backfill` | Multi-symbol/TF real historical pull |
| POST | `/api/market/seed` | Seed from active **real** provider |
| GET | `/api/ta/analyze` | TA + structure |
| GET | `/api/smc/analyze` | SMC events + score |
| GET | `/api/mtf/analyze` | Multi-TF bias / alignment |
| GET | `/api/strategy/analyze` | Rule-based signal + levels |
| GET | `/api/strategy/history` | Signal history |
| GET | `/api/combined/analyze` | Rule + ML combined signal |
| POST | `/api/combined/compare` | RULE_ONLY vs ML_FILTER |
| GET | `/api/risk/analyze` | Phase 10 signal → TradePlan |
| POST | `/api/risk/backtest` | RISK_PERCENT / FIXED_1R simulation |
| GET | `/api/risk/config` | Account risk config |
| PUT | `/api/risk/config` | Update config |
| GET | `/api/risk/instruments` | Instrument registry |
| GET | `/api/risk/paxgusd/spec` | PAXGUSD adapter spec |

Interactive docs: `http://localhost:8000/docs`  
Full summary: [docs/api.md](docs/api.md)

---

## 9. Configuration (central)

See `.env.example`. Important keys:

| Variable | Meaning |
|----------|---------|
| `MARKET_SYMBOL` | Default `PAXGUSD` (or `SLVONUSD`) |
| `DEFAULT_TIMEFRAME` | Default `1h` |
| `MARKET_DATA_PROVIDER` | `delta_india` (default) \| `twelvedata` \| `mock` |
| `ALLOW_MOCK_DATA` | `false` — must be `true` for pytest mock only |
| `DELTA_INDIA_BASE_URL` | `https://api.india.delta.exchange` |
| `DELTA_PAXGUSD_SYMBOL` | Verified via `/v2/products` (default `PAXGUSD`) |
| `DELTA_SLVONUSD_SYMBOL` | Verified via `/v2/products` (default `SLVONUSD`) |
| `TWELVEDATA_API_KEY` | Free key from twelvedata.com (legacy XAUUSD reference only) |
| `MARKET_DATA_STORE` | `memory` or `postgres` (prefer postgres for ML) |
| `RISK_PERCENT` / `MIN_RR` | Risk params |
| `STRATEGY_VERSION` / `MODEL_VERSION` | Version tracking |
| `VITE_API_BASE_URL` | Frontend → API base |

Do not hard-code these inside strategy/UI logic.

---

## 10. Critical trading / ML rules

### Always
- Chronological data only  
- Causal features (no future candles)  
- Closed HTF candles only in MTF  
- Allow **WAIT / NO TRADE**  
- Include costs/slippage in backtests  
- Report honestly if strategy underperforms  

### Never
- Look-ahead / data leakage  
- Random shuffle of time-series for ML  
- Force BUY/SELL when unclear  
- Optimize only on test data  
- Pretend untested features work  
- Silently fall back to mock market data  

---

## 11. How to run locally

### Backend
```bash
cd "C:\Users\admin\Desktop\Gold Trader\backend"
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend
```bash
cd "C:\Users\admin\Desktop\Gold Trader\frontend"
npm run dev
```

- UI: http://127.0.0.1:5173  
- API: http://127.0.0.1:8000/api/health  

### Real data backfill / validation
```bash
cd backend
python scripts/backfill_market_data.py
python scripts/validate_phase_11_5.py
```

### Tests
```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test
```

---

## 12. UI summary (current dashboard)

Gold-themed trading terminal with:

### Layout (2026-08-13)
- Shared sticky **`AppHeader`**: symbol tabs `PAXGUSD | SLVONUSD`, page nav, responsive hamburger `< lg`
- **Full-width price chart** on top (EMA + SMC + optional session bands; live ticker updates forming candle + countdown)
- **Equal three-column content grid** below (no empty center gap):
  - Left: Market Overview, **Trading Sessions (IST)**, Multi-Timeframe, SMC Analysis  
  - Center: SMC Overlays, TA Snapshot, EMA toggles, Signal History  
  - Right: Current Signal, Combined Signal, Risk & Position, Explainability  
- Nav to Backtest, ML Dataset, ML Model Lab, Risk Management, **Live Paper** pages

### Chart / overlays
- Candlestick zoom / pan / crosshair / OHLC banner  
- EMA 20 / 50 / 100 / 200 (toggleable)  
- SMC overlays (toggleable) — **overlay toggles update markers/price lines only** (no full chart rebuild / blank flash)  
- **Trading session bands** (Phase 11.10) — shaded Asia / London / NY / Overlap on **15m / 30m / 1h**; toggleable without chart rebuild; hidden on 4h/1d  
- Price lines cleared via `removePriceLine` (Lightweight Charts v4)

### AI Loader (`AiLoader`)
- Theme-matched **gold brick** with scan beam, orbit ring, glow  
- Sizes: `sm` / `md` / `lg`, plus inline (buttons) and overlay (long jobs)  
- Used on chart load, panel loads, risk calc, combined analyze, backtest, ML build/train  

### Decision / risk surfaces
- Live BUY / SELL / WAIT / NO TRADE signal card  
- Signal history table  
- Combined Signal (Rule + ML) panel  
- PAXGUSD / SLVONUSD risk calculator + trade plan status  
- Session reference table + live “active now” (display only)  
- **Live Paper** — client-side auto-pick + SL/TP book (localStorage; research only)  
- Research-only disclaimers throughout  

---

## 13. Documentation index

| Doc | Content |
|-----|---------|
| [README.md](README.md) | Quick start |
| [PROJECT.md](PROJECT.md) | Complete project info (this file) |
| [docs/architecture.md](docs/architecture.md) | System architecture |
| [docs/roadmap.md](docs/roadmap.md) | Phase roadmap |
| [docs/data-model.md](docs/data-model.md) | Data model |
| [docs/market-data.md](docs/market-data.md) | Market data engine (real providers) |
| [docs/phase-11.5-real-data-validation.md](docs/phase-11.5-real-data-validation.md) | Real-data Phase 7–11 report |
| [docs/phase-11.6-diagnosis.md](docs/phase-11.6-diagnosis.md) | Real-data strategy diagnosis |
| [docs/phase-11.6-recalibration-results.md](docs/phase-11.6-recalibration-results.md) | Recalibration + Phase 12 go/no-go |
| [docs/phase-11.7-diagnosis-review.md](docs/phase-11.7-diagnosis-review.md) | Why 11.6 failed; no-rewrite gate |
| [docs/ml-labeling.md](docs/ml-labeling.md) | Phase 11.8 triple-barrier candle labels |
| [docs/phase-11.8-candle-ml-results.md](docs/phase-11.8-candle-ml-results.md) | Candle-level dataset + model results |
| [docs/phase-11.9-liquidity-sweep-investigation.md](docs/phase-11.9-liquidity-sweep-investigation.md) | Phase 11.9 sweep condition investigation |
| [docs/trading-sessions.md](docs/trading-sessions.md) | Phase 11.10 session windows + chart overlay |
| [docs/phase-11.11-post-fix-backtest.md](docs/phase-11.11-post-fix-backtest.md) | Phase 11.11 post-SL-fix backtest re-run |
| [docs/monitoring-checklist.md](docs/monitoring-checklist.md) | Post-11.11 recheck cadence + escalation gates |
| [docs/recheck-log.md](docs/recheck-log.md) | Lightweight recheck log entries |
| [docs/binance-paxgusdt-research.md](docs/binance-paxgusdt-research.md) | Binance PAXGUSDT ML suggestion sidecar |
| [docs/chart.md](docs/chart.md) | Chart layer |
| [docs/technical-analysis.md](docs/technical-analysis.md) | TA engine |
| [docs/smc-rules.md](docs/smc-rules.md) | Exact SMC definitions |
| [docs/multi-timeframe.md](docs/multi-timeframe.md) | MTF sync + bias rules |
| [docs/strategy.md](docs/strategy.md) | BUY/SELL/WAIT/NO_TRADE rules |
| [docs/signal-engine.md](docs/signal-engine.md) | Strategy implementation notes |
| [docs/backtesting.md](docs/backtesting.md) | Backtest engine |
| [docs/combined-signal-engine.md](docs/combined-signal-engine.md) | Rule + ML filter |
| [docs/risk-management.md](docs/risk-management.md) | Risk engine |
| [docs/paxgusd-instrument.md](docs/paxgusd-instrument.md) | PAXGUSD instrument spec |
| [docs/slvonusd-instrument.md](docs/slvonusd-instrument.md) | SLVONUSD instrument spec |
| [docs/theming.md](docs/theming.md) | Gold / silver instrument theme tokens |
| [docs/position-sizing.md](docs/position-sizing.md) | Position sizing |
| [docs/api.md](docs/api.md) | API summary |

---

## 14. Known limitations (current)

1. **PAXGUSD and SLVONUSD are independent Delta series — never blend candles, signals, or backtest stats**  
2. **Legacy XAUUSD (Twelve Data), if used, is a different source — do not blend with Delta**  
3. **Delta India public API rate limits** may throttle backfill speed  
4. Default persistence is **in-memory** unless Postgres is configured — prefer postgres for durable ML datasets  
5. Docker may not be installed on all machines — compose files are ready  
6. Demand/Supply zones currently map from Order Blocks (documented)  
7. Strategy scores are research heuristics, not proven expectancy  
8. ML confidence is **not** a guaranteed win probability  
9. Signal history is in-memory (cleared on API restart)  
10. **No Phase-12 paper/live product yet** (blocked by Phase 11.6 NO-GO for PAXGUSD; SLVONUSD not yet gated). A **client-side Live Paper** UI (11.12.1) exists for research only — browser localStorage, no broker, no alerts pipeline  
11. No broker order placement or real-money paths  
12. **Phase 11.6 — real PAXGUSD rule strategy is not Phase-12-ready:** expanded max-history ALL backtest is only weakly positive (~+0.07R pre-recal, ~+0.01R after a rejected vol-penalty tweak, n≈34–40); held-out TEST is **−0.39R on n=6**. Delta history starts ~2026-02-19 — sample remains thin. Default `StrategyConfig` thresholds unchanged; candidate `config_real_recal.json` is audit-only.  
13. Phase 11.5 “0 trades” on Phase 10 TEST was largely a **measurement bug** (warmup applied after slicing a short TEST window); fixed in 11.6 via full-series context + `chronological_eval_bounds`. After the fix, TEST produces trades but still loses on average.  
14. **Phase 11.7 — insufficient evidence for a Phase 6 structural rewrite:** win rate (~33–38%) and payoff (TEST PF ~0.55) both look weak, and blockers *suggest* location/MTF/RR friction, but n is too small to localize a safe structural change. Forcing confluence edits now would be overfitting with a bigger blast radius than threshold tweaks. Prefer more history before reopening rule surgery.  
15. **Phase 11.8 — candle-level ML is research-only:** full-history triple-barrier dataset (~16 294 rows) replaces the thin ~34 trade-outcome sample for *ML research*, but held-out directional skill is weak (~2.7pp over majority). Artifacts live in `data/ml_datasets_candle/` and `artifacts/ml_candle/`. **Not** wired into Phase 6/10. UI `bar_limit=220` remains preview-only.  
16. **Phase 11.9 — liquidity sweep investigation inconclusive:** on TRAIN+VAL, sweep is unmet on ~78% of high-score no-trade samples (15-pt score gap) but sole unmet only ~6%. 1H reclaim sweeps are sparse (avg ~138 bars between unique events; ~23% of samples have any sweep in 40 bars). Widening `recent_sweep_bars` did nothing; 1H→15m fallback added trades but worsened VAL expectancy. **No production rule change.** Live `✗ Liquidity Sweep` on NO_TRADE/INVALIDATED cards is often a listed unmet condition, not a hard `liquidity_required` veto.
17. **Phase 11.11 — SL geometry fix does not clear Phase 12:** controlled re-run on the same Phase 11.6 window shows ALL expectancy ~unchanged (+0.07R) with more trades and worse max DD; TEST flips positive on n=9 only. Keep the Path B SL fix; do **not** treat that as a GO.
18. **Phase 11.12 — SLVONUSD is additive and ungated:** silver has its own contract spec and candle store. PAXGUSD’s NO-GO does **not** apply to SLVONUSD, and a future SLVONUSD backtest would **not** clear PAXGUSD. Evaluate each instrument on its own evidence.
19. **Phase 11.12.1 — Live Paper is not a Phase 12 GO:** browser paper book can open/close SL/TP for research UX; it does not imply strategy expectancy, alerts, or broker readiness. Treat PnL there as illustrative only.

---

## 15. Next step

Phase 11.12 added **SLVONUSD** as a second independent Delta instrument with its own theme and Phase 12 gate (unevaluated). **11.12.1** added a client-side Live Paper UI for research — **not** a Phase 12 unlock. **PAXGUSD remains NO-GO** after Phase 11.11. Do not loosen liquidity sweep in production without a pre-registered recalibration pass. Do not blend silver and gold research results.

Optional next work (when ready):
1. Continue PAXGUSD monitoring per [docs/monitoring-checklist.md](docs/monitoring-checklist.md)
2. Fresh SLVONUSD backtest / expectancy study on its own history (does not clear PAXGUSD)
3. Prefer more history before reopening Phase 6 structural edits
4. Optional: longer legacy XAUUSD reference study (do not blend with Delta)

**Operating mode:** patience + scheduled monitoring — not more strategy code. Follow [docs/monitoring-checklist.md](docs/monitoring-checklist.md); log each pass in [docs/recheck-log.md](docs/recheck-log.md).

Do **not** run `START PHASE 12`. Do **not** auto-wire candle models into live signals. Do **not** treat Live Paper PnL as a GO signal.

Preferred next work:

1. Every ~4 weeks (or on a clear regime shift): lightweight recheck per the monitoring checklist  
2. Escalate to a full Phase-11.6-style diagnosis only when checklist thresholds fire (e.g. ~80–100 trades, or ALL expectancy &gt; +0.15R for two consecutive rechecks)  
3. Optional: Binance PAXGUSDT research sidecar ([docs/binance-paxgusdt-research.md](docs/binance-paxgusdt-research.md)) — advisory only; weekly auto backfill/retrain while API runs (`BINANCE_WEEKLY_UPDATE_ENABLED`); do not blend into Delta GO  
4. Optional: longer XAUUSD reference study (do not blend with Delta PAXGUSD)  
5. Strategy GO still required (positive held-out expectancy on a defendable sample) before **Phase 12** paper trading + alerts

```text
START PHASE 12
```

…only after a documented **GO** that survives held-out check.

---

## 16. Final principle

Build a serious quantitative trading **research** platform — not a toy indicator website.

Correctness and causal data integrity always beat visual polish.
