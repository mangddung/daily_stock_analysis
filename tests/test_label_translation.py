# -*- coding: utf-8 -*-
"""Sector names show in the report language, translated once per language."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.services.label_translation import localize_rows


class LabelTranslationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name) / "labels.json"

    def test_translation_only_cached_per_language(self):
        generate = MagicMock(return_value='Sure: {"建筑安装业": "건축설치업", "食品": "식품", "金融": "금융", "x": "y"}')
        rows = [{"name": "建筑安装业", "change_pct": 1.0}, {"name": "食品 (1617)"}, {"name": "金融"}]
        localize_rows(rows, "ko", generate, self.cache)
        self.assertEqual([r["name"] for r in rows], ["건축설치업", "식품 (1617)", "금융"])
        self.assertEqual(rows[0]["change_pct"], 1.0)
        self.assertIn("Korean", generate.call_args[0][0])
        self.assertNotIn("1617", generate.call_args[0][0])  # ticker suffix is not sent

        again = [{"name": "建筑安装业"}]
        localize_rows(again, "ko", generate, self.cache)
        self.assertEqual(generate.call_count, 1)  # served from the cache
        self.assertEqual(again[0]["name"], "건축설치업")

    def test_same_language_and_failures_leave_names_unchanged(self):
        rows = [{"name": "금융"}, {"name": "Technology (XLK)"}]
        localize_rows(rows, "ko", MagicMock(return_value='{"금융": "금융", "Technology": "기술"}'), self.cache)
        self.assertEqual([r["name"] for r in rows], ["금융", "기술 (XLK)"])

        for reply in (RuntimeError("boom"), "not json", None):
            generate = MagicMock(side_effect=reply) if isinstance(reply, Exception) else MagicMock(return_value=reply)
            other = [{"name": "銀行"}]
            localize_rows(other, "en", generate, self.cache)
            self.assertEqual(other[0]["name"], "銀行")
        self.assertNotIn('"en"', self.cache.read_text(encoding="utf-8"))  # nothing cached on failure


if __name__ == "__main__":
    unittest.main()
