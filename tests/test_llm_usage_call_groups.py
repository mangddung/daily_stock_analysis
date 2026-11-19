# -*- coding: utf-8 -*-
"""LLM usage rows grouped by chat request id."""

import unittest
from datetime import datetime, timedelta

from src.storage import DatabaseManager, LLMUsage, llm_usage_request, persist_llm_usage


def _row(call_type, model, total, called_at, request_id=None):
    return LLMUsage(
        call_type=call_type,
        model=model,
        prompt_tokens=total // 2,
        completion_tokens=total - total // 2,
        total_tokens=total,
        called_at=called_at,
        request_id=request_id,
    )


class LLMUsageCallGroupsTestCase(unittest.TestCase):
    def setUp(self):
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url="sqlite:///:memory:")
        self.now = datetime.now().replace(microsecond=0)

    def tearDown(self):
        DatabaseManager.reset_instance()

    def _add(self, *rows):
        with self.db.session_scope() as session:
            session.add_all(rows)

    def _range(self):
        return self.now - timedelta(hours=1), self.now + timedelta(hours=1)

    def test_persist_tags_rows_only_inside_request_block(self):
        with llm_usage_request("req-1"):
            persist_llm_usage({"total_tokens": 5}, "m", call_type="agent")
            persist_llm_usage({"total_tokens": 7}, "m", call_type="agent")
        persist_llm_usage({"total_tokens": 9}, "m", call_type="analysis")

        with self.db.session_scope() as session:
            tags = [row.request_id for row in session.query(LLMUsage).order_by(LLMUsage.id)]
        self.assertEqual(tags, ["req-1", "req-1", None])

    def test_groups_by_request_and_paginates_newest_first(self):
        t = self.now
        self._add(
            _row("analysis", "old-model", 10, t - timedelta(minutes=30)),
            _row("agent", "model-a", 100, t - timedelta(minutes=10), "req-1"),
            _row("agent", "model-b", 50, t - timedelta(minutes=9), "req-1"),
            _row("agent", "model-a", 30, t - timedelta(minutes=8), "req-1"),
            # Client-chosen request id that looks like a row id must not merge with row 1.
            _row("agent", "model-c", 20, t - timedelta(minutes=5), "1"),
            _row("analysis", "old-model", 999, t - timedelta(days=3), "req-1"),
        )
        from_dt, to_dt = self._range()

        first = self.db.get_llm_usage_call_groups(from_dt, to_dt, page=1, page_size=2)
        self.assertEqual(first["total"], 3)
        self.assertEqual([g["request_id"] for g in first["items"]], ["1", "req-1"])
        grouped = first["items"][1]
        self.assertEqual(grouped["calls"], 3)
        self.assertEqual(grouped["total_tokens"], 180)
        self.assertEqual(grouped["models"], ["model-a", "model-b"])
        self.assertEqual(grouped["called_at"], t - timedelta(minutes=10))
        self.assertEqual([c["total_tokens"] for c in grouped["items"]], [100, 50, 30])

        second = self.db.get_llm_usage_call_groups(from_dt, to_dt, page=2, page_size=2)
        self.assertEqual(second["total"], 3)
        self.assertEqual(len(second["items"]), 1)
        single = second["items"][0]
        self.assertIsNone(single["request_id"])
        self.assertEqual(single["calls"], 1)
        self.assertEqual(single["items"][0]["model"], "old-model")

    def test_empty_range(self):
        future = datetime(2099, 1, 1)
        self.assertEqual(self.db.get_llm_usage_call_groups(future, future), {"total": 0, "items": []})


if __name__ == "__main__":
    unittest.main()
