# -*- coding: utf-8 -*-
"""Tests for English localization of the first-run setup status payload."""

import unittest

from src.services.setup_status_i18n import localize_setup_status


def _payload():
    return {
        "is_complete": False,
        "checks": [
            {"key": "llm_primary", "title": "LLM 主渠道", "status": "needs_action",
             "message": "尚未检测到主模型配置",
             "next_step": "请配置 LITELLM_MODEL、LLM_CHANNELS、LITELLM_CONFIG 或 legacy provider API Key。"},
            {"key": "stock_list", "title": "自选股", "status": "configured",
             "message": "已配置 2 只股票。", "next_step": None},
            {"key": "storage", "title": "数据库 / 本地存储", "status": "configured",
             "message": "数据库路径可用: /app/data/stock_analysis.db", "next_step": None},
            {"key": "llm_agent", "title": "Agent 渠道", "status": "configured",
             "message": "已检测到 显式主模型: openai/gpt-4o", "next_step": None},
        ],
    }


class SetupStatusI18nTest(unittest.TestCase):
    def test_zh_and_missing_language_are_unchanged(self):
        payload = _payload()
        self.assertIs(localize_setup_status(payload, None), payload)
        self.assertIs(localize_setup_status(payload, "zh"), payload)

    def test_english_translates_titles_messages_and_dynamic_values(self):
        checks = localize_setup_status(_payload(), "en")["checks"]
        self.assertEqual(checks[0]["title"], "Primary LLM channel")
        self.assertEqual(checks[0]["message"], "No primary model configuration detected.")
        self.assertIn("LITELLM_MODEL", checks[0]["next_step"])
        self.assertEqual(checks[1]["message"], "2 stock(s) configured.")
        self.assertIsNone(checks[1]["next_step"])
        self.assertEqual(checks[2]["message"], "Database path is available: /app/data/stock_analysis.db")
        self.assertEqual(checks[3]["message"], "Detected explicit primary model: openai/gpt-4o")

    def test_unknown_text_falls_back_to_original(self):
        payload = {"checks": [{"key": "other", "title": "其他", "message": "未知文案", "next_step": None}]}
        check = localize_setup_status(payload, "en")["checks"][0]
        self.assertEqual(check["title"], "其他")
        self.assertEqual(check["message"], "未知文案")


if __name__ == "__main__":
    unittest.main()
