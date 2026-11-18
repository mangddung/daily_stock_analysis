# -*- coding: utf-8 -*-
"""English/Korean localization for the first-run setup status payload.

SystemConfigService builds setup checks with Chinese text. This module maps that
text to English or Korean after the payload is built, so the service stays untouched.
Korean falls back to English for any entry without a Korean mapping.
Unknown text is returned unchanged.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from src.report_language import normalize_report_language

_TITLES_BY_KEY = {
    "llm_primary": "Primary LLM channel",
    "llm_agent": "Agent channel",
    "stock_list": "Watchlist",
    "notification": "Notification channels",
    "storage": "Database / local storage",
}

_EXACT: Dict[str, str] = {
    # Primary LLM
    "尚未检测到主模型配置": "No primary model configuration detected.",
    "主模型未出现在当前 LiteLLM YAML model_list 中": "The primary model is not in the current LiteLLM YAML model_list.",
    "主模型未出现在当前启用渠道模型列表中": "The primary model is not in the model list of the enabled channels.",
    "主模型缺少可用渠道或匹配的 API Key": "The primary model has no usable channel or matching API key.",
    "请配置 LITELLM_MODEL、LLM_CHANNELS、LITELLM_CONFIG 或 legacy provider API Key。":
        "Configure LITELLM_MODEL, LLM_CHANNELS, LITELLM_CONFIG, or a legacy provider API key.",
    "已选择 codex_cli，但 DSA 后端进程当前 PATH 中找不到 codex 可执行文件。":
        "codex_cli is selected, but the codex executable is not on the DSA backend process PATH.",
    "请确认 Codex CLI 已安装到后端 PATH 可见目录；桌面端请完全退出并重开。"
    "打开 Codex CLI 交互窗口不会改变已运行后端的 PATH；若找到后仍失败，再检查 Codex CLI 登录态，"
    "或将 GENERATION_BACKEND 设回 litellm。":
        "Make sure Codex CLI is installed in a directory on the backend PATH; on desktop, fully quit and reopen the app. "
        "Opening a Codex CLI window does not change the PATH of a running backend. If it is found but still fails, "
        "check the Codex CLI login, or set GENERATION_BACKEND back to litellm.",
    "请先安装并登录对应 CLI，或将 GENERATION_BACKEND 设回 litellm。":
        "Install and log in to the matching CLI first, or set GENERATION_BACKEND back to litellm.",
    # Agent
    "请将 AGENT_GENERATION_BACKEND 设为 auto 或 litellm，并配置 LiteLLM 工具调用渠道。":
        "Set AGENT_GENERATION_BACKEND to auto or litellm and configure a LiteLLM tool-calling channel.",
    "普通分析使用 Codex CLI；但当前 LiteLLM Agent 路径继承的是 Hermes-only 模型，"
    "Hermes Phase 3 不支持 Agent 工具调用。":
        "Regular analysis uses Codex CLI, but the LiteLLM Agent path inherits a Hermes-only model, "
        "and Hermes Phase 3 does not support Agent tool calling.",
    "如需使用 Ask-Stock Agent，请配置非 Hermes 的 AGENT_LITELLM_MODEL，"
    "或配置包含非 Hermes deployment 的 mixed Agent route。":
        "To use the Ask-Stock Agent, configure a non-Hermes AGENT_LITELLM_MODEL, "
        "or a mixed Agent route that includes a non-Hermes deployment.",
    "AGENT_GENERATION_BACKEND 已选择 litellm，但未检测到可用 LiteLLM 模型配置。":
        "AGENT_GENERATION_BACKEND is set to litellm, but no usable LiteLLM model configuration was detected.",
    "如需使用 Ask-Stock Agent，请配置 AGENT_LITELLM_MODEL、LITELLM_MODEL、LLM_CHANNELS 或 LITELLM_CONFIG。":
        "To use the Ask-Stock Agent, configure AGENT_LITELLM_MODEL, LITELLM_MODEL, LLM_CHANNELS, or LITELLM_CONFIG.",
    "Agent 工具调用需要 LiteLLM 模型配置；local CLI 主生成方式不会被自动继承。":
        "Agent tool calling needs a LiteLLM model configuration; a local CLI primary backend is not inherited.",
    "如需使用 Ask-Stock Agent，请配置 LiteLLM 模型，或将 AGENT_GENERATION_BACKEND 固定为 litellm 后补齐模型配置。":
        "To use the Ask-Stock Agent, configure a LiteLLM model, or set AGENT_GENERATION_BACKEND to litellm and complete the model configuration.",
    "Hermes Phase 3 不支持 Agent 工具调用，且当前继承的主模型没有非 Hermes deployment。":
        "Hermes Phase 3 does not support Agent tool calling, and the inherited primary model has no non-Hermes deployment.",
    "请选择非 Hermes Agent 模型，或配置包含非 Hermes deployment 的 mixed Agent route。":
        "Choose a non-Hermes Agent model, or configure a mixed Agent route that includes a non-Hermes deployment.",
    "未单独配置 Agent 主模型，将继承 LLM 主渠道。":
        "No separate Agent model is configured; the primary LLM channel will be inherited.",
    "Agent 未配置独立模型，且 LLM 主渠道尚不可用。":
        "No separate Agent model is configured, and the primary LLM channel is not available yet.",
    "请先补齐 LLM 主渠道配置。": "Complete the primary LLM channel configuration first.",
    "请选择非 Hermes Agent 模型，或配置 mixed route 中的非 Hermes deployment。":
        "Choose a non-Hermes Agent model, or configure a non-Hermes deployment in the mixed route.",
    "请调整 AGENT_LITELLM_MODEL 或补齐对应渠道配置。":
        "Adjust AGENT_LITELLM_MODEL or complete the matching channel configuration.",
    # Watchlist
    "当前 STOCK_LIST 为空。": "STOCK_LIST is empty.",
    "请至少添加 1 只股票用于首次试跑。": "Add at least one stock for the first trial run.",
    # Notifications
    "已检测到至少一个通知渠道配置。": "At least one notification channel is configured.",
    "通知为可选项，未配置也不影响首次跑通。":
        "Notifications are optional; the first run works without them.",
    "需要推送时可稍后配置飞书、钉钉、Telegram、邮件或其他通知渠道。":
        "When you need push messages, configure Feishu, DingTalk, Telegram, email, or another notification channel later.",
    # Storage
    "请检查 DATABASE_PATH 或上级目录权限。": "Check DATABASE_PATH or the parent directory permissions.",
    "请调整 DATABASE_PATH 或目录权限。": "Adjust DATABASE_PATH or the directory permissions.",
}

_SOURCE_LABELS = {
    "显式主模型": "explicit primary model",
    "LLM 渠道": "LLM channel",
}

_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"^已启用 (.+) 本地生成 Backend（experimental/limited）。$"),
     "Local generation backend {0} is enabled (experimental/limited)."),
    (re.compile(r"^已选择 (.+)，但未找到 (.+) 可执行文件。$"),
     "{0} is selected, but the {1} executable was not found."),
    (re.compile(r"^已检测到 (.+?): (.+)$"), "Detected {0}: {1}"),
    (re.compile(r"^Agent 工具调用暂不支持 (.+) text-only backend。$"),
     "Agent tool calling does not support the {0} text-only backend yet."),
    (re.compile(r"^普通分析使用 Codex CLI；Agent 工具调用仍使用 LiteLLM 主模型: (.+)$"),
     "Regular analysis uses Codex CLI; Agent tool calling still uses the LiteLLM primary model: {0}"),
    (re.compile(r"^Agent 主模型 (.+) 只有 Hermes deployment，Phase 3 不支持 Agent 工具调用。$"),
     "Agent model {0} only has a Hermes deployment; Phase 3 does not support Agent tool calling."),
    (re.compile(r"^已配置 Agent 主模型: (.+)$"), "Agent model configured: {0}"),
    (re.compile(r"^Agent 主模型 (.+) 缺少可用渠道或匹配的 API Key。$"),
     "Agent model {0} has no usable channel or matching API key."),
    (re.compile(r"^已配置 (\d+) 只股票。$"), "{0} stock(s) configured."),
    (re.compile(r"^数据库路径父目录不可用: (.+)$"), "Database parent directory is not available: {0}"),
    (re.compile(r"^数据库上级目录可创建: (.+)$"), "Database parent directory can be created: {0}"),
    (re.compile(r"^数据库路径可用: (.+)$"), "Database path is available: {0}"),
    (re.compile(r"^数据库路径上级目录不可写: (.+)$"), "Database parent directory is not writable: {0}"),
]

_TITLES_BY_KEY_KO = {
    "llm_primary": "기본 LLM 채널",
    "llm_agent": "Agent 채널",
    "stock_list": "관심종목",
    "notification": "알림 채널",
    "storage": "데이터베이스 / 로컬 저장소",
}

# Keyed by the Chinese source text, like _EXACT.
_EXACT_KO: Dict[str, str] = {
    # Primary LLM
    "尚未检测到主模型配置": "기본 모델 설정이 감지되지 않았습니다.",
    "主模型未出现在当前 LiteLLM YAML model_list 中": "기본 모델이 현재 LiteLLM YAML model_list에 없습니다.",
    "主模型未出现在当前启用渠道模型列表中": "기본 모델이 활성화된 채널의 모델 목록에 없습니다.",
    "主模型缺少可用渠道或匹配的 API Key": "기본 모델에 사용 가능한 채널 또는 일치하는 API 키가 없습니다.",
    "请配置 LITELLM_MODEL、LLM_CHANNELS、LITELLM_CONFIG 或 legacy provider API Key。":
        "LITELLM_MODEL, LLM_CHANNELS, LITELLM_CONFIG 또는 legacy provider API 키를 설정하십시오.",
    "已选择 codex_cli，但 DSA 后端进程当前 PATH 中找不到 codex 可执行文件。":
        "codex_cli가 선택되었지만 DSA 백엔드 프로세스의 PATH에서 codex 실행 파일을 찾을 수 없습니다.",
    "请确认 Codex CLI 已安装到后端 PATH 可见目录；桌面端请完全退出并重开。"
    "打开 Codex CLI 交互窗口不会改变已运行后端的 PATH；若找到后仍失败，再检查 Codex CLI 登录态，"
    "或将 GENERATION_BACKEND 设回 litellm。":
        "Codex CLI가 백엔드 PATH에 포함된 디렉터리에 설치되어 있는지 확인하십시오. 데스크톱에서는 앱을 완전히 종료한 후 다시 여십시오. "
        "Codex CLI 창을 열어도 이미 실행 중인 백엔드의 PATH는 바뀌지 않습니다. 찾았는데도 실패하면 "
        "Codex CLI 로그인 상태를 확인하거나 GENERATION_BACKEND를 litellm으로 되돌리십시오.",
    "请先安装并登录对应 CLI，或将 GENERATION_BACKEND 设回 litellm。":
        "먼저 해당 CLI를 설치하고 로그인하거나, GENERATION_BACKEND를 litellm으로 되돌리십시오.",
    # Agent
    "请将 AGENT_GENERATION_BACKEND 设为 auto 或 litellm，并配置 LiteLLM 工具调用渠道。":
        "AGENT_GENERATION_BACKEND를 auto 또는 litellm으로 설정하고 LiteLLM 도구 호출 채널을 구성하십시오.",
    "普通分析使用 Codex CLI；但当前 LiteLLM Agent 路径继承的是 Hermes-only 模型，"
    "Hermes Phase 3 不支持 Agent 工具调用。":
        "일반 분석은 Codex CLI를 사용하지만, LiteLLM Agent 경로는 Hermes 전용 모델을 상속하며 "
        "Hermes Phase 3는 Agent 도구 호출을 지원하지 않습니다.",
    "如需使用 Ask-Stock Agent，请配置非 Hermes 的 AGENT_LITELLM_MODEL，"
    "或配置包含非 Hermes deployment 的 mixed Agent route。":
        "종목 질문 Agent를 사용하려면 Hermes가 아닌 AGENT_LITELLM_MODEL을 설정하거나, "
        "Hermes가 아닌 deployment를 포함한 mixed Agent route를 구성하십시오.",
    "AGENT_GENERATION_BACKEND 已选择 litellm，但未检测到可用 LiteLLM 模型配置。":
        "AGENT_GENERATION_BACKEND가 litellm으로 설정되었지만 사용 가능한 LiteLLM 모델 설정이 감지되지 않았습니다.",
    "如需使用 Ask-Stock Agent，请配置 AGENT_LITELLM_MODEL、LITELLM_MODEL、LLM_CHANNELS 或 LITELLM_CONFIG。":
        "종목 질문 Agent를 사용하려면 AGENT_LITELLM_MODEL, LITELLM_MODEL, LLM_CHANNELS 또는 LITELLM_CONFIG를 설정하십시오.",
    "Agent 工具调用需要 LiteLLM 模型配置；local CLI 主生成方式不会被自动继承。":
        "Agent 도구 호출에는 LiteLLM 모델 설정이 필요하며, local CLI 기본 생성 방식은 자동으로 상속되지 않습니다.",
    "如需使用 Ask-Stock Agent，请配置 LiteLLM 模型，或将 AGENT_GENERATION_BACKEND 固定为 litellm 后补齐模型配置。":
        "종목 질문 Agent를 사용하려면 LiteLLM 모델을 설정하거나, AGENT_GENERATION_BACKEND를 litellm으로 고정한 후 모델 설정을 완료하십시오.",
    "Hermes Phase 3 不支持 Agent 工具调用，且当前继承的主模型没有非 Hermes deployment。":
        "Hermes Phase 3는 Agent 도구 호출을 지원하지 않으며, 현재 상속된 기본 모델에는 Hermes가 아닌 deployment가 없습니다.",
    "请选择非 Hermes Agent 模型，或配置包含非 Hermes deployment 的 mixed Agent route。":
        "Hermes가 아닌 Agent 모델을 선택하거나, Hermes가 아닌 deployment를 포함한 mixed Agent route를 구성하십시오.",
    "未单独配置 Agent 主模型，将继承 LLM 主渠道。":
        "별도의 Agent 모델이 설정되지 않아 기본 LLM 채널을 상속합니다.",
    "Agent 未配置独立模型，且 LLM 主渠道尚不可用。":
        "별도의 Agent 모델이 설정되지 않았으며, 기본 LLM 채널도 아직 사용할 수 없습니다.",
    "请先补齐 LLM 主渠道配置。": "먼저 기본 LLM 채널 설정을 완료하십시오.",
    "请选择非 Hermes Agent 模型，或配置 mixed route 中的非 Hermes deployment。":
        "Hermes가 아닌 Agent 모델을 선택하거나, mixed route에 Hermes가 아닌 deployment를 구성하십시오.",
    "请调整 AGENT_LITELLM_MODEL 或补齐对应渠道配置。":
        "AGENT_LITELLM_MODEL을 조정하거나 해당 채널 설정을 완료하십시오.",
    # Watchlist
    "当前 STOCK_LIST 为空。": "STOCK_LIST가 비어 있습니다.",
    "请至少添加 1 只股票用于首次试跑。": "첫 시험 실행을 위해 종목을 1개 이상 추가하십시오.",
    # Notifications
    "已检测到至少一个通知渠道配置。": "알림 채널이 하나 이상 설정되어 있습니다.",
    "通知为可选项，未配置也不影响首次跑通。":
        "알림은 선택 사항이며, 설정하지 않아도 첫 실행에는 영향이 없습니다.",
    "需要推送时可稍后配置飞书、钉钉、Telegram、邮件或其他通知渠道。":
        "푸시 알림이 필요하면 나중에 Feishu, DingTalk, Telegram, 이메일 또는 기타 알림 채널을 설정하십시오.",
    # Storage
    "请检查 DATABASE_PATH 或上级目录权限。": "DATABASE_PATH 또는 상위 디렉터리 권한을 확인하십시오.",
    "请调整 DATABASE_PATH 或目录权限。": "DATABASE_PATH 또는 디렉터리 권한을 조정하십시오.",
}

_SOURCE_LABELS_KO = {
    "显式主模型": "명시적 기본 모델",
    "LLM 渠道": "LLM 채널",
}

# Keyed by the English template in _PATTERNS.
_PATTERN_TEMPLATES_KO = {
    "Local generation backend {0} is enabled (experimental/limited).":
        "로컬 생성 Backend {0}이(가) 활성화되었습니다(experimental/limited).",
    "{0} is selected, but the {1} executable was not found.":
        "{0}이(가) 선택되었지만 {1} 실행 파일을 찾을 수 없습니다.",
    "Detected {0}: {1}": "{0} 감지됨: {1}",
    "Agent tool calling does not support the {0} text-only backend yet.":
        "Agent 도구 호출은 아직 {0} text-only backend를 지원하지 않습니다.",
    "Regular analysis uses Codex CLI; Agent tool calling still uses the LiteLLM primary model: {0}":
        "일반 분석은 Codex CLI를 사용하며, Agent 도구 호출은 여전히 LiteLLM 기본 모델을 사용합니다: {0}",
    "Agent model {0} only has a Hermes deployment; Phase 3 does not support Agent tool calling.":
        "Agent 기본 모델 {0}에는 Hermes deployment만 있으며, Phase 3는 Agent 도구 호출을 지원하지 않습니다.",
    "Agent model configured: {0}": "Agent 기본 모델 설정됨: {0}",
    "Agent model {0} has no usable channel or matching API key.":
        "Agent 기본 모델 {0}에 사용 가능한 채널 또는 일치하는 API 키가 없습니다.",
    "{0} stock(s) configured.": "종목 {0}개가 설정되었습니다.",
    "Database parent directory is not available: {0}": "데이터베이스 상위 디렉터리를 사용할 수 없습니다: {0}",
    "Database parent directory can be created: {0}": "데이터베이스 상위 디렉터리를 생성할 수 있습니다: {0}",
    "Database path is available: {0}": "데이터베이스 경로를 사용할 수 있습니다: {0}",
    "Database parent directory is not writable: {0}": "데이터베이스 상위 디렉터리에 쓸 수 없습니다: {0}",
}


def _translate(text: Optional[str], language: str = "en") -> Optional[str]:
    if not text:
        return text
    korean = language == "ko"
    if korean and text in _EXACT_KO:
        return _EXACT_KO[text]
    if text in _EXACT:
        return _EXACT[text]
    for pattern, template in _PATTERNS:
        match = pattern.match(text)
        if match:
            labels = _SOURCE_LABELS
            if korean:
                template = _PATTERN_TEMPLATES_KO.get(template, template)
                labels = {**_SOURCE_LABELS, **_SOURCE_LABELS_KO}
            groups = [labels.get(group, group) for group in match.groups()]
            return template.format(*groups)
    return text


def localize_setup_status(payload: Dict[str, Any], language: Optional[str]) -> Dict[str, Any]:
    """Return the payload with check text in the requested language (zh is unchanged)."""
    normalized = normalize_report_language(language) if isinstance(language, str) else "zh"
    if normalized not in ("en", "ko"):
        return payload
    titles = _TITLES_BY_KEY_KO if normalized == "ko" else _TITLES_BY_KEY
    checks = []
    for check in payload.get("checks", []):
        localized = dict(check)
        localized["title"] = titles.get(check.get("key"), check.get("title"))
        localized["message"] = _translate(check.get("message"), normalized)
        localized["next_step"] = _translate(check.get("next_step"), normalized)
        checks.append(localized)
    return {**payload, "checks": checks}
