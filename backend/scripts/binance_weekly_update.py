#!/usr/bin/env python3
"""CLI: run Binance weekly backfill+retrain (or force)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.research.binance_weekly import run_weekly_update, status_snapshot  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Binance PAXGUSDT weekly research update")
    parser.add_argument("--force", action="store_true", help="Ignore due/interval gates")
    parser.add_argument("--status", action="store_true", help="Print status only")
    args = parser.parse_args()
    if args.status:
        print(json.dumps(status_snapshot(), indent=2))
        return 0
    result = run_weekly_update(force=args.force)
    print(json.dumps({k: v for k, v in result.items() if k != "steps"}, indent=2, default=str))
    if result.get("ok"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
