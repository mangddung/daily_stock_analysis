# -*- coding: utf-8 -*-
"""English localization for the first-run setup status payload.

SystemConfigService builds setup checks with Chinese text. This module maps that
text to English after the payload is built, so the service stays untouched.
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


def _translate(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    if text in _EXACT:
        return _EXACT[text]
    for pattern, template in _PATTERNS:
        match = pattern.match(text)
        if match:
            groups = [_SOURCE_LABELS.get(group, group) for group in match.groups()]
            return template.format(*groups)
    return text


def localize_setup_status(payload: Dict[str, Any], language: Optional[str]) -> Dict[str, Any]:
    """Return the payload with check text in the requested language (zh is unchanged)."""
    if not isinstance(language, str) or normalize_report_language(language) != "en":
        return payload
    checks = []
    for check in payload.get("checks", []):
        localized = dict(check)
        localized["title"] = _TITLES_BY_KEY.get(check.get("key"), check.get("title"))
        localized["message"] = _translate(check.get("message"))
        localized["next_step"] = _translate(check.get("next_step"))
        checks.append(localized)
    return {**payload, "checks": checks}
