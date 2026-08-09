"""CSV (+ optional parquet) dataset export."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, List, Sequence

from app.ml.schemas import DatasetMetadata, DatasetRow


def flatten_row(row: DatasetRow) -> dict:
    out = {
        "timestamp": row.timestamp,
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "index": row.index,
    }
    for k, v in row.features.items():
        out[f"f_{k}"] = v
    for k, v in row.labels.items():
        out[f"y_{k}"] = v
    return out


def export_csv(path: Path, rows: Sequence[DatasetRow]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    flat = [flatten_row(r) for r in rows]
    if not flat:
        path.write_text("", encoding="utf-8")
        return path
    fieldnames = list(flat[0].keys())
    # union keys
    keys = []
    seen = set()
    for row in flat:
        for k in row:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        for row in flat:
            writer.writerow(row)
    return path


def export_metadata(path: Path, meta: DatasetMetadata) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
    return path


def try_export_parquet(path: Path, rows: Sequence[DatasetRow]) -> bool:
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return False
    flat = [flatten_row(r) for r in rows]
    if not flat:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        pd.DataFrame(flat).to_parquet(path, index=False)
    except Exception:
        # Optional dependency (pyarrow/fastparquet) may be missing
        return False
    return True
