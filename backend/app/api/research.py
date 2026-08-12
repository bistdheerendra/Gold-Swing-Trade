"""Research-only HTTP endpoints (Binance sidecar, etc.)."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.combined.model_runtime import ModelUnavailableError
from app.research.binance_suggest import suggest_from_binance
from app.research.binance_weekly import run_weekly_update, status_snapshot

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/binance-suggest")
async def binance_suggest(
    model_id: Optional[str] = Query(default=None),
    limit: int = Query(default=400, ge=120, le=2000),
) -> Dict[str, Any]:
    """
    Binance PAXGUSDT candle-ML suggestion.

    Research reference only — does not change Delta PAXGUSD strategy / Phase 12.
    """
    try:
        return suggest_from_binance(model_id=model_id, limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/binance-weekly-status")
async def binance_weekly_status() -> Dict[str, Any]:
    """Last weekly backfill/retrain status for Binance research sidecar."""
    return status_snapshot()


@router.post("/binance-weekly-update")
async def binance_weekly_update(
    background_tasks: BackgroundTasks,
    force: bool = Query(default=False, description="Ignore interval gate"),
    wait: bool = Query(
        default=False,
        description="If true, run inline (can take ~20–40 min). Prefer false.",
    ),
) -> Dict[str, Any]:
    """
    Trigger Binance weekly refresh (backfill + retrain).

    Default: queues in background and returns current status immediately.
    """
    snap = status_snapshot()
    if snap.get("running"):
        return {"queued": False, "reason": "already_running", **snap}

    if wait:
        result = await asyncio.to_thread(run_weekly_update, force=force)
        return {
            "queued": False,
            "waited": True,
            **{k: v for k, v in result.items() if k != "steps"},
        }

    background_tasks.add_task(run_weekly_update, force=force)
    return {"queued": True, "force": force, **snap}
