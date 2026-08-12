# Trading Sessions Overlay (Phase 11.10 / 11.10.1)

**Status:** Implemented (DST-aware)  
**Scope:** UI / reference only — does **not** feed Phase 6 strategy, Phase 10 combined signal, or Phase 11 risk.

## Purpose

Gold / PAXGUSD volatility characteristically differs by trading session. This feature tags candles and shades the chart so the user can see which session(s) apply — Asia, London, New York, and the London+NY overlap window.

## How windows are defined

| Session | Clock basis | Timezone / notes |
|---------|-------------|------------------|
| Asia | Fixed **UTC** `00:00–09:00` | Japan has no DST — year-round stable |
| London | Local **08:00–17:00** | `Europe/London` via `zoneinfo` |
| New York | Local **08:00–17:00** | `America/New_York` via `zoneinfo` |
| London + NY Overlap | **Derived** = London ∩ New York | Recomputed after DST-aware legs |

IST labels (`UTC+5:30`, no DST) are **display only** — convert the resulting UTC window for the `as_of` / candle date. India does not drive the London/NY legs.

## Why not fixed UTC minutes? (Phase 11.10.1)

London (UK/EU) and New York (US) observe DST on **different** transition dates. A year-round UTC table locked to one season is wrong for roughly half the year, and wrong in the multi-week spring/autumn gaps where only one region has switched.

Examples of UTC mapping for local 08:00–17:00:

| Season | London → UTC | New York → UTC | Overlap → UTC |
|--------|--------------|----------------|---------------|
| Northern summer (BST + EDT) | `07:00–16:00` | `12:00–21:00` | `12:00–16:00` |
| Northern winter (GMT + EST) | `08:00–17:00` | `13:00–22:00` | `13:00–17:00` |

So in **August**, New York / overlap open about **1 hour earlier** than the old Phase 11.10 fixed table (which matched winter NY / summer London inconsistently).

Transition-week example (2026-03-15): US already on EDT, UK still on GMT → London `08:00–17:00` UTC, NY `12:00–21:00` UTC, overlap `12:00–17:00` UTC. Hardcoded “add 1h April–October” rules miss this.

## Historical candles

Tagging uses the DST rules in effect on **that candle’s timestamp**, not “today”:

- Backend: `sessions_for_timestamp(ts)` → `astimezone(ZoneInfo(...))` for that `ts`
- Frontend chart bands: same idea via `Intl` + API-provided `timezone` / `local_*_minute` / `window_mode` (so scrolling old backfill data stays correct across DST boundaries)

## Overlap + multi-label tagging

A candle can belong to **multiple** sessions (e.g. Asia ∩ London mid-day IST). Overlap is tagged only when both London and New York contain the instant. Chart band color priority: Overlap > New York > London > Asia.

## Single source of truth

| Location | Role |
|----------|------|
| `backend/app/core/sessions.py` | Local clocks, zoneinfo tagging, derived overlap, Asia fixed UTC |
| `GET /api/market/sessions` | Defs for `as_of` (IST/UTC display) + `timezone` / `local_*` for chart |
| `GET /api/market/sessions/tag` | Tag one UTC timestamp |
| Frontend | Consumes API — no duplicated IST session tables |

## Chart behavior

- Semi-transparent histogram columns behind candles (gold-dark theme).
- Rendered only on **15m / 30m / 1h**; hidden on **4h / 1d**.
- Toggle updates histogram visibility/data only — **no full chart rebuild**.

## API

```http
GET /api/market/sessions?as_of=2026-06-15T13:00:00Z
GET /api/market/sessions/tag?timestamp=2026-01-15T12:00:00Z
```

Response `sessions[]` includes `window_mode` (`fixed_utc` | `local` | `overlap`), optional `timezone` / `local_start_minute` / `local_end_minute`, plus DST-aware `utc_*` and `ist_window` for the requested `as_of`.

## Hard constraints

- Do not wire session tags into BUY / SELL / WAIT / NO_TRADE decisions.
- Do not hardcode London/NY IST boundaries in frontend components.
