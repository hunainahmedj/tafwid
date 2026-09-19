"""The wait CLI observes real registry updates without invoking a model."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import worker_registry as registry

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "wait.py"
TASK = "00000000-0000-4000-8000-000000000001"


class WaitTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        env = patch.dict(os.environ, {"CODEX_HOME": str(self.root), "CODEX_THREAD_ID": TASK})
        env.start()
        self.addCleanup(env.stop)

    def tracker(self, name="run", task=TASK):
        out = self.root / name
        out.mkdir()
        return registry.Tracker(out, task, name, "Fixture worker", {}, str(self.root))

    def command(self, *paths, timeout=0):
        return [sys.executable, str(SCRIPT), "--timeout", str(timeout),
                *[part for path in paths for part in ("--run-dir", str(path))]]

    def run_wait(self, *paths, timeout=0):
        result = subprocess.run(self.command(*paths, timeout=timeout), capture_output=True,
                                text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def start_wait(self, *paths):
        proc = subprocess.Popen(self.command(*paths, timeout=4), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        def cleanup():
            if proc.poll() is None:
                proc.kill()
            proc.communicate()
        self.addCleanup(cleanup)
        return proc

    def test_running_snapshot_is_compact_and_does_not_change_worker(self):
        with self.tracker() as tracker:
            tracker.running(123)
            data = self.run_wait(tracker.record["output_dir"])
            self.assertEqual(data["event"], "waiting")
            self.assertEqual(data["ready"], [])
            self.assertEqual(data["pending_dirs"], [tracker.record["output_dir"]])
            self.assertNotIn("documents", json.dumps(data))
            self.assertEqual(registry.load_record(tracker.id)["status"], "running")

    def test_wait_returns_first_completion_without_waiting_for_other_worker(self):
        with self.tracker("slow") as slow, self.tracker("fast") as fast:
            proc = self.start_wait(slow.record["output_dir"], fast.record["output_dir"])
            time.sleep(.2)
            self.assertIsNone(proc.poll(), "Wait must stay quiet while both workers are active")
            fast.finish({"status": "completed"})
            stdout, stderr = proc.communicate(timeout=2)
            self.assertEqual(proc.returncode, 0, stderr)
            data = json.loads(stdout)
            self.assertEqual(data["event"], "ready")
            self.assertEqual([r["run_id"] for r in data["ready"]], [fast.id])
            self.assertEqual(data["pending_dirs"], [slow.record["output_dir"]])
            self.assertEqual(self.run_wait(*data["pending_dirs"])["ready"], [])

    def test_terminal_outcomes_are_delivered_with_compact_evidence(self):
        for status in ("completed", "native_required", "blocked", "needs_review", "error", "timeout", "interrupted"):
            with self.subTest(status=status), self.tracker(status) as tracker:
                out = Path(tracker.record["output_dir"])
                (out / "report.md").write_text("Useful report " + "x" * 8000)
                (out / "input.txt").write_text("PRIVATE PROMPT NOT NEEDED FOR WAITING")
                if status == "native_required":
                    (out / "handoff.json").write_text('{"capability":"browser"}')
                tracker.finish({"status": status})
                data = self.run_wait(out)
                ready = data["ready"][0]
                self.assertEqual(ready["status"], status)
                self.assertLessEqual(len(ready["report_excerpt"]), 1000)
                self.assertTrue(ready["report_truncated"])
                self.assertEqual(bool(ready["handoff_file"]), status == "native_required")
                self.assertNotIn("PRIVATE PROMPT", json.dumps(data))
                self.assertEqual(data["pending_dirs"], [])

    def test_wait_deadline_does_not_timeout_or_stop_the_worker(self):
        with self.tracker() as tracker:
            start = time.monotonic()
            data = self.run_wait(tracker.record["output_dir"], timeout=.25)
            self.assertGreaterEqual(time.monotonic() - start, .25)
            self.assertEqual(data["event"], "waiting")
            self.assertEqual(registry.load_record(tracker.id)["status"], "starting")

    def test_startup_registration_race_is_waited_for(self):
        out = self.root / "late"
        proc = self.start_wait(out)
        time.sleep(.2)
        with self.tracker("late") as tracker:
            tracker.finish({"status": "completed"})
            stdout, stderr = proc.communicate(timeout=2)
            self.assertEqual(proc.returncode, 0, stderr)
            self.assertEqual(json.loads(stdout)["ready"][0]["run_id"], tracker.id)

    def test_missing_record_returns_attention_instead_of_endless_wait(self):
        data = self.run_wait(self.root / "never-started", timeout=.1)
        self.assertEqual(data["event"], "attention")
        self.assertEqual(len(data["errors"]), 1)
        self.assertEqual(data["pending_dirs"], [])

    def test_other_tasks_run_is_not_returned(self):
        with self.tracker(task="00000000-0000-4000-8000-000000000002") as tracker:
            (Path(tracker.record["output_dir"]) / "report.md").write_text("OTHER TASK SECRET")
            tracker.finish({"status": "completed"})
            data = self.run_wait(tracker.record["output_dir"])
            self.assertEqual(data["event"], "attention")
            self.assertEqual(data["ready"], [])
            self.assertNotIn("OTHER TASK SECRET", json.dumps(data))

    def test_cached_report_survives_removed_artifact_directory(self):
        with self.tracker() as tracker:
            out = Path(tracker.record["output_dir"])
            report = out / "report.md"
            report.write_text("Cached completion")
            tracker.finish({"status": "completed"})
        report.unlink()
        out.rmdir()
        ready = self.run_wait(out)["ready"][0]
        self.assertEqual(ready["report_excerpt"], "Cached completion")
        self.assertIsNone(ready["report_file"])

    def test_stale_heartbeat_is_reported_without_claiming_worker_was_killed(self):
        tracker = self.tracker()
        tracker.record.update(status="running", updated_at=time.time() - 30)
        registry.atomic_json(tracker.path, tracker.record)
        ready = self.run_wait(tracker.record["output_dir"])["ready"][0]
        self.assertEqual(ready["status"], "interrupted")
        self.assertIn("stopped reporting", ready["status_note"])
        self.assertEqual(json.loads(tracker.path.read_text())["status"], "running")

    def test_duplicate_paths_do_not_repeat_completion(self):
        with self.tracker() as tracker:
            tracker.finish({"status": "completed"})
            out = tracker.record["output_dir"]
            self.assertEqual(len(self.run_wait(out, out)["ready"]), 1)

    def test_invalid_wait_bounds_and_missing_identity_are_rejected(self):
        for timeout in (-1, 61, "nan", "inf"):
            result = subprocess.run(self.command(self.root / "run", timeout=timeout),
                                    text=True, capture_output=True, timeout=3)
            self.assertEqual(result.returncode, 2)
        env = {k: v for k, v in os.environ.items() if k not in ("CODEX_THREAD_ID", "CODEX_SESSION_ID")}
        result = subprocess.run(self.command(self.root / "run"), env=env,
                                text=True, capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 2)
        self.assertIn("identity", result.stderr)


if __name__ == "__main__":
    unittest.main()
