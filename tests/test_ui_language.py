# -*- coding: utf-8 -*-
"""Tests for the per-request UI language middleware."""

import unittest

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from src.ui_language import UiLanguageMiddleware, current_ui_language, ui_text


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(UiLanguageMiddleware)

    @app.get("/text")
    def text():
        return {"language": current_ui_language(), "text": ui_text("中文", "English", "한국어")}

    @app.get("/fallback")
    def fallback():
        return {"text": ui_text("中文", "English")}

    @app.get("/stream")
    def stream():
        def gen():
            yield ui_text("中文", "English")
        return StreamingResponse(gen(), media_type="text/plain")

    return app


class UiLanguageMiddlewareTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(_app())

    def test_defaults_to_chinese_without_header(self):
        self.assertEqual(self.client.get("/text").json(), {"language": "zh", "text": "中文"})

    def test_english_header_selects_english(self):
        response = self.client.get("/text", headers={"X-DSA-UI-Language": "en"})
        self.assertEqual(response.json(), {"language": "en", "text": "English"})

    def test_korean_header_selects_korean_and_falls_back_to_english(self):
        response = self.client.get("/text", headers={"X-DSA-UI-Language": "ko"})
        self.assertEqual(response.json(), {"language": "ko", "text": "한국어"})
        response = self.client.get("/fallback", headers={"X-DSA-UI-Language": "ko-KR"})
        self.assertEqual(response.json()["text"], "English")

    def test_unknown_value_falls_back_to_chinese(self):
        response = self.client.get("/text", headers={"X-DSA-UI-Language": "fr"})
        self.assertEqual(response.json()["text"], "中文")

    def test_streaming_response_keeps_language(self):
        response = self.client.get("/stream", headers={"X-DSA-UI-Language": "en"})
        self.assertEqual(response.text, "English")

    def test_language_does_not_leak_between_requests(self):
        self.client.get("/text", headers={"X-DSA-UI-Language": "en"})
        self.assertEqual(self.client.get("/text").json()["text"], "中文")


if __name__ == "__main__":
    unittest.main()
