# -*- coding: utf-8 -*-
"""Sector rankings for non-A-share market reviews (A-shares keep DataFetcherManager).

Free sources only:
- us / jp / kr: sector ETFs via yfinance (SPDR Select Sector, NEXT FUNDS TOPIX-17,
  TIGER KOSPI 200 sector series) — ETF daily change is a proxy for the sector index.
- hk: Hang Seng Index sub-indices (Finance / Utilities / Properties / Commerce & Industry) via yfinance.
- tw: TWSE OpenAPI MI_INDEX sector indices (official, no key; previous trading day).

Rows match the A-share contract: ``{"name": str, "change_pct": float}``.
Everything is fail-open: errors return ``([], [])``.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import requests

logger = logging.getLogger(__name__)

TIMEOUT = 20
TWSE_MI_INDEX_URL = "https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX"
# TWSE parent/composite categories that would double-count their children.
_TWSE_COMPOSITES = {"水泥窯製", "塑膠化工", "機電", "化學生技醫療", "電子工業"}

# (ticker, display name). Names are in the market's own language, ticker kept for transparency.
SECTOR_PROXIES: Dict[str, List[Tuple[str, str]]] = {
    "us": [
        ("XLK", "Technology"), ("XLF", "Financials"), ("XLV", "Health Care"),
        ("XLY", "Consumer Discretionary"), ("XLP", "Consumer Staples"), ("XLE", "Energy"),
        ("XLI", "Industrials"), ("XLB", "Materials"), ("XLU", "Utilities"),
        ("XLRE", "Real Estate"), ("XLC", "Communication Services"),
    ],
    "jp": [
        ("1617.T", "食品"), ("1618.T", "エネルギー資源"), ("1619.T", "建設・資材"),
        ("1620.T", "素材・化学"), ("1621.T", "医薬品"), ("1622.T", "自動車・輸送機"),
        ("1623.T", "鉄鋼・非鉄"), ("1624.T", "機械"), ("1625.T", "電機・精密"),
        ("1626.T", "情報通信・サービスその他"), ("1627.T", "電力・ガス"), ("1628.T", "運輸・物流"),
        ("1629.T", "商社・卸売"), ("1630.T", "小売"), ("1631.T", "銀行"),
        ("1632.T", "金融(除く銀行)"), ("1633.T", "不動産"),
    ],
    "kr": [
        ("139260.KS", "IT"), ("139270.KS", "금융"), ("139250.KS", "에너지·화학"),
        ("139240.KS", "철강·소재"), ("139230.KS", "중공업"), ("139220.KS", "건설"),
        ("139290.KS", "경기소비재"), ("227560.KS", "생활소비재"), ("227550.KS", "산업재"),
        ("227540.KS", "헬스케어"),
    ],
    "hk": [
        ("^HSNF", "金融"), ("^HSNU", "公用事業"), ("^HSNP", "地產"), ("^HSNC", "工商業"),
    ],
}


def _split(rows: List[Dict], n: int) -> Tuple[List[Dict], List[Dict]]:
    """Top-n leaders and bottom-n laggards without overlap for small sector sets."""
    rows = sorted(rows, key=lambda row: row["change_pct"], reverse=True)
    k = min(n, len(rows) // 2)
    return rows[:k], list(reversed(rows[-k:])) if k else []


def _yfinance_rows(proxies: List[Tuple[str, str]]) -> List[Dict]:
    import yfinance as yf

    tickers = [ticker for ticker, _ in proxies]
    df = yf.download(tickers, period="7d", interval="1d", progress=False, auto_adjust=False, threads=True)
    close = df["Close"]
    rows = []
    for ticker, name in proxies:
        if ticker not in close:
            continue
        series = close[ticker].dropna()
        if len(series) < 2 or not series.iloc[-2]:
            continue
        change = (float(series.iloc[-1]) / float(series.iloc[-2]) - 1) * 100
        label = name if ticker.startswith("^") else f"{name} ({ticker.split('.')[0]})"
        rows.append({"name": label, "change_pct": round(change, 2)})
    return rows


def _twse_rows() -> List[Dict]:
    resp = requests.get(TWSE_MI_INDEX_URL, timeout=TIMEOUT)
    resp.raise_for_status()
    rows = []
    for item in resp.json():
        title = str(item.get("指數") or "")
        if not title.endswith("類指數"):
            continue
        name = title[: -len("類指數")]
        if name in _TWSE_COMPOSITES:
            continue
        raw = str(item.get("漲跌百分比") or "").strip()
        try:
            pct = 0.0 if raw in ("", "--") else float(raw)
        except ValueError:
            continue
        if str(item.get("漲跌") or "").strip() == "-":
            pct = -abs(pct)
        rows.append({"name": name, "change_pct": round(pct, 2)})
    return rows


def get_region_sector_rankings(region: str, n: int = 5) -> Tuple[List[Dict], List[Dict]]:
    """(leaders, laggards) for us/hk/jp/kr/tw; ``([], [])`` when unsupported or on error."""
    region = (region or "").lower()
    try:
        if region == "tw":
            rows = _twse_rows()
        elif region in SECTOR_PROXIES:
            rows = _yfinance_rows(SECTOR_PROXIES[region])
        else:
            return [], []
    except Exception as exc:
        logger.warning("[sector-rankings] %s failed: %s", region, exc)
        return [], []
    return _split(rows, n)
