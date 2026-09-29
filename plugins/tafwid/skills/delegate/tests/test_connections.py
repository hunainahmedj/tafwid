"""A task keeps a pool of exact connections, including legacy Claude state."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import accounts
import connections

TASK = "00000000-0000-4000-8000-000000000001"


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "codex"
        patch = mock.patch.dict(os.environ, {"CODEX_HOME": str(self.home)})
        patch.start()
        self.addCleanup(patch.stop)

    def test_legacy_enabled_and_off_migrate_without_rerouting(self):
        path = self.home / "tafwid/state" / (TASK + ".json")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"version": 1, "thread_id": TASK, "enabled": True}))
        self.assertEqual(connections.read(TASK)["connections"][0]["id"], "claude:default")
        self.assertEqual(connections.resolve(TASK, None)["id"], "claude:default")
        path.write_text(json.dumps({"version": 1, "thread_id": TASK, "enabled": False}))
        self.assertEqual(connections.read(TASK)["connections"], [])

    def test_multiple_accounts_require_exact_routing_and_off_is_selective(self):
        first = accounts.create("first", "personal")
        second = accounts.create("work", "business")
        with mock.patch("connections.accounts.check", side_effect=lambda row: {**row, "login_method": "chatgpt"}), \
             mock.patch("connections.claude_code.check_ready", return_value={"executable": "/fake/claude"}):
            with mock.patch("connections.accounts.get", side_effect=lambda name: {**({"first": first, "work": second}[name]), "status": "ready"}):
                connections.enable(TASK, "claude")
                connections.enable(TASK, "gpt:first")
                connections.enable(TASK, "gpt:work")
                self.assertEqual(len(connections.read(TASK)["connections"]), 3)
                with self.assertRaises(ValueError):
                    connections.resolve(TASK, None)
                self.assertEqual(connections.resolve(TASK, "gpt:work")["id"], "gpt:" + second["id"])
                connections.disable(TASK, "gpt:first")
                self.assertEqual(len(connections.read(TASK)["connections"]), 2)
                self.assertEqual(connections.resolve(TASK, "gpt:first", once=True)["id"], "gpt:" + first["id"])
                with self.assertRaises(ValueError):
                    connections.resolve(TASK, "gpt:first")
                connections.disable(TASK, None)
                self.assertFalse(connections.read(TASK)["enabled"])

    def test_failed_readiness_keeps_previous_pool(self):
        with mock.patch("connections.claude_code.check_ready", return_value={}):
            connections.enable(TASK, "claude")
        before = connections.read(TASK)
        with mock.patch("connections.claude_code.check_ready", side_effect=ValueError("not ready")):
            with self.assertRaises(ValueError):
                connections.enable(TASK, "claude")
        self.assertEqual(connections.read(TASK), before)


if __name__ == "__main__":
    unittest.main()
