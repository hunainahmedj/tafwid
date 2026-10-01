"""Coordinator detection must be explicit and never guess between hosts."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import host

A = "00000000-0000-4000-8000-000000000001"
B = "00000000-0000-4000-8000-000000000002"


class HostTests(unittest.TestCase):
    def test_each_host_is_detected_from_its_own_signal(self):
        self.assertEqual(host.detect({"CODEX_THREAD_ID": A}), "codex")
        self.assertEqual(host.detect({"CODEX_SESSION_ID": A}), "codex")
        self.assertEqual(host.detect({"CLAUDE_CODE_SESSION_ID": A}), "claude")
        self.assertIsNone(host.detect({}))
        self.assertEqual(host.task_id({"CODEX_THREAD_ID": A, "CODEX_SESSION_ID": B}), A)
        self.assertEqual(host.task_id({"CLAUDE_CODE_SESSION_ID": B}), B)
        self.assertIsNone(host.task_id({}))

    def test_both_signals_fail_without_guessing(self):
        env = {"CODEX_THREAD_ID": A, "CLAUDE_CODE_SESSION_ID": B}
        with self.assertRaisesRegex(ValueError, "TAFWID_HOST"):
            host.detect(env)
        with self.assertRaisesRegex(ValueError, "TAFWID_HOST"):
            host.task_id(env)
        self.assertEqual(host.display_name(env), "the coordinator")

    def test_override_selects_one_host_and_ignores_the_other_signal(self):
        env = {"CODEX_THREAD_ID": A, "CLAUDE_CODE_SESSION_ID": B}
        self.assertEqual(host.task_id({**env, "TAFWID_HOST": "codex"}), A)
        self.assertEqual(host.task_id({**env, "TAFWID_HOST": "claude"}), B)
        self.assertIsNone(host.task_id({"TAFWID_HOST": "codex", "CLAUDE_CODE_SESSION_ID": B}))
        with self.assertRaisesRegex(ValueError, "TAFWID_HOST"):
            host.detect({"TAFWID_HOST": "other"})

    def test_malformed_identity_is_rejected_with_the_host_name(self):
        with self.assertRaisesRegex(ValueError, "Invalid Codex task identity"):
            host.task_id({"CODEX_THREAD_ID": "../../outside"})
        with self.assertRaisesRegex(ValueError, "Invalid Claude Code task identity"):
            host.task_id({"CLAUDE_CODE_SESSION_ID": "not-a-uuid"})

    def test_display_names(self):
        self.assertEqual(host.display_name({"CODEX_THREAD_ID": A}), "Codex")
        self.assertEqual(host.display_name({"CLAUDE_CODE_SESSION_ID": A}), "Claude Code")
        self.assertEqual(host.display_name({}), "the coordinator")

    def test_hook_host_uses_the_plugin_root_variable(self):
        self.assertEqual(host.for_hook({"CLAUDE_PLUGIN_ROOT": "/plugin"}), "claude")
        self.assertEqual(host.for_hook({"PLUGIN_ROOT": "/plugin"}), "codex")
        self.assertEqual(host.for_hook({}), "codex")

    def test_worker_environment_drops_every_identity_variable(self):
        base = {"PATH": "/bin", "CODEX_THREAD_ID": A, "CODEX_SESSION_ID": A,
                "CLAUDE_CODE_SESSION_ID": B, "TAFWID_HOST": "claude", "CLAUDE_CONFIG_DIR": "/c"}
        self.assertEqual(host.worker_env(base), {"PATH": "/bin", "CLAUDE_CONFIG_DIR": "/c"})


class HookSeenTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(os.environ, {"CODEX_HOME": str(self.root), "TAFWID_HOME": str(self.root / "tafwid")})
        env.start()
        self.addCleanup(env.stop)

    def test_marker_round_trip_is_private_and_task_bound(self):
        self.assertIsNone(host.seen(A))
        self.assertIsNone(host.seen(None))
        host.record_seen(A, "bypassPermissions")
        self.assertEqual(host.seen(A)["permission_mode"], "bypassPermissions")
        self.assertEqual(host.seen_path(A).stat().st_mode & 0o777, 0o600)
        self.assertIsNone(host.seen(B))
        host.seen_path(A).write_text('{"version": 1, "thread_id": "other"}')
        self.assertIsNone(host.seen(A))
        host.seen_path(A).write_text("not json")
        self.assertIsNone(host.seen(A))

    def test_old_marker_no_longer_proves_hooks_or_full_access(self):
        host.record_seen(A, "bypassPermissions")
        marker = json.loads(host.seen_path(A).read_text())
        marker["seen_at"] = time.time() - host.MAX_SEEN_AGE_SECONDS - 1
        host.seen_path(A).write_text(json.dumps(marker))
        self.assertIsNone(host.seen(A))
        self.assertFalse(host.full_access({"CLAUDE_CODE_SESSION_ID": A}))
        marker["seen_at"] = "yesterday"
        host.seen_path(A).write_text(json.dumps(marker))
        self.assertIsNone(host.seen(A))

    def test_full_access_signal_per_host(self):
        self.assertTrue(host.full_access({"CODEX_THREAD_ID": A, "CODEX_PERMISSION_PROFILE": ":danger-full-access"}))
        self.assertFalse(host.full_access({"CODEX_THREAD_ID": A, "CODEX_PERMISSION_PROFILE": ":workspace-write"}))
        self.assertFalse(host.full_access({"CODEX_PERMISSION_PROFILE": ":danger-full-access"}))
        claude = {"CLAUDE_CODE_SESSION_ID": A}
        self.assertFalse(host.full_access(claude))
        host.record_seen(A, "default")
        self.assertFalse(host.full_access(claude))
        host.record_seen(A, "bypassPermissions")
        self.assertTrue(host.full_access(claude))
        self.assertFalse(host.full_access({"CLAUDE_CODE_SESSION_ID": B}))


if __name__ == "__main__":
    unittest.main()
