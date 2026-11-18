# -*- coding: utf-8 -*-
"""Response-time en/ko localization for task status/progress/error text.

Task messages are written in Chinese by worker threads (where the per-request UI language
is unavailable) and broadcast to every SSE subscriber, so the stored value stays Chinese
and the API layer calls ``localize_task_text`` / ``localize_task_fields`` when serving.
Same approach as ``screening_i18n``: anchored regex, unknown text passes through, variable
parts (stock names, counts, error details) are preserved.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from src.services.screening_i18n import _CJK, localize_screening_payload
from src.ui_language import current_ui_language

# (anchored zh regex, English template, Korean template)
_RULES: List[Tuple["re.Pattern[str]", str, str]] = [
    (re.compile(p, re.S), en, ko)
    for p, en, ko in [
        # task_queue status / errors
        (r"^任务已加入队列$", "Task queued", "작업이 대기열에 추가되었습니다"),
        (r"^正在分析中\.\.\.$", "Analyzing...", "분석 중..."),
        (r"^分析完成$", "Analysis complete", "분석 완료"),
        (r"^正在取消任务$", "Cancelling task", "작업을 취소하는 중"),
        (r"^任务已取消$", "Task cancelled", "작업이 취소되었습니다"),
        (r"^任务执行中$", "Task running", "작업 실행 중"),
        (r"^任务执行完成$", "Task finished", "작업 실행 완료"),
        (r"^分析失败: (.*)$", r"Analysis failed: \1", r"분석 실패: \1"),
        (r"^任务失败: (.*)$", r"Task failed: \1", r"작업 실패: \1"),
        (r"^分析返回空结果$", "Analysis returned an empty result", "분석 결과가 비어 있습니다"),
        (r"^任务返回空结果，未生成可持久化内容$", "Task returned an empty result; nothing to persist", "작업 결과가 비어 있어 저장할 내용이 없습니다"),
        (r"^股票 (\S+) 正在分析中 \(task_id: (.*)\)$", r"Stock \1 is already being analyzed (task_id: \2)", r"종목 \1은(는) 이미 분석 중입니다 (task_id: \2)"),
        (r"^分析股票 (\S+) 返回空结果$", r"Analysis of \1 returned an empty result", r"\1 분석 결과가 비어 있습니다"),
        (r"^分析股票 (\S+) 失败$", r"Analysis of \1 failed", r"\1 분석에 실패했습니다"),
        (r"^大盘复盘未返回可持久化报告$", "Market review returned no persistable report", "시장 리뷰에서 저장 가능한 리포트가 반환되지 않았습니다"),
        (r"^大盘复盘$", "Market review", "시장 리뷰"),
        # pipeline / analyzer progress (text after "<name>：")
        (r"^正在准备分析任务$", "Preparing analysis task", "분석 작업을 준비하는 중"),
        (r"^正在获取行情与筹码数据$", "Fetching quotes and chip data", "시세 및 매물대 데이터를 가져오는 중"),
        (r"^行情数据准备完成$", "Market data ready", "시세 데이터 준비 완료"),
        (r"^正在聚合基本面与趋势数据$", "Aggregating fundamentals and trend data", "펀더멘털 및 추세 데이터를 집계하는 중"),
        (r"^正在切换 Agent 分析链路$", "Switching to the Agent analysis pipeline", "Agent 분석 경로로 전환하는 중"),
        (r"^正在检索新闻与舆情$", "Searching news and sentiment", "뉴스와 여론을 검색하는 중"),
        (r"^正在整理分析上下文$", "Preparing analysis context", "분석 컨텍스트를 정리하는 중"),
        (r"^正在请求 LLM 生成报告$", "Requesting the LLM to generate the report", "LLM에 리포트 생성을 요청하는 중"),
        (r"^LLM 请求前等待 ([\d.]+) 秒$", r"Waiting \1 s before the LLM request", r"LLM 요청 전 \1초 대기 중"),
        (r"^LLM 已接收请求，等待响应$", "LLM received the request, awaiting response", "LLM이 요청을 받았으며 응답을 기다리는 중"),
        (r"^LLM 正在生成分析结果（已接收 (\d+) 字符）$", r"LLM is generating the analysis (\1 characters received)", r"LLM이 분석 결과를 생성하는 중 (\1자 수신)"),
        (r"^LLM 返回完成，正在解析 JSON$", "LLM response complete, parsing JSON", "LLM 응답 완료, JSON을 파싱하는 중"),
        (r"^报告字段不完整，正在补全重试（(\d+)/(\d+)）$", r"Report fields incomplete, retrying to fill them (\1/\2)", r"리포트 필드가 불완전하여 보완 재시도 중 (\1/\2)"),
        (r"^正在校验并整理分析结果$", "Validating and organizing analysis results", "분석 결과를 검증하고 정리하는 중"),
        (r"^正在保存分析报告$", "Saving the analysis report", "분석 리포트를 저장하는 중"),
    ]
]

_PREFIXED = re.compile(r"^(.{1,80}?)：(.*)$", re.S)
_IDX = {"en": 1, "ko": 2}


def _apply(text: str, idx: int) -> str | None:
    for rule in _RULES:
        if rule[0].match(text):
            return rule[0].sub(rule[idx], text)
    return None


def localize_task_text(text: Any) -> Any:
    """Translate one task message/error/name for the request UI language (zh/unknown unchanged)."""
    language = current_ui_language()
    idx = _IDX.get(language)
    if idx is None or not isinstance(text, str) or not _CJK.search(text):
        return text
    out = _apply(text, idx)
    if out is None:
        prefixed = _PREFIXED.match(text)
        tail = _apply(prefixed.group(2), idx) if prefixed else None
        if tail is not None:
            out = f"{prefixed.group(1)}: {tail}"
    if out is None:
        # screening task messages share the same queue
        return localize_screening_payload(text)
    return out


def localize_task_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of a task payload with message/error/stock_name localized."""
    if current_ui_language() == "zh" or not isinstance(data, dict):
        return data
    out = dict(data)
    for key in ("message", "error", "stock_name"):
        if key in out:
            out[key] = localize_task_text(out[key])
    return out
