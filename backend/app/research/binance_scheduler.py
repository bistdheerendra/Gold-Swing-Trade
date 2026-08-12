"""Async weekly scheduler for Binance research refresh (API process)."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.core.config import get_settings
from app.research.binance_weekly import is_due, run_weekly_update

logger = logging.getLogger(__name__)

_task: Optional[asyncio.Task] = None


async def _loop() -> None:
    settings = get_settings()
    # Initial delay so API finishes booting before a possible long train
    await asyncio.sleep(max(5, int(settings.binance_weekly_startup_delay_sec)))
    while True:
        try:
            if is_due():
                logger.info("binance_weekly_scheduler_due — starting update")
                result = await asyncio.to_thread(run_weekly_update, force=False)
                logger.info(
                    "binance_weekly_scheduler_result ok=%s skipped=%s status=%s",
                    result.get("ok"),
                    result.get("skipped"),
                    result.get("last_status") or result.get("reason"),
                )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("binance_weekly_scheduler_tick_failed")
        await asyncio.sleep(max(60, int(settings.binance_weekly_check_interval_sec)))


def start_binance_weekly_scheduler() -> None:
    global _task
    settings = get_settings()
    if not settings.binance_weekly_update_enabled:
        logger.info("binance_weekly_scheduler_disabled")
        return
    if _task is not None and not _task.done():
        return
    _task = asyncio.create_task(_loop(), name="binance-weekly-update")
    logger.info(
        "binance_weekly_scheduler_started interval_days=%s check_sec=%s",
        settings.binance_weekly_interval_days,
        settings.binance_weekly_check_interval_sec,
    )


async def stop_binance_weekly_scheduler() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
    logger.info("binance_weekly_scheduler_stopped")
