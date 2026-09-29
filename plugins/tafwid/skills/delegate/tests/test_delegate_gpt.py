"""Offline GPT dispatch keeps the selected account, task, and workspace."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import accounts

TASK = "00000000-0000-4000-8000-000000000001"
SESSION = "00000000-0000-4000-8000-000000000003"
FAKE = '''#!PYTHON_PATH
import json, os, pathlib, sys
args = sys.argv[1:]
if args[:2] == ["login", "status"]:
    print("Logged in using ChatGPT")
    sys.exit(0)
if args[0] != "exec":
    sys.exit(9)
pathlib.Path(os.environ["CALLS"]).write_text(json.dumps({"args": args, "home": os.environ["CODEX_HOME"],
    "prompt": sys.stdin.read(), "workspace": os.getcwd()}))
output = pathlib.Path(args[args.index("-o") + 1])
case = os.environ.get("CASE", "success")
if case != "missing":
    output.write_text(json.dumps({"status": "blocked" if case == "blocked" else "completed", "report": "Done"}))
print(json.dumps({"type": "thread.started", "thread_id": "SESSION_ID"}))
print(json.dumps({"type": "turn.completed" if case != "quota" else "turn.failed"}))
sys.exit(1 if case == "quota" else 0)
'''


class GPTDelegationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake = self.bin / "codex"
        fake.write_text(FAKE.replace("PYTHON_PATH", sys.executable).replace("SESSION_ID", SESSION))
        fake.chmod(0o700)
        self.calls = self.root / "calls.json"
        self.env = {**os.environ, "CODEX_HOME": str(self.root / "normal"),
                    "CODEX_THREAD_ID": TASK, "PATH": str(self.bin), "CALLS": str(self.calls)}
        with mock.patch.dict(os.environ, self.env):
            self.account = accounts.create("work", "business")
            Path(self.account["home"], "auth.json").write_text("private")
            self.account = accounts.confirm("work")
        self.brief = self.root / "brief.md"
        self.brief.write_text("Find the issue.")
        self.out = self.root / "run"

    def launch(self, *extra, case="success"):
        return subprocess.run([sys.executable, str(SCRIPTS / "delegate.py"), "--once",
            "--connection", "gpt:work", "--cwd", str(self.workspace), "--prompt-file", str(self.brief),
            "--output-dir", str(self.out), *extra], env={**self.env, "CASE": case},
            capture_output=True, text=True, timeout=5)

    def test_success_uses_only_selected_home_and_resume_identity(self):
        result = self.launch("--mode", "edit", "--model", "gpt-x")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["backend"], "gpt")
        self.assertEqual(summary["connection_id"], "gpt:" + self.account["id"])
        self.assertEqual(summary["session_id"], SESSION)
        called = json.loads(self.calls.read_text())
        self.assertEqual(called["home"], self.account["home"])
        self.assertIn("workspace-write", called["args"])
        self.assertIn("gpt-x", called["args"])
        previous = self.out
        self.out = self.root / "resume"
        resumed = self.launch("--resume-from", str(previous), "--mode", "edit")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertIn("resume", json.loads(self.calls.read_text())["args"])

    def test_failed_worker_never_falls_back(self):
        result = self.launch(case="quota")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["status"], "needs_review")
        self.assertFalse((self.workspace / "received.json").exists())

    def test_invalid_resume_account_id_stops_before_launch(self):
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        previous = self.out
        self.out = self.root / "resume"
        summary_file = previous / "summary.json"
        summary = json.loads(summary_file.read_text())
        summary["connection_id"] = "gpt:00000000-0000-4000-8000-000000000999"
        summary_file.write_text(json.dumps(summary))
        self.calls.unlink()
        resumed = self.launch("--resume-from", str(previous))
        self.assertEqual(resumed.returncode, 2)
        self.assertFalse(self.out.exists())
        self.assertFalse(self.calls.exists())


if __name__ == "__main__":
    unittest.main()
