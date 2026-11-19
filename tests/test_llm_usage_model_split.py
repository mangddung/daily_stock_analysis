# -*- coding: utf-8 -*-
"""Usage rows group one model under one name: LiteLLM route prefixes move to the provider column."""

import pytest

pytest.importorskip("litellm")

from src.storage import DatabaseManager, LLMUsage, _split_llm_usage_model, persist_llm_usage  # noqa: E402


@pytest.fixture()
def db():
    DatabaseManager.reset_instance()
    instance = DatabaseManager(db_url="sqlite:///:memory:")
    yield instance
    DatabaseManager.reset_instance()


def test_split_llm_usage_model():
    assert _split_llm_usage_model("anthropic/claude-haiku-5-5") == ("claude-haiku-5-5", "anthropic")
    assert _split_llm_usage_model("openrouter/anthropic/claude-x") == ("anthropic/claude-x", "openrouter")
    assert _split_llm_usage_model("claude-haiku-5-5") == ("claude-haiku-5-5", None)
    assert _split_llm_usage_model("not-a-provider/x") == ("not-a-provider/x", None)


def test_agent_route_and_analysis_model_share_one_name(db):
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    persist_llm_usage(dict(usage), "anthropic/claude-haiku-5-5", call_type="agent")
    persist_llm_usage({**usage, "provider": "anthropic"}, "claude-haiku-5-5", call_type="analysis")

    with db.session_scope() as session:
        rows = {(r.call_type, r.model, r.provider) for r in session.query(LLMUsage).all()}
    assert rows == {("agent", "claude-haiku-5-5", "anthropic"), ("analysis", "claude-haiku-5-5", "anthropic")}


def test_startup_backfill_normalizes_old_prefixed_rows(db):
    db.record_llm_usage(call_type="agent", model="anthropic/claude-haiku-5-5",
                        prompt_tokens=1, completion_tokens=1, total_tokens=2)
    db.record_llm_usage(call_type="agent", model="deepseek/deepseek-chat", provider="deepseek-custom",
                        prompt_tokens=1, completion_tokens=1, total_tokens=2)

    db._initialized = False  # the backfill runs inside __init__, before session_scope() is allowed
    try:
        db._normalize_llm_usage_model_prefixes()
        db._normalize_llm_usage_model_prefixes()  # idempotent
    finally:
        db._initialized = True

    with db.session_scope() as session:
        rows = {(r.model, r.provider) for r in session.query(LLMUsage).all()}
    assert rows == {("claude-haiku-5-5", "anthropic"), ("deepseek-chat", "deepseek-custom")}
