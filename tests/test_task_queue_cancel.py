# -*- coding: utf-8 -*-
"""Task cancellation: pending tasks stop at once, running analysis stops at the next checkpoint."""

from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

from src.services.task_queue import AnalysisTaskQueue, TaskStatus


class _ControlledAnalysisService:
    """Fake AnalysisService whose analyze_stock is driven by the test through events."""

    started = threading.Event()
    release = threading.Event()
    saved = False

    def __init__(self) -> None:
        self.last_error = None

    def analyze_stock(self, *, progress_callback, **_kwargs):
        progress_callback(20, "fetching data")
        type(self).started.set()
        type(self).release.wait(timeout=5)
        progress_callback(97, "saving report")  # checkpoint before save
        type(self).saved = True
        return {"stock_name": "Demo"}


class TaskQueueCancelTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._original_instance = AnalysisTaskQueue._instance
        AnalysisTaskQueue._instance = None
        self.queue = AnalysisTaskQueue(max_workers=1)
        _ControlledAnalysisService.started = threading.Event()
        _ControlledAnalysisService.release = threading.Event()
        _ControlledAnalysisService.saved = False
        patcher = patch("src.services.analysis_service.AnalysisService", _ControlledAnalysisService)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        _ControlledAnalysisService.release.set()
        if self.queue._executor is not None:
            self.queue._executor.shutdown(wait=True)
        AnalysisTaskQueue._instance = self._original_instance

    def _wait(self, task_id: str) -> None:
        self.queue._futures[task_id].result(timeout=5)

    def test_running_analysis_stops_at_next_checkpoint_without_saving(self) -> None:
        task = self.queue.submit_task("600519")
        self.assertTrue(_ControlledAnalysisService.started.wait(timeout=5))
        self.assertTrue(self.queue.get_task(task.task_id).cancellable)

        requested = self.queue.cancel_task(task.task_id)
        self.assertEqual(requested.status, TaskStatus.CANCEL_REQUESTED)
        self.assertFalse(requested.cancellable)

        _ControlledAnalysisService.release.set()
        self._wait(task.task_id)

        final = self.queue.get_task(task.task_id)
        self.assertEqual(final.status, TaskStatus.CANCELLED)
        self.assertFalse(_ControlledAnalysisService.saved)
        self.assertFalse(self.queue.is_analyzing("600519"))

    def test_pending_task_is_cancelled_immediately_and_can_be_resubmitted(self) -> None:
        running = self.queue.submit_task("600519")
        self.assertTrue(_ControlledAnalysisService.started.wait(timeout=5))
        pending = self.queue.submit_task("000001")

        cancelled = self.queue.cancel_task(pending.task_id)
        self.assertEqual(cancelled.status, TaskStatus.CANCELLED)
        self.assertFalse(self.queue.is_analyzing("000001"))

        _ControlledAnalysisService.release.set()
        self._wait(running.task_id)
        self.assertEqual(self.queue.get_task(running.task_id).status, TaskStatus.COMPLETED)
        self.queue.submit_task("000001")  # dedupe slot was released

    def test_finished_and_unknown_tasks_are_left_alone(self) -> None:
        _ControlledAnalysisService.release.set()
        task = self.queue.submit_task("600519")
        self._wait(task.task_id)

        self.assertEqual(self.queue.cancel_task(task.task_id).status, TaskStatus.COMPLETED)
        self.assertIsNone(self.queue.cancel_task("missing"))

    def test_running_background_task_is_not_cancellable(self) -> None:
        started = threading.Event()
        release = threading.Event()

        def run_task():
            started.set()
            release.wait(timeout=5)
            return {"ok": True}

        task = self.queue.submit_background_task(run_task, stock_code="market_review")
        self.assertTrue(started.wait(timeout=5))
        self.assertFalse(self.queue.get_task(task.task_id).cancellable)
        self.assertEqual(self.queue.cancel_task(task.task_id).status, TaskStatus.PROCESSING)
        release.set()
        self._wait(task.task_id)


if __name__ == "__main__":
    unittest.main()
