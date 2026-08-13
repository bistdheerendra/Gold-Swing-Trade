"""Real free-tier market data — Delta India (PAXGUSD, SLVONUSD) + Twelve Data (XAUUSD ref).

No silent fallback to mock data. API failures raise loudly.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Sequence, Set

import httpx

from app.core.logging import get_logger
from app.market.provider import MarketDataProvider, _align_timestamp
from app.market.schemas import OHLCVBar, Timeframe, ensure_utc, parse_timeframe, sort_bars
from app.market.validator import OHLCVValidator, clip_to_range

logger = get_logger(__name__)

ProviderBackend = Literal["delta_india", "twelvedata"]

DELTA_INDIA_BASE = "https://api.india.delta.exchange"
TWELVEDATA_BASE = "https://api.twelvedata.com"

# Verified via GET /v2/products — live perpetuals on Delta India
DEFAULT_DELTA_PAXGUSD_SYMBOL = "PAXGUSD"
DEFAULT_DELTA_SLVONUSD_SYMBOL = "SLVONUSD"

DEFAULT_DELTA_SYMBOL_MAP: Dict[str, str] = {
    "PAXGUSD": DEFAULT_DELTA_PAXGUSD_SYMBOL,
    "SLVONUSD": DEFAULT_DELTA_SLVONUSD_SYMBOL,
}

DEFAULT_TWELVEDATA_SYMBOL_MAP: Dict[str, str] = {
    "XAUUSD": "XAU/USD",
}

_DELTA_RESOLUTION: Dict[Timeframe, str] = {
    Timeframe.M1: "1m",
    Timeframe.M5: "5m",
    Timeframe.M15: "15m",
    Timeframe.M30: "30m",
    Timeframe.H1: "1h",
    Timeframe.H4: "4h",
    Timeframe.D1: "1d",
}

_TWELVE_INTERVAL: Dict[Timeframe, str] = {
    Timeframe.M1: "1min",
    Timeframe.M5: "5min",
    Timeframe.M15: "15min",
    Timeframe.M30: "30min",
    Timeframe.H1: "1h",
    Timeframe.H4: "4h",
    Timeframe.D1: "1day",
}

_DELTA_MAX_CANDLES = 2000
_TWELVE_MAX_OUTPUT = 5000

_last_provider_error: Optional[str] = None
_last_provider_ok: bool = True
_verified_delta_symbols: Dict[str, str] = {}
# Backward-compat alias used by older health consumers
_verified_delta_symbol: Optional[str] = None


def get_provider_health() -> dict[str, Any]:
    return {
        "ok": _last_provider_ok,
        "last_error": _last_provider_error,
        "verified_delta_paxgusd_symbol": _verified_delta_symbols.get("PAXGUSD")
        or _verified_delta_symbol,
        "verified_delta_symbols": dict(_verified_delta_symbols),
    }


def _set_provider_ok() -> None:
    global _last_provider_ok, _last_provider_error
    _last_provider_ok = True
    _last_provider_error = None


def _set_provider_error(message: str) -> None:
    global _last_provider_ok, _last_provider_error
    _last_provider_ok = False
    _last_provider_error = message
    logger.error("real_market_data_error %s", message)


async def _request_with_backoff(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    max_retries: int = 5,
    base_delay: float = 0.5,
) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = await client.request(method, url, params=params, headers=headers)
            if resp.status_code == 429 or resp.status_code >= 500:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else base_delay * (2**attempt)
                logger.warning(
                    "rate_limit_or_server_error status=%s attempt=%s sleep=%.2fs url=%s",
                    resp.status_code,
                    attempt + 1,
                    delay,
                    url,
                )
                await asyncio.sleep(delay)
                continue
            return resp
        except httpx.TransportError as exc:
            last_exc = exc
            delay = base_delay * (2**attempt)
            logger.warning(
                "transport_error attempt=%s sleep=%.2fs err=%s",
                attempt + 1,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
    if last_exc:
        raise RuntimeError(f"Request failed after retries: {last_exc}") from last_exc
    raise RuntimeError(f"Request failed after {max_retries} retries: {url}")


async def verify_delta_symbol(
    *,
    base_url: str = DELTA_INDIA_BASE,
    expected: str = DEFAULT_DELTA_PAXGUSD_SYMBOL,
    timeout_seconds: float = 30.0,
) -> str:
    """
    Confirm a Delta India product exists via GET /v2/products.
    Returns the exact listed symbol string. Raises if not found / not live.
    """
    global _verified_delta_symbol
    root = base_url.rstrip("/")
    if root.endswith("/v2"):
        products_url = f"{root}/products"
    else:
        products_url = f"{root}/v2/products"

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await _request_with_backoff(
            client, "GET", products_url, headers={"Accept": "application/json"}
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Delta products HTTP {resp.status_code}: {resp.text[:300]}"
            )
        payload = resp.json()

    products = payload.get("result") or []
    if not isinstance(products, list):
        raise RuntimeError("Unexpected Delta /v2/products payload")

    want = expected.strip().upper()
    for product in products:
        if not isinstance(product, dict):
            continue
        sym = str(product.get("symbol") or "").upper()
        if sym == want:
            state = str(product.get("state") or "").lower()
            if state and state not in ("live", "active", ""):
                raise RuntimeError(
                    f"Delta product {sym} found but state={state!r} (expected live)"
                )
            listed = str(product.get("symbol"))
            _verified_delta_symbols[want] = listed
            _verified_delta_symbol = listed
            logger.info(
                "delta_symbol_verified symbol=%s state=%s contract_type=%s",
                listed,
                product.get("state"),
                product.get("contract_type"),
            )
            return listed

    raise RuntimeError(
        f"Delta India /v2/products has no product symbol={want}. "
        "Do not assume the string — check the products catalog."
    )


async def verify_delta_paxgusd_symbol(
    *,
    base_url: str = DELTA_INDIA_BASE,
    expected: str = DEFAULT_DELTA_PAXGUSD_SYMBOL,
    timeout_seconds: float = 30.0,
) -> str:
    """Backward-compatible alias for verify_delta_symbol (PAXGUSD default)."""
    return await verify_delta_symbol(
        base_url=base_url, expected=expected, timeout_seconds=timeout_seconds
    )


class RealMarketDataProvider(MarketDataProvider):
    """
    Free-tier real OHLCV provider.

    - provider=\"delta_india\": authoritative PAXGUSD + SLVONUSD candles (no API key)
    - provider=\"twelvedata\": XAU/USD reference feed (free API key)

    Never falls back to mock or Binance proxies. Series are never blended across symbols.
    """

    def __init__(
        self,
        provider: ProviderBackend = "delta_india",
        *,
        delta_base_url: str = DELTA_INDIA_BASE,
        delta_paxgusd_symbol: str = DEFAULT_DELTA_PAXGUSD_SYMBOL,
        delta_slvonusd_symbol: str = DEFAULT_DELTA_SLVONUSD_SYMBOL,
        delta_symbol_map: Optional[Dict[str, str]] = None,
        twelvedata_base_url: str = TWELVEDATA_BASE,
        twelvedata_api_key: str = "",
        twelvedata_symbol_map: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 30.0,
        min_request_interval_seconds: float = 0.2,
        validate_responses: bool = True,
        verify_product_on_init: bool = False,
    ) -> None:
        backend = provider.strip().lower().replace("-", "_")
        if backend in ("delta", "delta_india"):
            backend = "delta_india"
        if backend not in ("delta_india", "twelvedata"):
            raise ValueError(
                f"Unsupported real provider '{provider}'. Allowed: delta_india, twelvedata"
            )
        self.backend: ProviderBackend = backend  # type: ignore[assignment]
        self.name = f"real_{self.backend}"
        self.delta_base_url = delta_base_url.rstrip("/")
        self.delta_paxgusd_symbol = delta_paxgusd_symbol.strip().upper() or (
            DEFAULT_DELTA_PAXGUSD_SYMBOL
        )
        self.delta_slvonusd_symbol = delta_slvonusd_symbol.strip().upper() or (
            DEFAULT_DELTA_SLVONUSD_SYMBOL
        )
        self.delta_symbol_map = dict(delta_symbol_map or DEFAULT_DELTA_SYMBOL_MAP)
        self.delta_symbol_map["PAXGUSD"] = self.delta_paxgusd_symbol
        self.delta_symbol_map["SLVONUSD"] = self.delta_slvonusd_symbol
        self.twelvedata_base_url = twelvedata_base_url.rstrip("/")
        self.twelvedata_api_key = (twelvedata_api_key or "").strip()
        self.twelvedata_symbol_map = twelvedata_symbol_map or dict(
            DEFAULT_TWELVEDATA_SYMBOL_MAP
        )
        self.timeout = timeout_seconds
        self.min_request_interval = min_request_interval_seconds
        self.validate_responses = validate_responses
        self._validator = OHLCVValidator()
        self._last_request_at = 0.0
        self._verified_app_symbols: Set[str] = set()

        if self.backend == "twelvedata" and not self.twelvedata_api_key:
            raise ValueError(
                "TWELVEDATA_API_KEY is required when MARKET_DATA_PROVIDER=twelvedata. "
                "Get a free key at https://twelvedata.com"
            )

    def map_symbol(self, symbol: str) -> str:
        key = symbol.strip().upper()
        if self.backend == "delta_india":
            if key in self.delta_symbol_map:
                return self.delta_symbol_map[key]
            raise ValueError(
                f"delta_india provider supports {', '.join(sorted(self.delta_symbol_map))} "
                f"(got '{symbol}'). Use MARKET_DATA_PROVIDER=twelvedata for XAUUSD reference."
            )
        if key not in self.twelvedata_symbol_map:
            raise ValueError(
                f"twelvedata provider does not support symbol '{symbol}'. "
                f"Supported: {', '.join(sorted(self.twelvedata_symbol_map))}"
            )
        return self.twelvedata_symbol_map[key]

    async def ensure_delta_symbol_verified(self, symbol: str = "PAXGUSD") -> str:
        """Verify one Delta product; caches per app symbol."""
        app_symbol = symbol.strip().upper()
        expected = self.map_symbol(app_symbol)
        if app_symbol in self._verified_app_symbols and expected in _verified_delta_symbols:
            return _verified_delta_symbols[expected]
        listed = await verify_delta_symbol(
            base_url=self.delta_base_url,
            expected=expected,
            timeout_seconds=self.timeout,
        )
        if listed.upper() != expected.upper():
            raise RuntimeError(
                f"Configured Delta symbol={expected} does not match listed symbol={listed}"
            )
        self.delta_symbol_map[app_symbol] = listed
        if app_symbol == "PAXGUSD":
            self.delta_paxgusd_symbol = listed
        elif app_symbol == "SLVONUSD":
            self.delta_slvonusd_symbol = listed
        self._verified_app_symbols.add(app_symbol)
        return listed

    async def get_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str | Timeframe,
        start: datetime,
        end: datetime,
    ) -> List[OHLCVBar]:
        tf = timeframe if isinstance(timeframe, Timeframe) else parse_timeframe(timeframe)
        start_utc = ensure_utc(start)
        end_utc = ensure_utc(end)
        if end_utc < start_utc:
            raise ValueError("end must be >= start")

        app_symbol = symbol.strip().upper()
        try:
            if self.backend == "delta_india":
                await self.ensure_delta_symbol_verified(app_symbol)
                bars = await self._fetch_delta(app_symbol, tf, start_utc, end_utc)
            else:
                bars = await self._fetch_twelvedata(app_symbol, tf, start_utc, end_utc)
        except Exception as exc:  # noqa: BLE001
            _set_provider_error(f"{self.name}: {exc}")
            raise

        clipped = clip_to_range(sort_bars(bars), start_utc, end_utc)
        if self.validate_responses:
            self._assert_valid(clipped, app_symbol, tf)
        _set_provider_ok()
        return clipped

    def _assert_valid(
        self,
        bars: Sequence[OHLCVBar],
        symbol: str,
        timeframe: Timeframe,
    ) -> None:
        report = self._validator.validate(
            list(bars),
            expect_symbol=symbol,
            expect_timeframe=timeframe,
            check_missing=True,
        )
        blocking = {
            "duplicate_timestamp",
            "invalid_ohlc",
            "timezone",
            "chronological_order",
            "empty",
            "symbol_mismatch",
            "timeframe_mismatch",
        }
        bad = [i for i in report.issues if i.code in blocking]
        if bad:
            detail = "; ".join(f"{i.code}: {i.message}" for i in bad[:5])
            raise RuntimeError(
                f"Rejecting malformed/gappy API response from {self.name}: {detail}"
            )

    async def _throttle(self) -> None:
        now = time.monotonic()
        wait = self.min_request_interval - (now - self._last_request_at)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request_at = time.monotonic()

    def _delta_api_root(self) -> str:
        root = self.delta_base_url.rstrip("/")
        return root if root.endswith("/v2") else f"{root}/v2"

    async def _fetch_delta(
        self,
        app_symbol: str,
        tf: Timeframe,
        start_utc: datetime,
        end_utc: datetime,
    ) -> List[OHLCVBar]:
        delta_symbol = self.map_symbol(app_symbol)
        resolution = _DELTA_RESOLUTION[tf]
        step_sec = int(tf.delta.total_seconds())
        aligned_start = _align_timestamp(start_utc, tf)
        end_epoch = int(end_utc.timestamp())
        start_epoch = int(aligned_start.timestamp())

        raw_rows: List[Dict[str, Any]] = []
        cursor_end = end_epoch
        url = f"{self._delta_api_root()}/history/candles"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for _ in range(40):
                cursor_start = max(
                    start_epoch,
                    cursor_end - (_DELTA_MAX_CANDLES * step_sec),
                )
                await self._throttle()
                params = {
                    "symbol": delta_symbol,
                    "resolution": resolution,
                    "start": cursor_start,
                    "end": cursor_end,
                }
                resp = await _request_with_backoff(
                    client,
                    "GET",
                    url,
                    params=params,
                    headers={"Accept": "application/json"},
                )
                if resp.status_code >= 400:
                    raise RuntimeError(
                        f"Delta candles HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                payload = resp.json()
                if not payload.get("success", True):
                    raise RuntimeError(f"Delta candles error: {payload}")
                chunk = payload.get("result") or []
                if not isinstance(chunk, list):
                    raise RuntimeError(
                        f"Unexpected Delta candles payload: {type(chunk)}"
                    )
                if not chunk:
                    break
                raw_rows.extend(chunk)
                oldest = min(int(r["time"]) for r in chunk)
                if oldest <= start_epoch:
                    break
                cursor_end = oldest - 1
                if cursor_end <= start_epoch:
                    break

        by_ts: Dict[int, Dict[str, Any]] = {}
        for row in raw_rows:
            if not isinstance(row, dict):
                raise RuntimeError(f"Malformed Delta candle row: {row!r}")
            try:
                ts = int(row["time"])
                o = float(row["open"])
                h = float(row["high"])
                l = float(row["low"])
                c = float(row["close"])
                vol = float(row.get("volume") or 0.0)
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(f"Non-numeric Delta candle: {row!r}") from exc
            if h < max(o, c) or l > min(o, c) or h < l:
                raise RuntimeError(f"Invalid OHLC invariants in Delta row: {row!r}")
            by_ts[ts] = {
                "time": ts,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": vol,
            }

        bars: List[OHLCVBar] = []
        for ts in sorted(by_ts):
            row = by_ts[ts]
            bars.append(
                OHLCVBar(
                    timestamp=datetime.fromtimestamp(ts, tz=timezone.utc),
                    symbol=app_symbol,
                    timeframe=tf,
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=max(0.0, row["volume"]),
                    source=self.name,
                )
            )
        return bars

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Read-only live ticker from Delta (no auth)."""
        if self.backend != "delta_india":
            raise RuntimeError("Ticker is only available for delta_india provider")
        app_symbol = symbol.strip().upper()
        await self.ensure_delta_symbol_verified(app_symbol)
        delta_symbol = self.map_symbol(app_symbol)
        url = f"{self._delta_api_root()}/tickers/{delta_symbol}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self._throttle()
            resp = await _request_with_backoff(
                client, "GET", url, headers={"Accept": "application/json"}
            )
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Delta ticker HTTP {resp.status_code}: {resp.text[:300]}"
                )
            payload = resp.json()
        result = payload.get("result") or {}
        quotes = result.get("quotes") or {}

        def _f(value: Any) -> Optional[float]:
            if value is None or value == "":
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        bid = _f(quotes.get("best_bid") or result.get("close"))
        ask = _f(quotes.get("best_ask") or result.get("close"))
        last = _f(result.get("close") or result.get("mark_price"))
        return {
            "symbol": app_symbol,
            "delta_symbol": delta_symbol,
            "bid": bid,
            "ask": ask,
            "last": last,
            "mark_price": _f(result.get("mark_price")),
            "spread_source": "LIVE" if bid is not None and ask is not None else "UNKNOWN",
            "source": self.name,
            "raw_time": result.get("time"),
        }

    async def _fetch_twelvedata(
        self,
        app_symbol: str,
        tf: Timeframe,
        start_utc: datetime,
        end_utc: datetime,
    ) -> List[OHLCVBar]:
        exchange_symbol = self.map_symbol(app_symbol)
        interval = _TWELVE_INTERVAL[tf]
        url = f"{self.twelvedata_base_url}/time_series"
        params = {
            "symbol": exchange_symbol,
            "interval": interval,
            "start_date": start_utc.strftime("%Y-%m-%d %H:%M:%S"),
            "end_date": end_utc.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": "UTC",
            "order": "ASC",
            "outputsize": _TWELVE_MAX_OUTPUT,
            "apikey": self.twelvedata_api_key,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await self._throttle()
            resp = await _request_with_backoff(client, "GET", url, params=params)
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Twelve Data HTTP {resp.status_code}: {resp.text[:300]}"
                )
            payload = resp.json()

        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected Twelve Data payload type: {type(payload)}")
        if payload.get("status") == "error" or (
            payload.get("values") is None and payload.get("code") is not None
        ):
            msg = payload.get("message") or payload.get("status") or str(payload)[:200]
            raise RuntimeError(f"Twelve Data error: {msg}")

        values = payload.get("values")
        if values is None:
            raise RuntimeError(f"Twelve Data missing values: {str(payload)[:400]}")
        if not isinstance(values, list):
            raise RuntimeError(f"Twelve Data values not a list: {type(values)}")

        bars: List[OHLCVBar] = []
        for row in values:
            if not isinstance(row, dict):
                raise RuntimeError(f"Malformed Twelve Data row: {row!r}")
            ts_raw = row.get("datetime")
            if not ts_raw:
                raise RuntimeError(f"Twelve Data row missing datetime: {row!r}")
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)
            try:
                o = float(row["open"])
                h = float(row["high"])
                l = float(row["low"])
                c = float(row["close"])
                vol = float(row.get("volume") or 0.0)
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(f"Non-numeric Twelve Data OHLC: {row!r}") from exc
            if h < max(o, c) or l > min(o, c) or h < l:
                raise RuntimeError(f"Invalid OHLC invariants in Twelve Data row: {row!r}")
            bars.append(
                OHLCVBar(
                    timestamp=ts,
                    symbol=app_symbol,
                    timeframe=tf,
                    open=o,
                    high=h,
                    low=l,
                    close=c,
                    volume=max(0.0, vol),
                    source=self.name,
                )
            )
        return bars
