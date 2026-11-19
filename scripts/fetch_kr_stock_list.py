#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild scripts/stock_index_seeds/stock_list_kr.csv from official listings.

Sources:
- KIND (kind.krx.co.kr) listed-company download: Korean name, market, 6-digit code.
  KOSPI -> ``.KS``, KOSDAQ -> ``.KQ``. KONEX is skipped (no verified Yahoo suffix).
- OpenDART corpCode.xml (optional, needs DART_API_KEY): official English names.

Existing seed rows are merged by code so their English names and aliases (including
the previous Chinese display names) keep working as search aliases.

Codes that are not 6 digits (e.g. ``0220W0``) are skipped: the app's KR symbol
rules only accept 6-digit bases. Preferred shares and ETFs are not in KIND's list.

Usage:
    python scripts/fetch_kr_stock_list.py            # write the seed CSV
    python scripts/fetch_kr_stock_list.py --test     # fetch and report only
Then rebuild only the KR rows of the web index:
    python scripts/generate_index_from_csv.py --seed-market KR
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, List

import requests

SEED_PATH = Path(__file__).parent / "stock_index_seeds" / "stock_list_kr.csv"
KIND_URL = "https://kind.krx.co.kr/corpgeneral/corpList.do"
KIND_MARKETS = {"stockMkt": "KS", "kosdaqMkt": "KQ"}
DART_CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
FIELDS = ["ts_code", "symbol", "name", "enname", "aliases"]


def fetch_kind(market_type: str) -> List[Dict[str, str]]:
    import pandas as pd

    resp = requests.get(
        KIND_URL,
        params={"method": "download", "marketType": market_type},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    resp.raise_for_status()
    html = resp.content.decode("euc-kr", errors="ignore")
    df = pd.read_html(io.StringIO(html), converters={"종목코드": str})[0]
    return [
        {"code": str(row["종목코드"]).strip(), "name": str(row["회사명"]).strip()}
        for _, row in df.iterrows()
    ]


def fetch_dart_english_names(api_key: str) -> Dict[str, str]:
    try:
        resp = requests.get(DART_CORP_CODE_URL, params={"crtfc_key": api_key}, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as exc:
        # Do not print the exception: its URL carries the API key.
        print(f"[Warning] OpenDART corpCode download failed ({type(exc).__name__}); English names skipped")
        return {}
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml_text = zf.read(zf.namelist()[0]).decode("utf-8", errors="ignore")
    names = {}
    for block in re.findall(r"<list>(.*?)</list>", xml_text, re.S):
        stock = re.search(r"<stock_code>\s*(\d{6})\s*</stock_code>", block)
        eng = re.search(r"<corp_eng_name>\s*(.*?)\s*</corp_eng_name>", block, re.S)
        if stock and eng and eng.group(1):
            names[stock.group(1)] = eng.group(1)
    return names


def load_existing_seed(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {row["ts_code"].split(".")[0]: row for row in csv.DictReader(f)}


def merge_aliases(name: str, old: Dict[str, str], enname: str) -> str:
    """Old aliases + old display name + English name, deduped, excluding the new name.

    The index generator splits aliases on commas too, so the English-name alias
    drops them ("KYOKUYO CO.,LTD." -> "KYOKUYO CO. LTD."); ``enname`` keeps the original.
    """
    en_alias = re.sub(r"\s*[,，;、]\s*", " ", enname).strip()
    aliases: List[str] = []
    for alias in (old.get("aliases") or "").split("|") + [old.get("name") or "", en_alias]:
        alias = alias.strip()
        if alias and alias != name and alias not in aliases:
            aliases.append(alias)
    return "|".join(aliases)


def write_seed(path: Path, rows: List[Dict[str, str]]) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def build_rows(
    listings: Dict[str, List[Dict[str, str]]],
    existing: Dict[str, Dict[str, str]],
    english: Dict[str, str],
) -> List[Dict[str, str]]:
    """Merge KIND listings with existing seed rows and DART English names."""
    rows = []
    for market_type, suffix in KIND_MARKETS.items():
        for item in listings.get(market_type, []):
            code, name = item["code"], item["name"]
            if not (re.fullmatch(r"\d{6}", code) and name):
                continue
            old = existing.get(code, {})
            enname = (old.get("enname") or english.get(code) or "").strip()
            ts_code = f"{code}.{suffix}"
            rows.append({"ts_code": ts_code, "symbol": ts_code, "name": name,
                         "enname": enname, "aliases": merge_aliases(name, old, enname)})
    rows.sort(key=lambda row: row["ts_code"])
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the KR stock seed from KIND (+ OpenDART English names)")
    parser.add_argument("--test", action="store_true", help="fetch and report without writing")
    args = parser.parse_args()

    listings = {market_type: fetch_kind(market_type) for market_type in KIND_MARKETS}
    for market_type, items in listings.items():
        print(f"KIND {market_type}: {len(items)} companies")

    api_key = os.getenv("DART_API_KEY", "").strip()
    english = fetch_dart_english_names(api_key) if api_key else {}
    print(f"OpenDART English names: {len(english)}" if api_key else "DART_API_KEY not set: English names only from existing seed")

    rows = build_rows(listings, load_existing_seed(SEED_PATH), english)
    skipped = sum(len(items) for items in listings.values()) - len(rows)
    print(f"Seed rows: {len(rows)} (skipped {skipped} non-6-digit codes)")
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
