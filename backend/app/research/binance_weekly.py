"""Weekly Binance PAXGUSDT research refresh — backfill + retrain.

Isolated from Delta PAXGUSD / Phase 12. Runs as background task or CLI.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
STATE_NAME = "LAST_WEEKLY_UPDATE.json"


def _artifacts_root() -> Path:
    settings = get_settings()
    root = Path(settings.binance_ml_artifacts_root)
    if not root.is_absolute():
        root = REPO_ROOT / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def state_path() -> Path:
    return _artifacts_root() / STATE_NAME


def load_state() -> Dict[str, Any]:
    path = state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(payload: Dict[str, Any]) -> None:
    path = state_path()
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except ValueError:
        return None


def bootstrap_state_from_existing_model() -> None:
    """
    If a selected model already exists but weekly state was never written,
    seed last_success_at from the pointer mtime so we do not retrain on first boot.
    """
    state = load_state()
    if state.get("last_success_at") or state.get("running"):
        return
    pointer = _artifacts_root() / "SELECTED_MODEL_ID.txt"
    if not pointer.exists():
        return
    mtime = datetime.fromtimestamp(pointer.stat().st_mtime, tz=timezone.utc)
    model_id = pointer.read_text(encoding="utf-8").strip() or None
    save_state(
        {
            **state,
            "running": False,
            "last_success_at": mtime.isoformat(),
            "last_run_at": mtime.isoformat(),
            "last_status": "ok",
            "last_model_id": model_id,
            "last_error": None,
            "seeded_from_selected_model": True,
        }
    )


def is_due(*, now: Optional[datetime] = None) -> bool:
    settings = get_settings()
    if not settings.binance_weekly_update_enabled:
        return False
    now = now or datetime.now(timezone.utc)
    bootstrap_state_from_existing_model()
    state = load_state()
    if state.get("running"):
        return False
    last = _parse_iso(state.get("last_success_at") or state.get("last_run_at"))
    if last is None:
        return True
    interval_days = max(1, int(settings.binance_weekly_interval_days))
    return now >= last + timedelta(days=interval_days)


def status_snapshot() -> Dict[str, Any]:
    settings = get_settings()
    bootstrap_state_from_existing_model()
    state = load_state()
    now = datetime.now(timezone.utc)
    last = _parse_iso(state.get("last_success_at") or state.get("last_run_at"))
    interval_days = max(1, int(settings.binance_weekly_interval_days))
    next_due = (
        (last + timedelta(days=interval_days)).isoformat()
        if last is not None
        else now.isoformat()
    )
    pointer = _artifacts_root() / "SELECTED_MODEL_ID.txt"
    selected = pointer.read_text(encoding="utf-8").strip() if pointer.exists() else None
    return {
        "enabled": bool(settings.binance_weekly_update_enabled),
        "interval_days": interval_days,
        "due_now": is_due(now=now),
        "running": bool(state.get("running")),
        "last_run_at": state.get("last_run_at"),
        "last_success_at": state.get("last_success_at"),
        "last_status": state.get("last_status"),
        "last_model_id": state.get("last_model_id") or selected,
        "last_error": state.get("last_error"),
        "next_due_at": next_due,
        "selected_model_id": selected,
    }


def _run_script(script_name: str, *, timeout_sec: int) -> Dict[str, Any]:
    script = BACKEND_ROOT / "scripts" / script_name
    if not script.exists():
        raise FileNotFoundError(script)
    py = sys.executable
    proc = subprocess.run(
        [py, str(script)],
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )
    return {
        "script": script_name,
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }


def run_weekly_update(*, force: bool = False) -> Dict[str, Any]:
    """
    Backfill Binance CSVs then retrain candle ML.
    Returns a status dict; raises on hard failure after updating state.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if not settings.binance_weekly_update_enabled and not force:
        return {"ok": False, "skipped": True, "reason": "BINANCE_WEEKLY_UPDATE_ENABLED=false"}
    if not force and not is_due(now=now):
        return {"ok": True, "skipped": True, "reason": "not_due", **status_snapshot()}

    state = load_state()
    if state.get("running"):
        return {"ok": False, "skipped": True, "reason": "already_running", **status_snapshot()}

    started = now.isoformat()
    save_state(
        {
            **state,
            "running": True,
            "last_run_at": started,
            "last_status": "running",
            "last_error": None,
        }
    )
    logger.info("binance_weekly_update_start force=%s", force)

    steps: list[Dict[str, Any]] = []
    try:
        backfill = _run_script(
            "backfill_binance_paxgusdt.py",
            timeout_sec=int(settings.binance_weekly_backfill_timeout_sec),
        )
        steps.append(backfill)
        if backfill["returncode"] != 0:
            raise RuntimeError(
                f"backfill failed rc={backfill['returncode']}: {backfill['stderr_tail']}"
            )

        train = _run_script(
            "phase_binance_paxgusdt_candle_ml.py",
            timeout_sec=int(settings.binance_weekly_train_timeout_sec),
        )
        steps.append(train)
        if train["returncode"] != 0:
            raise RuntimeError(
                f"train failed rc={train['returncode']}: {train['stderr_tail']}"
            )

        pointer = _artifacts_root() / "SELECTED_MODEL_ID.txt"
        model_id = pointer.read_text(encoding="utf-8").strip() if pointer.exists() else None
        finished = datetime.now(timezone.utc).isoformat()
        payload = {
            "running": False,
            "last_run_at": started,
            "last_success_at": finished,
            "last_status": "ok",
            "last_model_id": model_id,
            "last_error": None,
            "last_steps": [
                {"script": s["script"], "returncode": s["returncode"]} for s in steps
            ],
        }
        save_state(payload)
        logger.info("binance_weekly_update_ok model_id=%s", model_id)
        return {"ok": True, "skipped": False, **payload, "steps": steps}
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        save_state(
            {
                "running": False,
                "last_run_at": started,
                "last_success_at": state.get("last_success_at"),
                "last_status": "error",
                "last_model_id": state.get("last_model_id"),
                "last_error": err[:2000],
                "last_steps": [
                    {"script": s["script"], "returncode": s["returncode"]} for s in steps
                ],
            }
        )
        logger.exception("binance_weekly_update_failed")
        return {"ok": False, "skipped": False, "error": err, "steps": steps}
