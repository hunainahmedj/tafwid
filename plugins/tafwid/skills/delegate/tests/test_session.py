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
OVERRIDES = (
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
)
FAKE_AUTH = r'''
import json, os, sys
from pathlib import Path
assert sys.argv[1:] == ["auth", "status"], "Readiness must not launch or log in"
Path(os.environ["AUTH_MARKER"]).write_text("checked")
case = os.environ.get("AUTH_CASE", "ready")
if case == "failed":
    print("PRIVATE AUTH OUTPUT", file=sys.stderr)
    sys.exit(1)
if case == "malformed":
    print("PRIVATE AUTH OUTPUT")
    sys.exit(0)
print(json.dumps({
    "loggedIn": case != "logged_out",
    "authMethod": "api_key" if case == "api" else "claude.ai",
    "apiProvider": "firstParty",
    "subscriptionType": "max",
}))
'''


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "codex"
        self.env = {k: v for k, v in os.environ.items() if k not in ("CODEX_THREAD_ID", "CODEX_SESSION_ID")}
        self.env["CODEX_HOME"] = str(self.home)
        self.env["TAFWID_HOME"] = str(self.home / "tafwid")
        self.env["TAFWID_HOST"] = "codex"
        self.bin = Path(self.temp.name) / "bin"
        self.bin.mkdir()
        self.claude = self.bin / "claude"
        self.claude.write_text(f"#!{sys.executable}\n" + FAKE_AUTH)
        self.claude.chmod(0o700)
        self.marker = Path(self.temp.name) / "auth-checked"
        # Only the fake executable is discoverable; never use the developer's CLI.
        self.env["PATH"] = str(self.bin)
        self.env["AUTH_MARKER"] = str(self.marker)
        self.env["AUTH_CASE"] = "ready"
        for name in OVERRIDES:
            self.env.pop(name, None)

    def call(self, action, thread=A, cwd=None):
        env = dict(self.env)
        if thread is not None:
            env["CODEX_THREAD_ID"] = thread
        return subprocess.run([sys.executable, str(SCRIPT), action], cwd=cwd,
                              env=env, text=True, capture_output=True, timeout=5)

    def test_on_checks_authentication_before_enabling(self):
        result = self.call("on")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.marker.exists())
        self.assertEqual(json.loads(result.stdout), {"thread_id": A, "enabled": True})

    def test_on_claude_saves_task_harness_without_changing_global_defaults(self):
        result = subprocess.run([sys.executable, str(SCRIPT), 'on', 'claude'],
                                env={**self.env, 'CODEX_THREAD_ID': A}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        root = self.home / 'tafwid/state'
        data = json.loads((root / 'tasks' / A / 'settings.json').read_text())
        self.assertEqual(data['harness'], 'claude')
        self.assertFalse((root / 'settings.json').exists())
        before = (root / 'tasks' / A / 'settings.json').read_bytes()
        self.assertEqual(self.call('off').returncode, 0)
        self.assertEqual(self.call('on').returncode, 0)
        self.assertEqual((root / 'tasks' / A / 'settings.json').read_bytes(), before)

    def test_failed_harness_selection_preserves_task_settings(self):
        self.assertEqual(self.call('on').returncode, 0)
        path = self.home / 'tafwid/state/tasks' / A / 'settings.json'
        self.assertTrue(path.exists())
        before = path.read_bytes()
        self.env['AUTH_CASE'] = 'logged_out'
        result = subprocess.run([sys.executable, str(SCRIPT), 'on', 'claude'],
                                env={**self.env, 'CODEX_THREAD_ID': A}, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(path.read_bytes(), before)

    def test_missing_installation_does_not_enable_or_create_state(self):
        self.claude.unlink()
        result = self.call("on")
        self.assertEqual(result.returncode, 2, result.stderr)
        error = json.loads(result.stderr)["error"]
        self.assertIn("install", error.lower())
        self.assertIn("Claude", error)
        self.assertFalse(self.home.exists())

    def test_auth_failures_do_not_enable_or_expose_command_output(self):
        for case in ("logged_out", "api", "failed", "malformed"):
            with self.subTest(case=case):
                self.env["AUTH_CASE"] = case
                result = self.call("on")
                self.assertEqual(result.returncode, 2, result.stderr)
                error = json.loads(result.stderr)["error"]
                self.assertTrue(error)
                if case in ("logged_out", "api", "failed"):
                    self.assertIn("claude auth login", error)
                self.assertNotIn("PRIVATE AUTH OUTPUT", result.stdout + result.stderr)
                self.assertFalse(self.home.exists())

    def test_off_status_and_help_never_require_authentication(self):
        self.claude.unlink()
        for action in ("status", "off", "--help"):
            with self.subTest(action=action):
                result = self.call(action)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(self.marker.exists())

    def test_failed_reactivation_preserves_existing_switch(self):
        self.assertEqual(self.call("on").returncode, 0)
        state = self.home / "tafwid" / "state" / (A + ".json")
        before = state.read_bytes()
        self.env["AUTH_CASE"] = "logged_out"
        result = self.call("on")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(state.read_bytes(), before)
        self.assertEqual(self.call("off").returncode, 0)
        self.assertFalse(json.loads(self.call("status").stdout)["enabled"])

    def test_api_override_blocks_activation_without_exposing_its_value(self):
        self.env["ANTHROPIC_API_KEY"] = "PRIVATE OVERRIDE VALUE"
        result = self.call("on")
        self.assertEqual(result.returncode, 2)
        self.assertIn("ANTHROPIC_API_KEY", result.stderr)
        self.assertNotIn("PRIVATE OVERRIDE VALUE", result.stderr)
        self.assertFalse(self.home.exists())
        self.assertFalse(self.marker.exists())

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
        state = self.home / "tafwid" / "state" / (A + ".json")
        state.write_text('{"enabled": "false"}')
        self.assertNotEqual(self.call("status").returncode, 0)
        self.assertEqual(self.call("off").returncode, 0)
        self.assertFalse(json.loads(self.call("status").stdout)["enabled"])

    def test_bad_identity_cannot_escape_state_directory(self):
        self.assertNotEqual(self.call("on", "../../outside").returncode, 0)
        self.assertFalse(self.home.exists())


if __name__ == "__main__":
    unittest.main()
