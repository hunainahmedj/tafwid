"""Account homes stay separate and login checks never use inherited credentials."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import accounts


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "normal"
        self.patch = mock.patch.dict(os.environ, {"CODEX_HOME": str(self.home), "TAFWID_HOME": str(self.home / "tafwid"), "TAFWID_HOST": "codex"})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_names_types_and_private_distinct_homes(self):
        rows = [accounts.create("first", "personal"), accounts.create("second", "personal"),
                accounts.create("work", "business")]
        self.assertEqual([r["kind"] for r in rows], ["personal", "personal", "business"])
        self.assertEqual(len({r["id"] for r in rows}), 3)
        self.assertEqual(len({r["home"] for r in rows}), 3)
        for row in rows:
            path = Path(row["home"])
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(row["status"], "pending")
        self.assertFalse((self.home / "auth.json").exists())
        with self.assertRaises(ValueError):
            accounts.create("first", "business")
        for name in ("gpt", "business", "claude", "UPPER", "../other"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                accounts.create(name, "personal")

    def test_isolated_env_strips_account_overrides(self):
        row = accounts.create("work", "business")
        env = accounts.isolated_env(Path(row["home"]), {
            "PATH": "/bin", "SSL_CERT_FILE": "/cert", "CODEX_HOME": "/normal",
            "OPENAI_API_KEY": "secret", "CODEX_API_KEY": "secret",
            "CODEX_ACCESS_TOKEN": "secret", "OPENAI_FEDERATION_RULE_ID": "secret",
            "OPENAI_IDENTITY_TOKEN_FILE": "secret", "OPENAI_BASE_URL": "https://other",
        })
        self.assertEqual(env["CODEX_HOME"], row["home"])
        self.assertEqual(env["PATH"], "/bin")
        self.assertEqual(env["SSL_CERT_FILE"], "/cert")
        self.assertFalse(any(k in env for k in ("OPENAI_API_KEY", "CODEX_API_KEY",
                          "CODEX_ACCESS_TOKEN", "OPENAI_FEDERATION_RULE_ID",
                          "OPENAI_IDENTITY_TOKEN_FILE", "OPENAI_BASE_URL")))

    def test_symlink_home_is_rejected(self):
        row = accounts.create("safe", "personal")
        path = Path(row["home"])
        (path / "config.toml").unlink()
        path.rmdir()
        path.symlink_to(self.home)
        with self.assertRaises(ValueError):
            accounts.check(row)

    def test_symlink_codex_home_stops_before_registry_creation(self):
        real = Path(self.tmp.name) / "real"
        real.mkdir()
        self.home.symlink_to(real)
        with self.assertRaises(ValueError):
            accounts.create("safe", "personal")
        self.assertEqual(list(real.iterdir()), [])

    def test_world_readable_auth_is_not_accepted(self):
        row = accounts.create("safe", "personal")
        auth = Path(row["home"], "auth.json")
        auth.write_text("private")
        os.chmod(auth, 0o644)
        with mock.patch("accounts.shutil.which", return_value="/fake/codex"):
            self.assertEqual(accounts.check(row)["login_method"], "unavailable")

    def test_check_requires_chatgpt_file_login_and_confirmation(self):
        row = accounts.create("safe", "personal")
        with mock.patch("accounts.shutil.which", return_value=None):
            self.assertEqual(accounts.check(row)["login_method"], "unavailable")
        with mock.patch("accounts.shutil.which", return_value="/fake/codex"):
            self.assertEqual(accounts.check(row)["login_method"], "unavailable")
            Path(row["home"], "auth.json").write_text("private")
            os.chmod(Path(row["home"], "auth.json"), 0o600)
            fake = mock.Mock(returncode=0, stdout="Logged in using ChatGPT", stderr="")
            with mock.patch("accounts.subprocess.run", return_value=fake) as run:
                self.assertEqual(accounts.check(row)["login_method"], "chatgpt")
                self.assertEqual(run.call_args.args[0], ["/fake/codex", "login", "status"])
                self.assertEqual(run.call_args.kwargs["env"]["CODEX_HOME"], row["home"])
                fake.stdout, fake.stderr = "", "Logged in using ChatGPT"
                self.assertEqual(accounts.check(row)["login_method"], "chatgpt")
                ready = accounts.confirm("safe")
                self.assertEqual(ready["status"], "ready")
            fake.stdout = "Logged in using an API key"
            self.assertEqual(accounts.check(row)["login_method"], "unavailable")


if __name__ == "__main__":
    unittest.main()
