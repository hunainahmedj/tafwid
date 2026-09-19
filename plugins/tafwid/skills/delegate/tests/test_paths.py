import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import session
import settings
import worker_registry as registry


class StatePathsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        env = patch.dict(os.environ, {"CODEX_HOME": str(self.home)})
        env.start()
        self.addCleanup(env.stop)

    def test_new_install_uses_neutral_state_without_creating_it_on_read(self):
        expected = self.home / "state" / "tafwid"
        self.assertEqual(registry.state_root(), expected)
        self.assertEqual(session.state_path("task"), expected / "task.json")
        self.assertFalse(expected.exists())

    def test_existing_install_reuses_legacy_history_and_settings(self):
        legacy = self.home / "state" / "claude-delegate"
        legacy.mkdir(parents=True)
        config = legacy / "settings.json"
        config.write_text('{"version":1,"permission_policy":"inherit"}')
        task_id = "00000000-0000-4000-8000-000000000001"
        run_id = "00000000-0000-4000-8000-000000000002"
        (legacy / (task_id + ".json")).write_text(json.dumps(
            {"version": 1, "thread_id": task_id, "enabled": True}))
        (legacy / "workers").mkdir()
        (legacy / "workers" / (run_id + ".json")).write_text(json.dumps(
            {"id": run_id, "codex_thread_id": task_id, "status": "completed",
             "output_dir": str(self.home / "old-run"), "started_at": 1}))
        before = {p: p.read_bytes() for p in legacy.rglob("*") if p.is_file()}
        self.assertEqual(registry.state_root(), legacy)
        self.assertEqual(session.state_path("task"), legacy / "task.json")
        self.assertEqual(settings.read()["permission_policy"], "inherit")
        with patch.dict(os.environ, {"CODEX_THREAD_ID": task_id}):
            self.assertEqual(session.status(), {"thread_id": task_id, "enabled": True})
        self.assertEqual([r["id"] for r in registry.list_runs(task_id)], [run_id])
        self.assertEqual(before, {p: p.read_bytes() for p in legacy.rglob("*") if p.is_file()})
        self.assertFalse((self.home / "state" / "tafwid").exists())

    def test_conflicting_histories_fail_without_picking_or_merging(self):
        for name in ("tafwid", "claude-delegate"):
            path = self.home / "state" / name
            path.mkdir(parents=True)
            (path / "settings.json").write_text(name)
        with self.assertRaisesRegex(ValueError, "Both"):
            registry.state_root()
        with self.assertRaisesRegex(ValueError, "Both"):
            session.state_path("task")
        for name in ("tafwid", "claude-delegate"):
            self.assertEqual((self.home / "state" / name / "settings.json").read_text(), name)


if __name__ == "__main__":
    unittest.main()
