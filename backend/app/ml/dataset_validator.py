"""Dataset validation — fail loudly on leakage / data issues."""

from __future__ import annotations

import math
from typing import List, Sequence

from app.ml.schemas import DatasetRow


class DatasetValidationError(ValueError):
    pass


class DatasetValidator:
    FORBIDDEN_FEATURE_KEYS = {
        "trade_result",
        "trade_profit",
        "trade_exit",
        "tp_hit",
        "sl_hit",
        "future_return",
        "y_return",
    }

    def validate(self, rows: Sequence[DatasetRow]) -> List[str]:
        errors: List[str] = []
        if not rows:
            errors.append("empty dataset")
            return errors

        seen_ts = set()
        prev_ts = None
        for r in rows:
            if r.timestamp in seen_ts:
                errors.append(f"duplicate timestamp: {r.timestamp}")
            seen_ts.add(r.timestamp)
            if prev_ts is not None and r.timestamp < prev_ts:
                errors.append(f"timestamp ordering broken at {r.timestamp}")
            prev_ts = r.timestamp

            for k in r.features:
                lk = k.lower()
                if lk in self.FORBIDDEN_FEATURE_KEYS or lk.startswith("future_"):
                    errors.append(f"forbidden/leaky feature key: {k}")
                v = r.features[k]
                if isinstance(v, float):
                    if math.isnan(v):
                        errors.append(f"NaN feature {k} at {r.timestamp}")
                    if math.isinf(v):
                        errors.append(f"Inf feature {k} at {r.timestamp}")

            # Labels may be future — OK. Ensure strategy outcome not also in features.
            if "strategy_outcome" in r.features:
                errors.append("strategy_outcome must not be a feature")
            if "future_R" in r.features:
                errors.append("future_R must not be a feature")

        if errors:
            raise DatasetValidationError("; ".join(errors[:20]))
        return []
