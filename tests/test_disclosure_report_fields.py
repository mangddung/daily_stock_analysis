# -*- coding: utf-8 -*-
"""Disclosure lists reach the report verbatim; scheduled dates never count as news evidence."""

import re
import types
import unittest
from unittest.mock import MagicMock, patch

from src.analyzer import AnalysisResult, GeminiAnalyzer
from src.core.pipeline import _attach_disclosures
from src.notification import NotificationService
from src.report_language import get_report_labels
from src.services.disclosure_service import format_disclosure_context, format_recent_disclosures
from src.services.empty_news import news_evidence_present

UPCOMING = [{"date": "2026-11-26", "title": "Earnings announcement, Third quarter", "source": "JPX"}]
RECENT = [{"date": "2026-11-19", "title": "주요사항보고서(유상증자결정)", "summary": "1,000억원 유상증자",
           "source": "OpenDART"}]


def _result(**kw):
    return AnalysisResult(code="2590.T", name="DyDo", sentiment_score=50, trend_prediction="震荡",
                          operation_advice="观望", analysis_summary="x", report_language="ko", success=True, **kw)


class DisclosureReportFieldsTest(unittest.TestCase):
    def test_scheduled_dates_alone_are_not_news_evidence(self):
        only_upcoming = {"recent": [], "upcoming": UPCOMING}
        self.assertTrue(format_disclosure_context(only_upcoming))  # still fed to the LLM
        self.assertFalse(news_evidence_present(None, None, format_recent_disclosures(only_upcoming["recent"]), None))
        self.assertTrue(news_evidence_present(None, None, format_recent_disclosures(RECENT), None))

    def test_attach_and_round_trip_through_to_dict(self):
        result = _result()
        _attach_disclosures(result, {"recent": RECENT, "upcoming": UPCOMING})
        raw = result.to_dict()
        self.assertEqual(raw["upcoming_disclosures"], UPCOMING)
        self.assertEqual(raw["disclosures"], RECENT)
        _attach_disclosures(result, None)  # disabled: leaves fields alone
        self.assertEqual(result.disclosures, RECENT)

    def test_notification_lines_verbatim(self):
        lines = NotificationService._disclosure_lines(
            _result(disclosures=RECENT, upcoming_disclosures=UPCOMING), get_report_labels("ko"))
        self.assertEqual(lines, [
            "📅 **공시 예정**:",
            "- 2026-11-26 Earnings announcement, Third quarter (JPX)",
            "📑 **최근 공시**:",
            "- 2026-11-19 주요사항보고서(유상증자결정): 1,000억원 유상증자",
        ])
        self.assertEqual(NotificationService._disclosure_lines(_result(), get_report_labels("ko")), [])

    def test_markdown_template_renders_lists(self):
        from src.services.report_renderer import render

        out = render(platform="markdown", results=[_result(disclosures=RECENT, upcoming_disclosures=UPCOMING)],
                     report_date="2026-11-19", summary_only=False, extra_context={"report_language": "ko"})
        self.assertIn("- 2026-11-26 Earnings announcement, Third quarter (JPX)", out)
        self.assertIn("- 2026-11-19 주요사항보고서(유상증자결정): 1,000억원 유상증자", out)

    def test_generate_text_records_usage_under_given_call_type(self):
        stub = types.SimpleNamespace(_call_litellm=MagicMock(return_value=("요약", "model-x", {"total_tokens": 9})))
        with patch("src.analyzer.should_persist_usage_telemetry", return_value=True), \
                patch("src.analyzer.persist_llm_usage") as persist:
            self.assertEqual(GeminiAnalyzer.generate_text(stub, "p", call_type="disclosure_summary"), "요약")
            GeminiAnalyzer.generate_text(stub, "p")
        self.assertEqual([c.kwargs["call_type"] for c in persist.call_args_list],
                         ["disclosure_summary", "market_review"])


