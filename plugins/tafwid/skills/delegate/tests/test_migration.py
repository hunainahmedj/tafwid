"""Legacy state moves only on request, completely, and is restored on failure."""
import errno
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
import accounts
import migration
import paths
import settings

TASK = "00000000-0000-4000-8000-000000000001"
RUN = "00000000-0000-4000-8000-000000000002"


class MigrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.codex = self.root / "codex"
        self.neutral = self.root / "user" / ".tafwid" / "state"
        env = patch.dict(os.environ, {"CODEX_HOME": str(self.codex), "TAFWID_HOST": "codex",
                                      "TAFWID_HOME": str(self.neutral.parent)})
        env.start()
        self.addCleanup(env.stop)
        self.legacy = self.codex / "tafwid" / "state"

    def legacy_install(self):
        self.legacy.mkdir(parents=True)  # an existing pre-0.4 installation
        self.account = accounts.create("work", "business")
        settings.save({**settings.defaults(), "permission_policy": "inherit"})
        (self.legacy / "workers").mkdir()
        (self.legacy / "workers" / (RUN + ".json")).write_text(json.dumps(
            {"id": RUN, "codex_thread_id": TASK, "status": "completed", "output_dir": str(self.root / "run")}))
        self.assertEqual(paths.legacy_in_use(), self.legacy)

    def snapshot(self, root):
        return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}

    def test_nothing_to_migrate_on_a_fresh_install(self):
        self.assertEqual(migration.migrate()["event"], "nothing_to_migrate")
        self.assertFalse(self.neutral.parent.exists())

    def test_dry_run_reports_and_changes_nothing(self):
        self.legacy_install()
        before = self.snapshot(self.legacy)
        result = migration.migrate(dry_run=True)
        self.assertEqual(result["event"], "dry_run")
        self.assertEqual((result["accounts"], result["runs"]), (1, 1))
        self.assertEqual(self.snapshot(self.legacy), before)
        self.assertFalse(self.neutral.exists())

    def test_migrate_moves_state_and_keeps_accounts_usable(self):
        self.legacy_install()
        self.neutral.parent.mkdir(parents=True)  # ~/.tafwid may already exist without state
        result = migration.migrate()
        self.assertEqual(result["event"], "migrated")
        self.assertFalse(self.legacy.exists())
        self.assertEqual(paths.state_root(), self.neutral)
        self.assertIsNone(paths.legacy_in_use())
        row = accounts.get("work")
        self.assertEqual(Path(row["home"]), self.neutral / "accounts" / "homes" / self.account["id"])
        self.assertEqual(accounts.validate_home(row), Path(row["home"]))
        self.assertEqual(settings.read()["permission_policy"], "inherit")
        self.assertEqual(self.neutral.parent.stat().st_mode & 0o077, 0)

    def test_cross_filesystem_move_copies_verifies_and_removes(self):
        self.legacy_install()
        names = set(self.snapshot(self.legacy))
        with patch.object(migration.os, "rename", side_effect=OSError(errno.EXDEV, "cross-device")):
            self.assertEqual(migration.migrate()["event"], "migrated")
        self.assertFalse(self.legacy.exists())
        self.assertEqual(set(self.snapshot(self.neutral)), names)
        home = Path(accounts.get("work")["home"])
        self.assertEqual(home.stat().st_mode & 0o777, 0o700)
        self.assertEqual(accounts.validate_home(accounts.get("work")), home)

    def test_active_worker_blocks_migration(self):
        self.legacy_install()
        (self.legacy / "workers" / (RUN + ".json")).write_text(json.dumps(
            {"id": RUN, "status": "running", "updated_at": time.time(), "output_dir": str(self.root / "run")}))
        with self.assertRaisesRegex(ValueError, RUN):
            migration.migrate()
        self.assertTrue(self.legacy.exists())
        self.assertFalse(self.neutral.exists())

    def test_failure_after_the_move_restores_the_source(self):
        self.legacy_install()
        registry = self.legacy / "accounts" / "registry.json"
        registry.write_text("{not json")
        before = self.snapshot(self.legacy)
        with self.assertRaises(ValueError):
            migration.migrate()
        self.assertEqual(self.snapshot(self.legacy), before)
        self.assertFalse(self.neutral.exists())

    def test_redirected_source_is_refused(self):
        real = self.root / "elsewhere"
        real.mkdir()
        self.legacy.parent.mkdir(parents=True)
        self.legacy.symlink_to(real)
        with self.assertRaisesRegex(ValueError, "redirected"):
            migration.migrate()

    def test_cli_reports_json(self):
        self.legacy_install()
        command = [sys.executable, settings.__file__, "migrate"]
        dry = subprocess.run([*command, "--dry-run"], capture_output=True, text=True)
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertEqual(json.loads(dry.stdout)["event"], "dry_run")
        done = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(json.loads(done.stdout)["event"], "migrated")
        again = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(json.loads(again.stdout)["event"], "nothing_to_migrate")


if __name__ == "__main__":
    unittest.main()
