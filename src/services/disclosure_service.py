# -*- coding: utf-8 -*-
"""
Regulatory filing (disclosure) context for the analysis prompt.

Sources (all free, official or already-used):
- KR: OpenDART (requires DART_API_KEY)
- US: SEC EDGAR (requires SEC_USER_AGENT with a contact, per SEC fair-access policy)
- CN: cninfo via akshare list + static.cninfo.com.cn PDF (first pages, pypdf)

Event filings are summarized once by the configured LLM and the summary is
cached on disk under data/cache/disclosures (filings never change after
publication). Periodic reports (10-K/10-Q, 사업/분기보고서, 年报/季报) are listed by
title only because their opening pages are boilerplate.

Upcoming (scheduled) disclosures are appended after the recent filings, keyless:
- KR: KIND IR schedule (기업설명회) + statutory periodic-report deadlines
- JP: JPX 決算発表予定日 Excel lists
- CN: Eastmoney 预约披露时间 (same data as akshare.stock_yysj_em, one stock per request)
- HK: HKEXnews board meeting notifications
- US: yfinance calendar (Yahoo earnings date)

Everything is fail-open: any error yields an empty context, never an exception.
Every source call is recorded as a provider run (data_type "disclosure"): it shows in the run
flow, and a failure (including a market-wide list that parses to 0 rows, i.e. a layout change)
raises the Web shell runtime alert (kind "disclosure"); its next success clears it.
"""

from __future__ import annotations

import html
import io
import json
import logging
import os
import re
import threading
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional

import requests
from openpyxl import load_workbook
from pypdf import PdfReader

from data_provider.akshare_fetcher import is_hk_stock_code
from data_provider.us_index_mapping import is_us_stock_code
from src.services.market_symbol_utils import get_suffix_market, split_suffix_symbol
from src.services.run_diagnostics import record_provider_run, record_provider_run_started

logger = logging.getLogger(__name__)
# pypdf warns per font it cannot fully decode (e.g. "fontTools is required"); keep logs readable.
logging.getLogger("pypdf").setLevel(logging.ERROR)

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "disclosures"
MAX_ITEMS = 5  # per stock per analysis; bounds LLM summary calls
BODY_CHARS = 30000  # default filing text sent to the summarizer (DISCLOSURE_BODY_CHARS)
# Bump when what feeds the summarizer changes, so cached summaries are rebuilt once.
SUMMARY_CACHE_VERSION = 2
MAPPING_TTL = timedelta(days=7)
TIMEOUT = 10

DART_BASE = "https://opendart.fss.or.kr/api"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SEC_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
SEC_EVENT_FORMS = {"8-K", "6-K"}
SEC_PERIODIC_FORMS = {"10-K", "10-Q", "20-F", "40-F"}
DART_PERIODIC_RE = re.compile(r"사업보고서|반기보고서|분기보고서")
CNINFO_PDF_URL = "https://static.cninfo.com.cn/finalpage/{date}/{aid}.PDF"
CNINFO_PERIODIC_RE = re.compile(r"(年度|季度)报告(?!摘要)")
PDF_MAX_BYTES = 30 * 1024 * 1024  # annual-report PDFs run to tens of MB
PDF_MAX_PAGES = 100  # read pages until the text budget is met; cap bounds work on hostile PDFs
# The latest periodic report is included whatever the news window (they come out quarterly).
PERIODIC_LOOKBACK_DAYS = 150
PERIODIC_SECTION_PAGES = 40  # PDF pages read per bookmarked section
# Sections pulled from periodic reports, in priority order. Titles are fixed by the regulators'
# report templates, so plain matching on the documents' own structure beats asking an LLM.
DART_PERIODIC_SECTIONS = (
    "요약재무정보", "재무상태 및 영업실적", "매출 및 수주상황", "사업의 개요", "주요 제품 및 서비스", "기타 참고사항",
)
CNINFO_PERIODIC_SECTIONS = (
    r"主要会计数据和财务指标", r"发生变动的情况、原因", r"管理层讨论与分析|经营情况讨论与分析",
)
MIN_SECTION_CHARS = 100  # e.g. "분기보고서에는 본 항목을 기재하지 아니하였습니다"
# 10-K Item 7 / 10-Q Item 2 MD&A, 20-F Item 5; ends at the next item.
SEC_MDA_START_RE = re.compile(
    r"Item\s*(?:7|2)\s*[.:]?\s*Management[’'`]?s\s+Discussion|Item\s*5\s*[.:]?\s*Operating\s+and\s+Financial\s+Review",
    re.I,
)
SEC_MDA_END_RE = re.compile(
    r"Item\s*(?:7A|3)\s*[.:]?\s*Quantitative|Item\s*8\s*[.:]?\s*Financial\s+Statements|Item\s*6\s*[.:]?\s*Directors",
    re.I,
)
# 8-K/6-K primary documents usually only point at EX-99.x exhibits (press release, CFO commentary),
# which carry the actual numbers.
SEC_EXHIBIT_RE = re.compile(r"EX-99(\.\d+)?$")
SEC_MAX_EXHIBITS = 3
# KR 영업(잠정)실적 / 매출액·손익구조 변동, CN 业绩预告/快报, SEC 8-K Item 2.02 (via items in the title).
EARNINGS_TITLE_RE = re.compile(r"영업\(잠정\)실적|잠정실적|손익구조|业绩预告|业绩快报|业绩预增|业绩预减|2\.02")