class PeriodicSectionExtractionTest(unittest.TestCase):
    def test_dart_sections_follow_section_tags(self):
        from src.services.disclosure_service import _dart_sections

        pad = " 상세" * 60  # sections under MIN_SECTION_CHARS are dropped (e.g. "기재하지 아니하였습니다")
        xml = (
            "<SECTION-1><TITLE>II. 사업의 내용</TITLE>"
            f"<SECTION-2><TITLE>1. 사업의 개요</TITLE><P>메모리 반도체 사업{pad}</P></SECTION-2>"
            f"<SECTION-2><TITLE>4. 매출 및 수주상황</TITLE><P>DRAM 매출 70%{pad}</P></SECTION-2></SECTION-1>"
            "<SECTION-1><TITLE>III. 재무에 관한 사항</TITLE>"
            f"<SECTION-2><TITLE>1. 요약재무정보</TITLE><P>매출액 104조{pad}</P>"
            "<SECTION-3><TITLE>1-1. 연결</TITLE><P>영업이익 83조</P></SECTION-3></SECTION-2>"
            "<SECTION-2><TITLE>2. 연결재무제표</TITLE><P>재무상태표 전문</P></SECTION-2></SECTION-1>"
            "<SECTION-1><TITLE>IV. 이사의 경영진단 및 분석의견</TITLE>"
            "<SECTION-2><TITLE>3. 재무상태 및 영업실적</TITLE><P>분기보고서에는 기재하지 아니하였습니다.</P></SECTION-2>"
            "</SECTION-1>"
        )
        out = _dart_sections(xml, 10000)
        self.assertTrue(out.startswith("## 1. 요약재무정보\n매출액 104조"))  # priority order
        self.assertIn("영업이익 83조", out)  # nested subsection kept
        self.assertNotIn("재무상태표 전문", out)  # stops at the next sibling section
        self.assertNotIn("재무상태 및 영업실적", out)  # placeholder section dropped
        self.assertIn("## 4. 매출 및 수주상황\nDRAM 매출 70%", out)
        self.assertIn("## 1. 사업의 개요\n메모리 반도체 사업", out)

    def test_pdf_bookmarks_map_to_real_pages(self):
        from src.services.disclosure_service import _pdf_bookmarked_sections

        pages = [MagicMock(**{"extract_text.return_value": f"page{i} " + "字" * 120}) for i in range(12)]
        marks = {id(m): p for m, p in []}
        sec2, item7, item8, sec3, sec4 = (types.SimpleNamespace(title=t) for t in (
            "第二节公司简介和主要财务指标", "七、近三年主要会计数据和财务指标", "八、境内外会计准则下会计数据差异",
            "第三节管理层讨论与分析", "第四节公司治理"))
        marks.update({id(sec2): 4, id(item7): 5, id(item8): 6, id(sec3): 8, id(sec4): 11})
        reader = types.SimpleNamespace(
            pages=pages, outline=[sec2, [item7, item8], sec3, sec4],
            get_destination_page_number=lambda node: marks[id(node)],
        )
        out = _pdf_bookmarked_sections(reader, 10000)
        blocks = dict(block.split("\n", 1) for block in out.split("\n\n"))
        item7 = blocks["## 七、近三年主要会计数据和财务指标"]
        self.assertEqual(re.findall(r"page\d+", item7), ["page5", "page6"])  # to the next sibling's page
        self.assertEqual(re.findall(r"page\d+", blocks["## 第三节管理层讨论与分析"]),
                         ["page8", "page9", "page10", "page11"])
        self.assertNotIn("page4", out)
        self.assertEqual(_pdf_bookmarked_sections(types.SimpleNamespace(pages=pages, outline=[]), 10000), "")

    def test_sec_mda_is_the_longest_span_not_the_contents_entry(self):
        from src.services.disclosure_service import SEC_MDA_END_RE, SEC_MDA_START_RE, _longest_span

        text = (
            "Table of Contents Item 7. Management's Discussion and Analysis 30 "
            "Item 7A. Quantitative and Qualitative Disclosures 45 " + "filler " * 40
            + "Item 7. Management's Discussion and Analysis Revenue grew 20% to $10 billion. " + "detail " * 60
            + "Item 7A. Quantitative and Qualitative Disclosures about Market Risk ... "
            + "see Item 7. Management's Discussion and Analysis for more."
        )
        out = _longest_span(text, SEC_MDA_START_RE, SEC_MDA_END_RE)
        self.assertTrue(out.startswith("Item 7. Management's Discussion and Analysis Revenue grew 20%"))
        self.assertNotIn("Market Risk", out)


if __name__ == "__main__":
    unittest.main()
