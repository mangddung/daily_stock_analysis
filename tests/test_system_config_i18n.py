# -*- coding: utf-8 -*-
"""English UI text for system config warnings / notification test messages."""

import re
import unittest

from src.services.system_config_service import ConfigImportError, SystemConfigService
from src.ui_language import _ui_language, set_ui_language


class SystemConfigI18nTest(unittest.TestCase):
    def _in_lang(self, lang, fn):
        token = set_ui_language(lang)
        try:
            return fn()
        finally:
            _ui_language.reset(token)

    def test_cleanup_warning_language(self):
        def build():
            return SystemConfigService._build_runtime_model_cleanup_warnings(
                previous_map={"LITELLM_MODEL": "x/y"}, updates={"LITELLM_MODEL": ""}
            )[0]

        self.assertIn("检测到已同步清理", self._in_lang(None, build))
        en = self._in_lang("en", build)
        self.assertIn("Primary model", en)
        self.assertIsNone(re.search("[一-鿿]", en))

    def test_invalid_notification_message(self):
        def build():
            return SystemConfigService._get_invalid_notification_test_config_message(
                "ntfy", {"NTFY_URL": "https://ntfy.sh"}
            )

        self.assertTrue(self._in_lang("en", build).startswith("NTFY_URL must include"))
        self.assertIn("必须包含", self._in_lang(None, build))

    def test_import_error(self):
        def build():
            with self.assertRaises(ConfigImportError) as ctx:
                SystemConfigService._parse_imported_env_content("  ")
            return str(ctx.exception)

        self.assertIn("No valid .env", self._in_lang("en", build))
        self.assertIn("未识别到", self._in_lang(None, build))


if __name__ == "__main__":
    unittest.main()
