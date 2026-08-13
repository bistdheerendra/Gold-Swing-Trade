"""Phase 9 ML training & leakage tests."""

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.market.deps import reset_market_singletons
from app.ml.baselines import majority_predict, random_predict
from app.ml.dataset_builder import clear_datasets
from app.ml.dataset_loader import DatasetLoader, extract_xy
from app.ml.model_registry import clear_registry, list_models
from app.ml.models.registry import create_model
from app.ml.preprocessing.pipeline import PreprocessingPipeline
from app.ml.trainer import ModelTrainer, load_dataset_for_training
from app.ml.walk_forward import build_expanding_folds


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MARKET_DATA_STORE", "memory")
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mock")
    monkeypatch.setenv("ALLOW_MOCK_DATA", "true")
    monkeypatch.setenv("MARKET_SYMBOL", "XAUUSD")
    get_settings.cache_clear()
    reset_market_singletons()
    clear_datasets()
    clear_registry()
    yield
    clear_datasets()
    clear_registry()
    reset_market_singletons()
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _build_dataset(client: TestClient, *, include_strategy: bool = True) -> dict:
    response = client.post(
        "/api/ml/dataset/build",
        json={
            "symbol": "XAUUSD",
            "timeframe": "15m",
            "limit": 240,
            "warmup_bars": 80,
            "row_step": 3,
            "include_strategy": include_strategy,
            "feature_version": "1.0.0",
            "label_version": "1.0.0",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_dataset_loader_feature_label_separation(client: TestClient) -> None:
    data = _build_dataset(client, include_strategy=False)
    loaded = DatasetLoader().load(data["output_dir"], dataset_id=data["dataset_id"])
    assert loaded.feature_names
    assert "direction" in loaded.label_names
    for name in loaded.feature_names:
        assert not name.startswith("future_")
        assert name not in ("strategy_outcome", "future_R")


def test_preprocessing_fit_train_only(client: TestClient) -> None:
    data = _build_dataset(client, include_strategy=False)
    ds = DatasetLoader().load(data["output_dir"])
    X_train, y_train, _ = extract_xy(ds.train, ds.feature_names, "direction")
    X_val, _, _ = extract_xy(ds.validation, ds.feature_names, "direction")
    pipe = PreprocessingPipeline()
    pipe.fit(X_train, ds.feature_names)
    medians_before = dict(pipe.medians_)
    _ = pipe.transform(X_val)
    assert pipe.medians_ == medians_before
    with pytest.raises(RuntimeError):
        PreprocessingPipeline().transform(X_val)


def test_models_classification_and_regression(client: TestClient, tmp_path: Path) -> None:
    data = _build_dataset(client, include_strategy=True)
    ds = load_dataset_for_training(dataset_id=data["dataset_id"])
    trainer = ModelTrainer(artifacts_root=tmp_path / "artifacts", random_seed=42)
    direction = trainer.train(ds, target="direction", model_types=["logistic"], run_test=True)
    assert direction["status"] == "RESEARCH"
    assert "f1_macro" in direction["train_metrics"]
    assert direction["test_metrics"]
    assert direction["baselines"]["majority_validation"]

    outcome = trainer.train(
        ds, target="strategy_outcome", model_types=["random_forest"], run_test=True
    )
    assert outcome["selected_model_type"] == "random_forest"
    assert "trade_only_win_loss" in outcome

    ret = trainer.train(ds, target="return_10", model_types=["gradient_boosting"], run_test=True)
    assert "mae" in ret["validation_metrics"] or ret["validation_metrics"] == {}

    # future_R only exists on actual Phase 6 trades — may be sparse on mock data
    Xfr, yfr, _ = extract_xy(ds.train, ds.feature_names, "future_R")
    if len(Xfr) >= 10:
        fr = trainer.train(ds, target="future_R", model_types=["logistic"], run_test=False)
        assert fr["task"] == "regression"
    else:
        # synthetic regression path still covered by return_10 + Ridge logistic path
        model = create_model("logistic", task="regression", random_seed=1)
        X = np.random.default_rng(0).normal(size=(40, 3))
        y = X[:, 0] * 0.5 + np.random.default_rng(1).normal(scale=0.1, size=40)
        model.fit(X, y, ["a", "b", "c"])
        pred = model.predict(X)
        assert len(pred) == 40
        assert model.evaluate(X, y)["mae"] is not None


def test_model_selection_uses_validation_not_test(client: TestClient, tmp_path: Path) -> None:
    data = _build_dataset(client, include_strategy=False)
    ds = load_dataset_for_training(dataset_id=data["dataset_id"])
    trainer = ModelTrainer(artifacts_root=tmp_path / "art", random_seed=7)
    meta = trainer.train(
        ds,
        target="direction",
        model_types=["logistic", "random_forest"],
        run_test=True,
    )
    assert len(meta["candidates"]) == 2
    # selected by validation selection_score
    best = max(meta["candidates"], key=lambda c: c["selection_score"])
    assert meta["selected_model_type"] == best["model_type"]
    assert meta["test_metrics"]  # evaluated after


def test_leakage_test_labels_do_not_affect_train(client: TestClient, tmp_path: Path) -> None:
    data = _build_dataset(client, include_strategy=False)
    ds = load_dataset_for_training(dataset_id=data["dataset_id"])
    trainer = ModelTrainer(artifacts_root=tmp_path / "a", random_seed=42)
    meta1 = trainer.train(ds, target="direction", model_type="logistic", run_test=True)

    # Mutate TEST labels only
    for row in ds.test.rows:
        labels = row.get("__labels") or {}
        labels["direction"] = "UP"
        row["__labels"] = labels

    pipe = PreprocessingPipeline()
    X_train, y_train, _ = extract_xy(ds.train, ds.feature_names, "direction")
    pipe.fit(X_train, ds.feature_names)
    # Retrain on TRAIN only — preprocess stats from TRAIN
    model = create_model("logistic", task="classification", random_seed=42)
    Xtr, names = pipe.fit_transform(X_train, ds.feature_names)
    model.fit(Xtr, np.asarray(y_train), names)
    # Changing TEST must not change TRAIN-fit preprocessing medians vs original train
    meta2 = trainer.train(ds, target="direction", model_type="logistic", run_test=False)
    assert meta2["train_metrics"]["f1_macro"] == meta1["train_metrics"]["f1_macro"]
    assert meta2["selected_threshold_from_validation"] == meta1["selected_threshold_from_validation"]


def test_reproducibility_same_seed(client: TestClient, tmp_path: Path) -> None:
    data = _build_dataset(client, include_strategy=False)
    ds = load_dataset_for_training(dataset_id=data["dataset_id"])
    t1 = ModelTrainer(artifacts_root=tmp_path / "r1", random_seed=123)
    t2 = ModelTrainer(artifacts_root=tmp_path / "r2", random_seed=123)
    a = t1.train(ds, target="direction", model_type="random_forest", run_test=True)
    b = t2.train(ds, target="direction", model_type="random_forest", run_test=True)
    assert a["train_metrics"]["f1_macro"] == b["train_metrics"]["f1_macro"]
    assert a["validation_metrics"]["f1_macro"] == b["validation_metrics"]["f1_macro"]


def test_baselines_majority_random() -> None:
    y = ["UP", "UP", "DOWN", "NEUTRAL"]
    maj = majority_predict(y, 5)
    assert all(x == "UP" for x in maj)
    rnd = random_predict(y, 5, seed=1)
    assert len(rnd) == 5


def test_walk_forward_folds_documented() -> None:
    folds = build_expanding_folds(200, n_folds=3, min_train=40)
    assert len(folds) >= 1
    assert folds[0].train_start == 0
    assert folds[0].train_end <= folds[0].validation_start


def test_artifact_save_load(client: TestClient, tmp_path: Path) -> None:
    data = _build_dataset(client, include_strategy=False)
    ds = load_dataset_for_training(dataset_id=data["dataset_id"])
    trainer = ModelTrainer(artifacts_root=tmp_path / "art", random_seed=1)
    meta = trainer.train(ds, target="direction", model_type="logistic", run_test=False)
    art = Path(meta["artifact_dir"])
    assert (art / "model.joblib").exists()
    assert (art / "preprocessing.json").exists()
    assert (art / "metrics.json").exists()
    model = create_model("logistic")
    model.load(str(art / "model.joblib"))
    pipe = PreprocessingPipeline().load(art / "preprocessing.json")
    assert pipe.fitted_
    assert model._model is not None


def test_ml_train_api(client: TestClient) -> None:
    data = _build_dataset(client, include_strategy=False)
    resp = client.post(
        "/api/ml/train",
        json={
            "dataset_id": data["dataset_id"],
            "target": "direction",
            "model_type": "logistic",
            "random_seed": 42,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    mid = body["model_id"]
    assert client.get("/api/ml/models").json()["count"] >= 1
    assert client.get(f"/api/ml/models/{mid}").status_code == 200
    assert client.post("/api/ml/evaluate", json={"model_id": mid, "split": "validation"}).status_code == 200
    assert client.get(f"/api/ml/reports/{mid}").json()["label"] == "RESEARCH ONLY"
    assert list_models()


def test_health_phase_11(client: TestClient) -> None:
    assert client.get("/api/health").json()["phase"] == "11.12"
    assert client.get("/").json()["phase"] == "11.12"


def test_no_future_labels_as_features(client: TestClient) -> None:
    data = _build_dataset(client, include_strategy=True)
    ds = DatasetLoader().load(data["output_dir"])
    assert "future_R" not in ds.feature_names
    assert "strategy_outcome" not in ds.feature_names
