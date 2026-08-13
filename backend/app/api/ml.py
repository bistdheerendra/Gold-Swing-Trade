"""ML HTTP API — Phase 8 dataset + Phase 9 research training (no live predict)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.backtest.data import ProviderHistoricalAdapter
from app.core.config import Settings, get_settings
from app.core.errors import ValidationAppError
from app.market.deps import get_market_service
from app.market.schemas import ANALYSIS_TIMEFRAMES, ensure_utc, parse_timeframe
from app.market.service import MarketDataService
from app.ml.config import DatasetConfig, FeatureConfig, LabelConfig
from app.ml.dataset_builder import (
    DatasetBuilder,
    clear_datasets,
    get_dataset,
    get_dataset_rows,
)
from app.ml.model_registry import get_model, list_models, register_model
from app.ml.schemas import DatasetBuildResult, PointInTimeAudit
from app.ml.trainer import ModelTrainer, load_dataset_for_training

router = APIRouter(prefix="/ml", tags=["ml"])


class DatasetBuildRequest(BaseModel):
    symbol: str = "XAUUSD"
    timeframe: str = "15m"
    start: Optional[str] = None
    end: Optional[str] = None
    feature_version: str = "1.0.0"
    label_version: str = "1.0.0"
    dataset_version: str = "1.0.0"
    limit: int = Field(default=400, ge=160, le=5000)
    warmup_bars: int = 80
    row_step: int = 1
    include_strategy: bool = True


class AuditRequest(BaseModel):
    timestamp: str


class TrainRequest(BaseModel):
    dataset_id: str
    target: str = "direction"
    model_type: Optional[str] = Field(
        default=None,
        description="If set, train only this type; else compare all and select on validation",
    )
    random_seed: int = 42
    run_test: bool = True


class EvaluateRequest(BaseModel):
    model_id: str
    split: str = Field(default="test", pattern="^(train|validation|test)$")


@router.post("/dataset/build", response_model=DatasetBuildResult)
async def build_dataset(
    body: DatasetBuildRequest,
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetBuildResult:
    try:
        parse_timeframe(body.timeframe)
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc

    start = _parse_dt(body.start) if body.start else None
    end = _parse_dt(body.end) if body.end else None
    if start and end and start >= end:
        raise ValidationAppError("start must be before end")

    adapter = ProviderHistoricalAdapter(service)
    bars_by_tf: Dict[str, List] = {}
    for tf in ANALYSIS_TIMEFRAMES:
        bars_by_tf[tf] = await adapter.load(
            body.symbol.upper(), tf, start=start, end=end, limit=body.limit
        )

    cfg = DatasetConfig(
        dataset_version=body.dataset_version,
        symbol=body.symbol.upper(),
        timeframe=body.timeframe,
        warmup_bars=body.warmup_bars,
        row_step=body.row_step,
        strategy_version=settings.strategy_version or "1.0.0",
        feature=FeatureConfig(
            feature_version=body.feature_version,
            include_strategy=body.include_strategy,
        ),
        label=LabelConfig(
            label_version=body.label_version,
            include_strategy_outcome=body.include_strategy,
        ),
        output_dir=str(Path("data/ml_datasets")),
    )
    builder = DatasetBuilder(cfg)
    try:
        return builder.build(bars_by_tf, start=start, end=end, source="provider")
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc


@router.get("/dataset/{dataset_id}", response_model=DatasetBuildResult)
async def get_dataset_api(dataset_id: str) -> DatasetBuildResult:
    result = get_dataset(dataset_id)
    if result is None:
        raise ValidationAppError(f"Unknown dataset_id: {dataset_id}")
    return result


@router.get("/dataset/{dataset_id}/stats")
async def get_dataset_stats(dataset_id: str) -> dict:
    result = get_dataset(dataset_id)
    if result is None:
        raise ValidationAppError(f"Unknown dataset_id: {dataset_id}")
    return {
        "dataset_id": dataset_id,
        "statistics": result.statistics.model_dump(),
        "split": result.metadata.split.model_dump(),
        "missing_value_statistics": result.metadata.missing_value_statistics,
    }


@router.get("/dataset/{dataset_id}/audit", response_model=PointInTimeAudit)
async def audit_dataset(
    dataset_id: str,
    timestamp: str,
) -> PointInTimeAudit:
    result = get_dataset(dataset_id)
    rows = get_dataset_rows(dataset_id)
    if result is None or rows is None:
        raise ValidationAppError(f"Unknown dataset_id: {dataset_id}")
    try:
        return DatasetBuilder(result.config).audit_row(rows, timestamp)
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc


@router.post("/dataset/clear")
async def clear_ml_datasets() -> dict:
    clear_datasets()
    return {"status": "cleared"}


@router.post("/train")
async def train_model(body: TrainRequest) -> dict:
    """Research training — fit on TRAIN, select on VALIDATION, optional held-out TEST."""
    try:
        dataset = load_dataset_for_training(dataset_id=body.dataset_id)
    except (ValueError, FileNotFoundError) as exc:
        raise ValidationAppError(str(exc)) from exc
    trainer = ModelTrainer(random_seed=body.random_seed)
    try:
        meta = trainer.train(
            dataset,
            target=body.target,
            model_type=body.model_type,
            run_test=body.run_test,
        )
    except Exception as exc:  # noqa: BLE001
        raise ValidationAppError(f"Training failed: {exc}") from exc
    register_model(meta)
    return {
        "status": "RESEARCH",
        "model_id": meta["model_id"],
        "selected_model_type": meta["selected_model_type"],
        "target": meta["target"],
        "train_metrics": meta["train_metrics"],
        "validation_metrics": meta["validation_metrics"],
        "test_metrics": meta["test_metrics"],
        "baselines": meta["baselines"],
        "overfitting": meta["overfitting"],
        "feature_importance": meta["feature_importance"],
        "test_filter": meta.get("test_filter"),
        "notes": meta["notes"],
    }


@router.get("/models")
async def list_ml_models() -> dict:
    models = list_models()
    return {
        "count": len(models),
        "models": [
            {
                "model_id": m["model_id"],
                "model_type": m["model_type"],
                "target": m["target"],
                "status": m.get("status", "RESEARCH"),
                "dataset_id": m.get("dataset_id"),
                "trained_at": m.get("trained_at"),
                "overfitting": m.get("overfitting"),
                "scores": m.get("scores"),
            }
            for m in models
        ],
    }


@router.get("/models/{model_id}")
async def get_ml_model(model_id: str) -> dict:
    meta = get_model(model_id)
    if meta is None:
        raise ValidationAppError(f"Unknown model_id: {model_id}")
    return meta


@router.post("/evaluate")
async def evaluate_model(body: EvaluateRequest) -> dict:
    """Return stored split metrics for a registered research model (no retrain)."""
    meta = get_model(body.model_id)
    if meta is None:
        raise ValidationAppError(f"Unknown model_id: {body.model_id}")
    key = {
        "train": "train_metrics",
        "validation": "validation_metrics",
        "test": "test_metrics",
    }[body.split]
    return {
        "model_id": body.model_id,
        "split": body.split,
        "metrics": meta.get(key, {}),
        "status": meta.get("status", "RESEARCH"),
        "note": "RESEARCH ONLY — metrics from prior train/val/test run",
    }


@router.get("/reports/{model_id}")
async def get_ml_report(model_id: str) -> dict:
    meta = get_model(model_id)
    if meta is None:
        raise ValidationAppError(f"Unknown model_id: {model_id}")
    return {
        "model_id": model_id,
        "status": meta.get("status", "RESEARCH"),
        "target": meta.get("target"),
        "model_type": meta.get("model_type"),
        "summary_table": {
            "train": meta.get("train_metrics"),
            "validation": meta.get("validation_metrics"),
            "test": meta.get("test_metrics"),
        },
        "baselines": meta.get("baselines"),
        "calibration_validation": meta.get("calibration_validation"),
        "feature_importance": meta.get("feature_importance"),
        "explainability": meta.get("explainability"),
        "filter_research": meta.get("filter_research"),
        "test_filter": meta.get("test_filter"),
        "overfitting": meta.get("overfitting"),
        "walk_forward_architecture": meta.get("walk_forward_architecture"),
        "trade_only_win_loss": meta.get("trade_only_win_loss"),
        "notes": meta.get("notes"),
        "label": "RESEARCH ONLY",
    }


@router.get("/signal")
async def ml_signal_alias(
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    symbol: Optional[str] = None,
    as_of: Optional[str] = None,
    model_id: Optional[str] = None,
    mode: str = "ML_FILTER",
) -> dict:
    """Alias for Phase 10 combined analyze — research only, no orders."""
    from datetime import timezone

    from app.combined.config import CombinedSignalConfig
    from app.combined.engine import CombinedSignalEngine
    from app.market.schemas import OHLCVQuery, parse_timeframe
    from app.strategy.config import StrategyConfig

    sym = (symbol or settings.market_symbol).upper()
    as_of_utc = (
        ensure_utc(datetime.fromisoformat(as_of.replace("Z", "+00:00")))
        if as_of
        else datetime.now(timezone.utc)
    )
    bars_by_tf: Dict[str, List] = {}
    for tf in ANALYSIS_TIMEFRAMES:
        bars = await service.get_ohlcv(
            OHLCVQuery(symbol=sym, timeframe=parse_timeframe(tf), limit=500)
        )
        if not bars:
            bars, _ = await service.ensure_sample_data(sym, tf, bars=300)
        bars_by_tf[tf] = list(bars)
    engine = CombinedSignalEngine(
        CombinedSignalConfig(model_id=model_id),
        strategy_config=StrategyConfig(
            strategy_version=settings.strategy_version
            if settings.strategy_version not in ("", "none")
            else "1.0.0"
        ),
    )
    result = engine.analyze(
        bars_by_tf, symbol=sym, as_of=as_of_utc, model_id=model_id, mode=mode.upper()
    )
    return result.model_dump(mode="json")


def _parse_dt(raw: str) -> datetime:
    try:
        return ensure_utc(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except Exception as exc:  # noqa: BLE001
        raise ValidationAppError(f"Invalid datetime: {raw}") from exc
