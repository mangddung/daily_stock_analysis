# -*- coding: utf-8 -*-
"""Per-request Web UI language for backend-generated display text.

The web client sends ``X-DSA-UI-Language`` on every API request. UiLanguageMiddleware
stores it in a ContextVar so any code handling the request can pick zh/en text with
``ui_text(zh, en)`` without threading a parameter through every call. Requests without
the header (bots, CLI, desktop clients that don't send it) keep the Chinese default.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Awaitable, Callable, Dict, MutableMapping

UI_LANGUAGE_HEADER = b"x-dsa-ui-language"

_ui_language: ContextVar[str] = ContextVar("dsa_ui_language", default="zh")


def current_ui_language() -> str:
    return _ui_language.get()


def is_english_ui() -> bool:
    return _ui_language.get() == "en"


def ui_text(zh: str, en: str) -> str:
    """Return the English text for English UI requests, Chinese otherwise."""
    return en if _ui_language.get() == "en" else zh


def set_ui_language(value: str | None):
    """Set the language for the current context; returns a token for reset."""
    language = "en" if (value or "").strip().lower().startswith("en") else "zh"
    return _ui_language.set(language)


Scope = MutableMapping[str, Any]
ASGIApp = Callable[[Scope, Callable[..., Awaitable[Any]], Callable[..., Awaitable[Any]]], Awaitable[None]]


class UiLanguageMiddleware:
    """Pure ASGI middleware so the ContextVar also covers streaming responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers: Dict[bytes, bytes] = dict(scope.get("headers") or [])
        raw = headers.get(UI_LANGUAGE_HEADER, b"").decode("latin-1")
        token = set_ui_language(raw)
        try:
            await self.app(scope, receive, send)
        finally:
            _ui_language.reset(token)
