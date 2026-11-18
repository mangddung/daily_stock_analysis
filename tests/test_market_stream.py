# -*- coding: utf-8 -*-
"""Offline checks for the dashboard market stream merge and frame decoding."""

import base64
import json

import pytest

from src.services import market_stream
from src.services.market_stream import merge_quote

SNAPSHOT = {
    "shortName": "Apple Inc.",
    "currency": "USD",
    "marketState": "PRE",
    "exchangeDataDelayedBy": 15,
    "regularMarketPrice": 100.0,
    "regularMarketChange": 1.0,
    "regularMarketChangePercent": 1.0,
    "regularMarketTime": 1_000,
    "preMarketPrice": 101.0,
    "preMarketChange": 1.0,
    "preMarketChangePercent": 1.0,
    "preMarketTime": 2_000,
}


def _tick(session, time, price):
    return {"symbol": "AAPL", "price": price, "change": 0.5, "change_percent": 0.5, "time": time, "session": session}


def test_snapshot_only_quote_keeps_time_delay_and_premarket():
    quote = merge_quote("AAPL", SNAPSHOT, None)
    assert quote["session"] == "pre"
    assert quote["price"] == 100.0 and quote["as_of"] == 1_000 and quote["delay_minutes"] == 15
    assert quote["extended"]["price"] == 101.0 and quote["source"] == "snapshot"


def test_newer_regular_tick_replaces_price():
    quote = merge_quote("AAPL", SNAPSHOT, _tick("regular", 3_000, 105.0))
    assert quote["price"] == 105.0 and quote["as_of"] == 3_000 and quote["source"] == "stream"


def test_older_tick_is_ignored():
    quote = merge_quote("AAPL", SNAPSHOT, _tick("pre", 500, 90.0))
    assert quote["price"] == 100.0 and quote["extended"]["price"] == 101.0


def test_newer_premarket_tick_updates_extended_not_regular():
    quote = merge_quote("AAPL", SNAPSHOT, _tick("pre", 2_500, 102.0))
    assert quote["price"] == 100.0
    assert quote["extended"]["price"] == 102.0 and quote["extended"]["session"] == "pre"


def test_closed_market_drops_stale_extended_price():
    quote = merge_quote("AAPL", {**SNAPSHOT, "marketState": "POSTPOST"}, None)
    assert quote["session"] == "closed" and quote["extended"] is None


def test_missing_snapshot_waits_for_data():
    quote = merge_quote("^KS11", None, None, name="KOSPI")
    assert quote["name"] == "KOSPI" and quote["price"] is None and quote["source"] == "none"


@pytest.mark.skipif(not market_stream.STREAM_AVAILABLE, reason="yfinance streamer extras missing")
def test_decode_tick_reads_protobuf_frame():
    data = market_stream.PricingData(id="KRW=X", price=1331.5, time=1_700_000_000_000, change=-2.0, market_hours=1)
    raw = json.dumps({"message": base64.b64encode(data.SerializeToString()).decode()})
    tick = market_stream.decode_tick(raw)
    assert tick["symbol"] == "KRW=X" and tick["price"] == pytest.approx(1331.5)
    assert tick["time"] == 1_700_000_000 and tick["session"] == "regular"
