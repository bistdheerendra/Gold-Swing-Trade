"""Phase 10 combined signal tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.combined.config import CombinedSignalConfig, MlFallbackMode
from app.combined.decision import decide
from app.combined.engine import CombinedSignalEngine
from app.combined.history import reset_combined_store
from app.combined.schemas import MlStatus
from app.core.config import get_settings
from app.main import app
from app.market.deps import reset_market_singletons
from app.ml.dataset_builder import clear_datasets
from app.ml.model_registry import clear_registry, register_model
from app.ml.preprocessing.pipeline import PreprocessingPipeline
from app.ml.trainer import ModelTrainer, load_dataset_for_training
from app.strategy.schemas import SignalDirection


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARKET_DATA_STORE", "memory")
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mock")
    monkeypatch.setenv("ALLOW_MOCK_DATA", "true")
    monkeypatch.setenv("MARKET_SYMBOL", "XAUUSD")
    get_settings.cache_clear()
    reset_market_singletons()
    clear_datasets()
    clear_registry()
    reset_combined_store()
    yield
    clear_datasets()
    clear_registry()
    reset_combined_store()
    reset_market_singletons()
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_decision_matrix_cases() -> None:
    cfg = CombinedSignalConfig(min_ml_confidence=0.60)

    assert (
        decide(
            rule=SignalDirection.WAIT,
            rule_score=80,
            ml_prediction="BUY",
            ml_confidence=0.9,
            config=cfg,
        ).direction
        == SignalDirection.WAIT
    )
    assert (
        decide(
            rule=SignalDirection.NO_TRADE,
            rule_score=80,
            ml_prediction="BUY",
            ml_confidence=0.9,
            config=cfg,
        ).direction
        == SignalDirection.NO_TRADE
    )

    ok = decide(
        rule=SignalDirection.BUY,
        rule_score=78,
        ml_prediction="BUY",
        ml_confidence=0.82,
        config=cfg,
    )
    assert ok.direction == SignalDirection.BUY and ok.ml_status == MlStatus.CONFIRMED

    conflict = decide(
        rule=SignalDirection.BUY,
        rule_score=78,
        ml_prediction="SELL",
        ml_confidence=0.81,
        config=cfg,
    )
    assert conflict.direction == SignalDirection.NO_TRADE
    assert conflict.ml_status == MlStatus.REJECTED

    low = decide(
        rule=SignalDirection.BUY,
        rule_score=72,
        ml_prediction="BUY",
        ml_confidence=0.51,
        config=cfg,
    )
    assert low.direction == SignalDirection.WAIT
    assert low.ml_status == MlStatus.LOW_CONFIDENCE

    sell_ok = decide(
        rule=SignalDirection.SELL,
        rule_score=70,
        ml_prediction="SELL",
        ml_confidence=0.7,
        config=cfg,
    )
    assert sell_ok.direction == SignalDirection.SELL

    sell_conflict = decide(
        rule=SignalDirection.SELL,
        rule_score=70,
        ml_prediction="BUY",
        ml_confidence=0.7,
        config=cfg,
    )
    assert sell_conflict.direction == SignalDirection.NO_TRADE


def test_ml_unavailable_fallback() -> None:
    cfg = CombinedSignalConfig(ml_fallback=MlFallbackMode.FALLBACK_RULE)
    out = decide(
        rule=SignalDirection.BUY,
        rule_score=80,
        ml_prediction=None,
        ml_confidence=None,
        config=cfg,
        ml_available=False,
    )
    assert out.direction == SignalDirection.BUY
    assert out.ml_status == MlStatus.UNAVAILABLE

    cfg2 = CombinedSignalConfig(ml_fallback=MlFallbackMode.WAIT)
    out2 = decide(
        rule=SignalDirection.BUY,
        rule_score=80,
        ml_prediction=None,
        ml_confidence=None,
        config=cfg2,
        ml_available=False,
    )
    assert out2.direction == SignalDirection.WAIT


def test_model_incompatible() -> None:
    cfg = CombinedSignalConfig()
    out = decide(
        rule=SignalDirection.BUY,
        rule_score=80,
        ml_prediction="BUY",
        ml_confidence=0.9,
        config=cfg,
        ml_compatible=False,
    )
    assert out.ml_status == MlStatus.INCOMPATIBLE


def test_preprocessing_not_refit_on_predict(client: TestClient, tmp_path: Path) -> None:
    r = client.post(
        "/api/ml/dataset/build",
        json={
            "limit": 240,
            "warmup_bars": 80,
            "row_step": 3,
            "include_strategy": False,
        },
    )
    assert r.status_code == 200
    ds = load_dataset_for_training(dataset_id=r.json()["dataset_id"])
    trainer = ModelTrainer(artifacts_root=tmp_path / "art", random_seed=1)
    meta = trainer.train(ds, target="direction", model_type="logistic", run_test=False)
    register_model(meta)

    pipe = PreprocessingPipeline().load(Path(meta["artifact_dir"]) / "preprocessing.json")
    medians = dict(pipe.medians_)
    engine = CombinedSignalEngine(
        CombinedSignalConfig(model_id=meta["model_id"], min_ml_confidence=0.5)
    )
    engine.ensure_model(meta["model_id"])
    assert engine._runtime is not None
    assert engine._runtime.pipeline.medians_ == medians

    resp = client.get(f"/api/combined/analyze?model_id={meta['model_id']}&mode=ML_FILTER")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "direction" in data
    assert data["probability_calibrated"] is False
    assert engine._runtime.pipeline.medians_ == medians


def test_future_mutation_as_of_stable(client: TestClient, tmp_path: Path) -> None:
    r = client.post(
        "/api/ml/dataset/build",
        json={
            "limit": 240,
            "warmup_bars": 80,
            "row_step": 3,
            "include_strategy": False,
        },
    )
    assert r.status_code == 200
    ds = load_dataset_for_training(dataset_id=r.json()["dataset_id"])
    meta = ModelTrainer(artifacts_root=tmp_path / "a", random_seed=2).train(
        ds, target="direction", model_type="logistic", run_test=False
    )
    register_model(meta)

    client.post("/api/market/seed?timeframe=15m&bars=300")
    client.post("/api/market/seed?timeframe=1h&bars=300")
    client.post("/api/market/seed?timeframe=4h&bars=300")
    client.post("/api/market/seed?timeframe=1d&bars=300")
    a_resp = client.get(f"/api/combined/analyze?model_id={meta['model_id']}")
    assert a_resp.status_code == 200, a_resp.text
    a = a_resp.json()
    assert "rule_signal" in a, a
    as_of = a["as_of"]
    from urllib.parse import quote

    b_resp = client.get(
        f"/api/combined/analyze?model_id={meta['model_id']}&as_of={quote(as_of)}"
    )
    assert b_resp.status_code == 200, b_resp.text
    b = b_resp.json()
    assert a["rule_signal"] == b["rule_signal"]
    assert a["direction"] == b["direction"]
    assert a.get("ml_prediction") == b.get("ml_prediction")


def test_combined_api_and_history(client: TestClient) -> None:
    resp = client.get("/api/combined/analyze?mode=RULE_ONLY")
    assert resp.status_code == 200, resp.text
    hist = client.get("/api/combined/history").json()
    assert hist["count"] >= 1
    assert client.get("/api/health").json()["phase"] == "11.12"
    assert client.get("/").json()["phase"] == "11.12"


def test_backtest_modes(client: TestClient, tmp_path: Path) -> None:
    r = client.post(
        "/api/ml/dataset/build",
        json={
            "limit": 240,
            "warmup_bars": 80,
            "row_step": 4,
            "include_strategy": False,
        },
    )
    assert r.status_code == 200
    ds = load_dataset_for_training(dataset_id=r.json()["dataset_id"])
    meta = ModelTrainer(artifacts_root=tmp_path / "b", random_seed=3).train(
        ds, target="direction", model_type="random_forest", run_test=False
    )
    register_model(meta)

    rule = client.post(
        "/api/backtest/run",
        json={
            "limit": 320,
            "warmup_bars": 60,
            "signal_mode": "RULE_ONLY",
            "split_segment": "ALL",
            "step": 4,
            "cost_config": {"mode": "ZERO_COST"},
        },
    )
    assert rule.status_code == 200, rule.text

    ml = client.post(
        "/api/backtest/run",
        json={
            "limit": 320,
            "warmup_bars": 60,
            "signal_mode": "ML_FILTER",
            "model_id": meta["model_id"],
            "min_ml_confidence": 0.55,
            "split_segment": "ALL",
            "step": 4,
            "cost_config": {"mode": "ZERO_COST"},
        },
    )
    assert ml.status_code == 200, ml.text
    assert "signal_mode=ML_FILTER" in " ".join(ml.json().get("notes") or [])


def test_compare_endpoint(client: TestClient, tmp_path: Path) -> None:
    r = client.post(
        "/api/ml/dataset/build",
        json={
            "limit": 240,
            "warmup_bars": 80,
            "row_step": 4,
            "include_strategy": False,
        },
    )
    ds = load_dataset_for_training(dataset_id=r.json()["dataset_id"])
    meta = ModelTrainer(artifacts_root=tmp_path / "c", random_seed=4).train(
        ds, target="direction", model_type="logistic", run_test=False
    )
    register_model(meta)
    # expose step on compare via BacktestConfig — keep scan off for speed
    # Patch compare to use step by setting on engines through limit/warmup only
    resp = client.post(
        "/api/combined/compare",
        json={
            "limit": 280,
            "warmup_bars": 50,
            "model_id": meta["model_id"],
            "min_ml_confidence": 0.60,
            "run_threshold_scan": False,
            "evaluate_test": False,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "RULE_ONLY" in body and "ML_FILTER" in body
    assert "filter_quality" in body
    assert body["threshold_frozen_from_validation"] == 0.60
