"""The Stop hook waits only for a deliberately armed worker in its own chat."""

import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import completion_hook
import run_state

TASK = "00000000-0000-4000-8000-000000000001"
OTHER = "00000000-0000-4000-8000-000000000002"


class CompletionHookTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(os.environ, {"CODEX_HOME": str(self.root), "CODEX_THREAD_ID": TASK})
        environment.start()
        self.addCleanup(environment.stop)
        available = patch.object(completion_hook, "hook_status", return_value={"active": True})
        available.start()
        self.addCleanup(available.stop)

    def worker(self, name="worker", task=TASK):
        output = self.root / name
        output.mkdir()
        return run_state.Tracker(output, task, "session", name, {}, str(self.root))

    def event(self, task=TASK):
        return {"session_id": task, "stop_hook_active": False}

    def test_unarmed_and_other_chat_stop_do_nothing(self):
        with self.worker() as worker:
            worker.running(123)
            self.assertEqual(completion_hook.on_stop(self.event()), {})
            self.assertEqual(completion_hook.arm([worker.id])["event"], "active")
            self.assertEqual(completion_hook.on_stop(self.event(OTHER)), {})

    def test_unavailable_hook_does_not_arm(self):
        with self.worker() as worker:
            with patch.object(completion_hook, "hook_status", return_value={
                "active": False, "reason": "not trusted"}):
                self.assertEqual(completion_hook.arm([worker.id])["event"], "unavailable")
            self.assertFalse(completion_hook.arm_path(TASK).exists())

    def test_foreign_worker_cannot_be_armed(self):
        with self.worker(task=OTHER) as worker:
            with self.assertRaisesRegex(ValueError, "another chat"):
                completion_hook.arm([worker.id])

    def test_completion_resumes_once_with_compact_result(self):
        with self.worker() as worker:
            worker.running(123)
            completion_hook.arm([worker.id])
            thread = threading.Thread(target=lambda: (time.sleep(.1), worker.finish({
                "status": "completed", "report_excerpt": "Finished"})))
            thread.start()
            try:
                with patch.object(completion_hook, "HOOK_WAIT_SECONDS", 2):
                    result = completion_hook.on_stop(self.event())
            finally:
                thread.join(timeout=2)
            self.assertEqual(result["decision"], "block")
            self.assertIn(worker.id, result["reason"])
            self.assertNotIn("Finished", result["reason"])
            self.assertEqual(completion_hook.on_stop(self.event()), {})

    def test_first_completion_leaves_other_run_pending(self):
        with self.worker("first") as first, self.worker("second") as second:
            first.finish({"status": "completed"})
            second.running(123)
            completion_hook.arm([first.id, second.id])
            result = completion_hook.on_stop(self.event())
            self.assertEqual(result["decision"], "block")
            self.assertIn(first.id, result["reason"])
            self.assertIn(second.id, result["reason"])
            self.assertEqual(completion_hook.on_stop(self.event()), {})

    def test_stale_arm_and_interrupt_do_not_wait(self):
        with self.worker() as worker:
            worker.running(123)
            completion_hook.arm([worker.id])
            marker = completion_hook.arm_path(TASK)
            saved = json.loads(marker.read_text())
            saved["armed_at"] = time.time() - completion_hook.ARM_MAX_AGE_SECONDS - 1
            marker.write_text(json.dumps(saved))
            self.assertEqual(completion_hook.on_stop(self.event()), {})
            self.assertFalse(marker.exists())
            completion_hook.arm([worker.id])
            completion_hook.disarm(self.event())
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
