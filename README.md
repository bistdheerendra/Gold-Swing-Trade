# Gold Swing AI

Production-oriented **decision-support** platform for **PAXGUSD** and **SLVONUSD** (Delta Exchange India) swing analysis.

> This system analyzes markets, scores setups, and can recommend BUY / SELL / **WAIT** / **NO TRADE**.
> It does **not** execute real-money trades in early phases.

## Current status

**Phase 11.12 complete · Dual Delta instruments:** public candles for **PAXGUSD** and **SLVONUSD** (independent research tracks; no API key; symbols verified via `/v2/products`). UI tabs `PAXGUSD | SLVONUSD` with gold/silver themes. PAXGUSD Phase 12 remains **NO-GO**; SLVONUSD starts its own gate unevaluated. Mock only with `ALLOW_MOCK_DATA=true` for pytest.

> This system analyzes markets, scores setups, and can recommend BUY / SELL / **WAIT** / **NO TRADE**.
> It does **not** execute real-money trades. Market data is read-only (no API keys / no orders).

## Project layout

```
Gold Trader/
├── frontend/          # React dashboard
├── backend/           # FastAPI API (+ app/strategy)
├── ml/                # ML pipelines (later phases)
├── strategy/          # Placeholder (logic lives in backend/app/strategy)
├── data/              # Sample / fixture market data
├── database/          # SQL init + migrations
├── tests/             # Cross-cutting / integration tests
├── docs/              # Architecture & phase docs
├── docker/            # Dockerfiles + nginx
└── docker-compose.yml
```

## Quick start (local)

### 1. Environment

```bash
cp .env.example .env
```

### 2. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard: [http://localhost:5173](http://localhost:5173)

### 4. Infrastructure (optional)

Docker Desktop required:

```bash
docker compose up -d postgres redis
```

## Tests

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

## Design principles

1. Correctness before visuals
2. WAIT / NO TRADE is a first-class outcome
3. No look-ahead bias in features or labels
4. Loose coupling between data → indicators → SMC → strategy → ML → risk → UI
5. Central configuration via environment (see `.env.example`)

## Next phase

Say **`START PHASE 12`** for Paper Trading + Live Monitoring + Alerts.

## Documentation

- [PROJECT.md](PROJECT.md) — complete project information
- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Risk management](docs/risk-management.md)
- [Position sizing](docs/position-sizing.md)
- [PAXGUSD instrument](docs/paxgusd-instrument.md)
- [Cost model](docs/cost-model.md)
- [Strategy](docs/strategy.md)
- [Signal engine](docs/signal-engine.md)
- [Backtesting](docs/backtesting.md)
- [Execution model](docs/execution-model.md)
- [Performance metrics](docs/performance-metrics.md)
- [ML dataset](docs/ml-dataset.md)
- [ML features](docs/ml-features.md)
- [ML labels](docs/ml-labels.md)
- [Data leakage](docs/data-leakage.md)
- [Data model](docs/data-model.md)
- [Market data](docs/market-data.md)
- [Chart](docs/chart.md)
- [Technical analysis](docs/technical-analysis.md)
- [SMC rules](docs/smc-rules.md)
- [Multi-timeframe](docs/multi-timeframe.md)
- [API](docs/api.md)
"# Gold-Swing-Trade" 
