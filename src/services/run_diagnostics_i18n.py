# -*- coding: utf-8 -*-
"""Response-time en/ko localization for run-flow snapshots and diagnostic summaries.

Flow events/diagnostics are recorded in worker threads (Chinese) and persisted, so the
API layer localizes the built payload just before serving. Whole-string anchored rules
only; provider names, models, channels and error details are preserved, unknown text
passes through. Group names: ``L*`` = data-type/component label (looked up), ``R*`` =
nested text (localized recursively), anything else is copied verbatim.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from src.services.screening_i18n import _CJK
from src.services.task_message_i18n import localize_task_text
from src.ui_language import current_ui_language

# zh -> (en, ko). Shared by flow and summary.
_EXACT: Dict[str, Tuple[str, str]] = {
    # lanes
    "入口": ("Entry", "진입"), "数据来源": ("Data sources", "데이터 소스"),
    "分析引擎": ("Analysis engine", "분석 엔진"), "产物": ("Artifacts", "산출물"),
    # data-type / component labels
    "实时行情": ("Real-time quote", "실시간 시세"), "日线K线": ("Daily bars", "일봉"),
    "日线数据": ("Daily data", "일봉 데이터"), "技术指标": ("Technical indicators", "기술 지표"),
    "新闻舆情": ("News & sentiment", "뉴스·여론"), "基本面": ("Fundamentals", "펀더멘털"),
    "所属板块": ("Sector membership", "소속 업종"), "筹码结构": ("Chip distribution", "매물대 분포"),
    "新闻搜索": ("News search", "뉴스 검색"), "历史保存": ("History saving", "기록 저장"),
    "官方公告": ("Disclosures", "공시"),
    # nodes
    "用户请求": ("User request", "사용자 요청"), "任务队列": ("Task queue", "작업 대기열"),
    "分析流程": ("Analysis pipeline", "분석 프로세스"), "LLM 生成": ("LLM generation", "LLM 생성"),
    "保存报告": ("Save report", "리포트 저장"), "推送通知": ("Send notification", "알림 전송"),
    # edges
    "提交": ("Submit", "제출"), "调度": ("Dispatch", "배정"), "输入": ("Input", "입력"),
    "组装": ("Assemble", "조립"), "生成": ("Generate", "생성"), "保存": ("Save", "저장"),
    "调用": ("Invoke", "호출"), "降级": ("Fallback", "폴백"), "重试": ("Retry", "재시도"),
    "详情": ("Details", "상세"),
    # statuses / generic
    "正常": ("Normal", "정상"), "部分降级": ("Partially degraded", "부분 저하"),
    "失败": ("Failed", "실패"), "未知": ("Unknown", "알 수 없음"),
    "未知错误": ("Unknown error", "알 수 없는 오류"),
    "所有数据源尝试失败": ("All data source attempts failed", "모든 데이터 소스 시도가 실패했습니다"),
    "旧报告或诊断证据不足，无法判断本次运行状态": ("Legacy report or insufficient diagnostic evidence; the run status cannot be determined", "이전 리포트이거나 진단 근거가 부족하여 이번 실행 상태를 판단할 수 없습니다"),
    # events
    "任务请求已创建": ("Task request created", "작업 요청이 생성되었습니다"),
    "历史分析记录": ("Historical analysis record", "과거 분석 기록"),
    "任务已完成并进入历史记录": ("Task finished and added to history", "작업이 완료되어 기록에 추가되었습니다"),
    "任务完成": ("Task completed", "작업 완료"), "历史记录已生成": ("History record generated", "기록이 생성되었습니다"),
    "任务已创建": ("Task created", "작업 생성됨"), "任务开始执行": ("Task started", "작업 시작"),
    "任务失败": ("Task failed", "작업 실패"), "任务取消": ("Task cancelled", "작업 취소"),
    "任务请求取消": ("Cancellation requested", "취소 요청됨"), "运行事件": ("Run event", "실행 이벤트"),
    "任务已完成": ("Task completed", "작업 완료"), "任务状态未知": ("Task status unknown", "작업 상태를 알 수 없음"),
    "LLM 开始": ("LLM started", "LLM 시작"), "LLM 成功": ("LLM succeeded", "LLM 성공"),
    "LLM 失败": ("LLM failed", "LLM 실패"), "LLM 未记录诊断信息": ("LLM diagnostics not recorded", "LLM 진단 정보가 기록되지 않았습니다"),
    "LLM 成功，模型未记录": ("LLM succeeded, model not recorded", "LLM 성공, 모델 미기록"),
    "历史保存成功": ("History saved", "기록 저장 성공"), "历史保存失败": ("History save failed", "기록 저장 실패"),
    "历史记录已存在": ("History record already exists", "기록이 이미 존재합니다"),
    "历史保存未记录诊断信息": ("History save diagnostics not recorded", "기록 저장 진단 정보가 기록되지 않았습니다"),
    "报告历史已保存": ("Report history saved", "리포트 기록이 저장되었습니다"),
    "报告历史保存失败": ("Report history save failed", "리포트 기록 저장에 실패했습니다"),
    "通知发送成功": ("Notification sent", "알림 전송 성공"), "通知跳过": ("Notification skipped", "알림 건너뜀"),
    "通知失败": ("Notification failed", "알림 실패"), "通知结果未记录": ("Notification result not recorded", "알림 결과가 기록되지 않았습니다"),
    "部分通知渠道失败，其余渠道已发送": ("Some notification channels failed; the rest were sent", "일부 알림 채널이 실패했고 나머지는 전송되었습니다"),
    "通知未配置或本次跳过": ("Notification not configured or skipped this run", "알림이 설정되지 않았거나 이번에는 건너뛰었습니다"),
    "尚未记录输入上下文诊断": ("Input context diagnostics not recorded yet", "입력 컨텍스트 진단이 아직 기록되지 않았습니다"),
    "尚未记录 LLM 诊断": ("LLM diagnostics not recorded yet", "LLM 진단이 아직 기록되지 않았습니다"),
    "尚未记录历史保存结果": ("History save result not recorded yet", "기록 저장 결과가 아직 기록되지 않았습니다"),
    "尚未记录通知结果": ("Notification result not recorded yet", "알림 결과가 아직 기록되지 않았습니다"),
    "未记录 AnalysisContextPack overview": ("AnalysisContextPack overview not recorded", "AnalysisContextPack 개요가 기록되지 않았습니다"),
    "输入上下文已组装": ("Input context assembled", "입력 컨텍스트가 조립되었습니다"),
    # analysis-input block statuses
    "已进入本次分析输入": ("Included in this analysis input", "이번 분석 입력에 포함됨"),
    "本次分析输入使用降级数据": ("This analysis input uses fallback data", "이번 분석 입력에 폴백 데이터가 사용되었습니다"),
    "本次分析输入仅部分可用": ("This analysis input is only partially available", "이번 분석 입력은 일부만 사용할 수 있습니다"),
    "本次分析输入使用过期数据": ("This analysis input uses stale data", "이번 분석 입력에 오래된 데이터가 사용되었습니다"),
    "本次分析输入使用估算数据": ("This analysis input uses estimated data", "이번 분석 입력에 추정 데이터가 사용되었습니다"),
    "输入块抓取失败": ("Input block fetch failed", "입력 블록 가져오기 실패"),
    "输入块显示抓取失败": ("Input block shows a fetch failure", "입력 블록에 가져오기 실패가 표시됨"),
    "输入块标记为不支持": ("Input block is marked unsupported", "입력 블록이 미지원으로 표시됨"),
    "未进入本次分析输入": ("Not included in this analysis input", "이번 분석 입력에 포함되지 않음"),
    "当前市场或链路不支持该输入块": ("The current market or pipeline does not support this input block", "현재 시장 또는 경로에서 이 입력 블록을 지원하지 않습니다"),
    # news
    "新闻搜索无结果": ("News search returned no results", "뉴스 검색 결과가 없습니다"),
    "新闻检索未记录原始证据，可能未尝试或未启用": ("No raw news evidence recorded; search may not have been attempted or enabled", "뉴스 원본 근거가 기록되지 않았습니다. 검색을 시도하지 않았거나 비활성화되었을 수 있습니다"),
    "新闻搜索未记录诊断信息": ("News search diagnostics not recorded", "뉴스 검색 진단 정보가 기록되지 않았습니다"),
}
# Same zh text, different meaning per payload type.
_FLOW_EXACT = {"通知": ("Notify", "알림")}
_SUMMARY_EXACT = {"通知": ("Notification", "알림")}

_LAB = "实时行情|日线数据|日线K线|技术指标|新闻舆情|基本面|所属板块|筹码结构|新闻搜索|官方公告"
_SUB = "(?P<L>" + _LAB + "|LLM)"
_NEWS_TAIL = "；报告页相关资讯可能来自后续检索或历史持久化"
_NEWS_TAIL_EN = "; report-page news may come from later searches or persisted history"
_NEWS_TAIL_KO = "; 리포트 페이지의 뉴스는 이후 검색이나 저장된 기록에서 온 것일 수 있습니다"

# (regex, en format, ko format)
_RULES: List[Tuple["re.Pattern[str]", str, str]] = [
    (re.compile(p, re.S), en, ko)
    for p, en, ko in [
        (rf"^(?P<L>{_LAB})开始$", "{L} started", "{L} 시작"),
        (rf"^(?P<L>{_LAB})成功$", "{L} succeeded", "{L} 성공"),
        (rf"^(?P<L>{_LAB})失败$", "{L} failed", "{L} 실패"),
        (rf"^{_SUB} ?(?P<p>.+?) 调用中$", "{L} {p} in progress", "{L} {p} 호출 중"),
        (rf"^{_SUB} ?(?P<p>.+?) 成功，返回 (?P<n>\d+) 条$", "{L} {p} succeeded, {n} records returned", "{L} {p} 성공, {n}건 반환"),
        (rf"^{_SUB} ?(?P<p>.+?) 成功，但(?P<R>.*)$", "{L} {p} succeeded, but: {R}", "{L} {p} 성공, 단 {R}"),
        (rf"^{_SUB} ?(?P<p>.+?) 成功，前置数据源失败后已继续$", "{L} {p} succeeded after earlier data sources failed", "{L} {p} 성공 (앞선 데이터 소스 실패 후 계속 진행)"),
        (rf"^{_SUB} ?(?P<p>.+?) 成功，期间发生过失败或模型切换$", "{L} {p} succeeded after a failure or model switch", "{L} {p} 성공 (중간에 실패 또는 모델 전환 발생)"),
        (rf"^{_SUB} ?(?P<p>.+?) 成功，期间发生模型切换$", "{L} {p} succeeded after a model switch", "{L} {p} 성공 (중간에 모델 전환 발생)"),
        (rf"^{_SUB} ?(?P<p>.+?) 成功$", "{L} {p} succeeded", "{L} {p} 성공"),
        (rf"^{_SUB} ?(?P<p>.+?) 失败：(?P<R>.*)$", "{L} {p} failed: {R}", "{L} {p} 실패: {R}"),
        (rf"^{_SUB}失败：(?P<R>.*)$", "{L} failed: {R}", "{L} 실패: {R}"),
        (rf"^(?P<L>{_LAB})未记录诊断信息$", "{L} diagnostics not recorded", "{L} 진단 정보가 기록되지 않았습니다"),
        (rf"^(?P<L>{_LAB}) · (?P<p>.*)$", "{L} · {p}", "{L} · {p}"),
        (r"^推送通知 · (?P<p>.*)$", "Send notification · {p}", "알림 전송 · {p}"),
        (r"^(?P<c>.+?) 通知发送成功$", "{c} notification sent", "{c} 알림 전송 성공"),
        (r"^(?P<c>.+?) 通知跳过$", "{c} notification skipped", "{c} 알림 건너뜀"),
        (r"^(?P<c>.+?) 通知失败：(?P<R>.*)$", "{c} notification failed: {R}", "{c} 알림 실패: {R}"),
        (r"^(?P<c>.+?) 通知结果未知$", "{c} notification result unknown", "{c} 알림 결과를 알 수 없음"),
        (r"^通知失败：(?P<R>.*)$", "Notification failed: {R}", "알림 실패: {R}"),
        (r"^报告历史保存失败：(?P<R>.*)$", "Report history save failed: {R}", "리포트 기록 저장 실패: {R}"),
        (r"^输入上下文已组装，可用块 (?P<n>\d+)$", "Input context assembled, {n} blocks available", "입력 컨텍스트 조립 완료, 사용 가능한 블록 {n}개"),
        (r"^未进入本次分析输入：(?P<R>.*)$", "Not included in this analysis input: {R}", "이번 분석 입력에 포함되지 않음: {R}"),
        (r"^输入块状态为 (?P<s>.*)$", "Input block status is {s}", "입력 블록 상태: {s}"),
        (r"^(?P<L>.+?)输入状态$", "{L} input status", "{L} 입력 상태"),
        (r"^新闻检索返回 (?P<n>\d+) 条结果，但新闻(?P<R>.*)" + _NEWS_TAIL + "$", "News search returned {n} results, but news: {R}" + _NEWS_TAIL_EN, "뉴스 검색 결과 {n}건이 반환되었으나 뉴스: {R}" + _NEWS_TAIL_KO),
        (r"^新闻检索返回 (?P<n>\d+) 条结果$", "News search returned {n} results", "뉴스 검색 결과 {n}건 반환"),
        (r"^新闻(?P<R>.*)" + _NEWS_TAIL + "$", "News: {R}" + _NEWS_TAIL_EN, "뉴스: {R}" + _NEWS_TAIL_KO),
    ]
]
_IDX = {"en": 0, "ko": 1}


def _text(text: str, idx: int, overlay: Dict[str, Tuple[str, str]]) -> str:
    key = text.strip()
    hit = overlay.get(key) or _EXACT.get(key)
    if hit:
        return hit[idx]
    for pattern, en, ko in _RULES:
        match = pattern.match(text)
        if not match:
            continue
        groups = match.groupdict()
        for name, value in groups.items():
            if name == "L":
                groups[name] = _text(value, idx, overlay) if value != "LLM" else value
            elif name == "R":
                groups[name] = _text(value, idx, overlay) if _CJK.search(value) else value
        return (en, ko)[idx].format(**groups)
    return localize_task_text(text)


def _walk(value: Any, idx: int, overlay: Dict[str, Tuple[str, str]]) -> Any:
    if isinstance(value, str):
        return _text(value, idx, overlay) if _CJK.search(value) else value
    if isinstance(value, list):
        return [_walk(item, idx, overlay) for item in value]
    if isinstance(value, dict):
        return {key: _walk(item, idx, overlay) for key, item in value.items()}
    return value


def localize_run_diagnostics(payload: Any, *, flow: bool = False) -> Any:
    """Localize a run-flow snapshot (``flow=True``) or diagnostic summary dict for the UI language."""
    idx = _IDX.get(current_ui_language())
    if idx is None:
        return payload
    return _walk(payload, idx, _FLOW_EXACT if flow else _SUMMARY_EXACT)
