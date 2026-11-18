# -*- coding: utf-8 -*-
"""Trading session phase per market: pre-market, regular, lunch break, post-market or closed.

Regular hours, lunch breaks, holidays and early closes come from exchange_calendars.
Pre/post-market windows come from market_extended_hours.json, written as offsets from
the regular open/close, so DST and early closes need no code changes.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from src.core.trading_calendar import MARKET_EXCHANGE, MARKET_TIMEZONE

logger = logging.getLogger(__name__)

try:
    import exchange_calendars as xcals

    _XCALS_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    _XCALS_AVAILABLE = False

EXTENDED_HOURS_FILE = Path(__file__).with_name("market_extended_hours.json")


class Interval(NamedTuple):
    start: datetime
    end: datetime
    phase: str  # pre | regular | break | post
    session_date: date


@lru_cache(maxsize=1)
def load_extended_hours() -> Dict[str, Dict[str, Any]]:
    data = json.loads(EXTENDED_HOURS_FILE.read_text(encoding="utf-8"))
    return {market: windows for market, windows in data.items() if not market.startswith("_")}


@lru_cache(maxsize=None)
def _calendar(exchange: str):
    return xcals.get_calendar(exchange)


def _utc(value: Any) -> Optional[datetime]:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).tz_convert("UTC").to_pydatetime()


def session_intervals(market: str, start: date, end: date) -> List[Interval]:
    """All phases of every trading session between two exchange-local dates, in time order."""
    schedule = _calendar(MARKET_EXCHANGE[market]).schedule.loc[str(start):str(end)]
    extended = load_extended_hours().get(market, {})
    intervals: List[Interval] = []
    for session_day, row in schedule.iterrows():
        day = session_day.date()
        anchors = {"open": _utc(row["open"]), "close": _utc(row["close"])}
        break_start, break_end = _utc(row.get("break_start")), _utc(row.get("break_end"))

        def window(phase: str) -> None:
            spec = extended.get(phase)
            if spec:
                anchor = anchors[spec["anchor"]]
                intervals.append(Interval(
                    anchor + timedelta(minutes=spec["start"]),
                    anchor + timedelta(minutes=spec["end"]),
                    phase,
                    day,
                ))

        window("pre")
        if break_start and break_end:
            intervals += [
                Interval(anchors["open"], break_start, "regular", day),
                Interval(break_start, break_end, "break", day),
                Interval(break_end, anchors["close"], "regular", day),
            ]
        else:
            intervals.append(Interval(anchors["open"], anchors["close"], "regular", day))
        window("post")
    return intervals


def market_phase(market: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Current phase of one market plus the times a dashboard needs for countdowns.

    Times are epoch seconds. ``schedule`` lists the phases of the session that is
    running now, or of the next one when the market is closed.
    """
    now = now or datetime.now(timezone.utc)
    result: Dict[str, Any] = {
        "market": market,
        "timezone": MARKET_TIMEZONE.get(market),
        "session": "unknown",
        "session_ends_at": None,
        "next_session": None,
        "next_session_starts_at": None,
        "next_regular_open": None,
        "schedule": [],
    }
    if not _XCALS_AVAILABLE or market not in MARKET_EXCHANGE:
        return result

    today = now.astimezone(ZoneInfo(MARKET_TIMEZONE[market])).date()
    try:
        # Pre-market can start the evening before (e.g. KR clock vs US session), so look back a few days.
        intervals = session_intervals(market, today - timedelta(days=4), today + timedelta(days=14))
    except Exception as exc:
        logger.warning("[MarketHours] %s schedule unavailable: %s", market, exc)
        return result

    current = next((iv for iv in intervals if iv.start <= now < iv.end), None)
    upcoming = [iv for iv in intervals if iv.start > now]
    next_regular = next((iv for iv in upcoming if iv.phase == "regular"), None)
    focus = current or (upcoming[0] if upcoming else None)

    result["session"] = current.phase if current else "closed"
    if current:
        result["session_ends_at"] = current.end.timestamp()
    if upcoming:
        result["next_session"] = upcoming[0].phase
        result["next_session_starts_at"] = upcoming[0].start.timestamp()
    if next_regular:
        result["next_regular_open"] = next_regular.start.timestamp()
    if focus:
        result["schedule"] = [
            {"phase": iv.phase, "start": iv.start.timestamp(), "end": iv.end.timestamp()}
            for iv in intervals
            if iv.session_date == focus.session_date
        ]
    return result
