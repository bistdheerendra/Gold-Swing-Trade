"""CombinedSignalEngine — Phase 6 setup + Phase 9 ML filter."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Mapping, Optional, Sequence

from app.combined.config import CombinedSignalConfig
from app.combined.decision import combined_score, decide
from app.combined.features import build_feature_row
from app.combined.history import get_combined_store
from app.combined.model_runtime import (
    ModelCompatibilityError,
    ModelUnavailableError,
    load_runtime_model,
    predict_ml,
)
from app.combined.schemas import CombinedSignalResult, MlStatus
from app.market.schemas import OHLCVBar, ensure_utc
from app.strategy.config import StrategyConfig
from app.strategy.engine import SignalStore, StrategyEngine
from app.strategy.schemas import SignalDirection


class CombinedSignalEngine:
    def __init__(
        self,
        config: Optional[CombinedSignalConfig] = None,
        *,
        strategy_config: Optional[StrategyConfig] = None,
        store: Optional[SignalStore] = None,
        runtime_model=None,
    ) -> None:
        self.config = config or CombinedSignalConfig()
        self.strategy_config = strategy_config or StrategyConfig()
        self.store = store or SignalStore()
        self.strategy = StrategyEngine(config=self.strategy_config, store=self.store)
        self._runtime = runtime_model
        self._runtime_error: Optional[str] = None

    def ensure_model(self, model_id: Optional[str] = None) -> None:
        mid = model_id or self.config.model_id
        try:
            self._runtime = load_runtime_model(
                mid, expected_feature_version=self.config.feature_version_expected
            )
            if self._runtime.selected_threshold:
                self.config = self.config.model_copy(
                    update={
                        "min_ml_confidence": self._runtime.selected_threshold,
                        "model_id": self._runtime.model_id,
                        "probability_calibrated": self._runtime.probability_calibrated,
                    }
                )
            self._runtime_error = None
        except ModelCompatibilityError as exc:
            self._runtime = None
            self._runtime_error = f"MODEL_INCOMPATIBLE: {exc}"
        except (ModelUnavailableError, Exception) as exc:  # noqa: BLE001
            self._runtime = None
            self._runtime_error = f"ML_UNAVAILABLE: {exc}"

    def analyze(
        self,
        bars_by_tf: Mapping[str, Sequence[OHLCVBar]],
        *,
        symbol: str = "XAUUSD",
        as_of: Optional[datetime] = None,
        timeframes: Optional[Sequence[str]] = None,
        model_id: Optional[str] = None,
        mode: str = "ML_FILTER",
    ) -> CombinedSignalResult:
        as_of_u = ensure_utc(as_of or datetime.now(timezone.utc))
        from app.market.schemas import MTF_HIERARCHY

        tfs = list(timeframes or MTF_HIERARCHY)

        rule = self.strategy.analyze(
            bars_by_tf, symbol=symbol, as_of=as_of_u, timeframes=tfs
        )

        ts = as_of_u.isoformat()
        base_kwargs = dict(
            signal_id=rule.signal_id or str(uuid.uuid4()),
            setup_id=rule.setup_id,
            symbol=symbol.upper(),
            timeframe="15m",
            as_of=rule.as_of,
            timestamp=ts,
            rule_signal=rule.signal,
            rule_score=rule.score,
            entry=rule.entry,
            stop_loss=rule.stop_loss,
            targets=rule.targets,
            primary_rr=rule.primary_rr,
            market_context=rule.market_context,
            strategy_version=rule.strategy_version,
            feature_version=self.config.feature_version_expected,
            rule_result=rule,
            rule_reasons=list(rule.reasons),
            status=rule.status,
        )

        if mode == "RULE_ONLY":
            out = CombinedSignalResult(
                **base_kwargs,
                direction=rule.signal,
                ml_status=MlStatus.RULE_ONLY,
                reasons=list(rule.reasons),
                risks=list(rule.risks),
                notes=["MODE=RULE_ONLY — ML not applied"],
            )
            get_combined_store().append(out)
            return out

        if rule.signal in (SignalDirection.WAIT, SignalDirection.NO_TRADE):
            out = CombinedSignalResult(
                **base_kwargs,
                direction=rule.signal,
                ml_status=MlStatus.SKIPPED,
                reasons=list(rule.reasons)
                + ["ML skipped — rule did not produce a trade setup."],
                risks=list(rule.risks),
                notes=["ML cannot invent BUY/SELL when rule is WAIT/NO_TRADE"],
            )
            get_combined_store().append(out)
            return out

        if self._runtime is None or (
            model_id and (self._runtime is None or self._runtime.model_id != model_id)
        ):
            self.ensure_model(model_id)

        ml_pred = None
        ml_conf = None
        ml_reasons: List[str] = []
        detail: Dict = {}
        ml_compatible = True
        ml_available = True

        if self._runtime_error and self._runtime_error.startswith("MODEL_INCOMPATIBLE"):
            ml_compatible = False
            ml_available = False
            ml_reasons.append(self._runtime_error)
        elif self._runtime is None:
            ml_available = False
            ml_compatible = True
            ml_reasons.append(self._runtime_error or "ML_UNAVAILABLE")
        else:
            try:
                features, _bar, _idx = build_feature_row(
                    bars_by_tf, as_of=as_of_u, entry_tf="15m", strategy=rule
                )
                ml_pred, ml_conf, detail = predict_ml(
                    self._runtime, features, rule_direction=rule.signal.value
                )
                ml_reasons.append(
                    f"ML raw={detail.get('raw_prediction')} → {ml_pred} "
                    f"(confidence={ml_conf:.2f}, calibrated={self._runtime.probability_calibrated})"
                )
                if not self._runtime.probability_calibrated:
                    ml_reasons.append(
                        "probability_calibrated=false — confidence is not a true win probability."
                    )
                imp = self._runtime.model.feature_importance()
                if imp:
                    tops = sorted(imp.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
                    ml_reasons.append(
                        "Top model features: " + ", ".join(k for k, _ in tops)
                    )
            except ModelCompatibilityError as exc:
                ml_compatible = False
                ml_available = False
                ml_reasons.append(f"MODEL_INCOMPATIBLE: {exc}")
            except Exception as exc:  # noqa: BLE001
                ml_available = False
                ml_reasons.append(f"ML_UNAVAILABLE during predict: {exc}")

        outcome = decide(
            rule=rule.signal,
            rule_score=rule.score,
            ml_prediction=ml_pred,
            ml_confidence=ml_conf,
            config=self.config,
            ml_available=ml_available and ml_compatible,
            ml_compatible=ml_compatible,
        )

        cscore = combined_score(rule.score, ml_conf, self.config)
        risks = list(rule.risks)
        if outcome.ml_status == MlStatus.REJECTED:
            risks.append("ML rejected rule setup")
        if outcome.ml_status == MlStatus.LOW_CONFIDENCE:
            risks.append("ML confidence below research threshold")

        out = CombinedSignalResult(
            **base_kwargs,
            direction=outcome.direction,
            ml_prediction=ml_pred,
            ml_confidence=ml_conf,
            ml_model_id=self._runtime.model_id if self._runtime else None,
            ml_model_version=self._runtime.model_version if self._runtime else None,
            ml_status=outcome.ml_status,
            probability_calibrated=(
                self._runtime.probability_calibrated if self._runtime else False
            ),
            combined_score=cscore,
            preprocessing_version=(
                self._runtime.preprocessing_version if self._runtime else None
            ),
            label_version=self._runtime.label_version if self._runtime else None,
            dataset_version=self._runtime.dataset_version if self._runtime else None,
            reasons=list(rule.reasons) + outcome.reasons + ml_reasons,
            risks=risks,
            ml_reasons=ml_reasons + outcome.reasons,
            metadata={
                "mode": mode,
                "min_ml_confidence": self.config.min_ml_confidence,
                "predict_detail": detail,
            },
            notes=list(self.config.notes)
            + [
                "RESEARCH ONLY",
                f"Decision ml_status={outcome.ml_status.value}",
            ],
        )
        get_combined_store().append(out)
        return out
