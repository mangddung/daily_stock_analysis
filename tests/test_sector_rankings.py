# -*- coding: utf-8 -*-
"""Offline tests for non-A-share sector rankings (yfinance / TWSE mocked)."""

import sys
import types
from unittest.mock import MagicMock, patch

import pandas as pd

from data_provider import sector_rankings as sr
from src.config import Config
from src.market_analyzer import MarketAnalyzer, MarketOverview


def _fake_yf(closes: dict) -> types.SimpleNamespace:
    frame = pd.concat({"Close": pd.DataFrame(closes)}, axis=1)
    return types.SimpleNamespace(download=MagicMock(return_value=frame))


def test_yfinance_proxy_rankings_split_without_overlap():
    proxies = [("^HSNF", "金融"), ("^HSNU", "公用事業"), ("^HSNP", "地產"), ("^HSNC", "工商業")]
    fake = _fake_yf({"^HSNF": [100, 101], "^HSNU": [100, 99], "^HSNP": [100, 102], "^HSNC": [100, 98]})
    with patch.dict(sr.SECTOR_PROXIES, {"hk": proxies}), patch.dict(sys.modules, {"yfinance": fake}):
        top, bottom = sr.get_region_sector_rankings("hk", 5)
    assert top == [{"name": "地產", "change_pct": 2.0}, {"name": "金融", "change_pct": 1.0}]
    assert bottom == [{"name": "工商業", "change_pct": -2.0}, {"name": "公用事業", "change_pct": -1.0}]


def test_etf_proxy_names_carry_ticker():
    fake = _fake_yf({"XLK": [200, 210], "XLE": [100, 90]})
    with patch.dict(sr.SECTOR_PROXIES, {"us": [("XLK", "Technology"), ("XLE", "Energy")]}), \
            patch.dict(sys.modules, {"yfinance": fake}):
        top, bottom = sr.get_region_sector_rankings("us", 5)
    assert top == [{"name": "Technology (XLK)", "change_pct": 5.0}]
    assert bottom == [{"name": "Energy (XLE)", "change_pct": -10.0}]


def test_twse_rows_signed_and_composites_skipped():
    payload = [
        {"指數": "半導體類指數", "漲跌": "+", "漲跌百分比": "0.64"},
        {"指數": "塑膠類指數", "漲跌": "-", "漲跌百分比": "3.26"},
        {"指數": "造紙類指數", "漲跌": "-", "漲跌百分比": "--"},
        {"指數": "電子工業類指數", "漲跌": "+", "漲跌百分比": "0.88"},  # composite parent
        {"指數": "臺灣50指數", "漲跌": "+", "漲跌百分比": "1.00"},  # not a sector index
    ]
    resp = MagicMock(**{"json.return_value": payload})
    with patch.object(sr.requests, "get", return_value=resp):
        top, bottom = sr.get_region_sector_rankings("tw", 5)
    assert top == [{"name": "半導體", "change_pct": 0.64}]
    assert bottom == [{"name": "塑膠", "change_pct": -3.26}]


def test_failures_and_unknown_regions_fail_open():
    with patch.object(sr.requests, "get", side_effect=RuntimeError("down")):
        assert sr.get_region_sector_rankings("tw") == ([], [])
    assert sr.get_region_sector_rankings("cn") == ([], [])


def test_market_analyzer_uses_region_source_and_gates_prompt_on_data():
    with patch("src.market_analyzer.DataFetcherManager") as manager:
        analyzer = MarketAnalyzer(region="kr", config=Config(report_language="en"))
    overview = MarketOverview(date="2026-11-19")
    rows = ([{"name": "IT (139260)", "change_pct": 2.94}], [{"name": "금융 (139270)", "change_pct": -1.09}])
    with patch("src.market_analyzer.get_region_sector_rankings", return_value=rows) as source:
        analyzer._get_sector_rankings(overview)
    source.assert_called_once_with("kr", 5)
    manager.return_value.get_sector_rankings.assert_not_called()
    assert overview.top_sectors == rows[0]

    with_data = analyzer._build_review_prompt(overview, [])
    assert "IT (139260)" in with_data and "Sector Highlights" in with_data
    assert "Sector/theme ranking data is not available" not in with_data

    empty = analyzer._build_review_prompt(MarketOverview(date="2026-11-19"), [])
    assert "Sector Highlights" not in empty
    assert "Sector/theme ranking data is not available" in empty
