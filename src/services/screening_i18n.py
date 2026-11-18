# -*- coding: utf-8 -*-
"""Response-time English/Korean localization for screening payloads.

Screening results are produced in background tasks and persisted (run history, task
results, hotspot caches), so the per-request UI language is unknown at generation time
and stored text is frozen in Chinese. Instead the service keeps generating Chinese and
the API layer calls ``localize_screening_payload`` just before serving: for English UI
requests, fixed phrases (exact match) and templated sentences (anchored regex) are
rewritten. Chinese UI (no header) returns the payload untouched. Free-form data (LLM
prose, news titles, sector/stock names) has no rule and stays as-is.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from src.ui_language import current_ui_language

_CJK = re.compile("[一-鿿]")

# Whole-string matches only, so Chinese data that merely contains these words is safe.
_EXACT: Dict[str, str] = {
    # strategies (yaml display_name / description)
    "均衡多因子": "Balanced multi-factor",
    "综合估值、资金、动量、稳定性的通用候选发现策略": "General candidate discovery blending valuation, capital flow, momentum and stability",
    "蓝筹收益质量": "Blue-chip income quality",
    "面向高流动性大盘蓝筹的收益质量候选，强调合理估值、稳定成交和防守型持有体验": "Income-quality candidates among liquid large-cap blue chips, favoring fair valuation, steady turnover and defensive holding",
    "资金热度": "Capital heat",
    "资金活跃、量价同步但未极端过热的短线候选": "Short-term candidates with active capital and aligned price/volume that are not overheated",
    "双低选股": "Dual-low screen",
    "偏稳健的低估值筛选策略，叠加当日活跃度与形态确认，避免长期只命中静态低估值票": "Conservative low-valuation screen with same-day activity and pattern confirmation, avoiding stale value-only hits",
    "低波质量": "Low-volatility quality",
    "偏防守的质量型候选，优先选择波动较低、回撤浅、估值不过热且数据质量可靠的股票": "Defensive quality candidates with low volatility, shallow drawdowns, reasonable valuation and reliable data",
    "趋势质量": "Trend quality",
    "兼顾趋势确认和基本面质量的中线候选发现": "Medium-term candidates combining trend confirmation and fundamental quality",
    "超跌反转": "Oversold reversal",
    "跌幅可控、流动性仍在、具备修复观察价值的反转候选": "Reversal candidates with contained declines, intact liquidity and rebound potential",
    "稳健价值": "Steady value",
    "估值合理、流动性充足、波动不过热，并要求有温和活跃度确认的稳健候选": "Steady candidates with fair valuation, ample liquidity, moderate volatility and mild activity confirmation",
    "缩量回踩": "Low-volume pullback",
    "上升趋势中缩量回踩均线支撑，趋势延续的入场机会": "Low-volume pullback to moving-average support in an uptrend, a trend-continuation entry",
    "放量突破": "Volume breakout",
    "成交量放大突破关键阻力位，趋势启动信号": "Volume expansion breaking key resistance, a trend-start signal",
    # hotspot stages / roles / route titles
    "初次异动": "Initial move", "确认扩散": "Spreading", "加速主升": "Accelerating",
    "分歧放量": "Diverging", "降温退潮": "Cooling", "加速发酵": "Accelerating",
    "持续发酵": "Sustained", "快速拉升": "Rapid rally",
    "核心龙头": "Core leader", "助攻": "Supporting", "补涨": "Laggard catch-up",
    "后排": "Secondary", "掉队": "Laggard", "异动核心": "Move leader", "概念股": "Theme stock",
    "等待发酵": "Awaiting catalyst",
    "暂未获取到明确催化事件，可继续观察涨跌幅、成交额和核心个股联动。": "No clear catalyst yet; keep watching price change, turnover and core-stock moves.",
    "同花顺板块概况": "THS sector overview", "题材驱动": "Theme driver",
    "当日发酵": "Today's move", "当前发酵": "Current activity", "消息催化": "News catalyst",
    "热点源连接中断，暂无可用缓存。": "Hotspot source connection lost and no cache is available.",
    # progress / errors / explanations
    "选股任务已提交": "Screening task submitted",
    "正在执行选股，外部数据源较慢时会持续后台运行": "Running screening; slow external data sources keep it running in the background",
    "正在读取全市场快照": "Loading the full-market snapshot",
    "正在补充候选行情与基本面": "Enriching candidate quotes and fundamentals",
    "正在补充入选股票的新闻与事件": "Adding news and events for selected stocks",
    "正在执行 LLM 候选重排": "Re-ranking candidates with the LLM",
    "正在执行最终评分与风险校验": "Running final scoring and risk checks",
    "选股核心流程完成": "Core screening finished",
    "热点题材名称不能为空。": "Hotspot topic name is required.",
    "选股策略列表结构非法。": "The screening strategy list is malformed.",
    "选股功能初始化失败，请检查策略文件、依赖和服务端日志。": "Screening failed to initialize; check strategy files, dependencies and server logs.",
    "请检查后端日志、策略资源和基础数据依赖。": "Check backend logs, strategy resources and base data dependencies.",
    "DSA 数据库未注入，无法读取选股运行历史。": "The DSA database is not injected, so screening run history cannot be read.",
    "模型已参与排序（未提供入选理由）": "The model took part in ranking (no selection reason provided)",
    "已进入当前选股候选结果": "Included in the current screening results",
    "暂无带来源的价格、消息或事件证据": "No sourced price, news or event evidence yet",
}

# Move-event labels used inside the "当日结构" sentence.
_EVENT_LABELS: Dict[str, str] = {
    "有打开跌停板": "Limit-down opened", "60日大幅上涨": "60-day surge", "60日大幅下跌": "60-day plunge",
    "60日新高": "60-day high", "60日新低": "60-day low", "快速拉升": "Rapid rally",
    "快速回落": "Rapid drop", "大幅上涨": "Sharp rise", "大幅下跌": "Sharp fall",
    "有大笔买入": "Large buy orders", "有大笔卖出": "Large sell orders", "火箭发射": "Rocket launch",
    "高台跳水": "Sharp dive", "大笔买入": "Large buy", "大笔卖出": "Large sell",
    "封涨停板": "Limit-up sealed", "打开涨停板": "Limit-up opened", "封跌停板": "Limit-down sealed",
    "向上缺口": "Gap up", "向下缺口": "Gap down", "竞价上涨": "Auction up", "竞价下跌": "Auction down",
    "高开": "Gap-up open", "低开": "Gap-down open", "放量": "Volume surge", "缩量": "Volume shrink",
    "向上突破": "Breakout up", "向下破位": "Breakdown",
}


_EXACT_KO: Dict[str, str] = {
    # strategies (yaml display_name / description)
    "均衡多因子": "균형 멀티팩터",
    "综合估值、资金、动量、稳定性的通用候选发现策略": "밸류에이션, 자금 흐름, 모멘텀, 안정성을 종합한 범용 후보 발굴 전략",
    "蓝筹收益质量": "블루칩 수익 품질",
    "面向高流动性大盘蓝筹的收益质量候选，强调合理估值、稳定成交和防守型持有体验": "유동성 높은 대형 블루칩 중 수익 품질 후보로, 적정 밸류에이션, 안정적인 거래, 방어적 보유를 중시",
    "资金热度": "자금 열기",
    "资金活跃、量价同步但未极端过热的短线候选": "자금이 활발하고 가격·거래량이 함께 움직이지만 과열되지 않은 단기 후보",
    "双低选股": "이중 저평가 발굴",
    "偏稳健的低估值筛选策略，叠加当日活跃度与形态确认，避免长期只命中静态低估值票": "당일 활성도와 패턴 확인을 더한 보수적 저밸류에이션 발굴로, 정체된 저평가 종목만 걸리는 것을 방지",
    "低波质量": "저변동 품질",
    "偏防守的质量型候选，优先选择波动较低、回撤浅、估值不过热且数据质量可靠的股票": "변동성이 낮고 낙폭이 얕으며 밸류에이션이 적정하고 데이터가 신뢰할 만한 방어적 품질 후보",
    "趋势质量": "추세 품질",
    "兼顾趋势确认和基本面质量的中线候选发现": "추세 확인과 펀더멘털 품질을 함께 고려한 중기 후보",
    "超跌反转": "과매도 반전",
    "跌幅可控、流动性仍在、具备修复观察价值的反转候选": "하락폭이 제한적이고 유동성이 유지되며 반등 가능성이 있는 반전 후보",
    "稳健价值": "안정 가치",
    "估值合理、流动性充足、波动不过热，并要求有温和活跃度确认的稳健候选": "밸류에이션이 적정하고 유동성이 충분하며 변동성이 과열되지 않고 완만한 활성도가 확인된 안정적 후보",
    "缩量回踩": "거래량 축소 눌림",
    "上升趋势中缩量回踩均线支撑，趋势延续的入场机会": "상승 추세에서 거래량이 줄며 이동평균선 지지까지 눌린 추세 지속 진입 기회",
    "放量突破": "거래량 돌파",
    "成交量放大突破关键阻力位，趋势启动信号": "거래량 증가와 함께 핵심 저항선을 돌파하는 추세 시작 신호",
    # hotspot stages / roles / route titles
    "初次异动": "초기 움직임", "确认扩散": "확산 중", "加速主升": "가속",
    "分歧放量": "분화", "降温退潮": "냉각", "加速发酵": "가속",
    "持续发酵": "지속", "快速拉升": "급등",
    "核心龙头": "핵심 대장주", "助攻": "보조", "补涨": "후발 상승",
    "后排": "후순위", "掉队": "낙오", "异动核心": "움직임 주도주", "概念股": "테마주",
    "等待发酵": "촉매 대기",
    "暂未获取到明确催化事件，可继续观察涨跌幅、成交额和核心个股联动。": "아직 뚜렷한 촉매가 없습니다. 등락률, 거래대금, 핵심 종목의 움직임을 계속 지켜보세요.",
    "同花顺板块概况": "THS 업종 개요", "题材驱动": "테마 동인",
    "当日发酵": "당일 움직임", "当前发酵": "현재 동향", "消息催化": "뉴스 촉매",
    "热点源连接中断，暂无可用缓存。": "핫이슈 소스 연결이 끊겼으며 사용 가능한 캐시가 없습니다.",
    # progress / errors / explanations
    "选股任务已提交": "종목 발굴 작업이 제출되었습니다",
    "正在执行选股，外部数据源较慢时会持续后台运行": "종목 발굴 실행 중입니다. 외부 데이터 소스가 느리면 백그라운드에서 계속 실행됩니다",
    "正在读取全市场快照": "전체 시장 스냅샷을 불러오는 중",
    "正在补充候选行情与基本面": "후보 시세와 펀더멘털을 보강하는 중",
    "正在补充入选股票的新闻与事件": "선정 종목의 뉴스와 이벤트를 추가하는 중",
    "正在执行 LLM 候选重排": "LLM으로 후보를 재정렬하는 중",
    "正在执行最终评分与风险校验": "최종 점수 산정 및 위험 점검 중",
    "选股核心流程完成": "핵심 종목 발굴 완료",
    "热点题材名称不能为空。": "핫 테마 이름을 입력해야 합니다.",
    "选股策略列表结构非法。": "종목 발굴 전략 목록의 형식이 올바르지 않습니다.",
    "选股功能初始化失败，请检查策略文件、依赖和服务端日志。": "종목 발굴 초기화에 실패했습니다. 전략 파일, 의존성, 서버 로그를 확인하세요.",
    "请检查后端日志、策略资源和基础数据依赖。": "백엔드 로그, 전략 리소스, 기본 데이터 의존성을 확인하세요.",
    "DSA 数据库未注入，无法读取选股运行历史。": "DSA 데이터베이스가 주입되지 않아 종목 발굴 실행 기록을 읽을 수 없습니다.",
    "模型已参与排序（未提供入选理由）": "모델이 순위 산정에 참여했습니다(선정 이유 미제공)",
    "已进入当前选股候选结果": "현재 종목 발굴 결과에 포함됨",
    "暂无带来源的价格、消息或事件证据": "출처가 있는 가격, 뉴스 또는 이벤트 근거가 아직 없습니다",
}

_EVENT_LABELS_KO: Dict[str, str] = {
    "有打开跌停板": "하한가 해제", "60日大幅上涨": "60일 급등", "60日大幅下跌": "60일 급락",
    "60日新高": "60일 신고가", "60日新低": "60일 신저가", "快速拉升": "급등",
    "快速回落": "급락", "大幅上涨": "큰 폭 상승", "大幅下跌": "큰 폭 하락",
    "有大笔买入": "대량 매수 주문", "有大笔卖出": "대량 매도 주문", "火箭发射": "로켓 발사",
    "高台跳水": "급강하", "大笔买入": "대량 매수", "大笔卖出": "대량 매도",
    "封涨停板": "상한가 고정", "打开涨停板": "상한가 해제", "封跌停板": "하한가 고정",
    "向上缺口": "상승 갭", "向下缺口": "하락 갭", "竞价上涨": "동시호가 상승", "竞价下跌": "동시호가 하락",
    "高开": "갭 상승 출발", "低开": "갭 하락 출발", "放量": "거래량 급증", "缩量": "거래량 감소",
    "向上突破": "상향 돌파", "向下破位": "하향 이탈",
}


def _structure_items(match: "re.Match[str]", labels: Dict[str, str], move_type: str, count_fmt: str) -> str:
    items = []
    for part in match.group(1).split("；"):
        item = re.match(r"(.+?)出现 (\d+) 次$", part)
        if item:
            label = item.group(1).strip()
            label = labels.get(label) or re.sub(r"^异动类型 ?", move_type, label)
            items.append(count_fmt.format(label=label, count=item.group(2)))
        else:
            items.append(part)
    return "; ".join(items)


def _structure(match: "re.Match[str]") -> str:
    return " Today's structure: " + _structure_items(match, _EVENT_LABELS, "Move type ", "{label} x{count}") + "."


def _structure_ko(match: "re.Match[str]") -> str:
    return " 당일 구조: " + _structure_items(match, _EVENT_LABELS_KO, "움직임 유형 ", "{label} {count}회") + "."


_PATTERNS: List[Tuple["re.Pattern[str]", Any]] = [
    (re.compile(r"选股运行 (\S+) 不存在。"), r"Screening run \1 does not exist."),
    (re.compile(r"^Screening 参数非法：(.*)$", re.S), r"Invalid screening parameters: \1"),
    (re.compile(r"^Screening 选股运行失败：(.*)$", re.S), r"Screening run failed: \1"),
    (re.compile(r"^选股功能状态检查失败：(.*)$", re.S), r"Screening status check failed: \1"),
    (re.compile(r"^市场 (\S+) 不在选股功能支持范围内（支持市场：(.*)）。$"), r"Market \1 is not supported by screening (supported markets: \2)."),
    (re.compile(r"^快照筛选完成，保留 (\d+) 条候选$"), r"Snapshot filtering done, kept \1 candidates"),
    (re.compile(r"^选股已完成，正在整理 (\d+) 条候选$"), r"Screening done, organizing \1 candidates"),
    (re.compile(r"^(.+)，带动(.+)发酵。$"), r"\1, driving \2."),
    (re.compile(r"^(.+)，市场关注(.+)相关产业链机会。$"), r"\1; the market is watching \2-related supply-chain opportunities."),
    (re.compile(r"^本地后置评分: 未发现额外加分项"), "Local post-scoring: no extra bonus factors"),
    (re.compile(r"^本地后置评分: "), "Local post-scoring: "),
    (re.compile(r"；风险: "), "; risks: "),
    (re.compile(r"^核心因子："), "Top factors: "),
    (re.compile(r"^主要因子："), "Main factors: "),
    (re.compile(r"^模型催化判断："), "Model catalyst view: "),
    (re.compile(r"^消息："), "News: "),
    (re.compile(r"^事件："), "Event: "),
    (re.compile(r"^涨跌幅：(.*)$"), r"Change: \1"),
    (re.compile(r"^成交额：(.*)$"), r"Turnover: \1"),
    (re.compile(r"^(\S+) 后分析已完成，评分调整 (\S+)（未提供摘要）$"), r"\1 post-analysis done, score adjustment \2 (no summary provided)"),
    (re.compile(r"^DSA行情[：:] 现价 "), "DSA quote: price "),
    (re.compile(r"[，,] 涨跌幅 "), ", change "),
    (re.compile(r"^DSA基本面覆盖[：:] "), "DSA fundamentals coverage: "),
    (re.compile(r"^DSA新闻[：:] "), "DSA news: "),
    (re.compile(r"^DSA事件[：:] "), "DSA events: "),
    # hotspot summary sentences
    (re.compile(r"^(.+?)热度 (-?[\d.]+)"), r"\1 heat \2"),
    (re.compile(r"，阶段 (\S+?)(，|。|$)"), lambda m: f", stage {_EXACT.get(m.group(1), m.group(1))}{m.group(2)}"),
    (re.compile(r"，核心股 "), ", leaders "),
    (re.compile(r"^(.+?) 当前暂无可用的板块异动摘要。$"), r"\1 has no sector move summary available right now."),
    (re.compile(r"^(.+?) 当前涨跌幅 (-?[\d.]+)%"), r"\1 current change \2%"),
    (re.compile(r"^(.+?) 当前有异动记录"), r"\1 has move records"),
    (re.compile(r"，盘中异动 (\d+) 次"), r", \1 intraday moves"),
    (re.compile(r"，高频异动个股为 "), ", most frequent mover: "),
    (re.compile(r" 当日结构：(.*)。$", re.S), _structure),
]

_PATTERNS_KO: List[Tuple["re.Pattern[str]", Any]] = [
    (re.compile(r"选股运行 (\S+) 不存在。"), r"종목 발굴 실행 \1이(가) 존재하지 않습니다."),
    (re.compile(r"^Screening 参数非法：(.*)$", re.S), r"종목 발굴 파라미터가 올바르지 않습니다: \1"),
    (re.compile(r"^Screening 选股运行失败：(.*)$", re.S), r"종목 발굴 실행 실패: \1"),
    (re.compile(r"^选股功能状态检查失败：(.*)$", re.S), r"종목 발굴 상태 점검 실패: \1"),
    (re.compile(r"^市场 (\S+) 不在选股功能支持范围内（支持市场：(.*)）。$"), r"시장 \1은(는) 종목 발굴을 지원하지 않습니다(지원 시장: \2)."),
    (re.compile(r"^快照筛选完成，保留 (\d+) 条候选$"), r"스냅샷 필터링 완료, 후보 \1개 유지"),
    (re.compile(r"^选股已完成，正在整理 (\d+) 条候选$"), r"종목 발굴 완료, 후보 \1개 정리 중"),
    (re.compile(r"^(.+)，带动(.+)发酵。$"), r"\1, \2 움직임을 견인했습니다."),
    (re.compile(r"^(.+)，市场关注(.+)相关产业链机会。$"), r"\1. 시장은 \2 관련 공급망 기회에 주목하고 있습니다."),
    (re.compile(r"^本地后置评分: 未发现额外加分项"), "로컬 후처리 점수: 추가 가점 요인 없음"),
    (re.compile(r"^本地后置评分: "), "로컬 후처리 점수: "),
    (re.compile(r"；风险: "), "; 위험: "),
    (re.compile(r"^核心因子："), "핵심 요인: "),
    (re.compile(r"^主要因子："), "주요 요인: "),
    (re.compile(r"^模型催化判断："), "모델 촉매 판단: "),
    (re.compile(r"^消息："), "뉴스: "),
    (re.compile(r"^事件："), "이벤트: "),
    (re.compile(r"^涨跌幅：(.*)$"), r"등락률: \1"),
    (re.compile(r"^成交额：(.*)$"), r"거래대금: \1"),
    (re.compile(r"^(\S+) 后分析已完成，评分调整 (\S+)（未提供摘要）$"), r"\1 사후 분석 완료, 점수 조정 \2(요약 미제공)"),
    (re.compile(r"^DSA行情[：:] 现价 "), "DSA 시세: 현재가 "),
    (re.compile(r"[，,] 涨跌幅 "), ", 등락률 "),
    (re.compile(r"^DSA基本面覆盖[：:] "), "DSA 펀더멘털 커버리지: "),
    (re.compile(r"^DSA新闻[：:] "), "DSA 뉴스: "),
    (re.compile(r"^DSA事件[：:] "), "DSA 이벤트: "),
    # hotspot summary sentences
    (re.compile(r"^(.+?)热度 (-?[\d.]+)"), r"\1 열기 \2"),
    (re.compile(r"，阶段 (\S+?)(，|。|$)"), lambda m: f", 단계 {_EXACT_KO.get(m.group(1), m.group(1))}{m.group(2)}"),
    (re.compile(r"，核心股 "), ", 핵심 종목 "),
    (re.compile(r"^(.+?) 当前暂无可用的板块异动摘要。$"), r"\1: 현재 사용 가능한 업종 움직임 요약이 없습니다."),
    (re.compile(r"^(.+?) 当前涨跌幅 (-?[\d.]+)%"), r"\1 현재 등락률 \2%"),
    (re.compile(r"^(.+?) 当前有异动记录"), r"\1 움직임 기록 있음"),
    (re.compile(r"，盘中异动 (\d+) 次"), r", 장중 움직임 \1회"),
    (re.compile(r"，高频异动个股为 "), ", 최다 움직임 종목: "),
    (re.compile(r" 当日结构：(.*)。$", re.S), _structure_ko),
]

_RULES = {"en": (_EXACT, _PATTERNS), "ko": (_EXACT_KO, _PATTERNS_KO)}

_ASCII_PUNCT = {"，": ", ", "；": "; ", "：": ": ", "。": ".", "、": ", ", "（": " (", "）": ")"}


def _translate(text: str, exact_map: Dict[str, str], patterns: List[Tuple["re.Pattern[str]", Any]]) -> str:
    if not _CJK.search(text):
        return text
    exact = exact_map.get(text.strip())
    if exact is not None:
        return exact
    out = text
    for pattern, repl in patterns:
        out = pattern.sub(repl, out)
    if out != text and not _CJK.search(out):
        for zh, en in _ASCII_PUNCT.items():
            out = out.replace(zh, en)
    return out


def localize_screening_payload(value: Any) -> Any:
    """Return ``value`` with fixed Chinese phrases rewritten when the UI is English or Korean."""
    rules = _RULES.get(current_ui_language())
    if rules is None:
        return value
    return _walk(value, *rules)


def _walk(value: Any, exact_map: Dict[str, str], patterns: List[Tuple["re.Pattern[str]", Any]]) -> Any:
    if isinstance(value, str):
        return _translate(value, exact_map, patterns)
    if isinstance(value, list):
        return [_walk(item, exact_map, patterns) for item in value]
    if isinstance(value, dict):
        return {key: _walk(item, exact_map, patterns) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return _walk(value.model_dump(), exact_map, patterns)
    return value
