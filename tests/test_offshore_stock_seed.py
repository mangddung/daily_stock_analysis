# -*- coding: utf-8 -*-
"""Offline tests for the KR/JP seed builders and the --seed-market index merge."""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fetch_jp_stock_list as jp  # noqa: E402
import fetch_kr_stock_list as kr  # noqa: E402
import generate_index_from_csv as gen  # noqa: E402


def test_jp_build_rows_keeps_stock_segments_and_official_names():
    ja_rows = [
        {"code": "7203", "name": "トヨタ自動車", "segment": "プライム（内国株式）"},
        {"code": "1306", "name": "ＮＥＸＴ　ＦＵＮＤＳ", "segment": "ETF・ETN"},
        {"code": "130A", "name": "新規", "segment": "グロース（内国株式）"},
        {"code": "1301", "name": "極洋", "segment": "スタンダード（外国株式）"},
    ]
    en_names = {"7203": "TOYOTA MOTOR CORPORATION", "1301": "KYOKUYO CO.,LTD."}
    existing = {"7203": {"ts_code": "7203.T", "name": "丰田汽车", "enname": "Toyota Motor Corporation",
                         "aliases": "Toyota|トヨタ"}}
    rows = jp.build_rows(ja_rows, en_names, existing)

    assert [row["ts_code"] for row in rows] == ["1301.T", "7203.T"]  # ETF and alphanumeric code dropped
    toyota = rows[1]
    assert toyota["name"] == "トヨタ自動車"
    assert toyota["enname"] == "TOYOTA MOTOR CORPORATION"  # JPX official English wins over old seed
    assert toyota["aliases"].split("|") == ["Toyota", "トヨタ", "丰田汽车", "TOYOTA MOTOR CORPORATION"]
    # Generator splits aliases on commas: alias drops them, enname keeps the official spelling.
    assert rows[0]["enname"] == "KYOKUYO CO.,LTD."
    assert gen.parse_aliases({"aliases": rows[0]["aliases"]}) == ["KYOKUYO CO. LTD."]


def test_build_rows_merges_existing_aliases_and_skips_bad_codes():
    listings = {
        "stockMkt": [{"code": "000660", "name": "SK하이닉스"}, {"code": "0220W0", "name": "신규"}],
        "kosdaqMkt": [{"code": "247540", "name": "에코프로비엠"}],
    }
    existing = {"000660": {"ts_code": "000660.KS", "name": "SK海力士", "enname": "SK hynix Inc.",
                           "aliases": "SK Hynix|하이닉스"}}
    rows = kr.build_rows(listings, existing, {"247540": "Ecopro BM Co. Ltd."})

    assert [row["ts_code"] for row in rows] == ["000660.KS", "247540.KQ"]
    assert rows[0]["name"] == "SK하이닉스"
    assert rows[0]["aliases"].split("|") == ["SK Hynix", "하이닉스", "SK海力士", "SK hynix Inc."]
    assert rows[1]["enname"] == "Ecopro BM Co. Ltd."
    assert rows[1]["aliases"] == "Ecopro BM Co. Ltd."


def test_seed_market_only_replaces_only_kr_rows_in_place(tmp_path):
    output = tmp_path / "stocks.index.json"
    payload = [
        ["600519.SH", "600519", "贵州茅台", "guizhoumaotai", "gzmt", ["茅台"], "CN", "stock", True, 100],
        ["005930.KS", "005930.KS", "三星电子", "sanxingdianzi", "sxdz", [], "KR", "stock", True, 100],
        ["AAPL", "AAPL", "Apple Inc.", "Apple Inc.", "Apple Inc.", [], "US", "stock", True, 100],
    ]
    output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    seed = tmp_path / "stock_list_kr.csv"
    with open(seed, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=kr.FIELDS)
        writer.writeheader()
        writer.writerow({"ts_code": "005930.KS", "symbol": "005930.KS", "name": "삼성전자",
                         "enname": "", "aliases": "Samsung|三星电子"})
        writer.writerow({"ts_code": "247540.KQ", "symbol": "247540.KQ", "name": "에코프로비엠",
                         "enname": "", "aliases": ""})

    merged = gen.run_seed_market_only(output, "KR", seed)

    assert [item[0] for item in merged] == ["600519.SH", "005930.KS", "247540.KQ", "AAPL"]
    assert merged[1][2] == "삼성전자" and merged[1][5] == ["Samsung", "三星电子"]
    assert json.loads(output.read_text(encoding="utf-8")) == merged


def test_seed_market_only_writes_optional_name_en_field(tmp_path):
    output = tmp_path / "stocks.index.json"
    base = ["600519.SH", "600519", "贵州茅台", "guizhoumaotai", "gzmt", [], "CN", "stock", True, 100]
    output.write_text(json.dumps([base], ensure_ascii=False), encoding="utf-8")
    seed = tmp_path / "stock_list_jp.csv"
    with open(seed, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=kr.FIELDS)
        writer.writeheader()
        writer.writerow({"ts_code": "7203.T", "symbol": "7203.T", "name": "トヨタ自動車",
                         "enname": "TOYOTA MOTOR CORPORATION", "aliases": ""})
        writer.writerow({"ts_code": "1301.T", "symbol": "1301.T", "name": "極洋", "enname": "", "aliases": ""})

    merged = gen.run_seed_market_only(output, "JP", seed)

    assert merged[0] == base  # untouched rows stay 10 fields
    by_code = {item[0]: item for item in merged}
    assert len(by_code["7203.T"]) == 11 and by_code["7203.T"][10] == "TOYOTA MOTOR CORPORATION"
    assert len(by_code["1301.T"]) == 10  # no English name -> field omitted


def test_validator_accepts_optional_name_en_and_rejects_bad_values():
    import pytest
    from src.services.stock_index_remote_service import validate_stock_index_payload

    row = ["7203.T", "7203.T", "トヨタ自動車", None, None, [], "JP", "stock", True, 100]
    validate_stock_index_payload([row, row + ["TOYOTA MOTOR CORPORATION"], row + [None]], min_items=0)
    with pytest.raises(ValueError):
        validate_stock_index_payload([row + [""]], min_items=0)
