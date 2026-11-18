# -*- coding: utf-8 -*-
"""Process-wide rate-limit alerts feeding the Web shell badge."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from src.services import run_diagnostics as rd


@pytest.fixture(autouse=True)
def _clear_alerts():
    rd._RATE_LIMITS.clear()
    yield
    rd._RATE_LIMITS.clear()


@pytest.mark.parametrize(
    "error_type, message, expected",
    [
        ("RateLimitError", None, True),
        ("CircuitOpen", None, True),
        ("HTTPError", "HTTP 429: Too Many Requests", True),
        (None, "API 配额已用尽: quota exceeded", True),
        ("ValueError", "empty dataframe", False),
        ("HTTPError", "HTTP 4290 bytes", False),
    ],
)
def test_is_rate_limit_error(error_type, message, expected):
    assert rd.is_rate_limit_error(error_type, message) is expected


def test_provider_failure_raises_alert_and_success_clears_it():
    rd.record_provider_run(
        data_type="daily", provider="akshare", operation="fetch", success=False,
        error_type="RateLimitError", error_message="Akshare 可能被限流 token=abc123",
    )
    rd.record_provider_run(
        data_type="news_search", provider="tavily", operation="search", success=False,
        error_message="HTTP 429",
    )
    rd.record_provider_run(data_type="daily", provider="yfinance", operation="fetch", success=False,
                           error_message="empty")

    alerts = {(a["kind"], a["source"]): a for a in rd.get_rate_limit_alerts()}
    assert set(alerts) == {("market", "akshare"), ("news", "tavily")}
    assert "abc123" not in alerts[("market", "akshare")]["message"]

    # A cache hit says nothing about the upstream; a real success clears it.
    rd.record_provider_run(data_type="daily", provider="akshare", operation="fetch", success=True, cache_hit=True)
    assert len(rd.get_rate_limit_alerts()) == 2
    rd.record_provider_run(data_type="daily", provider="akshare", operation="fetch", success=True)
    assert [a["source"] for a in rd.get_rate_limit_alerts()] == ["tavily"]


def test_llm_alert_counts_repeats_and_expires():
    for _ in range(2):
        rd.note_rate_limit_outcome("llm", "anthropic/claude-haiku", success=False, error_type="RateLimitError")
    (alert,) = rd.get_rate_limit_alerts()
    assert (alert["kind"], alert["count"]) == ("llm", 2)

    rd._RATE_LIMITS[("llm", "anthropic/claude-haiku")]["last_at"] -= rd.RATE_LIMIT_ALERT_TTL + timedelta(seconds=1)
    assert rd.get_rate_limit_alerts() == []


def test_runtime_alerts_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr("api.middlewares.auth.is_auth_enabled", lambda: False)
    from api.app import create_app

    rd.note_rate_limit_outcome("news", "bocha", success=False, error_message="请求频率达到限制")
    response = TestClient(create_app(static_dir=tmp_path / "static")).get("/api/v1/system/runtime-alerts")

    assert response.status_code == 200
    body = response.json()
    assert body["ttl_minutes"] == 15
    assert [(a["kind"], a["source"], a["count"]) for a in body["alerts"]] == [("news", "bocha", 1)]
