# Signal Engine — Implementation Notes (Phase 6)

## Package layout

```
backend/app/strategy/
  config.py          StrategyConfig + ScoreWeights
  schemas.py         BUY/SELL/WAIT/NO_TRADE typed models
  conditions.py      Directional condition scoring
  setup_detector.py  BUY/SELL setup detection
  confidence.py      Threshold → direction mapping
  filters.py         MarketConditionFilter + ATR bands
  signal_engine.py   Entry / SL / TP / RR validation
  explanation.py     Reasons + risks from real conditions
  engine.py          StrategyEngine + SignalStore
```

## Orchestration flow

```
bars_by_tf
  → MultiTimeframeAnalyzer (Phase 5)
  → SmcEngine on 4H / 1H / 15M closed windows (Phase 4)
  → TechnicalAnalysisEngine on 15M (ATR) (Phase 3)
  → detect_setups (score both sides)
  → volatility + market filters
  → compute_levels + validate
  → direction_from_scores
  → explanation + dedup/expire
  → StrategyAnalyzeResult
```

## API

### `GET /api/strategy/analyze`

Query: `symbol`, `as_of`, `timeframes`, `limit`, optional threshold/RR overrides.

Response highlights:

- `signal`, `score`, `score_label`
- `entry`, `stop_loss`, `targets[]`, `primary_rr`
- `market_context`, `conditions[]`, `reasons[]`, `risks[]`
- `strategy_version`, `config`

### `GET /api/strategy/history`

In-memory history of stored signals (BUY/SELL/WAIT). Not fabricated.

### `POST /api/strategy/history/clear`

Dev/test helper.

## Deduplication

Same `setup_id` while ACTIVE/CONFIRMED refreshes the existing `signal_id` instead of inserting duplicates.

## Testing

See `backend/tests/test_strategy_*.py`:

- scoring / thresholds / weights  
- SL/TP side + RR validation  
- future-bar leakage  
- unsafe market filter  
- API phase wiring  

## Non-goals

- ML probability  
- Backtest optimizer  
- Broker orders  
- Live news feed  
