"""Binance research suggest — portable artifact paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.research.binance_suggest import _load_meta, _resolve_local_artifact_dir


@pytest.fixture(autouse=True)
def _clear_settings() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_resolve_local_artifact_dir_skips_foreign_absolute(tmp_path: Path) -> None:
    local = tmp_path / "binance_paxgusdt_direction_logistic_deadbeef"
    local.mkdir()
    (local / "model.joblib").write_bytes(b"stub")
    foreign = Path(
        r"C:\Users\dheerendra.bist.DESKTOP-LGNCEAB\Desktop\Gold-Swing-Trade"
        r"\artifacts\ml_candle_binance\direction"
        r"\binance_paxgusdt_direction_logistic_deadbeef"
    )
    resolved = _resolve_local_artifact_dir(str(foreign), local)
    assert resolved == local


def test_load_meta_uses_discovered_dir_when_stored_path_inaccessible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_id = "binance_paxgusdt_direction_logistic_deadbeef"
    art = tmp_path / "artifacts" / "ml_candle_binance" / "direction" / model_id
    art.mkdir(parents=True)
    (art / "model.joblib").write_bytes(b"stub")
    (art / "registry_entry.json").write_text(
        json.dumps(
            {
                "model_id": model_id,
                "artifact_dir": (
                    r"C:\Users\dheerendra.bist.DESKTOP-LGNCEAB\Desktop"
                    r"\Gold-Swing-Trade\artifacts\ml_candle_binance\direction"
                    f"\\{model_id}"
                ),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BINANCE_ML_ARTIFACTS_ROOT", str(art.parents[1]))
    get_settings.cache_clear()

    meta = _load_meta(model_id)
    assert Path(meta["artifact_dir"]) == art
