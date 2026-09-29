"""The wait CLI observes real registry updates without invoking a model."""
import hashlib
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
import run_state as registry
import paths
import wait as waiter

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

    def command(self, *paths, timeout=0, run_ids=(), watch_keys=None):
        return [sys.executable, str(SCRIPT), "--timeout", str(timeout),
                *[part for path in paths for part in ("--run-dir", str(path))],
                *[part for run_id in run_ids for part in ("--run-id", run_id)],
                *[part for run_id, key in (watch_keys or {}).items()
                  for part in ("--watch-key", f"{run_id}={key}")]]

    def run_wait(self, *paths, timeout=0, run_ids=(), watch_keys=None):
        result = subprocess.run(self.command(*paths, timeout=timeout, run_ids=run_ids,
                                            watch_keys=watch_keys), capture_output=True,
                                text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def start_wait(self, *paths, run_ids=(), watch_keys=None, timeout=4):
        proc = subprocess.Popen(self.command(*paths, timeout=timeout, run_ids=run_ids,
                                             watch_keys=watch_keys), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        def cleanup():
            if proc.poll() is None:
                proc.kill()
            proc.communicate()
        self.addCleanup(cleanup)
        return proc

    def test_run_id_reads_only_selected_record_and_deduplicates(self):
        with self.tracker() as tracker:
            tracker.running(123)
            with patch.object(registry, "list_runs", side_effect=AssertionError("No registry scan needed")):
                data = waiter.wait_for_runs(run_ids=[tracker.id, tracker.id], timeout=0)
            self.assertEqual(data["event"], "waiting")
            self.assertEqual(data["pending_run_ids"], [tracker.id])
            self.assertEqual(data["pending_dirs"], [tracker.record["output_dir"]])
            self.assertEqual(registry.load_record(tracker.id)["status"], "running")

    def test_run_ids_return_first_completion_and_completion_between_waits(self):
        with self.tracker("slow") as slow, self.tracker("fast") as fast:
            proc = self.start_wait(run_ids=[slow.id, fast.id])
            time.sleep(.2)
            self.assertIsNone(proc.poll())
            fast.finish({"status": "completed"})
            stdout, stderr = proc.communicate(timeout=2)
            self.assertEqual(proc.returncode, 0, stderr)
            data = json.loads(stdout)
            self.assertEqual([r["run_id"] for r in data["ready"]], [fast.id])
            self.assertEqual(data["pending_run_ids"], [slow.id])
            slow.finish({"status": "completed"})
            next_result = self.run_wait(run_ids=data["pending_run_ids"])
            self.assertEqual([r["run_id"] for r in next_result["ready"]], [slow.id])
            self.assertEqual(next_result["pending_run_ids"], [])

    def test_run_id_can_wait_for_late_registration(self):
        tracker = self.tracker()
        proc = self.start_wait(run_ids=[tracker.id])
        time.sleep(.2)
        with tracker:
            tracker.finish({"status": "completed"})
            stdout, stderr = proc.communicate(timeout=2)
        self.assertEqual(proc.returncode, 0, stderr)
        self.assertEqual(json.loads(stdout)["ready"][0]["run_id"], tracker.id)

    def test_unknown_run_id_returns_attention(self):
        data = self.run_wait(run_ids=["00000000-0000-4000-8000-000000000009"], timeout=.1)
        self.assertEqual(data["event"], "attention")
        self.assertEqual(len(data["errors"]), 1)
        self.assertEqual(data["pending_run_ids"], [])
        self.assertIn("startup error", data["errors"][0]["error"])

    def test_run_id_rejects_other_task_before_reading_report(self):
        with self.tracker(task="00000000-0000-4000-8000-000000000002") as tracker:
            (Path(tracker.record["output_dir"]) / "report.md").write_text("OTHER TASK SECRET")
            tracker.finish({"status": "completed"})
            with patch.object(waiter, "completion", side_effect=AssertionError("Foreign report must not be read")):
                data = waiter.wait_for_runs(run_ids=[tracker.id], timeout=0)
            self.assertEqual(data["event"], "attention")
            self.assertEqual(data["ready"], [])
            self.assertNotIn("OTHER TASK SECRET", json.dumps(data))
            self.assertNotIn("output_dir", data["errors"][0])

    def test_monitor_key_allows_another_task_to_observe_without_changing_run(self):
        with self.tracker() as tracker:
            key = "authorized-monitor"
            tracker.record["watch_key_hash"] = hashlib.sha256(key.encode()).hexdigest()
            tracker.running(123)
            with patch.dict(os.environ, {"CODEX_THREAD_ID": "00000000-0000-4000-8000-000000000002"}):
                before = tracker.path.read_bytes()
                data = self.run_wait(run_ids=[tracker.id], watch_keys={tracker.id: key})
                self.assertEqual(data["event"], "waiting", data)
                self.assertEqual(data["pending_run_ids"], [tracker.id])
                self.assertEqual(tracker.path.read_bytes(), before)
                tracker.finish({"status": "completed", "report_excerpt": "Finished assignment"})
                before = tracker.path.read_bytes()
                data = self.run_wait(run_ids=[tracker.id], watch_keys={tracker.id: key})
                self.assertEqual(data["ready"][0]["report_excerpt"], "Finished assignment")
                self.assertEqual(tracker.path.read_bytes(), before)
                self.assertNotIn(key, json.dumps(data))
                self.assertNotIn("watch_key_hash", json.dumps(data))

    def test_monitor_key_cannot_observe_another_run_or_reveal_its_report(self):
        with self.tracker("authorized") as authorized, self.tracker("other") as other:
            other.finish({"status": "completed", "report_excerpt": "UNAUTHORIZED REPORT"})
            with patch.dict(os.environ, {"CODEX_THREAD_ID": "00000000-0000-4000-8000-000000000002"}):
                for key in ("incorrect-key", authorized.watch_key):
                    with self.subTest(key_is_from_other_run=key == authorized.watch_key):
                        data = self.run_wait(run_ids=[other.id], watch_keys={other.id: key})
                        self.assertEqual(data["event"], "attention", data)
                        self.assertEqual(data["ready"], [])
                        self.assertNotIn("UNAUTHORIZED REPORT", json.dumps(data))
                        self.assertNotIn(other.record["output_dir"], json.dumps(data))
                        self.assertNotIn(key, json.dumps(data))

    def test_monitor_wait_returns_completion_during_and_between_waits(self):
        with self.tracker("slow") as slow, self.tracker("fast") as fast:
            with patch.dict(os.environ, {"CODEX_THREAD_ID": "00000000-0000-4000-8000-000000000002"}):
                proc = self.start_wait(run_ids=[slow.id, fast.id],
                                       watch_keys={slow.id: slow.watch_key, fast.id: fast.watch_key})
                time.sleep(.2)
                self.assertIsNone(proc.poll())
                fast.finish({"status": "needs_review", "report_excerpt": "Needs attention"})
                stdout, stderr = proc.communicate(timeout=2)
                self.assertEqual(proc.returncode, 0, stderr)
                data = json.loads(stdout)
                self.assertEqual(data["ready"][0]["run_id"], fast.id)
                self.assertEqual(data["ready"][0]["status"], "needs_review")
                self.assertEqual(data["pending_run_ids"], [slow.id])
                slow.finish({"status": "completed"})
                data = self.run_wait(run_ids=data["pending_run_ids"], watch_keys={slow.id: slow.watch_key})
                self.assertEqual(data["ready"][0]["run_id"], slow.id)
                self.assertEqual(data["pending_run_ids"], [])

    def test_legacy_record_remains_owner_only(self):
        with self.tracker() as tracker:
            tracker.record.pop("watch_key_hash")
            tracker.finish({"status": "completed"})
            self.assertEqual(self.run_wait(run_ids=[tracker.id])["event"], "ready")
            with patch.dict(os.environ, {"CODEX_THREAD_ID": "00000000-0000-4000-8000-000000000002"}):
                data = self.run_wait(run_ids=[tracker.id], watch_keys={tracker.id: tracker.watch_key})
                self.assertEqual(data["event"], "attention", data)
                self.assertEqual(data["ready"], [])

    def test_monitor_observation_preserves_ownership_and_does_not_create_settings(self):
        # Observation must not reassign ownership or initialize the monitor's settings.
        with self.tracker() as tracker:
            tracker.finish({"status": "completed"})
            before = tracker.path.read_bytes()
            with patch.dict(os.environ, {"CODEX_THREAD_ID": "00000000-0000-4000-8000-000000000002"}):
                self.assertEqual(self.run_wait(run_ids=[tracker.id],
                    watch_keys={tracker.id: tracker.watch_key})["event"], "ready")
            self.assertEqual(tracker.path.read_bytes(), before)
            self.assertEqual(json.loads(before)["codex_thread_id"], TASK)
            self.assertFalse((paths.state_root() / "tasks").exists())

    def test_invalid_monitor_key_arguments_do_not_reveal_supplied_keys(self):
        with self.tracker() as tracker:
            for options in (("--watch-key", "PRIVATE-KEY"),
                            ("--watch-key", f"{tracker.id}="),
                            ("--watch-key", f"{tracker.id}=PRIVATE-KEY",
                             "--watch-key", f"{tracker.id}=PRIVATE-KEY"),
                            ("--watch-key", f"{TASK}=PRIVATE-KEY")):
                with self.subTest(options=options):
                    result = subprocess.run([*self.command(run_ids=[tracker.id]), *options],
                                            capture_output=True, text=True, timeout=3)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertNotIn("PRIVATE-KEY", result.stdout + result.stderr)
            result = subprocess.run(self.command(tracker.record["output_dir"],
                                   watch_keys={tracker.id: tracker.watch_key}),
                                   capture_output=True, text=True, timeout=3)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn(tracker.watch_key, result.stdout + result.stderr)

    def test_run_id_observes_cached_result_after_artifacts_are_removed(self):
        with self.tracker() as tracker:
            tracker.finish({"status": "completed", "report_excerpt": "Cached completion"})
        Path(tracker.record["output_dir"]).rmdir()
        ready = self.run_wait(run_ids=[tracker.id])["ready"][0]
        self.assertEqual(ready["report_excerpt"], "Cached completion")
        self.assertIsNone(ready["report_file"])

    def test_invalid_or_mixed_identifiers_are_rejected(self):
        for run_id in ("not-a-uuid", "../../private", "00000000000040008000000000000001"):
            with self.subTest(run_id=run_id):
                result = subprocess.run(self.command(run_ids=[run_id]), capture_output=True, text=True, timeout=3)
                self.assertEqual(result.returncode, 2)
                self.assertIn("Invalid run ID", result.stderr)
        for command in (self.command(), self.command(self.root / "run", run_ids=[TASK])):
            result = subprocess.run(command, capture_output=True, text=True, timeout=3)
            self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / "tafwid").exists())

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
        for status in ("completed", "blocked", "needs_review", "error", "timeout", "interrupted"):
            with self.subTest(status=status), self.tracker(status) as tracker:
                out = Path(tracker.record["output_dir"])
                (out / "report.md").write_text("Useful report " + "x" * 8000)
                (out / "input.txt").write_text("PRIVATE PROMPT NOT NEEDED FOR WAITING")
                tracker.finish({"status": status})
                data = self.run_wait(out)
                ready = data["ready"][0]
                self.assertEqual(ready["status"], status)
                self.assertLessEqual(len(ready["report_excerpt"]), 1000)
                self.assertTrue(ready["report_truncated"])
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
            tracker.finish({"status": "completed", "report_excerpt": "Cached completion"})
        report.unlink()
        out.rmdir()
        ready = self.run_wait(out)["ready"][0]
        self.assertEqual(ready["report_excerpt"], "Cached completion")
        self.assertIsNone(ready["report_file"])

    def test_stale_heartbeat_is_reported_without_claiming_worker_was_killed(self):
        tracker = self.tracker()
        tracker.record.update(status="running", updated_at=time.time() - 30)
        paths.atomic_json(tracker.path, tracker.record)
        ready = self.run_wait(tracker.record["output_dir"])["ready"][0]
        self.assertEqual(ready["status"], "interrupted")
        self.assertIn("stopped reporting", ready["status_note"])
        self.assertEqual(json.loads(tracker.path.read_text())["status"], "running")

    def test_duplicate_paths_do_not_repeat_completion(self):
        with self.tracker() as tracker:
            tracker.finish({"status": "completed"})
            out = tracker.record["output_dir"]
            self.assertEqual(len(self.run_wait(out, out)["ready"]), 1)

    def test_five_minute_wait_returns_early_on_completion(self):
        with self.tracker() as tracker:
            proc = self.start_wait(run_ids=[tracker.id], timeout=300)
            time.sleep(.2)
            self.assertIsNone(proc.poll())
            tracker.finish({"status": "completed"})
            stdout, stderr = proc.communicate(timeout=2)
            self.assertEqual(proc.returncode, 0, stderr)
            data = json.loads(stdout)
            self.assertEqual(data["ready"][0]["run_id"], tracker.id)
            self.assertLess(data["waited_seconds"], 2)

    def test_default_wait_keeps_running_worker_pending_for_five_minutes(self):
        clock = [0.0]

        def advance(seconds):
            clock[0] += seconds

        with self.tracker() as tracker:
            tracker.running(123)
            with patch.object(waiter.time, "monotonic", side_effect=lambda: clock[0]), \
                 patch.object(waiter.time, "sleep", side_effect=advance):
                data = waiter.wait_for_runs(run_ids=[tracker.id])
            self.assertEqual(data["event"], "waiting")
            self.assertEqual(data["waited_seconds"], 300)
            self.assertEqual(data["pending_run_ids"], [tracker.id])
            self.assertEqual(registry.load_record(tracker.id)["status"], "running")

    def test_invalid_wait_bounds_and_missing_identity_are_rejected(self):
        for timeout in (-1, 301, "nan", "inf"):
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
