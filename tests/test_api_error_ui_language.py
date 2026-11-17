# -*- coding: utf-8 -*-
"""HTTP error messages follow the X-DSA-UI-Language header."""

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


class ApiErrorUiLanguageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        env = d / ".env"
        db = d / "t.db"
        env.write_text(
            f"STOCK_LIST=600519\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=false\nDATABASE_PATH={db}\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(env)
        os.environ["DATABASE_PATH"] = str(db)
        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.client = TestClient(create_app(static_dir=d / "static"))

    def tearDown(self):
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.tmp.cleanup()

    def _get(self, path, lang=None):
        headers = {"X-DSA-UI-Language": lang} if lang else {}
        return self.client.get(path, headers=headers)

    def test_backtest_not_found_english(self):
        r = self._get("/api/v1/backtest/performance", "en")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["message"], "Overall backtest summary not found")

    def test_backtest_not_found_default_chinese(self):
        r = self._get("/api/v1/backtest/performance")
        self.assertEqual(r.json()["message"], "未找到整体回测汇总")

    def test_history_not_found_english_and_chinese(self):
        en = self._get("/api/v1/history/999999", "en").json()["message"]
        zh = self._get("/api/v1/history/999999").json()["message"]
        self.assertEqual(en, "Analysis record not found for id/query_id=999999")
        self.assertEqual(zh, "未找到 id/query_id=999999 的分析记录")

    def test_empty_stock_code_english(self):
        r = self.client.post(
            "/api/v1/analysis/analyze", json={}, headers={"X-DSA-UI-Language": "en"}
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("required", r.json()["message"])


if __name__ == "__main__":
    unittest.main()
