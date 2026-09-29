"""The account command signs in visibly and waits for user confirmation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "account.py"
FAKE = '''#!{python}
import os, pathlib, sys
home = pathlib.Path(os.environ["CODEX_HOME"])
with open(os.environ["CALLS"], "a") as log:
    log.write(" ".join(sys.argv[1:]) + " " + str(home) + "\\n")
if sys.argv[1:3] == ["login", "status"]:
    print("Logged in using ChatGPT" if (home / "auth.json").exists() else "not logged in")
    sys.exit(0 if (home / "auth.json").exists() else 1)
if sys.argv[1] == "login":
    (home / "auth.json").write_text("PRIVATE TOKEN")
    print("Sign-in complete")
    sys.exit(0)
sys.exit(9)
'''


class AccountCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        cli = bin_dir / "codex"
        cli.write_text(FAKE.format(python=sys.executable))
        cli.chmod(0o700)
        self.calls = self.root / "calls"
        self.env = {**os.environ, "CODEX_HOME": str(self.root / "ordinary"),
                    "PATH": str(bin_dir), "CALLS": str(self.calls)}

    def call(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], env=self.env,
                              capture_output=True, text=True, timeout=5)

    def test_add_stays_pending_until_confirmed_and_reuses_home(self):
        added = self.call("add", "gpt", "business", "--name", "work")
        self.assertEqual(added.returncode, 0, added.stderr)
        row = json.loads(added.stdout)
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["kind"], "business")
        self.assertNotIn("PRIVATE TOKEN", added.stdout + added.stderr)
        checked = self.call("check", "work")
        self.assertEqual(json.loads(checked.stdout)["login_method"], "chatgpt")
        self.assertEqual(json.loads(self.call("list").stdout)[0]["status"], "pending")
        self.assertEqual(self.call("login", "work", "--device-auth").returncode, 0)
        self.assertEqual(json.loads(self.call("confirm", "work").stdout)["status"], "ready")
        calls = self.calls.read_text()
        self.assertIn("login " + row["home"], calls)
        self.assertIn("login --device-auth " + row["home"], calls)
        self.assertFalse((self.root / "ordinary" / "auth.json").exists())

    def test_help_does_not_create_state_or_login(self):
        result = self.call("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Exit", result.stdout)
        self.assertFalse(self.calls.exists())
        self.assertFalse((self.root / "ordinary").exists())


if __name__ == "__main__":
    unittest.main()
