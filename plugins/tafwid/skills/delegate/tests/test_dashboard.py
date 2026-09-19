import json
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import worker_registry as registry
import dashboard


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"CODEX_HOME": str(self.home)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.out = self.home / "run"
        self.out.mkdir()
        (self.out / "brief.md").write_text("Inspect the fixture")

    def tracker(self, **kwargs):
        return registry.Tracker(self.out, "thread-one", "session-one", "Fixture worker",
                                {"requested_model": "opus", "role": "reviewer"}, str(self.home), **kwargs)

    def test_conversation_titles_follow_renames_and_tolerate_partial_index(self):
        index = self.home / "session_index.jsonl"
        index.write_text('\n'.join([json.dumps({"id": "thread-one", "thread_name": "Old name", "updated_at": "2026-01-01T00:00:00Z"}),
            json.dumps({"id": "thread-one", "thread_name": "Example reader task", "updated_at": "2026-02-01T00:00:00Z"}),
            json.dumps({"id": "thread-one", "thread_name": "Stale name", "updated_at": "2025-01-01T00:00:00Z"}),
            json.dumps({"id": "unrelated", "thread_name": "Private unrelated conversation"}), '{partial']))
        with self.tracker() as tracker:
            tracker.finish({"status": "completed"})
        self.assertEqual(registry.list_runs()[0].get("conversation_title"), "Example reader task")
        self.assertEqual(registry.details(tracker.id).get("conversation_title"), "Example reader task")
        with index.open("a") as file:
            file.write('\n' + json.dumps({"id": "thread-one", "thread_name": "Renamed conversation", "updated_at": "2026-03-01T00:00:00Z"}))
        self.assertEqual(registry.list_runs()[0].get("conversation_title"), "Renamed conversation")
        self.assertNotIn("Private unrelated conversation", json.dumps(registry.list_runs()))

    def test_missing_conversation_index_keeps_worker_available(self):
        with self.tracker() as tracker:
            tracker.finish({"status": "completed"})
        self.assertIsNone(registry.list_runs()[0].get("conversation_title"))
        self.assertEqual(registry.details(tracker.id)["title"], "Fixture worker")

    def test_worker_history_keeps_ordered_exchanges_and_excludes_other_conversations(self):
        (self.out / "input.txt").write_text("Exact initial instructions")
        with self.tracker() as first:
            (self.out / "report.md").write_text("First reply")
            first.finish({"status": "needs_review"})
        resumed = self.home / "resumed"
        resumed.mkdir()
        (resumed / "input.txt").write_text("Correct the reviewed finding")
        with registry.Tracker(resumed, "thread-one", "session-one", "Correction", {}, str(self.home)) as second:
            (resumed / "report.md").write_text("Correction verified")
            second.finish({"status": "completed"})
        with registry.Tracker(resumed, "other-thread", "session-one", "Unrelated", {}, str(self.home)) as other:
            other.finish({"status": "completed"})
        # Cached exchanges remain available after temporary run artifacts disappear.
        for name in ("input.txt", "report.md"):
            (self.out / name).unlink()
        detail = registry.details(second.id)
        history = detail.get("runs", [])
        self.assertEqual([r["id"] for r in history], [first.id, second.id])
        self.assertEqual(history[0]["documents"]["input"], "Exact initial instructions")
        self.assertEqual(history[0]["documents"]["report"], "First reply")
        self.assertEqual(history[1]["documents"]["input"], "Correct the reviewed finding")
        self.assertNotIn("runs", history[0])

    def test_running_and_completed_records_keep_separate_attempts(self):
        with self.tracker() as tracker:
            tracker.running(123)
            active = registry.list_runs("thread-one")
            self.assertEqual(active[0]["status"], "running")
            self.assertEqual(active[0]["model_selection"]["requested_model"], "opus")
            (self.out / "report.md").write_text("Verified")
            tracker.finish({"status": "completed", "models_used": ["claude-opus-5"]})
        with self.tracker() as other:
            other.finish({"status": "blocked"})
        self.assertNotEqual(tracker.id, other.id)
        self.assertEqual(len(registry.list_runs()), 2)
        self.assertEqual(registry.list_runs("unrelated"), [])
        record = registry.details(tracker.id)
        self.assertEqual(record["documents"]["report"], "Verified")
        (self.out / "report.md").unlink()
        self.assertEqual(registry.details(tracker.id)["documents"]["report"], "Verified")

    def test_exception_records_failure_and_stale_heartbeat_is_not_running(self):
        with self.assertRaises(RuntimeError):
            with self.tracker() as tracker:
                raise RuntimeError("fixture error")
        self.assertEqual(registry.details(tracker.id)["status"], "error")
        path = registry.state_root() / "workers" / (tracker.id + ".json")
        record = json.loads(path.read_text())
        record.update(status="running", updated_at=time.time() - 60, ended_at=None)
        registry.atomic_json(path, record)
        self.assertEqual(registry.details(tracker.id)["status"], "interrupted")

    def test_registry_failure_does_not_fail_the_worker(self):
        with patch.object(registry, "atomic_json", side_effect=OSError("disk full")), contextlib.redirect_stderr(io.StringIO()) as warning:
            with self.tracker() as tracker:
                tracker.running(123)
                tracker.finish({"status": "completed"})
        self.assertIn("Dashboard recording unavailable", warning.getvalue())

    def test_import_is_idempotent_and_missing_artifacts_are_explained(self):
        (self.out / "summary.json").write_text(json.dumps({"status": "completed", "session_id": "session-one",
            "codex_thread_id": "thread-one", "cwd": str(self.home), "report_excerpt": "Saved report"}))
        first = registry.import_run(self.out, "Imported fixture")
        second = registry.import_run(self.out, "Imported fixture")
        self.assertEqual(first, second)
        self.assertEqual(len(registry.list_runs()), 1)
        self.assertEqual(registry.details(first)["documents"]["report"], "Saved report")

    def test_documents_are_bounded_and_external_symlinks_are_not_read(self):
        private = self.home / "private.txt"
        private.write_text("do-not-expose")
        (self.out / "stderr.log").symlink_to(private)
        (self.out / "report.md").write_text("x" * 200000)
        with self.tracker() as tracker:
            tracker.finish({"status": "completed"})
        docs = registry.details(tracker.id)["documents"]
        self.assertNotIn("do-not-expose", docs["stderr"])
        self.assertLess(len(docs["report"]), 70000)
        with self.assertRaises(ValueError):
            registry.details("../../private")

    def test_http_requires_token_and_rejects_foreign_origin_and_paths(self):
        with self.tracker() as tracker:
            tracker.finish({"status": "completed"})
        server = dashboard.make_server("test-token")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = "http://127.0.0.1:" + str(server.server_port)
        def get(path, token=True, extra=None):
            headers = {"Authorization": "Bearer test-token"} if token else {}
            headers.update(extra or {})
            return urlopen(Request(base + path, headers=headers), timeout=2)
        with self.assertRaises(HTTPError) as missing:
            get("/api/runs", False)
        self.assertEqual(missing.exception.code, 401)
        missing.exception.close()
        with self.assertRaises(HTTPError) as missing_activity:
            get("/api/activity?thread=thread-one", False)
        self.assertEqual(missing_activity.exception.code, 401)
        missing_activity.exception.close()
        with self.assertRaises(HTTPError) as unrelated_activity:
            get("/api/activity?thread=aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        self.assertEqual(unrelated_activity.exception.code, 404)
        unrelated_activity.exception.close()
        with get("/api/runs?thread=thread-one") as response:
            self.assertEqual(len(json.load(response)["runs"]), 1)
        for headers in ({"Origin": "https://example.com"}, {"Host": "attacker.example"}):
            with self.assertRaises(HTTPError) as foreign:
                get("/api/runs", extra=headers)
            self.assertEqual(foreign.exception.code, 403)
            foreign.exception.close()
        with self.assertRaises(HTTPError) as traversal:
            get("/api/runs/../../private.txt")
        self.assertIn(traversal.exception.code, (400, 404))
        traversal.exception.close()
        with get("/") as page:
            self.assertIn("Content-Security-Policy", page.headers)
            self.assertNotIn(b"test-token", page.read())

    def test_message_endpoint_returns_only_registered_task_request_previews(self):
        task='12345678-1234-4234-8234-123456789abc'
        with registry.Tracker(self.out, task, 'session-one', 'Fixture', {}, str(self.home)) as tracker:
            tracker.finish({'status':'completed'})
        path=self.home/'sessions'/f'rollout-test-{task}.jsonl'
        path.parent.mkdir()
        path.write_text(json.dumps({'type':'session_meta','payload':{'id':task}})+'\n'+json.dumps({
            'type':'response_item','timestamp':'2026-09-17T10:00:00Z','payload':{'type':'message','role':'user',
            'content':[{'type':'input_text','text':'work on slice 2'}]}})+'\n')
        server=dashboard.make_server('test-token')
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base='http://127.0.0.1:'+str(server.server_port)+'/api/messages?thread='
        with urlopen(Request(base+task,headers={'Authorization':'Bearer test-token'})) as response:
            data=json.load(response)
        self.assertEqual(data['messages'][0]['preview'],'work on slice 2')
        self.assertNotIn('events',data)
        for requested,headers,code in [(task,{},401),('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',{'Authorization':'Bearer test-token'},404)]:
            with self.assertRaises(HTTPError) as error:urlopen(Request(base+requested,headers=headers))
            self.assertEqual(error.exception.code,code);error.exception.close()


if __name__ == "__main__":
    unittest.main()
