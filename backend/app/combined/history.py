"""In-memory combined signal history (Phase 10)."""

from __future__ import annotations

import threading
from typing import List, Optional

from app.combined.schemas import CombinedSignalResult

_STORE: Optional["CombinedSignalStore"] = None
_LOCK = threading.Lock()


class CombinedSignalStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: List[CombinedSignalResult] = []

    def append(self, item: CombinedSignalResult) -> None:
        with self._lock:
            self._items.append(item)
            if len(self._items) > 500:
                self._items = self._items[-500:]

    def list(
        self, *, symbol: Optional[str] = None, limit: int = 50
    ) -> List[CombinedSignalResult]:
        with self._lock:
            items = list(self._items)
        if symbol:
            items = [i for i in items if i.symbol.upper() == symbol.upper()]
        return list(reversed(items[-limit:]))

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


def get_combined_store() -> CombinedSignalStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = CombinedSignalStore()
        return _STORE


def reset_combined_store() -> None:
    global _STORE
    with _LOCK:
        _STORE = CombinedSignalStore()
