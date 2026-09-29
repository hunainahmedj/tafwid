"""Codex worker commands retain sandbox limits and validate structured results."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codex_cli

SESSION = "00000000-0000-4000-8000-000000000003"


class CodexCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.schema = self.root / "schema.json"
        self.final = self.root / "final.json"
        self.events = self.root / "events.jsonl"

    def test_fresh_and_resume_keep_limits(self):
        fresh = codex_cli.build_command("/fake/codex", cwd=self.root, schema=self.schema,
                                        mode="read", model=None, session_id=None, output=self.final)
        self.assertEqual(fresh[:2], ["/fake/codex", "exec"])
        self.assertIn("read-only", fresh)
        self.assertIn('approval_policy="never"', fresh)
        self.assertEqual(fresh[-1], "-")
        resumed = codex_cli.build_command("/fake/codex", cwd=self.root, schema=self.schema,
                                          mode="edit", model="gpt-x", session_id=SESSION, output=self.final)
        self.assertEqual(resumed[:3], ["/fake/codex", "exec", "resume"])
        self.assertIn('sandbox_mode="workspace-write"', resumed)
        self.assertIn('approval_policy="never"', resumed)
        self.assertIn(SESSION, resumed)
        self.assertIn("gpt-x", resumed)
        with self.assertRaises(ValueError):
            codex_cli.build_command("codex", cwd=self.root, schema=self.schema,
                                    mode="full", model=None, session_id=None, output=self.final)

    def test_completed_blocked_and_invalid_results(self):
        self.events.write_text(json.dumps({"type": "thread.started", "thread_id": SESSION}) + "\n" +
                               json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10}}) + "\n")
        self.final.write_text(json.dumps({"status": "completed", "report": "Done"}))
        result = codex_cli.parse_result(self.events, self.final, exit_code=0)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["session_id"], SESSION)
        self.final.write_text(json.dumps({"status": "blocked", "report": "Need access"}))
        self.assertEqual(codex_cli.parse_result(self.events, self.final, exit_code=0)["status"], "blocked")
        with self.assertRaises(ValueError):
            codex_cli.parse_result(self.events, self.final, exit_code=0,
                                   expected_session_id="00000000-0000-4000-8000-000000000004")
        self.final.write_text(json.dumps({"status": "completed", "report": ""}))
        self.assertEqual(codex_cli.parse_result(self.events, self.final, exit_code=0)["status"], "needs_review")
        self.events.write_text("not json\n")
        self.assertEqual(codex_cli.parse_result(self.events, self.final, exit_code=0)["status"], "needs_review")


if __name__ == "__main__":
    unittest.main()
