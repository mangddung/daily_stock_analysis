# -*- coding: utf-8 -*-
"""Live market overview for the home dashboard."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, Depends

from api.deps import get_system_config_service
from api.v1.endpoints.stocks import _read_watchlist_codes
from src.core.market_hours import market_phase
from src.services.market_stream import get_market_stream
from src.services.system_config_service import SystemConfigService

router = APIRouter()

DASHBOARD_MARKETS = ("us", "kr", "jp", "hk", "cn")


@router.get(
    "/overview",
    summary="Live market overview",
    description=(
        "Market sessions, major indices, FX rates and watchlist quotes. Prices come from "
        "Yahoo Finance snapshots plus its streamer; each quote carries as_of (epoch seconds) "
        "and delay_minutes so the client can show how fresh it is."
    ),
)
async def get_market_overview(
    service: SystemConfigService = Depends(get_system_config_service),
) -> Dict[str, Any]:
    codes = await asyncio.to_thread(_read_watchlist_codes, service)
    payload = get_market_stream().overview(codes)
    # First call builds the exchange calendars (slow), so keep it off the event loop.
    payload["markets"] = await asyncio.to_thread(lambda: [market_phase(m) for m in DASHBOARD_MARKETS])
    return payload
