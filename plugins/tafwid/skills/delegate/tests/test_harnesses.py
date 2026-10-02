"""Readiness routing and process failures must not corrupt session state."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import claude_code
import harnesses
import session

TASK = "00000000-0000-4000-8000-000000000001"


class ReadyFixture:
    """A harness with no Claude installation or authentication dependency."""

    @staticmethod
    def check_ready(*, cwd=None):
        return {"executable": "fixture-worker"}


class HarnessTests(unittest.TestCase):
    def setUp(self):
        mask = os.umask(0o077)
        os.umask(mask)
        self.addCleanup(os.umask, mask)
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        self.root = Path(home.name)
        env = patch.dict(os.environ, {
            "CODEX_HOME": str(self.root), "CODEX_THREAD_ID": TASK, "PATH": "",
            "TAFWID_HOME": str(self.root / "tafwid"), "TAFWID_HOST": "codex",
        })
        env.start()
        self.addCleanup(env.stop)
        for name in claude_code.OVERRIDES:
            os.environ.pop(name, None)

    def test_named_gpt_readiness_uses_selected_account(self):
        account = {"id": "id", "name": "work", "kind": "business", "status": "ready", "home": "/private"}
        with patch.object(harnesses.codex_cli, "check_ready", return_value={"executable": "codex"}) as check:
            result = harnesses.check_ready("gpt", account=account)
        self.assertEqual(result["executable"], "codex")
        check.assert_called_once_with(account, cwd=None)

    def test_unknown_default_does_not_enable_or_fall_back(self):
        with patch.object(harnesses, "DEFAULT_HARNESS", "unsupported"):
            with self.assertRaisesRegex(ValueError, "Unsupported worker harness"):
                harnesses.check_ready()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_auth_process_failures_return_safe_json_without_writing_state(self):
        failures = (
            subprocess.TimeoutExpired(
                ["claude", "auth", "status"], 30,
                output="PRIVATE AUTH OUTPUT", stderr="PRIVATE AUTH OUTPUT",
            ),
            OSError("PRIVATE AUTH OUTPUT"),
            UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid byte"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                stderr = io.StringIO()
                with (
                    patch.object(claude_code.shutil, "which", return_value="/fake/claude"),
                    patch.object(claude_code.subprocess, "run", side_effect=failure),
                    patch.object(sys, "argv", ["session.py", "on"]),
                    contextlib.redirect_stderr(stderr),
                ):
                    code = session.main()
                self.assertEqual(code, 2)
                error = json.loads(stderr.getvalue())["error"]
                self.assertIn("claude auth status", error)
                self.assertNotIn("PRIVATE AUTH OUTPUT", error)
                self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
