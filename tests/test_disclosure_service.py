# -*- coding: utf-8 -*-
"""Offline tests for DisclosureService (no network: requests.get is mocked)."""

import io
import sys
import tempfile
import types
import unittest
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from src.services import disclosure_service as ds
from src.services import run_diagnostics as rd

TODAY = datetime.now().strftime("%Y%m%d")
OLD = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
TODAY_ISO = datetime.now().strftime("%Y-%m-%d")


def _zip(name: str, text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, text)
    return buf.getvalue()


def _resp(*, json_data=None, content=b"", text="", status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.content = content
    resp.text = text
    if status >= 400:
        err = requests.HTTPError(f"{status} for url: https://x/api?crtfc_key=SECRET")
        err.response = resp
        resp.raise_for_status.side_effect = err
    return resp


class DisclosureServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.summarize = MagicMock(return_value="유상증자 1,000억원 결정")
        rd._RATE_LIMITS.clear()
        self.addCleanup(rd._RATE_LIMITS.clear)
        # Upcoming schedules hit other hosts; covered by UpcomingDisclosureTest.
        patcher = patch.object(ds.DisclosureService, "_upcoming_items", return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def _svc(self, **kw):
        return ds.DisclosureService(
            dart_api_key=kw.get("dart", "DARTKEY123"),
            sec_user_agent=kw.get("ua", "TestApp test@example.com"),
            summarize=self.summarize,
            cache_dir=Path(self.tmp.name),
        )

    def _dart_router(self, url, params=None, headers=None, timeout=None, stream=False):
        if url.endswith("corpCode.xml"):
            xml = "<result><list><corp_code>00126380</corp_code><stock_code>005930</stock_code></list></result>"
            return _resp(content=_zip("CORPCODE.xml", xml))
        if url.endswith("list.json"):
            assert params["corp_code"] == "00126380"
            return _resp(json_data={"status": "000", "list": [
                {"rcept_no": "20261119000001", "rcept_dt": TODAY, "report_nm": "주요사항보고서(유상증자결정)"},
                {"rcept_no": "20261119000002", "rcept_dt": TODAY, "report_nm": "분기보고서 (2026.09)"},
            ]})
        if "document.xml" in url:
            return _resp(content=_zip("doc.xml", "<P>신주 발행 <B>1,000억원</B></P>"))
        raise AssertionError(url)

    def test_dart_event_and_periodic_summarized_once_and_cached(self):
        with patch.object(ds.requests, "get", side_effect=self._dart_router) as get:
            out = self._svc().get_disclosure_context("005930.KS", 3)
            self.assertIn("OpenDART", out)
            self.assertIn(f"- {TODAY_ISO} | 주요사항보고서(유상증자결정) | 유상증자 1,000억원 결정", out)
            self.assertIn(f"- {TODAY_ISO} | 분기보고서 (2026.09) | 유상증자 1,000억원 결정", out)
            self.assertEqual(out.count("주요사항보고서"), 1)  # overlapping list queries deduplicated
            prompts = [c[0][0] for c in self.summarize.call_args_list]
            self.assertIn("periodic report", prompts[0])  # periodic gets the periodic prompt
            self.assertIn("신주 발행 1,000억원", prompts[1])
            calls_first = get.call_count

            out2 = self._svc().get_disclosure_context("005930.KS", 3)
        self.assertEqual(out, out2)
        self.assertEqual(self.summarize.call_count, 2)  # summaries came from disk cache
        self.assertEqual(get.call_count - calls_first, 2)  # window + periodic list.json; the rest cached

    def test_http_error_does_not_leak_api_key(self):
        with patch.object(ds.requests, "get", return_value=_resp(status=500)):
            with self.assertLogs(ds.logger, level="WARNING") as logs:
                self.assertEqual(self._svc().get_disclosure_context("005930.KS", 3), "")
        text = "\n".join(logs.output)
        self.assertNotIn("SECRET", text)
        self.assertNotIn("DARTKEY123", text)

    def test_dart_quota_status_raises_runtime_alert(self):
        def router(url, params=None, headers=None, timeout=None, stream=False):
            if url.endswith("list.json"):
                return _resp(json_data={"status": "020", "message": "사용한도를 초과하였습니다."})
            return self._dart_router(url, params=params)

        with patch.object(ds.requests, "get", side_effect=router), self.assertLogs(ds.logger, level="WARNING"):
            self.assertEqual(self._svc().get_disclosure_context("005930.KS", 3), "")
        alerts = [a for a in rd.get_rate_limit_alerts() if a["kind"] == "disclosure"]
        self.assertEqual([a["source"] for a in alerts], ["OpenDART"])
        self.assertIn("020", alerts[0]["message"])
        self.assertNotIn("DARTKEY123", alerts[0]["message"])

    def test_summary_retried_once_and_written_in_report_language(self):
        self.summarize.side_effect = ["", "자기주식 취득 결정 요약", "요약"]
        svc = ds.DisclosureService(dart_api_key="DARTKEY123", sec_user_agent=None, summarize=self.summarize,
                                   cache_dir=Path(self.tmp.name), report_language="ko")
        item = {"id": "20261119000001", "date": TODAY_ISO, "title": "주요사항보고서", "periodic": False,
                "body_url": f"{ds.DART_BASE}/document.xml?rcept_no=20261119000001"}
        with patch.object(ds.requests, "get", side_effect=self._dart_router):
            self.assertEqual(svc._summary_for("OpenDART", item), "자기주식 취득 결정 요약")
        self.assertEqual(self.summarize.call_count, 2)  # empty first reply retried once
        self.assertIn("Write the summary in Korean", self.summarize.call_args[0][0])
        self.assertTrue((Path(self.tmp.name) / "OpenDART" / "20261119000001.ko.json").exists())

        self.summarize.reset_mock(side_effect=True)
        self.summarize.return_value = None  # every attempt fails: title only, no cache entry
        en = ds.DisclosureService(dart_api_key="DARTKEY123", sec_user_agent=None, summarize=self.summarize,
                                  cache_dir=Path(self.tmp.name), report_language="en")
        with patch.object(ds.requests, "get", side_effect=self._dart_router):
            self.assertEqual(en._summary_for("OpenDART", item), "")  # ko cache is not reused for en
        self.assertEqual(self.summarize.call_count, ds.SUMMARY_ATTEMPTS)
        self.assertFalse((Path(self.tmp.name) / "OpenDART" / "20261119000001.en.json").exists())

    def test_earnings_filing_survives_the_item_cap(self):
        noise = [{"rcept_no": f"2026111900000{i}", "rcept_dt": TODAY, "report_nm": f"현금ㆍ현물배당결정 {i}"}
                 for i in range(6)]
        earnings = {"rcept_no": "20261119800036", "rcept_dt": TODAY,
                    "report_nm": "연결재무제표기준영업(잠정)실적(공정공시)"}

        def router(url, params=None, headers=None, timeout=None, stream=False):
            if url.endswith("list.json"):
                return _resp(json_data={"status": "000", "list": noise + [earnings]})  # newest first, earnings last
            return self._dart_router(url, params=params)

        with patch.object(ds.requests, "get", side_effect=router):
            recent = self._svc().get_disclosures("005930.KS", 3)["recent"]
        self.assertEqual(len(recent), ds.MAX_ITEMS)
        self.assertEqual(recent[0]["title"], earnings["report_nm"])

    def test_latest_periodic_report_included_outside_news_window(self):
        old = (datetime.now() - timedelta(days=40)).strftime("%Y%m%d")

        def router(url, params=None, headers=None, timeout=None, stream=False):
            if url.endswith("list.json"):
                if params.get("pblntf_ty") == "A":
                    self.assertLessEqual(params["bgn_de"], old)  # lookback, not the 3-day window
                    return _resp(json_data={"status": "000", "list": [
                        {"rcept_no": "20261005000001", "rcept_dt": old, "report_nm": "반기보고서 (2026.06)"}]})
                return _resp(json_data={"status": "013"})  # nothing in the news window
            return self._dart_router(url, params=params)

        with patch.object(ds.requests, "get", side_effect=router):
            recent = self._svc().get_disclosures("005930.KS", 3)["recent"]
        self.assertEqual([r["title"] for r in recent], ["반기보고서 (2026.06)"])

    def test_old_summary_cache_version_is_rebuilt(self):
        old = Path(self.tmp.name) / "OpenDART" / "20261119000001.json"
        old.parent.mkdir(parents=True)
        old.write_text('{"summary": "stale 6000-char summary"}', encoding="utf-8")  # pre-v2 cache entry
        with patch.object(ds.requests, "get", side_effect=self._dart_router):
            out = self._svc().get_disclosure_context("005930.KS", 3)
        self.assertNotIn("stale", out)
        self.assertEqual(self.summarize.call_count, 2)  # rebuilt event + new periodic

    def test_sec_8k_summary_includes_ex99_exhibits_within_budget(self):
        folder = "https://www.sec.gov/Archives/edgar/data/320193/000032019326000001"
        index = (
            "<table>"
            '<tr><td>1</td><td>8-K</td><td><a href="/ix?doc=/Archives/edgar/data/320193/000032019326000001/a.htm">'
            "a.htm</a></td><td>8-K</td></tr>"
            '<tr><td>2</td><td>Press release</td><td><a href="/Archives/edgar/data/320193/000032019326000001/pr.htm">'
            "pr.htm</a></td><td>EX-99.1</td></tr>"
            '<tr><td>3</td><td>Logo</td><td><a href="/Archives/edgar/data/320193/000032019326000001/logo.jpg">'
            "logo.jpg</a></td><td>GRAPHIC</td></tr>"
            "</table>"
        )
        fetched = []

        def router(url, params=None, headers=None, timeout=None, stream=False):
            fetched.append(url)
            if url == ds.SEC_TICKERS_URL:
                return _resp(json_data={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"}})
            if "submissions" in url:
                return _resp(json_data={"filings": {"recent": {
                    "form": ["8-K"], "filingDate": [TODAY_ISO], "accessionNumber": ["0000320193-26-000001"],
                    "primaryDocument": ["a.htm"], "primaryDocDescription": ["8-K"],
                }}})
            if url == f"{folder}/a.htm":
                return _resp(text="<p>Item 2.02 Results. See Exhibit 99.1.</p>")
            if url == f"{folder}/0000320193-26-000001-index.html":
                return _resp(text=index)
            if url == f"{folder}/pr.htm":
                return _resp(text="<p>" + "Revenue of $10.0 billion, up 20%. " * 50 + "</p>")
            raise AssertionError(url)

        svc = ds.DisclosureService(dart_api_key=None, sec_user_agent="TestApp test@example.com",
                                   summarize=self.summarize, cache_dir=Path(self.tmp.name), body_chars=300)
        with patch.object(ds.requests, "get", side_effect=router):
            svc.get_disclosure_context("AAPL", 3)
        prompt = self.summarize.call_args[0][0]
        body = prompt.split("Title: 8-K\n\n", 1)[1]
        self.assertTrue(body.startswith("Item 2.02 Results. See Exhibit 99.1. Revenue of $10.0 billion"))
        self.assertEqual(len(body), 300)  # primary + exhibit, capped at the budget
        self.assertNotIn(f"{folder}/logo.jpg", fetched)

    def test_sec_filters_forms_and_window(self):
        def router(url, params=None, headers=None, timeout=None, stream=False):
            self.assertEqual(headers["User-Agent"], "TestApp test@example.com")
            if url == ds.SEC_TICKERS_URL:
                return _resp(json_data={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"}})
            if "submissions" in url:
                self.assertIn("CIK0000320193", url)
                return _resp(json_data={"filings": {"recent": {
                    "form": ["8-K", "4", "10-Q", "8-K"],
                    "filingDate": [TODAY_ISO, TODAY_ISO, TODAY_ISO, OLD],
                    "accessionNumber": ["0001-26-000001", "0001-26-000002", "0001-26-000003", "0001-26-000004"],
                    "primaryDocument": ["a.htm", "f4.xml", "q.htm", "old.htm"],
                    "primaryDocDescription": ["8-K", "", "10-Q", "8-K"],
                }}})
            if url.endswith("/000126000001/a.htm"):
                return _resp(text="<html><body>Item 2.02 Results</body></html>")
            raise AssertionError(url)

        with patch.object(ds.requests, "get", side_effect=router):
            out = self._svc().get_disclosure_context("AAPL", 3)
        lines = out.splitlines()[1:]
        self.assertEqual(len(lines), 2)  # Form 4 and out-of-window 8-K dropped
        self.assertEqual(lines[0], f"- {TODAY_ISO} | 10-Q")  # periodic first; body not routed here
        self.assertTrue(lines[1].startswith(f"- {TODAY_ISO} | 8-K | "))
        self.assertEqual(self.summarize.call_count, 1)

    def test_missing_credentials_skip_network(self):
        with patch.object(ds.requests, "get") as get:
            self.assertEqual(self._svc(dart=None).get_disclosure_context("005930.KS", 3), "")
            self.assertEqual(self._svc(ua=None).get_disclosure_context("AAPL", 3), "")
        get.assert_not_called()

    def test_cninfo_pdf_summary_periodic_and_garbled_fallback(self):
        import pandas as pd

        def row(aid, title):
            link = f"http://www.cninfo.com.cn/new/disclosure/detail?stockCode=600519&announcementId={aid}&orgId=x"
            return {"公告标题": title, "公告时间": f"{TODAY_ISO} 00:00:00", "公告链接": link}

        fake_ak = types.SimpleNamespace(stock_zh_a_disclosure_report_cninfo=MagicMock(return_value=pd.DataFrame([
            row("111", "关于回购股份的公告"),
            row("222", "2026年第三季度报告"),
            row("333", "H股公告"),
        ])))
        pdf_text = {
            "111": ["本公司拟回购股份 金额不超过10亿元"],
            "222": ["第三季度 营业收入 100亿元 同比增长10%"],
            "333": ["ٺܢứྛದˢˢၘứྛࠇٺܢῠթ"],  # broken font encoding
        }

        def fake_get(url, params=None, headers=None, timeout=None, stream=False):
            self.assertTrue(url.startswith("https://static.cninfo.com.cn/finalpage/"))
            resp = _resp()
            resp.iter_content.return_value = [url.rsplit("/", 1)[1].split(".")[0].encode()]
            return resp

        def fake_reader(buf):
            pages = [MagicMock(**{"extract_text.return_value": t}) for t in pdf_text[buf.getvalue().decode()]]
            return types.SimpleNamespace(pages=pages)

        with patch.dict(sys.modules, {"akshare": fake_ak}), \
                patch.object(ds.requests, "get", side_effect=fake_get) as get, \
                patch.object(ds, "PdfReader", side_effect=fake_reader):
            out = self._svc().get_disclosure_context("600519", 3)
        lines = out.splitlines()[1:]
        self.assertEqual(lines[0], f"- {TODAY_ISO} | 2026年第三季度报告 | 유상증자 1,000억원 결정")  # periodic first
        self.assertEqual(lines[1], f"- {TODAY_ISO} | 关于回购股份的公告 | 유상증자 1,000억원 결정")
        self.assertEqual(lines[2], f"- {TODAY_ISO} | H股公告")  # garbled: title only
        self.assertEqual(get.call_count, 3)
        self.assertEqual(self.summarize.call_count, 2)
        self.assertIn("营业收入 100亿元", self.summarize.call_args_list[0][0][0])  # no bookmarks: head of report
        self.assertIn("回购股份 金额不超过10亿元", self.summarize.call_args_list[1][0][0])

    def test_pdf_download_size_cap(self):
        resp = _resp()
        resp.iter_content.return_value = [b"x" * 600, b"x" * 600]
        with patch.object(ds.requests, "get", return_value=resp):
            with self.assertRaises(RuntimeError):
                ds._get("https://static.cninfo.com.cn/a.PDF", max_bytes=1000)
        resp.close.assert_called_once()



def _in(days: int) -> date:
    return date.today() + timedelta(days=days)


class UpcomingDisclosureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.svc = ds.DisclosureService(dart_api_key=None, sec_user_agent=None,
                                        summarize=MagicMock(), cache_dir=Path(self.tmp.name))
        rd._RATE_LIMITS.clear()
        self.addCleanup(rd._RATE_LIMITS.clear)

    def _lines(self, code):
        out = self.svc.get_disclosure_context(code, 3)
        self.assertTrue(out.startswith("【Upcoming disclosures"), out)
        return out.splitlines()[1:]

    def test_kr_kind_ir_dedup_plus_statutory_deadline(self):
        def row(corp, title, day, hour):
            return (f"<tr><td>1</td><td><a onclick=\"companysummary_open('{corp}'); return false;\">x</a></td>"
                    f"<td><a href=\"#\" onclick=\"fnDetailView('1'); return false;\">{title}</a></td>"
                    f"<td>place</td><td class=\"txc\">{day}</td><td class=\"txc\"> {hour} </td></tr>")
        page = "<table><tbody>" + "".join([
            row("00593", "2026년 3분기 실적 &amp; 설명", _in(3), "16:00"),
            row("00593", "Q3 earnings &amp; briefing", _in(3), "16:00"),  # English twin: dropped
            row("01233", "other company", _in(1), "10:00"),
        ]) + "</tbody></table>"
        with patch.object(ds.requests, "post", return_value=_resp(text=page)) as post, \
                patch.object(ds.requests, "get") as get:
            lines = self._lines("005930.KS")
            self._lines("005935.KS")  # preferred share: same KIND key, served from cache
        get.assert_not_called()  # no DART key: recent filings skipped
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs["data"]["fromDate"], date.today().isoformat())
        self.assertEqual(lines[0], f"- {_in(3)} | IR (기업설명회) 16:00: 2026년 3분기 실적 & 설명 [KIND]")
        self.assertEqual(len(lines), 2)
        self.assertIn("statutory filing deadline", lines[1])

    def test_layout_change_alerts_keeps_stale_cache_and_success_clears(self):
        def row(day):
            return (f"<tr><td><a onclick=\"companysummary_open('00593')\">x</a></td>"
                    f"<td><a onclick=\"fnDetailView('1')\">IR</a></td><td>{day}</td></tr>")
        good = "<tbody>" + row(_in(3)) + "</tbody>"
        with patch.object(ds.requests, "post", return_value=_resp(text=good)):
            self.assertEqual(len(self._lines("005930.KS")), 2)
        self.assertEqual(rd.get_rate_limit_alerts(), [])

        cache = Path(self.tmp.name) / "kind_ir_schedule.json"
        cache.write_text(cache.read_text(encoding="utf-8").replace('"fetched_at": "', '"fetched_at": "2000'),
                         encoding="utf-8")  # unparseable timestamp: forces a refresh
        with patch.object(ds.requests, "post", return_value=_resp(text="<div>new layout</div>")),                 self.assertLogs(ds.logger, level="WARNING"):
            self.assertEqual(len(self._lines("005930.KS")), 2)  # stale list still served
        alerts = rd.get_rate_limit_alerts()
        self.assertEqual([(a["kind"], a["source"]) for a in alerts], [("disclosure", "KIND")])
        self.assertIn("0 rows parsed", alerts[0]["message"])

        cache.write_text(cache.read_text(encoding="utf-8").replace('"fetched_at": "', '"fetched_at": "2000'),
                         encoding="utf-8")
        with patch.object(ds.requests, "post", return_value=_resp(text=good)):
            self._lines("005930.KS")
        self.assertEqual(rd.get_rate_limit_alerts(), [])

    def test_source_calls_appear_in_run_flow_diagnostics(self):
        page = ("<tr><td><a onclick=\"companysummary_open('00593')\">x</a></td>"
                f"<td><a onclick=\"fnDetailView('1')\">IR</a></td><td>{_in(3)}</td></tr>")
        events = []
        token = rd.activate_run_diagnostic_context(trace_id="t-disc", stock_code="005930.KS", event_sink=events.append)
        try:
            with patch.object(ds.requests, "post", return_value=_resp(text=page)):
                self._lines("005930.KS")
                self._lines("005930.KS")  # second read comes from the 12h cache
            runs = rd.current_diagnostic_snapshot()["provider_runs"]
        finally:
            rd.reset_run_diagnostic_context(token)
        self.assertEqual([(r["data_type"], r["provider"], r["success"], r.get("cache_hit")) for r in runs],
                         [("disclosure", "KIND", True, None), ("disclosure", "KIND", True, True)])
        self.assertEqual(runs[0]["record_count"], 1)
        self.assertTrue(any("官方公告" in str(e) for e in events))  # live run-flow node label

    def test_kr_statutory_deadline_edges(self):
        nxt = ds._kr_next_periodic_deadline
        self.assertEqual(nxt(date(2026, 11, 14))["date"], "2026-11-14")
        self.assertEqual(nxt(date(2026, 11, 15))["date"], "2027-03-31")
        self.assertEqual(nxt(date(2028, 1, 5))["date"], "2028-03-30")  # leap year: 90 days
        self.assertIn("반기보고서", nxt(date(2026, 6, 1))["title"])

    def test_jp_jpx_excel(self):
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["title"])
        ws.append(["決算発表予定日", "コード", "会社名", "Issue Name", "決算期末", "業種名", "Industry",
                   "種別", "Fiscal Year/Quarter", "市場区分", "Market Segment"])
        for when, code in ((datetime.combine(_in(5), datetime.min.time()), 2590), ("未定", 7203),
                           (datetime.combine(_in(-1), datetime.min.time()), 2590)):
            ws.append([when, code, "x", "X", datetime(2027, 1, 20), "", "", "第３四半期", "Third quarter", "", ""])
        buf = io.BytesIO()
        wb.save(buf)

        def router(url, params=None, headers=None, timeout=None, stream=False):
            if url == ds.JPX_SCHEDULE_PAGE:
                return _resp(text='<a href="/listing/event-schedules/financial-announcement/a/kessan10.xlsx">x</a>')
            self.assertTrue(url.endswith("kessan10.xlsx"))
            resp = _resp()
            resp.iter_content.return_value = [buf.getvalue()]
            return resp

        with patch.object(ds.requests, "get", side_effect=router):
            self.assertEqual(self._lines("2590.T"),
                             [f"- {_in(5)} | Earnings announcement, Third quarter (FYE 2027-01) [JPX]"])
            self.assertEqual(self.svc.get_disclosure_context("7203.T", 3), "")  # undecided date skipped

    def test_hk_board_meetings(self):
        def row(day, code, purpose):
            cell = "<td><font face='monospace'>{}</font></td>"
            return "<tr>" + "".join(cell.format(c) for c in (day.strftime("%d/%m/%Y"), "", "NAME",
                                                             f"&nbsp;{code}", purpose, "6-MTH")) + "</tr>"
        page = "<table>" + row(_in(2), 700, "INT RES") + row(_in(4), 1563, "FINAL RES") + "</table>"
        pages = {ds.HKEX_BMN_URLS[0]: page, ds.HKEX_BMN_URLS[1]: "<table></table>"}  # main board, GEM
        with patch.object(ds.requests, "get", side_effect=lambda url, **kw: _resp(text=pages[url])) as get:
            self.assertEqual(self._lines("00700"), [f"- {_in(2)} | Board meeting: INT RES (6-MTH) [HKEXnews]"])
        self.assertEqual(get.call_count, len(ds.HKEX_BMN_URLS))

    def test_cn_eastmoney_latest_change_wins_and_published_skipped(self):
        data = {"result": {"data": [
            {"REPORT_TYPE_NAME": "2026年 年报", "FIRST_APPOINT_DATE": f"{_in(30)} 00:00:00",
             "FIRST_CHANGE_DATE": f"{_in(40)} 00:00:00", "ACTUAL_PUBLISH_DATE": None},
            {"REPORT_TYPE_NAME": "2026年 三季报", "FIRST_APPOINT_DATE": f"{_in(1)} 00:00:00",
             "ACTUAL_PUBLISH_DATE": "2026-10-31 00:00:00"},
        ]}}
        with patch.object(ds.requests, "get", side_effect=lambda url, **kw: _resp(json_data=data)
                          if url == ds.EASTMONEY_URL else _resp(json_data=None)) as get, \
                patch.object(ds.DisclosureService, "_recent_items", return_value=[]):
            self.assertEqual(self._lines("600519"), [f"- {_in(40)} | 2026年 年报 预约披露 [Eastmoney]"])
        self.assertEqual(get.call_args.kwargs["params"]["filter"], '(SECURITY_CODE="600519")')

    def test_us_yfinance_and_fail_open(self):
        fake_yf = types.SimpleNamespace(Ticker=MagicMock(return_value=types.SimpleNamespace(
            calendar={"Earnings Date": [_in(10), _in(12)]})))
        with patch.dict(sys.modules, {"yfinance": fake_yf}):
            self.assertEqual(self._lines("BRK.B"),
                             [f"- {_in(10)} | Earnings release (Yahoo estimate) [Yahoo Finance]"])
        fake_yf.Ticker.assert_called_with("BRK-B")
        fake_yf.Ticker.side_effect = RuntimeError("boom")
        with patch.dict(sys.modules, {"yfinance": fake_yf}), self.assertLogs(ds.logger, level="WARNING"):
            self.assertEqual(self.svc.get_disclosure_context("AAPL", 3), "")
        self.assertEqual([a["source"] for a in rd.get_rate_limit_alerts()], ["Yahoo Finance"])


if __name__ == "__main__":
    unittest.main()
