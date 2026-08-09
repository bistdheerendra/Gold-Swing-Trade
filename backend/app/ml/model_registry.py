"""In-memory + disk model registry (RESEARCH status only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

_REGISTRY: Dict[str, dict] = {}


def register_model(meta: dict) -> dict:
    mid = meta["model_id"]
    _REGISTRY[mid] = meta
    # also index file
    root = Path(meta.get("artifact_dir", "artifacts/ml"))
    root.mkdir(parents=True, exist_ok=True)
    (root / "registry_entry.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    return meta


def get_model(model_id: str) -> Optional[dict]:
    return _REGISTRY.get(model_id)


def list_models() -> List[dict]:
    return list(_REGISTRY.values())


def clear_registry() -> None:
    _REGISTRY.clear()
