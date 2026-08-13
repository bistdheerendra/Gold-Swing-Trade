"""Build leakage-free ML datasets from causal engines."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from app.backtest.engine import resample_ohlcv
from app.market.schemas import ANALYSIS_TIMEFRAMES, OHLCVBar, ensure_utc, parse_timeframe
from app.ml.config import DatasetConfig
from app.ml.dataset_split import assert_no_split_contamination, chronological_split
from app.ml.dataset_validator import DatasetValidator
from app.ml.exporter import export_csv, export_metadata, try_export_parquet
from app.ml.feature_builder import FeatureBuilder
from app.ml.feature_schema import feature_catalog
from app.ml.label_builder import LabelBuilder
from app.ml.schemas import (
    DatasetBuildResult,
    DatasetMetadata,
    DatasetRow,
    PointInTimeAudit,
)
from app.ml.statistics import compute_statistics
from app.mtf.analyzer import MultiTimeframeAnalyzer
from app.mtf.sync import candle_close_time
from app.smc.engine import SmcEngine
from app.strategy.config import StrategyConfig
from app.strategy.engine import SignalStore, StrategyEngine
from app.ta.engine import TechnicalAnalysisEngine

HTFS = ANALYSIS_TIMEFRAMES


class DatasetBuilder:
    def __init__(self, config: Optional[DatasetConfig] = None) -> None:
        self.config = config or DatasetConfig()
        self.feature_builder = FeatureBuilder(self.config.feature)
        self.label_builder = LabelBuilder(self.config.label)
        self.ta_engine = TechnicalAnalysisEngine()
        self.smc_engine = SmcEngine()
        self.mtf_analyzer = MultiTimeframeAnalyzer()
        self.validator = DatasetValidator()

    def build(
        self,
        bars_by_tf: Mapping[str, Sequence[OHLCVBar]],
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        source: str = "provider",
        output_root: Optional[Path] = None,
        progress_every: int = 0,
    ) -> DatasetBuildResult:
        cfg = self.config
        entry_tf = cfg.timeframe
        entry = list(bars_by_tf.get(entry_tf) or bars_by_tf.get("15m") or [])
        if not entry:
            raise ValueError("No entry-timeframe bars available")

        prepared: Dict[str, List[OHLCVBar]] = {}
        for tf in HTFS:
            if tf in bars_by_tf and bars_by_tf[tf]:
                prepared[tf] = list(bars_by_tf[tf])
            else:
                prepared[tf] = resample_ohlcv(entry, tf)

        if start:
            su = ensure_utc(start)
            entry = [b for b in entry if ensure_utc(b.timestamp) >= su]
        if end:
            eu = ensure_utc(end)
            entry = [b for b in entry if ensure_utc(b.timestamp) <= eu]
        prepared[entry_tf] = entry

        if cfg.label.labeling_mode == "triple_barrier":
            max_h = int(cfg.label.triple_barrier.horizon_bars)
        else:
            max_h = max(cfg.label.horizons) if cfg.label.horizons else 0
        warmup = cfg.warmup_bars
        min_needed = warmup + max_h + 5
        if len(entry) < min_needed:
            raise ValueError(
                f"Insufficient bars: need at least {min_needed} "
                f"(warmup={warmup} + horizon={max_h} + 5), got {len(entry)}. "
                f"Raise the bar limit or refresh market data, then retry."
            )

        need_strategy = cfg.feature.include_strategy or cfg.label.include_strategy_outcome
        store = SignalStore()
        strategy_engine = (
            StrategyEngine(
                StrategyConfig(strategy_version=cfg.strategy_version),
                store=store,
            )
            if need_strategy
            else None
        )

        # Precompute ATR once for triple-barrier labels (causal at each index)
        if cfg.label.labeling_mode == "triple_barrier":
            self.label_builder.prime_atr(entry)

        max_ctx = max(80, int(cfg.max_context_bars))
        rows: List[DatasetRow] = []
        end_i = len(entry) - max_h
        for i in range(warmup, end_i):
            if (i - warmup) % max(1, cfg.row_step) != 0:
                continue
            if progress_every and (i - warmup) % progress_every == 0:
                print(
                    f"  dataset build {i}/{end_i} ({100.0 * i / max(1, end_i):.1f}%)",
                    flush=True,
                )
            bar = entry[i]
            as_of = candle_close_time(bar, entry_tf)
            windowed = {}
            for tf, series in prepared.items():
                clipped = [
                    b
                    for b in series
                    if ensure_utc(b.timestamp) <= ensure_utc(bar.timestamp)
                ]
                windowed[tf] = clipped[-max_ctx:]
            entry_window = windowed.get(entry_tf) or entry[max(0, i + 1 - max_ctx) : i + 1]
            if len(entry_window) < 30:
                continue

            ta = self.ta_engine.analyze(
                entry_window,
                symbol=cfg.symbol,
                timeframe=entry_tf,
                as_of_index=len(entry_window) - 1,
            )
            smc = self.smc_engine.analyze(
                entry_window,
                symbol=cfg.symbol,
                timeframe=entry_tf,
                as_of_index=len(entry_window) - 1,
            )
            mtf = self.mtf_analyzer.analyze(
                windowed, symbol=cfg.symbol, as_of=as_of, timeframes=list(HTFS)
            )

            strategy = None
            if need_strategy and strategy_engine is not None:
                try:
                    strategy = strategy_engine.analyze(
                        windowed,
                        symbol=cfg.symbol,
                        as_of=as_of,
                        timeframes=list(HTFS),
                    )
                except Exception:
                    strategy = None

            local_idx = len(entry_window) - 1
            features = self.feature_builder.build_with_close(
                bar=bar,
                index=local_idx,
                ta=ta,
                smc=smc,
                mtf=mtf,
                strategy=strategy,
            )
            # Labels use FULL entry series with global index i (future bars allowed)
            labels = self.label_builder.build(entry, i, strategy=strategy)
            if cfg.label.labeling_mode == "triple_barrier" and labels.get("direction") is None:
                continue

            latest_smc = None
            if smc.bos:
                latest_smc = smc.bos[-1].id
            elif smc.liquidity_sweeps:
                latest_smc = smc.liquidity_sweeps[-1].id

            audit = {
                "latest_source_candle": bar.timestamp.isoformat(),
                "latest_htf_candles": {
                    tf: (windowed[tf][-1].timestamp.isoformat() if windowed.get(tf) else None)
                    for tf in HTFS
                },
                "latest_smc_event": latest_smc,
                "latest_strategy_event": strategy.signal.value if strategy else None,
                "as_of": as_of.isoformat(),
                "labeling_mode": cfg.label.labeling_mode,
            }

            rows.append(
                DatasetRow(
                    timestamp=bar.timestamp.isoformat(),
                    symbol=cfg.symbol.upper(),
                    timeframe=entry_tf,
                    index=i,
                    features=features,
                    labels=labels,
                    audit=audit,
                )
            )

        self.validator.validate(rows)
        train, val, test, split = chronological_split(
            rows,
            train_ratio=cfg.train_ratio,
            validation_ratio=cfg.validation_ratio,
            test_ratio=cfg.test_ratio,
        )
        assert_no_split_contamination(train, val, test)
        stats = compute_statistics(rows)

        dataset_id = str(uuid.uuid4())
        root = Path(output_root or cfg.output_dir) / dataset_id
        root.mkdir(parents=True, exist_ok=True)
        files = [
            str(export_csv(root / "all.csv", rows)),
            str(export_csv(root / "train.csv", train)),
            str(export_csv(root / "validation.csv", val)),
            str(export_csv(root / "test.csv", test)),
        ]
        if try_export_parquet(root / "all.parquet", rows):
            files.append(str(root / "all.parquet"))

        catalog = feature_catalog(entry_tf)
        notes = [
            "FEATURE = past/present only; LABEL = future only",
            "Scalers must be fit on TRAIN only",
            f"catalog_size={len(catalog)}",
            f"labeling_mode={cfg.label.labeling_mode}",
            f"max_context_bars={cfg.max_context_bars}",
        ]
        if cfg.label.labeling_mode == "triple_barrier":
            tb = cfg.label.triple_barrier
            notes.extend(
                [
                    f"triple_barrier N={tb.horizon_bars} k={tb.atr_mult} atr_period={tb.atr_period}",
                    "Phase 11.8 candle-level research dataset — not wired to Phase 6/10",
                    "Do not confuse with Phase 8 trade-outcome datasets under data/ml_datasets/",
                ]
            )
        else:
            notes.append("No model training in Phase 8 builder itself")

        meta = DatasetMetadata(
            dataset_id=dataset_id,
            dataset_version=cfg.dataset_version,
            feature_version=cfg.feature.feature_version,
            label_version=cfg.label.label_version,
            strategy_version=cfg.strategy_version,
            symbol=cfg.symbol.upper(),
            timeframe=entry_tf,
            start=rows[0].timestamp if rows else "",
            end=rows[-1].timestamp if rows else "",
            row_count=len(rows),
            feature_count=stats.feature_count,
            label_count=stats.label_count,
            timezone=cfg.timezone,
            source=source,
            split=split,
            missing_value_statistics=stats.missing_by_feature,
            output_files=files,
            notes=notes,
        )
        export_metadata(root / "dataset_metadata.json", meta)
        files.append(str(root / "dataset_metadata.json"))
        meta.output_files = files

        result = DatasetBuildResult(
            dataset_id=dataset_id,
            metadata=meta,
            statistics=stats,
            preview_rows=rows[:25],
            config=cfg,
            output_dir=str(root),
        )
        store_dataset(result, rows)
        return result

    def audit_row(self, rows: Sequence[DatasetRow], timestamp: str) -> PointInTimeAudit:
        for r in rows:
            if r.timestamp == timestamp:
                return PointInTimeAudit(
                    timestamp=r.timestamp,
                    index=r.index,
                    latest_source_candle=r.audit.get("latest_source_candle"),
                    latest_htf_candles=r.audit.get("latest_htf_candles") or {},
                    latest_smc_event=r.audit.get("latest_smc_event"),
                    latest_strategy_event=r.audit.get("latest_strategy_event"),
                    feature_keys=sorted(r.features.keys()),
                )
        raise ValueError(f"No row for timestamp {timestamp}")


_DATASETS: Dict[str, DatasetBuildResult] = {}
_ROWS: Dict[str, List[DatasetRow]] = {}


def store_dataset(result: DatasetBuildResult, rows: List[DatasetRow]) -> None:
    _DATASETS[result.dataset_id] = result
    _ROWS[result.dataset_id] = rows


def get_dataset(dataset_id: str) -> Optional[DatasetBuildResult]:
    return _DATASETS.get(dataset_id)


def get_dataset_rows(dataset_id: str) -> Optional[List[DatasetRow]]:
    return _ROWS.get(dataset_id)


def clear_datasets() -> None:
    _DATASETS.clear()
    _ROWS.clear()
