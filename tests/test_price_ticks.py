# -*- coding: utf-8 -*-
"""Market price precision in the analysis prompt (KR tick size, JP whole yen)."""

import copy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.utils.price_ticks import kr_tick, price_market, price_precision_rule, round_market_price
from tests.test_analyzer_prompt_language import _make_analyzer, _rich_context


@pytest.mark.parametrize("price, tick", [
    (1_999, 1), (2_000, 5), (4_999, 5), (5_000, 10), (19_990, 10), (20_000, 50),
    (49_950, 50), (50_000, 100), (199_900, 100), (200_000, 500), (499_500, 500), (500_000, 1_000),
])
def test_kr_tick_table(price, tick):
    assert kr_tick(price) == tick


def test_round_market_price():
    assert round_market_price(1_152_200.0, "kr") == 1_152_000  # MA5 from the SK hynix report
    assert round_market_price(1_177_200.0, "kr") == 1_177_000
    assert round_market_price(48_730.0, "kr") == 48_750
    assert round_market_price(3_456.6, "jp") == 3_457
    assert round_market_price(10.555, None) == 10.555
    assert round_market_price("N/A", "kr") == "N/A"
    assert round_market_price(True, "kr") is True


def test_price_market_and_rules():
    assert price_market("000660.KS") == "kr"
    assert price_market("7203.T") == "jp"
    assert price_market("600519") is None and price_market("AAPL") is None
    assert price_precision_rule(None, True) == "to two decimals"
    assert price_precision_rule(None, False) == "精确到分"
    assert "KRX tick size" in price_precision_rule("kr", True)


def _prompt(code: str, language: str) -> str:
    context = copy.deepcopy(_rich_context())
    context["code"] = code
    context["today"].update({"close": 1_183_000.0, "ma5": 1_152_200.0, "ma10": 1_177_200.0})
    context["realtime"]["price"] = 1_183_400.0
    fake_cfg = SimpleNamespace(news_max_age_days=3, news_strategy_profile="short")
    with patch("src.analyzer.get_config", return_value=fake_cfg):
        return _make_analyzer(legacy=True)._format_prompt(context, "SK hynix", report_language=language)


def test_kr_prompt_uses_tick_rounded_prices_and_whole_won_rule():
    prompt = _prompt("000660.KS", "ko")
    assert "| MA5 | 1152000 |" in prompt and "| MA10 | 1177000 |" in prompt
    assert "| Current Price | 1183000 |" in prompt
    assert "1152200" not in prompt
    assert "KRW whole numbers with no decimals" in prompt
    assert "to two decimals" not in prompt


def test_cn_prompt_keeps_two_decimal_rule():
    prompt = _prompt("600519", "zh")
    assert "目标价（精确到分）" in prompt
    assert "| MA5 | 1152200.0 |" in prompt
