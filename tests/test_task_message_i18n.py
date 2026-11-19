# -*- coding: utf-8 -*-
import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch

from src import ui_language
from src.market_phase_summary import format_public_market_status_line
from src.services.run_diagnostics_i18n import localize_run_diagnostics
from src.services.task_message_i18n import localize_task_fields, localize_task_text


class _Lang:
    def __init__(self, lang):
        self.lang = lang

    def __enter__(self):
        self.token = ui_language.set_ui_language(self.lang)

    def __exit__(self, *exc):
        ui_language._ui_language.reset(self.token)


class TaskMessageI18nTest(unittest.TestCase):
    def test_zh_unchanged(self):
        self.assertEqual(localize_task_text("CSCO：行情数据准备完成"), "CSCO：行情数据准备完成")

    def test_progress_prefixed_with_name(self):
        with _Lang("en"):
            self.assertEqual(localize_task_text("CSCO：行情数据准备完成"), "CSCO: Market data ready")
            self.assertEqual(
                localize_task_text("贵州茅台：LLM 正在生成分析结果（已接收 320 字符）"),
                "贵州茅台: LLM is generating the analysis (320 characters received)",
            )
        with _Lang("ko"):
            self.assertEqual(localize_task_text("CSCO：行情数据准备完成"), "CSCO: 시세 데이터 준비 완료")
            self.assertIn("320자", localize_task_text("AAPL：LLM 正在生成分析结果（已接收 320 字符）"))

    def test_status_and_errors_keep_variable_parts(self):
        with _Lang("en"):
            self.assertEqual(localize_task_text("任务已加入队列"), "Task queued")
            self.assertEqual(localize_task_text("分析失败: boom 细节"), "Analysis failed: boom 细节")
            self.assertEqual(
                localize_task_text("股票 AAPL 正在分析中 (task_id: abc)"),
                "Stock AAPL is already being analyzed (task_id: abc)",
            )
            self.assertEqual(localize_task_text("大盘复盘"), "Market review")
        with _Lang("ko"):
            self.assertEqual(localize_task_text("任务已取消"), "작업이 취소되었습니다")
            self.assertEqual(localize_task_text("任务失败: x"), "작업 실패: x")

    def test_unknown_passthrough_and_fields(self):
        with _Lang("en"):
            self.assertEqual(localize_task_text("某个未知消息"), "某个未知消息")
            self.assertEqual(localize_task_text(None), None)
            out = localize_task_fields({"message": "分析完成", "error": None, "task_id": "t1"})
            self.assertEqual(out, {"message": "Analysis complete", "error": None, "task_id": "t1"})

    def test_screening_message_falls_back_to_screening_localizer(self):
        with _Lang("en"):
            self.assertEqual(localize_task_text("选股任务已提交"), "Screening task submitted")

    def test_sse_task_progress_localizes_live_flow_event(self):
        from api.v1.endpoints.analysis import _format_sse_event

        flow_event = {"id": "flow_0001", "title": "日线K线成功", "message": "日线K线 YfinanceFetcher 成功，返回 39 条",
                      "node": {"label": "日线K线 · YfinanceFetcher"}}
        with _Lang("ko"):
            payload = _format_sse_event("task_progress", {"message": "分析完成", "flow_event": flow_event})
        data = json.loads(payload.split("data: ", 1)[1])
        self.assertEqual(data["flow_event"]["title"], "일봉 성공")
        self.assertEqual(data["flow_event"]["message"], "일봉 YfinanceFetcher 성공, 39건 반환")
        self.assertEqual(data["flow_event"]["node"]["label"], "일봉 · YfinanceFetcher")
        self.assertEqual(data["flow_event"]["id"], "flow_0001")

    def test_sse_event_localized_and_query_param(self):
        from api.v1.endpoints.analysis import _format_sse_event, task_stream

        with _Lang("en"):
            payload = _format_sse_event("task_progress", {"message": "CSCO：正在保存分析报告"})
        self.assertEqual(json.loads(payload.split("data: ", 1)[1])["message"], "CSCO: Saving the analysis report")

        queue = MagicMock()
        queue.list_pending_tasks.return_value = [
            MagicMock(to_dict=lambda: {"message": "任务已加入队列", "stock_name": "大盘复盘"})
        ]

        async def run():
            with patch("api.v1.endpoints.analysis.get_task_queue", return_value=queue):
                response = await task_stream(ui_language="ko")
                gen = response.body_iterator
                await gen.__anext__()  # connected
                return await gen.__anext__()

        chunk = asyncio.run(run())
        data = json.loads(chunk.split("data: ", 1)[1])
        self.assertEqual(data["message"], "작업이 대기열에 추가되었습니다")
        self.assertEqual(data["stock_name"], "시장 리뷰")


class RunDiagnosticsI18nTest(unittest.TestCase):
    def test_summary_component_messages(self):
        payload = {
            "status_label": "部分降级",
            "components": {
                "realtime_quote": {"label": "实时行情", "message": "实时行情akshare 成功，前置数据源失败后已继续"},
                "notification": {"label": "通知", "message": "telegram 通知失败：超时 boom"},
                "daily_data": {"label": "日线数据", "message": "日线数据tushare 成功，但本次分析输入使用降级数据"},
            },
        }
        with _Lang("en"):
            out = localize_run_diagnostics(payload)
        comps = out["components"]
        self.assertEqual(out["status_label"], "Partially degraded")
        self.assertEqual(comps["realtime_quote"]["message"], "Real-time quote akshare succeeded after earlier data sources failed")
        self.assertEqual(comps["notification"]["label"], "Notification")
        self.assertEqual(comps["notification"]["message"], "telegram notification failed: 超时 boom")
        self.assertIn("tushare succeeded, but: This analysis input uses fallback data", comps["daily_data"]["message"])
        with _Lang("zh"):
            self.assertIs(localize_run_diagnostics(payload), payload)

    def test_flow_labels_and_events(self):
        payload = {
            "lanes": [{"id": "entry", "label": "入口"}],
            "edges": [{"label": "通知"}, {"label": "调用"}],
            "nodes": [{"label": "日线K线 · akshare"}],
            "events": [{"title": "日线K线成功", "message": "日线K线 akshare 成功，返回 120 条"}],
        }
        with _Lang("ko"):
            out = localize_run_diagnostics(payload, flow=True)
        self.assertEqual(out["lanes"][0]["label"], "진입")
        self.assertEqual(out["edges"][0]["label"], "알림")
        self.assertEqual(out["nodes"][0]["label"], "일봉 · akshare")
        self.assertEqual(out["events"][0]["title"], "일봉 성공")
        self.assertEqual(out["events"][0]["message"], "일봉 akshare 성공, 120건 반환")


class MarketPhaseKoTest(unittest.TestCase):
    def test_korean_status_line(self):
        line = format_public_market_status_line({"phase": "postmarket", "market": "kr"}, report_language="ko")
        self.assertEqual(line, "시장 상태: KR · 장 마감 후")
        line = format_public_market_status_line({"phase": "intraday", "market": "us"}, report_language="ko")
        self.assertEqual(line, "시장 상태: 미국 · 장중")


if __name__ == "__main__":
    unittest.main()
