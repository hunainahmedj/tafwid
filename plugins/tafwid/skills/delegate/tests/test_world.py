import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import world


class WorldTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        env = patch.dict(os.environ, {"CODEX_HOME": str(self.home / "codex"),
                                      "TAFWID_HOME": str(self.home / "tafwid")})
        env.start()
        self.addCleanup(env.stop)

    def test_disabled_by_default(self):
        self.assertFalse(world.enabled())
        self.assertFalse(world.world_dir().exists())
        self.assertEqual(world.status()["enabled"], False)

    def test_on_creates_marker_with_private_dir(self):
        result = world.enable()
        self.assertTrue(world.enabled())
        self.assertTrue(result["enabled"])
        self.assertTrue((world.world_dir() / "enabled").is_file())
        self.assertEqual(world.world_dir().stat().st_mode & 0o777, 0o700)

    def test_off_removes_marker(self):
        world.enable()
        result = world.disable()
        self.assertFalse(world.enabled())
        self.assertFalse(result["enabled"])
        self.assertFalse((world.world_dir() / "enabled").exists())
        self.assertFalse(world.disable()["enabled"])

    def test_uses_neutral_home_even_with_legacy_state(self):
        legacy = self.home / "codex" / "state" / "claude-delegate"
        legacy.mkdir(parents=True)
        self.assertEqual(world.world_dir(), self.home / "tafwid" / "state" / "world")
        world.enable()
        self.assertTrue((self.home / "tafwid" / "state" / "world" / "enabled").exists())
        self.assertFalse((legacy / "world").exists())

    def test_hash_is_stable_and_salt_private(self):
        first = world.hash_id("session-1")
        self.assertRegex(first, r"^[0-9a-f]{16}$")
        self.assertEqual(world.hash_id("session-1"), first)
        self.assertNotEqual(world.hash_id("session-2"), first)
        salt = world.world_dir() / "salt"
        self.assertEqual(salt.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(salt.read_bytes()), 32)
        salt.write_bytes(b"x" * 32)
        self.assertNotEqual(world.hash_id("session-1"), first)

    def test_append_writes_one_json_line_with_version_and_time(self):
        world.enable()
        before = time.time()
        world.append_event({"kind": "tool", "agent": "abc"})
        world.append_event({"kind": "stop"})
        files = list(world.world_dir().glob("events-*.jsonl"))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)
        lines = files[0].read_text().splitlines()
        self.assertEqual(len(lines), 2)
        event = json.loads(lines[0])
        self.assertEqual(event["v"], 1)
        self.assertGreaterEqual(event["t"], before)
        self.assertEqual(event["kind"], "tool")
        self.assertEqual(world.status()["today_events"], 2)

    def test_prune_deletes_files_older_than_7_days(self):
        world.enable()
        now = time.time()
        old = world.world_dir() / "events-2000-01-01.jsonl"
        recent = world.world_dir() / "events-2000-01-02.jsonl"
        old.write_text("{}\n")
        recent.write_text("{}\n")
        os.utime(old, (now - 8 * 86400, now - 8 * 86400))
        os.utime(recent, (now - 6 * 86400, now - 6 * 86400))
        world.prune(now)
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

    def test_error_log_capped_at_100_lines(self):
        world.enable()
        for index in range(130):
            world.log_error("failure %d" % index)
        lines = (world.world_dir() / "hook-errors.log").read_text().splitlines()
        self.assertEqual(len(lines), 100)
        self.assertTrue(lines[-1].endswith("failure 129"))
        self.assertTrue(lines[0].endswith("failure 30"))

    def test_short_or_empty_salt_is_never_used(self):
        world.enable()
        salt = world.world_dir() / "salt"
        for bad in (b"", b"short"):
            salt.write_bytes(bad)
            value = world.hash_id("x")
            self.assertRegex(value, r"^[0-9a-f]{16}$")
            self.assertEqual(len(salt.read_bytes()), 32)
            self.assertEqual(salt.stat().st_mode & 0o777, 0o600)
            self.assertEqual(world.hash_id("x"), value)

    def test_concurrent_first_use_hash_agrees(self):
        code = ("import sys; sys.path.insert(0, %r); import world; print(world.hash_id('same'))"
                % str(SCRIPTS))
        procs = [subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
                 for _ in range(8)]
        outputs = [proc.communicate()[0].strip() for proc in procs]
        self.assertTrue(all(proc.returncode == 0 for proc in procs))
        self.assertEqual(len(set(outputs)), 1, outputs)
        self.assertRegex(outputs[0], r"^[0-9a-f]{16}$")
        salt = world.world_dir() / "salt"
        self.assertEqual(len(salt.read_bytes()), 32)
        self.assertEqual(salt.stat().st_mode & 0o777, 0o600)
        self.assertEqual(world.hash_id("same"), outputs[0])
        self.assertEqual([p.name for p in world.world_dir().iterdir() if p.name.startswith(".salt-")], [])

    def test_concurrent_log_error_never_raises_and_stays_capped(self):
        failures = []

        def work(worker):
            try:
                for index in range(30):
                    world.log_error("worker %d failure %d" % (worker, index))
            except BaseException as error:
                failures.append(error)

        threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(failures, [])
        lines = (world.world_dir() / "hook-errors.log").read_text().splitlines()
        self.assertLessEqual(len(lines), 100)
        self.assertGreater(len(lines), 0)
        self.assertEqual([p.name for p in world.world_dir().iterdir() if p.name.startswith(".errors-")], [])

    def test_log_error_survives_damaged_log_and_caps_message(self):
        world.enable()
        log = world.world_dir() / "hook-errors.log"
        log.write_bytes(b"ok line\n\xff\xfe broken\n")
        world.log_error("x" * 5000)
        lines = log.read_text(errors="replace").splitlines()
        self.assertLessEqual(len(lines[-1]), 20 + 1 + 500)
        with patch.object(tempfile, "mkstemp", side_effect=OSError("disk full")):
            world.log_error("never raises")

    def test_cli_status_json(self):
        script = str(SCRIPTS / "world.py")
        out = subprocess.run([sys.executable, script, "status"], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertEqual(data["enabled"], False)
        self.assertEqual(data["dir"], str(self.home / "tafwid" / "state" / "world"))
        self.assertEqual(data["today_events"], 0)
        on = subprocess.run([sys.executable, script, "on"], capture_output=True, text=True)
        self.assertEqual(on.returncode, 0)
        self.assertTrue(json.loads(on.stdout)["enabled"])
        off = subprocess.run([sys.executable, script, "off"], capture_output=True, text=True)
        self.assertFalse(json.loads(off.stdout)["enabled"])
        bad = subprocess.run([sys.executable, script, "bogus"], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
