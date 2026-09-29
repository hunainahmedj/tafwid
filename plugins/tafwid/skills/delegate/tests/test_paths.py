import itertools
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
import run_state as registry


class StatePathsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        env = patch.dict(os.environ, {"CODEX_HOME": str(self.home)})
        env.start()
        self.addCleanup(env.stop)

    def test_new_install_uses_tafwid_state_without_creating_it_on_read(self):
        expected = self.home / "tafwid" / "state"
        self.assertEqual(registry.state_root(), expected)
        self.assertEqual(session.state_path("task"), expected / "task.json")
        self.assertEqual(settings.settings_file(), expected / "settings.json")
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
        self.assertFalse((self.home / "tafwid" / "state").exists())

    def test_previous_tafwid_location_is_reused_without_creating_a_second_store(self):
        old = self.home / "state" / "tafwid"
        old.mkdir(parents=True)
        config = old / "settings.json"
        config.write_text('{"version":1,"permission_policy":"inherit"}')
        before = config.read_bytes()
        self.assertEqual(registry.state_root(), old)
        self.assertEqual(settings.read()["permission_policy"], "inherit")
        self.assertEqual(config.read_bytes(), before)
        self.assertFalse((self.home / "tafwid" / "state").exists())

    def test_existing_new_location_is_used(self):
        current = self.home / "tafwid" / "state"
        current.mkdir(parents=True)
        (current / "settings.json").write_text(
            '{"version":1,"permission_policy":"full"}'
        )
        self.assertEqual(settings.read()["permission_policy"], "full")
        self.assertEqual(session.state_path("task"), current / "task.json")
        self.assertFalse((self.home / "state").exists())

    def test_conflicting_histories_fail_without_picking_or_merging(self):
        locations = ("tafwid/state", "state/tafwid", "state/claude-delegate")
        for index, pair in enumerate(itertools.combinations(locations, 2)):
            with self.subTest(pair=pair):
                home = self.home / str(index)
                for name in pair:
                    directory = home / name
                    directory.mkdir(parents=True)
                    (directory / "settings.json").write_text(name)
                with patch.dict(os.environ, {"CODEX_HOME": str(home)}):
                    with self.assertRaisesRegex(ValueError, "state directories"):
                        registry.state_root()
                    with self.assertRaises(ValueError):
                        session.state_path("task")
                for name in pair:
                    self.assertEqual((home / name / "settings.json").read_text(), name)


if __name__ == "__main__":
    unittest.main()
