# -*- coding: utf-8 -*-
"""Session phase checks against real exchange calendars (no network)."""

from datetime import datetime, timezone

import pytest

from src.core import market_hours
from src.core.market_hours import market_phase

pytestmark = pytest.mark.skipif(not market_hours._XCALS_AVAILABLE, reason="exchange_calendars not installed")


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def ts(*args):
    return utc(*args).timestamp()


def test_extended_hours_file_loads_us_and_kr():
    windows = market_hours.load_extended_hours()
    assert set(windows["us"]) == {"pre", "post"} and set(windows["kr"]) == {"pre", "post"}


def test_us_premarket_in_winter_starts_0400_et():
    # 2026-11-18 05:00 EST
    phase = market_phase("us", utc(2026, 11, 18, 10, 0))
    assert phase["session"] == "pre"
    assert phase["schedule"][0]["start"] == ts(2026, 11, 18, 9, 0)  # 04:00 EST = 18:00 KST
    assert phase["next_regular_open"] == ts(2026, 11, 18, 14, 30)


def test_us_premarket_follows_dst_without_code_changes():
    # 2026-07-15 04:30 EDT
    phase = market_phase("us", utc(2026, 7, 15, 8, 30))
    assert phase["session"] == "pre"
    assert phase["next_regular_open"] == ts(2026, 7, 15, 13, 30)  # 09:30 EDT = 22:30 KST


def test_us_early_close_shifts_after_hours():
    # Day after Thanksgiving closes 13:00 EST; after hours run until 17:00 EST.
    phase = market_phase("us", utc(2026, 11, 27, 18, 30))
    assert phase["session"] == "post"
    assert phase["session_ends_at"] == ts(2026, 11, 27, 22, 0)


def test_us_holiday_is_closed_until_next_premarket():
    phase = market_phase("us", utc(2026, 11, 26, 15, 0))  # Thanksgiving
    assert phase["session"] == "closed"
    assert phase["next_session"] == "pre"
    assert phase["next_regular_open"] == ts(2026, 11, 27, 14, 30)


def test_kr_nxt_premarket_and_gap_before_open():
    assert market_phase("kr", utc(2026, 11, 18, 23, 30))["session"] == "pre"  # 08:30 KST
    gap = market_phase("kr", utc(2026, 11, 18, 23, 55))  # 08:55 KST, between NXT pre and KRX open
    assert gap["session"] == "closed" and gap["next_regular_open"] == ts(2026, 11, 19, 0, 0)


def test_jp_lunch_break_counts_down_to_afternoon_session():
    phase = market_phase("jp", utc(2026, 11, 18, 3, 0))  # 12:00 JST
    assert phase["session"] == "break"
    assert phase["next_regular_open"] == ts(2026, 11, 18, 3, 30)
    assert [w["phase"] for w in phase["schedule"]] == ["regular", "break", "regular"]


def test_unknown_market_is_reported_as_unknown():
    assert market_phase("xx", utc(2026, 11, 18))["session"] == "unknown"
