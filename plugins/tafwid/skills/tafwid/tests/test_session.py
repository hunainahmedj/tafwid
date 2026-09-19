"""Task-local state must survive processes and remain isolated between chats."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "session.py"
A = "00000000-0000-4000-8000-000000000001"
B = "00000000-0000-4000-8000-000000000002"


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "codex"
        self.env = {k: v for k, v in os.environ.items() if k not in ("CODEX_THREAD_ID", "CODEX_SESSION_ID")}
        self.env["CODEX_HOME"] = str(self.home)

    def call(self, action, thread=A, cwd=None):
        env = dict(self.env)
        if thread is not None:
            env["CODEX_THREAD_ID"] = thread
        return subprocess.run([sys.executable, str(SCRIPT), action], cwd=cwd,
                              env=env, text=True, capture_output=True)

    def test_missing_state_is_off_without_writing_files(self):
        result = self.call("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["enabled"])
        self.assertFalse(self.home.exists())

    def test_switch_persists_across_processes_and_directories(self):
        result = self.call("on")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(self.call("status", cwd="/").stdout)["enabled"])
        self.assertEqual(self.call("off").returncode, 0)
        self.assertFalse(json.loads(self.call("status").stdout)["enabled"])

    def test_another_chat_or_fork_defaults_off(self):
        self.assertEqual(self.call("on", A).returncode, 0)
        self.assertFalse(json.loads(self.call("status", B).stdout)["enabled"])
        self.assertTrue(json.loads(self.call("status", A).stdout)["enabled"])

    def test_turning_one_chat_off_preserves_another(self):
        self.assertEqual(self.call("on", A).returncode, 0)
        self.assertEqual(self.call("on", B).returncode, 0)
        self.assertEqual(self.call("off", A).returncode, 0)
        self.assertTrue(json.loads(self.call("status", B).stdout)["enabled"])

    def test_missing_identity_is_off_and_cannot_be_enabled(self):
        result = self.call("status", None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["enabled"])
        self.assertNotEqual(self.call("on", None).returncode, 0)
        self.assertFalse(self.home.exists())

    def test_thread_identity_wins_over_session_fallback(self):
        self.env["CODEX_SESSION_ID"] = B
        self.assertEqual(self.call("on", A).returncode, 0)
        self.assertFalse(json.loads(self.call("status", None).stdout)["enabled"])

    def test_malformed_state_is_not_treated_as_enabled(self):
        self.assertEqual(self.call("on").returncode, 0)
        state = self.home / "state" / "tafwid" / (A + ".json")
        state.write_text('{"enabled": "false"}')
        self.assertNotEqual(self.call("status").returncode, 0)
        self.assertEqual(self.call("off").returncode, 0)
        self.assertFalse(json.loads(self.call("status").stdout)["enabled"])

    def test_bad_identity_cannot_escape_state_directory(self):
        self.assertNotEqual(self.call("on", "../../outside").returncode, 0)
        self.assertFalse(self.home.exists())


if __name__ == "__main__":
    unittest.main()