UPCOMING_DAYS = 90  # KIND IR query window; other sources only publish near-term dates
SCHEDULE_TTL = timedelta(hours=12)  # market-wide schedule lists change daily
KIND_IR_URL = "https://kind.krx.co.kr/corpgeneral/irschedule.do"
JPX_SCHEDULE_PAGE = "https://www.jpx.co.jp/listing/event-schedules/financial-announcement/index.html"
JPX_BASE = "https://www.jpx.co.jp"
HKEX_BMN_URLS = ("https://www3.hkexnews.hk/reports/bmn/ebmn.htm", "https://www3.hkexnews.hk/reports/bmn/ebmngem.htm")
EASTMONEY_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
BROWSER_UA = {"User-Agent": "Mozilla/5.0"}
XLSX_MAX_BYTES = 10 * 1024 * 1024
# (quarter end month, day, days allowed, report) under the Korean Capital Markets Act, Dec FYE.
KR_PERIODIC_DEADLINES = (
    (3, 31, 45, "Q1 report (분기보고서)"),
    (6, 30, 45, "half-year report (반기보고서)"),
    (9, 30, 45, "Q3 report (분기보고서)"),
    (12, 31, 90, "annual report (사업보고서)"),
)

SUMMARY_PROMPT = (
    "Summarize the key facts of this regulatory filing in 2-3 sentences. "
    "Keep concrete numbers, amounts, dates and counterparties. "
    "Write the summary in {language}, keeping company and product names as published. "
    "Output only the summary.\n\n"
    "Title: {title}\n\n{body}"
)
PERIODIC_SUMMARY_PROMPT = (
    "Summarize these sections of a periodic report in 3-5 sentences: headline revenue, operating "
    "profit and net income with period-over-period changes, the business drivers behind them, and any "
    "outlook or risks management states. Keep concrete numbers and periods. "
    "Write the summary in {language}, keeping company and product names as published. "
    "Output only the summary.\n\n"
    "Title: {title}\n\n{body}"
)
SUMMARY_LANGUAGES = {"zh": "Simplified Chinese", "en": "English", "ko": "Korean"}
SUMMARY_ATTEMPTS = 2  # an empty/failed LLM reply is retried once

_mapping_lock = threading.Lock()


def _html_to_text(raw: str) -> str:
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _get(url: str, *, params: Optional[dict] = None, headers: Optional[dict] = None,
         timeout: int = TIMEOUT, max_bytes: Optional[int] = None, data: Optional[dict] = None):
    """GET (POST when ``data`` is given) that never leaks query strings (API keys) into exceptions.

    With ``max_bytes`` the body is streamed and returned as bytes, aborting past the cap.
    """
    try:
        if data is not None:
            resp = requests.post(url, data=data, headers=headers, timeout=timeout, stream=max_bytes is not None)
        else:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout, stream=max_bytes is not None)
        resp.raise_for_status()
        if max_bytes is None:
            return resp
        buf = bytearray()
        for chunk in resp.iter_content(64 * 1024):
            buf.extend(chunk)
            if len(buf) > max_bytes:
                resp.close()
                raise RuntimeError(f"body exceeds {max_bytes} bytes url={url.split('?')[0]}")
        return bytes(buf)
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        raise RuntimeError(f"{type(exc).__name__} status={status} url={url.split('?')[0]}") from None


_READABLE_RE = re.compile(r"[一-鿿　-〿＀-￯\x20-\x7e]")


def _looks_garbled(text: str) -> bool:
    """True when extracted PDF text is mostly outside CJK/ASCII (broken font encoding)."""
    if not text:
        return True
    return len(_READABLE_RE.findall(text)) / len(text) < 0.8


def _record(source: str, operation: str, *, started: Optional[float] = None, exc: Optional[Exception] = None,
            count: Optional[int] = None, cache_hit: Optional[bool] = None) -> None:
    """Report one source call to run diagnostics: a run-flow node plus the runtime alert."""
    record_provider_run(
        data_type="disclosure", provider=source, operation=operation, success=exc is None,
        latency_ms=int((time.monotonic() - started) * 1000) if started is not None else None,
        error_type=type(exc).__name__ if exc else None, error_message=str(exc) if exc else None,
        cache_hit=cache_hit, record_count=count,
    )


