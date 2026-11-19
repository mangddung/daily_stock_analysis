# -*- coding: utf-8 -*-
"""Market price precision for LLM prompts (KR/JP quote in whole units).

KRX tick table (KOSPI/KOSDAQ unified since 2023-01-25):
<2,000: 1 / <5,000: 5 / <20,000: 10 / <50,000: 50 / <200,000: 100 /
<500,000: 500 / >=500,000: 1,000 KRW.

TSE ticks also depend on TOPIX100 membership, which the app does not track, so
JP prices are only rounded to whole yen.
"""

from __future__ import annotations

from typing import Any, Optional

from src.services.market_symbol_utils import get_suffix_market

_KR_TICKS = ((2_000, 1), (5_000, 5), (20_000, 10), (50_000, 50), (200_000, 100), (500_000, 500))
_KR_TICK_TEXT = "<2,000: 1; <5,000: 5; <20,000: 10; <50,000: 50; <200,000: 100; <500,000: 500; >=500,000: 1,000"


def price_market(code: str) -> Optional[str]:
    """'kr' / 'jp' for whole-unit markets, else None (keep two decimals)."""
    market = get_suffix_market(code or "")
    return market if market in ("kr", "jp") else None


def kr_tick(price: float) -> int:
    for limit, tick in _KR_TICKS:
        if price < limit:
            return tick
    return 1_000


def round_market_price(value: Any, market: Optional[str]) -> Any:
    """Round a numeric price to the market unit; non-numeric values pass through."""
    if market is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    if market == "kr":
        tick = kr_tick(value)
        return int(round(value / tick) * tick)
    return int(round(value))


def price_precision_rule(market: Optional[str], english: bool) -> str:
    """Instruction text for sniper price precision in the analysis prompt."""
    if market == "kr":
        if english:
            return f"KRW whole numbers with no decimals, each rounded to the KRX tick size ({_KR_TICK_TEXT} KRW)"
        return f"韩元取整、不保留小数，并按 KRX 最小报价单位取整（{_KR_TICK_TEXT} 韩元）"
    if market == "jp":
        return "JPY whole numbers with no decimals" if english else "日元取整、不保留小数"
    return "to two decimals" if english else "精确到分"
