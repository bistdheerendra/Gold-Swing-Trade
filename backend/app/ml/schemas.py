"""Typed ML dataset schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.ml.config import DatasetConfig


class NormalizationHint(str, Enum):
    NONE = "NONE"
    STANDARDIZE = "STANDARDIZE"
    MINMAX = "MINMAX"
    LOG = "LOG"
    CATEGORICAL = "CATEGORICAL"


class FeatureMeta(BaseModel):
    name: str
    dtype: str  # float | int | category
    source: str
    timeframe: str
    description: str
    causal: bool = True
    normalization: NormalizationHint = NormalizationHint.NONE
    missing_behavior: str = "null"


class DatasetRow(BaseModel):
    timestamp: str
    symbol: str
    timeframe: str
    index: int
    features: Dict[str, Optional[float | int | str]]
    labels: Dict[str, Optional[float | int | str]]
    audit: Dict[str, Any] = Field(default_factory=dict)


class DatasetSplitSizes(BaseModel):
    train: int
    validation: int
    test: int
    total: int


class ClassCount(BaseModel):
    key: str
    count: int
    percentage: float


class DatasetStatistics(BaseModel):
    row_count: int
    feature_count: int
    label_count: int
    missing_by_feature: Dict[str, float] = Field(default_factory=dict)
    class_distribution: Dict[str, List[ClassCount]] = Field(default_factory=dict)
    feature_summary: Dict[str, Dict[str, Optional[float]]] = Field(default_factory=dict)


class PointInTimeAudit(BaseModel):
    timestamp: str
    index: int
    latest_source_candle: Optional[str] = None
    latest_htf_candles: Dict[str, Optional[str]] = Field(default_factory=dict)
    latest_smc_event: Optional[str] = None
    latest_strategy_event: Optional[str] = None
    feature_keys: List[str] = Field(default_factory=list)


class DatasetMetadata(BaseModel):
    dataset_id: str
    dataset_version: str
    feature_version: str
    label_version: str
    strategy_version: str
    symbol: str
    timeframe: str
    start: str
    end: str
    row_count: int
    feature_count: int
    label_count: int
    timezone: str
    source: str
    split: DatasetSplitSizes
    missing_value_statistics: Dict[str, float] = Field(default_factory=dict)
    output_files: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class DatasetBuildResult(BaseModel):
    dataset_id: str
    metadata: DatasetMetadata
    statistics: DatasetStatistics
    preview_rows: List[DatasetRow] = Field(default_factory=list)
    config: DatasetConfig
    output_dir: str