def _tracked(source: str, operation: str, fetch: Callable, *args):
    """Run one per-stock source call and report it (run flow + runtime alert)."""
    record_provider_run_started(data_type="disclosure", provider=source, operation=operation)
    started = time.monotonic()
    try:
        result = fetch(*args)
    except Exception as exc:
        _record(source, operation, started=started, exc=exc)
        raise
    _record(source, operation, started=started, count=len(result) if isinstance(result, list) else None)
    return result


def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


class DisclosureService:
    def __init__(
        self,
        *,
        dart_api_key: Optional[str],
        sec_user_agent: Optional[str],
        summarize: Callable[[str], Optional[str]],
        cache_dir: Path = CACHE_DIR,
        body_chars: Optional[int] = None,
        report_language: Optional[str] = None,
    ):
        self._dart_key = (dart_api_key or "").strip() or None
        self._sec_ua = (sec_user_agent or "").strip() or None
        self._summarize = summarize
        self._cache_dir = cache_dir
        self._body_chars = body_chars or BODY_CHARS
        self._language = report_language if report_language in SUMMARY_LANGUAGES else "zh"

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def get_disclosures(self, code: str, window_days: int) -> Dict[str, List[dict]]:
        """Recent filings ``{date, title, summary, source}`` and upcoming ``{date, title, source}``."""
        code = code.strip().upper()
        return {"recent": self._recent_items(code, window_days), "upcoming": self._upcoming_items(code)}

    def get_disclosure_context(self, code: str, window_days: int) -> str:
        """Return prompt blocks of recent filings and upcoming scheduled disclosures, or ''."""
        return format_disclosure_context(self.get_disclosures(code, window_days))

    def _recent_items(self, code: str, window_days: int) -> List[dict]:
        try:
            since = (datetime.now() - timedelta(days=max(1, window_days))).date()
            source, items = self._fetch(code, since)
        except Exception as exc:
            logger.warning("[disclosure] %s fetch failed: %s", code, exc)
            return []
        # Earnings filings first, then the periodic report (stable sort keeps date order otherwise): on
        # results day issuers file dividends/buybacks/IR notices at once, and a plain newest-first cap
        # would drop the results.
        items = sorted(items, key=lambda item: (not EARNINGS_TITLE_RE.search(item["title"]),
                                                not item.get("periodic")))
        return [
            {"date": item["date"], "title": item["title"], "summary": self._summary_for(source, item),
             "source": source}
            for item in items[:MAX_ITEMS]
        ]

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _fetch(self, code: str, since) -> tuple[str, List[dict]]:
        if get_suffix_market(code) == "kr":
            if not self._dart_key:
                return "OpenDART", []
            return "OpenDART", _tracked("OpenDART", "filings", self._dart_list, split_suffix_symbol(code)[0], since)
        if is_us_stock_code(code):
            if not self._sec_ua:
                return "SEC EDGAR", []
            return "SEC EDGAR", _tracked("SEC EDGAR", "filings", self._sec_list, code, since)
        if code.isdigit() and len(code) == 6:
            return "cninfo", _tracked("cninfo", "filings", self._cninfo_list, code, since)
        return "", []

    def _summary_for(self, source: str, item: dict) -> str:
        if not item.get("body_url"):
            return ""
        # One cached summary per filing and report language.
        path = self._cache_dir / re.sub(r"[^A-Za-z0-9_-]", "_", source) / f"{item['id']}.{self._language}.json"
        cached = _read_json(path)
        if cached and cached.get("summary") and cached.get("v") == SUMMARY_CACHE_VERSION:
            return cached["summary"]
        periodic = bool(item.get("periodic"))
        try:
            body = self._fetch_periodic_body(source, item["body_url"]) if periodic \
                else self._fetch_body(source, item["body_url"])
        except Exception as exc:
            logger.warning("[disclosure] body fetch failed %s: %s", item["id"], exc)
            _record(source, "document", exc=exc)
            return ""
        if not body:
            return ""
        prompt = (PERIODIC_SUMMARY_PROMPT if periodic else SUMMARY_PROMPT).format(
            title=item["title"], body=body[:self._body_chars], language=SUMMARY_LANGUAGES[self._language],
        )
        summary = ""
        for attempt in range(1, SUMMARY_ATTEMPTS + 1):
            try:
                summary = re.sub(r"\s+", " ", (self._summarize(prompt) or "")).strip()
            except Exception as exc:  # summarizer contract is None on failure; stay fail-open anyway
                logger.warning("[disclosure] summary call raised %s: %s", item["id"], exc)
            if summary:
                break
            logger.warning("[disclosure] empty summary for %s (attempt %d/%d)", item["id"], attempt, SUMMARY_ATTEMPTS)
        if summary:
            _write_json(path, {"title": item["title"], "date": item["date"], "summary": summary,
                               "v": SUMMARY_CACHE_VERSION})
        return summary

    def _fetch_body(self, source: str, url: str) -> str:
        if source == "OpenDART":
            resp = _get(url, params={"crtfc_key": self._dart_key})
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                parts = [zf.read(name).decode("utf-8", errors="ignore") for name in zf.namelist()]
            return _html_to_text(" ".join(parts))
        if source == "cninfo":
            reader = PdfReader(io.BytesIO(_get(url, max_bytes=PDF_MAX_BYTES)))
            text = ""
            for page in reader.pages[:PDF_MAX_PAGES]:
                text += " " + re.sub(r"\s+", " ", page.extract_text() or "")
                if len(text) >= self._body_chars:
                    break
            text = text.strip()
            # Scanned PDFs yield '' and custom-encoded fonts (e.g. H-share forms) yield mojibake;
            # both fall back to title only rather than feeding garbage to the summarizer.
            return "" if _looks_garbled(text) else text
        text = _html_to_text(_get(url, headers={"User-Agent": self._sec_ua}).text)
        return text + self._sec_exhibits_text(url, self._body_chars - len(text))

    def _fetch_periodic_body(self, source: str, url: str) -> str:
        """Standard sections of a periodic report, found through the document's own structure.

        DART: SECTION/TITLE tags; cninfo: PDF bookmarks (real page numbers, unlike the printed
        contents page); SEC: the MD&A item. Without structure, the head of the report is used.
        """
        budget = self._body_chars
        if source == "OpenDART":
            resp = _get(url, params={"crtfc_key": self._dart_key}, timeout=60)
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                docs = [zf.read(name).decode("utf-8", errors="ignore") for name in zf.namelist()]
            main = max(docs, key=lambda doc: doc.count("<TITLE"), default="")  # report, not attachments
            full = _html_to_text(main)
            # Short reports fit whole; sections only pay off once the report exceeds the budget.
            return full if len(full) <= budget else (_dart_sections(main, budget) or full[:budget])
        if source == "cninfo":
            reader = PdfReader(io.BytesIO(_get(url, max_bytes=PDF_MAX_BYTES, timeout=60)))
            # ponytail: ~2000 chars/page estimate decides "fits whole"; measure pages if it misjudges.
            text = "" if len(reader.pages) * 2000 <= budget else _pdf_bookmarked_sections(reader, budget)
            if not text:
                for page in reader.pages[:PDF_MAX_PAGES]:
                    text += " " + re.sub(r"\s+", " ", page.extract_text() or "")
                    if len(text) >= budget:
                        break
            text = text.strip()
            return "" if _looks_garbled(text) else text
        text = _html_to_text(_get(url, headers={"User-Agent": self._sec_ua}, timeout=60,
                                  max_bytes=PDF_MAX_BYTES).decode("utf-8", errors="ignore"))
        return _longest_span(text, SEC_MDA_START_RE, SEC_MDA_END_RE)[:budget] or text[:budget]

    def _sec_exhibits_text(self, primary_url: str, budget: int) -> str:
        """Text of a filing's EX-99.x exhibits; failures fall back to the primary document only."""
        if budget <= 0:
            return ""
        folder = primary_url.rsplit("/", 1)[0]
        acc = folder.rsplit("/", 1)[1]
        headers = {"User-Agent": self._sec_ua}
        try:
            index = _get(f"{folder}/{acc[:10]}-{acc[10:12]}-{acc[12:]}-index.html", headers=headers).text
        except Exception as exc:
            logger.warning("[disclosure] SEC filing index failed %s: %s", acc, exc)
            return ""
        parts: List[str] = []
        for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", index):
            cells = [_html_to_text(c) for c in re.findall(r"(?is)<td[^>]*>(.*?)</td>", row)]
            href = re.search(r'href="(/Archives/edgar/data/[^"]+)"', row)
            if len(cells) < 4 or not SEC_EXHIBIT_RE.match(cells[3]) or not href:
                continue
            try:
                parts.append(_html_to_text(_get("https://www.sec.gov" + href.group(1), headers=headers).text))
            except Exception as exc:
                logger.warning("[disclosure] SEC exhibit failed %s: %s", href.group(1), exc)
                continue
            if len(parts) >= SEC_MAX_EXHIBITS or sum(map(len, parts)) >= budget:
                break
        return (" " + " ".join(parts))[:budget] if parts else ""

    # ------------------------------------------------------------------
    # OpenDART
    # ------------------------------------------------------------------

    def _dart_list(self, stock_code: str, since) -> List[dict]:
        # Own alert key: the list call's success must not clear a failed mapping refresh.
        corp_code = self._cached_mapping("OpenDART corpCode", "dart_corp_codes.json",
                                         self._download_dart_corp_codes).get(stock_code)
        if not corp_code:
            return []
        lookback = date.today() - timedelta(days=PERIODIC_LOOKBACK_DAYS)
        # Window filings, plus periodic-only (pblntf_ty A) over the lookback for the latest report.
        items = self._dart_rows(corp_code, since, page_count=100) + \
            self._dart_rows(corp_code, min(since, lookback), page_count=10, pblntf_ty="A")
        return _events_plus_latest_periodic(items, since)

    def _dart_rows(self, corp_code: str, bgn, **params) -> List[dict]:
        data = _get(
            f"{DART_BASE}/list.json",
            params={"crtfc_key": self._dart_key, "corp_code": corp_code, "bgn_de": bgn.strftime("%Y%m%d"), **params},
        ).json()
        if data.get("status") not in ("000", "013"):  # 013 = no data; 020 = daily quota exceeded
            raise RuntimeError(f"OpenDART list status {data.get('status')}: {data.get('message')}")
        items = []
        for row in data.get("list") or []:
            title = (row.get("report_nm") or "").strip()
            rcept_no = row.get("rcept_no") or ""
            dt = row.get("rcept_dt") or ""
            if not (title and rcept_no and len(dt) == 8):
                continue
            items.append({
                "id": rcept_no,
                "date": f"{dt[:4]}-{dt[4:6]}-{dt[6:]}",
                "title": title,
                "periodic": bool(DART_PERIODIC_RE.search(title)),
                "body_url": f"{DART_BASE}/document.xml?rcept_no={rcept_no}",
            })
        return items

    def _download_dart_corp_codes(self) -> Dict[str, str]:
        resp = _get(f"{DART_BASE}/corpCode.xml", params={"crtfc_key": self._dart_key}, timeout=60)
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            xml_text = zf.read(zf.namelist()[0]).decode("utf-8", errors="ignore")
        # Flat, fixed schema: regex avoids running an XML parser on downloaded data.
        mapping = {}
        for block in re.findall(r"<list>(.*?)</list>", xml_text, re.S):
            corp = re.search(r"<corp_code>\s*(\d+)\s*</corp_code>", block)
            stock = re.search(r"<stock_code>\s*(\d{6})\s*</stock_code>", block)
            if corp and stock:
                mapping[stock.group(1)] = corp.group(1)
        return mapping

    # ------------------------------------------------------------------
    # SEC EDGAR
    # ------------------------------------------------------------------

    def _sec_list(self, ticker: str, since) -> List[dict]:
        cik = self._cached_mapping("SEC EDGAR tickers", "sec_tickers.json",
                                   self._download_sec_tickers).get(ticker.replace(".", "-"))
        if not cik:
            return []
        resp = _get(SEC_SUBMISSIONS_URL.format(cik=int(cik)), headers={"User-Agent": self._sec_ua})
        recent = (resp.json().get("filings") or {}).get("recent") or {}
        forms = recent.get("form", [])
        lookback = (date.today() - timedelta(days=PERIODIC_LOOKBACK_DAYS)).isoformat()
        items = []
        for form, filed, acc, doc, desc, form_items in zip(
            forms,
            recent.get("filingDate", []),
            recent.get("accessionNumber", []),
            recent.get("primaryDocument", []),
            recent.get("primaryDocDescription", []),
            recent.get("items") or [""] * len(forms),
        ):
            periodic = form in SEC_PERIODIC_FORMS
            if not (periodic or form in SEC_EVENT_FORMS) or filed < (lookback if periodic else since.isoformat()):
                continue
            title = f"{form} {desc}".strip() if desc and desc != form else form
            if form_items:  # e.g. "2.02,9.01": Item 2.02 = results of operations
                title += f" (Items {form_items.replace(',', ', ')})"
            items.append({
                "id": acc,
                "date": filed,
                "title": title,
                "periodic": periodic,
                "body_url": SEC_ARCHIVE_URL.format(cik=int(cik), acc=acc.replace("-", ""), doc=doc) if doc else None,
            })
        return _events_plus_latest_periodic(items, since)

    def _download_sec_tickers(self) -> Dict[str, str]:
        resp = _get(SEC_TICKERS_URL, headers={"User-Agent": self._sec_ua}, timeout=30)
        return {str(row["ticker"]).upper(): str(row["cik_str"]) for row in resp.json().values()}

    # ------------------------------------------------------------------
    # cninfo (akshare)
    # ------------------------------------------------------------------

    def _cninfo_list(self, code: str, since) -> List[dict]:
        import akshare as ak

        lookback = date.today() - timedelta(days=PERIODIC_LOOKBACK_DAYS)
        df = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=code,
            market="沪深京",
            start_date=min(since, lookback).strftime("%Y%m%d"),  # one query covers events + latest report
            end_date=datetime.now().strftime("%Y%m%d"),
        )
        if df is None or df.empty:
            return []
        items = []
        for _, row in df.iterrows():
            title = str(row.get("公告标题") or "").strip()
            filed = str(row.get("公告时间") or "")[:10]
            aid = re.search(r"announcementId=(\d+)", str(row.get("公告链接") or ""))
            if not (title and len(filed) == 10 and aid) or "英文" in title:  # English duplicates
                continue
            items.append({
                "id": aid.group(1),
                "date": filed,
                "title": title,
                "periodic": bool(CNINFO_PERIODIC_RE.search(title)),
                "body_url": CNINFO_PDF_URL.format(date=filed, aid=aid.group(1)),
            })
        return _events_plus_latest_periodic(items, since)

    # ------------------------------------------------------------------
    # Upcoming (scheduled) disclosures
    # ------------------------------------------------------------------

    def _upcoming_items(self, code: str) -> List[dict]:
        today = date.today()
        try:
            items = self._fetch_upcoming(code, today)
        except Exception as exc:
            logger.warning("[disclosure] %s upcoming schedule failed: %s", code, exc)
            return []
        items = sorted((i for i in items if i["date"] >= today.isoformat()), key=lambda i: i["date"])
        return [{"date": i["date"], "title": i["title"], "source": i["source"]} for i in items[:MAX_ITEMS]]

    def _fetch_upcoming(self, code: str, today: date) -> List[dict]:
        market = get_suffix_market(code)
        if market == "kr":
            base = split_suffix_symbol(code)[0]
            ir = self._cached_mapping("KIND", "kind_ir_schedule.json", self._download_kind_ir, SCHEDULE_TTL)
            return ir.get(base[:5], []) + [_kr_next_periodic_deadline(today)]
        if market == "jp":
            base = split_suffix_symbol(code)[0]
            return self._cached_mapping("JPX", "jpx_earnings_schedule.json", self._download_jpx_schedule,
                                        SCHEDULE_TTL).get(base, [])
        if is_us_stock_code(code):
            return _tracked("Yahoo Finance", "schedule", self._yfinance_earnings, code)
        if code.isdigit() and len(code) == 6:
            return _tracked("Eastmoney", "schedule", self._eastmoney_appointment, code)
        if is_hk_stock_code(code):
            digits = re.sub(r"\D", "", code)
            return self._cached_mapping("HKEXnews", "hkex_board_meetings.json", self._download_hkex_bmn,
                                        SCHEDULE_TTL).get(str(int(digits)), []) if digits else []
        return []

    def _download_kind_ir(self) -> Dict[str, List[dict]]:
        today = date.today()
        text = _get(KIND_IR_URL, headers=BROWSER_UA, timeout=30, data={
            "method": "searchIRScheduleSub",
            "forward": "searchirschedule_sub",
            "currentPageSize": "3000",
            "pageIndex": "1",
            "orderMode": "4",
            "orderStat": "A",
            "fromDate": today.isoformat(),
            "toDate": (today + timedelta(days=UPCOMING_DAYS)).isoformat(),
        }).text
        mapping: Dict[str, List[dict]] = {}
        for row in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", text):
            corp = re.search(r"companysummary_open\('(\w+)'\)", row)
            title = re.search(r"fnDetailView\([^)]*\)[^>]*>(.*?)</a>", row, re.S)
            day = re.search(r"\d{4}-\d{2}-\d{2}", row)
            if not (corp and title and day):
                continue
            hour = re.search(r">\s*(\d{1,2}:\d{2})\s*<", row)
            hour = f" {hour.group(1)}" if hour else ""
            events = mapping.setdefault(corp.group(1), [])
            # Issuers often post the same event in Korean and English; keep the first.
            if any(e["date"] == day.group(0) and e["hour"] == hour for e in events):
                continue
            events.append({
                "date": day.group(0),
                "hour": hour,
                "title": f"IR (기업설명회){hour}: {_html_to_text(title.group(1))}",
                "source": "KIND",
            })
        return mapping

    def _download_jpx_schedule(self) -> Dict[str, List[dict]]:
        page = _get(JPX_SCHEDULE_PAGE, headers=BROWSER_UA).text
        links = sorted(set(re.findall(r'href="(/listing/event-schedules/financial-announcement/[^"]+\.xlsx)"', page)))
        if not links:
            raise RuntimeError("no JPX schedule files found")
        mapping: Dict[str, List[dict]] = {}
        for link in links:
            wb = load_workbook(io.BytesIO(_get(JPX_BASE + link, headers=BROWSER_UA, timeout=30,
                                                 max_bytes=XLSX_MAX_BYTES)), read_only=True)
            for row in wb.worksheets[0].iter_rows(values_only=True):
                # Columns: scheduled date, code, name, English name, FYE, industry, industry EN, kind, kind EN, ...
                if len(row) < 9 or not isinstance(row[0], datetime) or row[1] is None:
                    continue  # header rows and "未定" (undecided) dates
                fye = f" (FYE {row[4]:%Y-%m})" if isinstance(row[4], datetime) else ""
                mapping.setdefault(str(row[1]).strip(), []).append({
                    "date": row[0].date().isoformat(),
                    "title": f"Earnings announcement, {row[8] or row[7]}{fye}",
                    "source": "JPX",
                })
            wb.close()
        return mapping

    def _download_hkex_bmn(self) -> Dict[str, List[dict]]:
        mapping: Dict[str, List[dict]] = {}
        for url in HKEX_BMN_URLS:
            text = _get(url, headers=BROWSER_UA, timeout=30).text
            for row in re.findall(r"(?is)<tr>(.*?)</tr>", text):
                cells = [_html_to_text(c) for c in re.findall(r"(?is)<td[^>]*>(.*?)(?=<td|$)", row)]
                cells = [c for c in cells if c]
                if len(cells) < 4 or not re.fullmatch(r"\d{2}/\d{2}/\d{4}", cells[0]) or not cells[2].isdigit():
                    continue
                dd, mm, yyyy = cells[0].split("/")
                period = f" ({cells[4]})" if len(cells) > 4 else ""
                mapping.setdefault(str(int(cells[2])), []).append({
                    "date": f"{yyyy}-{mm}-{dd}",
                    "title": f"Board meeting: {cells[3]}{period}",
                    "source": "HKEXnews",
                })
        return mapping

    def _eastmoney_appointment(self, code: str) -> List[dict]:
        data = _get(EASTMONEY_URL, headers=BROWSER_UA, params={
            "reportName": "RPT_PUBLIC_BS_APPOIN",
            "columns": "REPORT_TYPE_NAME,FIRST_APPOINT_DATE,FIRST_CHANGE_DATE,SECOND_CHANGE_DATE,"
                       "THIRD_CHANGE_DATE,ACTUAL_PUBLISH_DATE",
            "filter": f'(SECURITY_CODE="{code}")',
            "sortColumns": "REPORT_DATE",
            "sortTypes": "-1",
            "pageSize": "2",
            "pageNumber": "1",
        }).json()
        items = []
        for row in ((data.get("result") or {}).get("data") or []):
            if row.get("ACTUAL_PUBLISH_DATE"):
                continue
            # Latest change wins over the first appointment.
            when = next((row.get(k) for k in ("THIRD_CHANGE_DATE", "SECOND_CHANGE_DATE",
                                              "FIRST_CHANGE_DATE", "FIRST_APPOINT_DATE") if row.get(k)), None)
            if when:
                items.append({
                    "date": str(when)[:10],
                    "title": f"{row.get('REPORT_TYPE_NAME') or 'Periodic report'} 预约披露",
                    "source": "Eastmoney",
                })
        return items

    def _yfinance_earnings(self, code: str) -> List[dict]:
        import yfinance as yf

        calendar = yf.Ticker(code.replace(".", "-")).calendar or {}
        return [
            {"date": d.isoformat(), "title": "Earnings release (Yahoo estimate)", "source": "Yahoo Finance"}
            for d in (calendar.get("Earnings Date") or [])[:1]
            if isinstance(d, date)
        ]

    # ------------------------------------------------------------------
    # Mapping cache (stock code -> issuer id)
    # ------------------------------------------------------------------

    def _cached_mapping(self, source: str, filename: str, download: Callable[[], dict],
                        ttl: timedelta = MAPPING_TTL) -> dict:
        path = self._cache_dir / filename
        with _mapping_lock:
            cached = _read_json(path)
            if cached:
                try:
                    fresh = datetime.now() - datetime.fromisoformat(cached["fetched_at"]) < ttl
                except (KeyError, ValueError):
                    fresh = False
                if fresh:
                    _record(source, path.stem, cache_hit=True, count=len(cached.get("map") or {}))
                    return cached.get("map") or {}
            record_provider_run_started(data_type="disclosure", provider=source, operation=path.stem)
            started = time.monotonic()
            try:
                mapping = download()
                if not mapping:  # every list here is never legitimately empty
                    raise RuntimeError("0 rows parsed (source layout changed?)")
            except Exception as exc:
                logger.warning("[disclosure] %s refresh failed: %s", filename, exc)
                _record(source, path.stem, started=started, exc=exc)
                return (cached or {}).get("map") or {}  # stale beats nothing
            _record(source, path.stem, started=started, count=len(mapping))
            _write_json(path, {"fetched_at": datetime.now().isoformat(), "map": mapping})
            return mapping


