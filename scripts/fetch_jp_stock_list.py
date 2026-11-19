#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild scripts/stock_index_seeds/stock_list_jp.csv from JPX's listed-issue files.

Source: JPX "東証上場銘柄一覧" (data_j.xlsx) and its English edition (data_e.xlsx),
published monthly. Both carry the same codes, so each row gets the official
Japanese name (display name) and the official English name (``enname`` + alias).

Only Prime/Standard/Growth stocks are kept (ETF/ETN, REIT, PRO Market and
investment units are skipped). Codes that are not 4 digits (e.g. ``130A``) are
skipped: the app's JP symbol rules only accept digit bases. Existing seed rows are
merged by code so their aliases and previous display names stay searchable.

Usage:
    python scripts/fetch_jp_stock_list.py            # write the seed CSV
    python scripts/fetch_jp_stock_list.py --test     # fetch and report only
Then rebuild only the JP rows of the web index:
    python scripts/generate_index_from_csv.py --seed-market JP
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List

import requests

from fetch_kr_stock_list import load_existing_seed, merge_aliases, write_seed

SEED_PATH = Path(__file__).parent / "stock_index_seeds" / "stock_list_jp.csv"
JPX_BASE = "https://www.jpx.co.jp"
JPX_PAGES = {
    "ja": "/markets/statistics-equities/misc/01.html",
    "en": "/english/markets/statistics-equities/misc/01.html",
}
STOCK_SEGMENT_RE = re.compile(r"^(プライム|スタンダード|グロース)（(内国|外国)株式）$")
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_listing(lang: str) -> "pandas.DataFrame":
    """Download the current data_{j,e}.xlsx linked from the JPX page (file path changes over time)."""
    import pandas as pd

    page = requests.get(JPX_BASE + JPX_PAGES[lang], headers=HEADERS, timeout=30)
    page.raise_for_status()
    name = "data_j" if lang == "ja" else "data_e"
    match = re.search(rf'href="([^"]+/{name}\.xlsx?)"', page.text)
    if not match:
        raise RuntimeError(f"JPX {lang} page has no {name}.xlsx link")
    resp = requests.get(JPX_BASE + match.group(1), headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return pd.read_excel(io.BytesIO(resp.content), dtype=str)


def build_rows(ja_rows: List[Dict[str, str]], en_names: Dict[str, str],
               existing: Dict[str, Dict[str, str]]) -> List[Dict[str, str]]:
    rows = []
    for item in ja_rows:
        code = (item["code"] or "").strip()
        name = unicodedata.normalize("NFKC", item["name"] or "").strip()
        if not (re.fullmatch(r"\d{4}", code) and name and STOCK_SEGMENT_RE.match(item["segment"] or "")):
            continue
        old = existing.get(code, {})
        enname = (en_names.get(code) or old.get("enname") or "").strip()
        ts_code = f"{code}.T"
        rows.append({"ts_code": ts_code, "symbol": ts_code, "name": name,
                     "enname": enname, "aliases": merge_aliases(name, old, enname)})
    rows.sort(key=lambda row: row["ts_code"])
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the JP stock seed from JPX listed-issue files")
    parser.add_argument("--test", action="store_true", help="fetch and report without writing")
    args = parser.parse_args()

    ja = fetch_listing("ja")
    en = fetch_listing("en")
    ja_rows = [{"code": r["コード"], "name": r["銘柄名"], "segment": r["市場・商品区分"]} for _, r in ja.iterrows()]
    en_names = {str(r["Local Code"]).strip(): str(r["Name (English)"]).strip() for _, r in en.iterrows()}
    print(f"JPX listings: {len(ja_rows)} (ja), {len(en_names)} (en)")

    rows = build_rows(ja_rows, en_names, load_existing_seed(SEED_PATH))
    print(f"Seed rows: {len(rows)} (Prime/Standard/Growth, 4-digit codes)")
    if len(rows) < 1000:
        print("[Error] Suspiciously few rows; refusing to overwrite the seed")
        return 1
    if args.test:
        return 0
    write_seed(SEED_PATH, rows)
    print(f"Wrote {SEED_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
