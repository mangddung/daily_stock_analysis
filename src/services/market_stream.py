# -*- coding: utf-8 -*-
"""Live market overview for the home dashboard.

Two Yahoo Finance sources are merged per symbol:
- a ``Ticker.info`` snapshot (refreshed every SNAPSHOT_TTL seconds) that carries the
  quote time, exchange delay, market state and pre/post-market prices;
- ticks from Yahoo's public streamer websocket (no API key) that keep the price live.

The background work starts on the first overview request and stops by itself once
nobody has asked for the overview for IDLE_TIMEOUT seconds.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:  # Shipped as yfinance dependencies; without them the overview runs on snapshots only.
    from websockets.asyncio.client import connect as ws_connect
    from yfinance.pricing_pb2 import PricingData

    STREAM_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the installed yfinance build
    STREAM_AVAILABLE = False

STREAM_URL = "wss://streamer.finance.yahoo.com/?version=2"
SNAPSHOT_TTL = 120.0
IDLE_TIMEOUT = 300.0
RATE_LIMIT_BACKOFF = 300.0
RESUBSCRIBE_INTERVAL = 15.0  # Yahoo drops subscriptions that are not refreshed
SNAPSHOT_CONCURRENCY = 4

# (symbol, display name, market)
INDICES: List[Tuple[str, str, str]] = [
    ("^GSPC", "S&P 500", "us"),
    ("^IXIC", "NASDAQ", "us"),
    ("^DJI", "Dow Jones", "us"),
    ("^KS11", "KOSPI", "kr"),
    ("^KQ11", "KOSDAQ", "kr"),
    ("^N225", "Nikkei 225", "jp"),
    ("^HSI", "Hang Seng", "hk"),
    ("000001.SS", "SSE Composite", "cn"),
]
FX: List[Tuple[str, str]] = [
    ("KRW=X", "USD/KRW"),
    ("JPY=X", "USD/JPY"),
    ("CNY=X", "USD/CNY"),
    ("EURUSD=X", "EUR/USD"),
]

# Yahoo marketState -> dashboard session. PREPRE/POSTPOST/CLOSED all mean no trading.
_SESSION_BY_STATE = {"PRE": "pre", "REGULAR": "regular", "POST": "post"}
# Streamer market_hours: 0 pre-market, 1 regular, 2 post-market.
_SESSION_BY_MARKET_HOURS = {0: "pre", 1: "regular", 2: "post"}

_INFO_FIELDS = (
    "shortName",
    "currency",
    "marketState",
    "exchangeDataDelayedBy",
    "regularMarketPrice",
    "regularMarketChange",
    "regularMarketChangePercent",
    "regularMarketTime",
    "preMarketPrice",
    "preMarketChange",
    "preMarketChangePercent",
    "preMarketTime",
    "postMarketPrice",
    "postMarketChange",
    "postMarketChangePercent",
    "postMarketTime",
)


def to_yahoo_symbol(code: str) -> str:
    """Map a watchlist code (600519, hk00700, AAPL, 005930.KS) to its Yahoo symbol."""
    from data_provider.yfinance_fetcher import YfinanceFetcher

    return YfinanceFetcher()._convert_stock_code(code)


def fetch_snapshot(symbol: str) -> Dict[str, Any]:
    """Blocking ``Ticker.info`` call reduced to the fields the dashboard needs."""
    import yfinance as yf

    info = yf.Ticker(symbol).info or {}
    return {key: info.get(key) for key in _INFO_FIELDS}


def decode_tick(raw: str) -> Optional[Dict[str, Any]]:
    """Decode one streamer frame (JSON wrapping a base64 protobuf PricingData)."""
    data = PricingData()
    data.ParseFromString(base64.b64decode(json.loads(raw).get("message", "")))
    if not data.id:
        return None
    return {
        "symbol": data.id,
        "price": data.price,
        "change": data.change,
        "change_percent": data.change_percent,
        "time": int(data.time) / 1000.0,  # epoch ms -> s
        "session": _SESSION_BY_MARKET_HOURS.get(data.market_hours, "regular"),
    }


def _session_from_state(state: Optional[str]) -> str:
    return _SESSION_BY_STATE.get(str(state or "").upper(), "closed")


def merge_quote(
    symbol: str,
    snapshot: Optional[Dict[str, Any]],
    tick: Optional[Dict[str, Any]],
    *,
    name: Optional[str] = None,
    code: Optional[str] = None,
) -> Dict[str, Any]:
    """Combine the snapshot with a newer streamed tick into one dashboard quote."""
    snap = snapshot or {}
    quote: Dict[str, Any] = {
        "symbol": symbol,
        "code": code or symbol,
        "name": name or snap.get("shortName") or symbol,
        "currency": snap.get("currency"),
        "session": _session_from_state(snap.get("marketState")),
        "delay_minutes": snap.get("exchangeDataDelayedBy"),
        "price": snap.get("regularMarketPrice"),
        "change": snap.get("regularMarketChange"),
        "change_percent": snap.get("regularMarketChangePercent"),
        "as_of": snap.get("regularMarketTime"),
        "extended": None,
        "source": "snapshot" if snap else "none",
    }
    for prefix, session in (("preMarket", "pre"), ("postMarket", "post")):
        price = snap.get(f"{prefix}Price")
        if price is not None and quote["session"] == session:
            quote["extended"] = {
                "session": session,
                "price": price,
                "change": snap.get(f"{prefix}Change"),
                "change_percent": snap.get(f"{prefix}ChangePercent"),
                "as_of": snap.get(f"{prefix}Time"),
            }

    if not tick or tick["time"] < (quote["as_of"] or 0):
        return quote
    if tick["session"] == "regular":
        quote.update(
            price=tick["price"],
            change=tick["change"],
            change_percent=tick["change_percent"],
            as_of=tick["time"],
            source="stream",
        )
    else:
        current = quote["extended"]
        if current is None or tick["time"] >= (current.get("as_of") or 0):
            quote["extended"] = {
                "session": tick["session"],
                "price": tick["price"],
                "change": tick["change"],
                "change_percent": tick["change_percent"],
                "as_of": tick["time"],
            }
            quote["source"] = "stream"
    return quote


class MarketStream:
    """Keeps snapshots and streamed ticks for the dashboard symbols."""

    def __init__(self) -> None:
        self._snapshots: Dict[str, Dict[str, Any]] = {}
        self._snapshot_at: Dict[str, float] = {}
        self._ticks: Dict[str, Dict[str, Any]] = {}
        self._watchlist: List[Tuple[str, str]] = []  # (code, yahoo symbol)
        self._symbol_cache: Dict[str, str] = {}
        self._last_access = 0.0
        self._backoff_until = 0.0
        self._stream_connected = False
        self._task: Optional[asyncio.Task] = None

    # ---- public -------------------------------------------------------------

    def overview(self, watchlist_codes: Iterable[str]) -> Dict[str, Any]:
        """Return the current overview and make sure background updates are running."""
        self._last_access = time.monotonic()
        self._set_watchlist(watchlist_codes)
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._run())
        return self._build()

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    # ---- state --------------------------------------------------------------

    def _set_watchlist(self, codes: Iterable[str]) -> None:
        watchlist = []
        for code in codes:
            code = str(code).strip()
            if not code:
                continue
            if code not in self._symbol_cache:
                try:
                    self._symbol_cache[code] = to_yahoo_symbol(code)
                except Exception:  # unknown format: try the code as-is
                    self._symbol_cache[code] = code.upper()
            watchlist.append((code, self._symbol_cache[code]))
        self._watchlist = watchlist

    def _symbols(self) -> List[str]:
        symbols = [s for s, _, _ in INDICES] +[s for s, _ in FX] + [s for _, s in self._watchlist]
        return list(dict.fromkeys(symbols))

    def _quote(self, symbol: str, **kwargs: Any) -> Dict[str, Any]:
        return merge_quote(symbol, self._snapshots.get(symbol), self._ticks.get(symbol), **kwargs)

    def _build(self) -> Dict[str, Any]:
        return {
            "server_time": time.time(),
            "stream_connected": self._stream_connected,
            "indices": [{**self._quote(s, name=n), "market": m} for s, n, m in INDICES],
            "fx": [self._quote(s, name=n) for s, n in FX],
            "watchlist": [self._quote(s, code=c) for c, s in self._watchlist],
        }

    # ---- background ---------------------------------------------------------

    async def _run(self) -> None:
        workers = [asyncio.create_task(self._snapshot_loop())]
        if STREAM_AVAILABLE:
            workers.append(asyncio.create_task(self._stream_loop()))
        try:
            while time.monotonic() - self._last_access < IDLE_TIMEOUT:
                await asyncio.sleep(5)
        finally:
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            self._stream_connected = False

    async def _snapshot_loop(self) -> None:
        semaphore = asyncio.Semaphore(SNAPSHOT_CONCURRENCY)

        async def refresh(symbol: str) -> None:
            async with semaphore:
                if time.monotonic() < self._backoff_until:
                    return
                try:
                    self._snapshots[symbol] = await asyncio.to_thread(fetch_snapshot, symbol)
                except Exception as exc:
                    if type(exc).__name__ == "YFRateLimitError":
                        logger.warning("[MarketStream] Yahoo rate limit hit, pausing snapshots")
                        self._backoff_until = time.monotonic() + RATE_LIMIT_BACKOFF
                    else:
                        logger.debug("[MarketStream] snapshot %s failed: %s", symbol, exc)
                # Failed symbols also wait a full TTL so a bad code is not retried every few seconds.
                self._snapshot_at[symbol] = time.monotonic()

        while True:
            now = time.monotonic()
            stale = [s for s in self._symbols() if now - self._snapshot_at.get(s, -SNAPSHOT_TTL) >= SNAPSHOT_TTL]
            if stale and now >= self._backoff_until:
                await asyncio.gather(*(refresh(s) for s in stale))
            await asyncio.sleep(2)

    async def _stream_loop(self) -> None:
        while True:
            try:
                async with ws_connect(STREAM_URL) as ws:
                    subscribed: set = set()
                    last_subscribe = 0.0
                    while True:
                        wanted = set(self._symbols())
                        now = time.monotonic()
                        if wanted != subscribed or now - last_subscribe >= RESUBSCRIBE_INTERVAL:
                            removed = subscribed - wanted
                            if removed:
                                await ws.send(json.dumps({"unsubscribe": sorted(removed)}))
                            await ws.send(json.dumps({"subscribe": sorted(wanted)}))
                            subscribed, last_subscribe = wanted, now
                            self._stream_connected = True
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=RESUBSCRIBE_INTERVAL)
                        except asyncio.TimeoutError:
                            continue
                        try:
                            tick = decode_tick(raw)
                        except Exception as exc:
                            logger.debug("[MarketStream] undecodable frame: %s", exc)
                            continue
                        if tick:
                            self._ticks[tick["symbol"]] = tick
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("[MarketStream] stream disconnected, retrying: %s", exc)
            self._stream_connected = False
            await asyncio.sleep(5)


_market_stream: Optional[MarketStream] = None


def get_market_stream() -> MarketStream:
    global _market_stream
    if _market_stream is None:
        _market_stream = MarketStream()
    return _market_stream