def _events_plus_latest_periodic(items: List[dict], since) -> List[dict]:
    """Event filings inside the window, plus the newest periodic report from the lookback."""
    unique = list({i["id"]: i for i in items}.values())  # the two DART queries can overlap
    events = [i for i in unique if not i["periodic"] and i["date"] >= since.isoformat()]
    latest = max((i for i in unique if i["periodic"]), key=lambda i: i["date"], default=None)
    return events + ([latest] if latest else [])


def _join_sections(sections: List[tuple], budget: int) -> str:
    """'## title' blocks sharing ``budget`` evenly, so one long section cannot crowd out the rest."""
    sections = [(title, text) for title, text in sections if len(text) >= MIN_SECTION_CHARS]
    if not sections:
        return ""
    share = max(budget // len(sections), 2000)
    return "\n\n".join(f"## {title}\n{text[:share]}" for title, text in sections)[:budget]


def _dart_sections(xml: str, budget: int) -> str:
    heads = [(m.end(), int(m.group(1)), _html_to_text(m.group(2)), m.start())
             for m in re.finditer(r"<SECTION-(\d)[^>]*>\s*<TITLE[^>]*>(.*?)</TITLE>", xml, re.S)]
    picked = []
    for wanted in DART_PERIODIC_SECTIONS:
        for index, (end, level, title, _start) in enumerate(heads):
            if wanted in title:
                # A section runs until the next heading at the same or a higher level.
                stop = next((h[3] for h in heads[index + 1:] if h[1] <= level), len(xml))
                picked.append((title, _html_to_text(xml[end:stop])))
                break
    return _join_sections(picked, budget)


def _pdf_bookmarked_sections(reader, budget: int) -> str:
    flat: List[tuple] = []  # (depth, title, 0-based page)

    def walk(nodes, depth):
        for node in nodes:
            if isinstance(node, list):
                walk(node, depth + 1)
                continue
            try:
                flat.append((depth, str(node.title), reader.get_destination_page_number(node)))
            except Exception:  # broken destinations in hostile/odd PDFs
                continue

    try:
        walk(getattr(reader, "outline", None) or [], 0)
    except Exception:
        return ""
    share = max(budget // len(CNINFO_PERIODIC_SECTIONS), 2000)
    picked = []
    for pattern in CNINFO_PERIODIC_SECTIONS:
        for index, (depth, title, page) in enumerate(flat):
            if not re.search(pattern, title):
                continue
            nxt = next((p for d, _t, p in flat[index + 1:] if d <= depth and p > page), page + 1)
            text = ""
            for number in range(page, min(nxt + 1, page + PERIODIC_SECTION_PAGES, len(reader.pages))):
                text += " " + re.sub(r"\s+", " ", reader.pages[number].extract_text() or "")
                if len(text) >= share:
                    break
            picked.append((title, text.strip()))
            break
    return _join_sections(picked, budget)


def _longest_span(text: str, start_re: "re.Pattern[str]", end_re: "re.Pattern[str]") -> str:
    """Body of a section whose heading also appears in the contents and in cross-references.

    The real section is the longest span from a heading match to the next end marker; matches with
    no end marker after them (late cross-references) would run to the end of the file and are skipped.
    """
    best = ""
    for match in start_re.finditer(text):
        end = end_re.search(text, match.end())
        if end and end.start() - match.start() > len(best):
            best = text[match.start():end.start()]
    return best


def format_recent_disclosures(items: List[dict]) -> str:
    """Prompt block for recent filings, or ''. Also the news-evidence signal: real filings only."""
    if not items:
        return ""
    lines = [f"【Regulatory filings · {items[0]['source']} (official disclosure source)】"]
    for item in items:
        line = f"- {item['date']} | {item['title']}"
        if item.get("summary"):
            line += f" | {item['summary']}"
        lines.append(line)
    return "\n".join(lines)


def format_upcoming_disclosures(items: List[dict]) -> str:
    """Prompt block for scheduled disclosure dates, or ''."""
    if not items:
        return ""
    lines = [
        "【Upcoming disclosures (scheduled dates; issuers may change them). "
        "Factor the nearest date into risk and catalyst timing.】"
    ]
    lines += [f"- {i['date']} | {i['title']} [{i['source']}]" for i in items]
    return "\n".join(lines)


def format_disclosure_context(disclosures: Dict[str, List[dict]]) -> str:
    blocks = [format_recent_disclosures(disclosures.get("recent") or []),
              format_upcoming_disclosures(disclosures.get("upcoming") or [])]
    return "\n\n".join(b for b in blocks if b)


def _kr_next_periodic_deadline(today: date) -> dict:
    """Next statutory periodic-report deadline, assuming a December fiscal year end."""
    candidates = []
    for year in (today.year - 1, today.year):
        for month, day, days, report in KR_PERIODIC_DEADLINES:
            due = date(year, month, day) + timedelta(days=days)
            if due >= today:
                candidates.append((due, report))
    due, report = min(candidates)
    return {
        "date": due.isoformat(),
        "title": f"{report} statutory filing deadline (Dec FYE assumed; filed on or before)",
        "source": "Capital Markets Act",
    }
