"""OpenCode adapter contracts, with no model requests or real credentials."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import delegate
import opencode_worker as worker

MODEL = "openrouter/example/coder:free"
CATALOGUE = {"id": "example/coder:free", "context_length": 32768,
             "pricing": {"prompt": "0", "completion": "0"},
             "supported_parameters": ["tools"]}
FAKE = r'''
import json, os, sys, time
from pathlib import Path
if sys.argv[1] == "export":
    args=json.loads(Path("received.json").read_text())["args"]
    provider,model=args[args.index("--model")+1].split("/",1)
    print(json.dumps({"info":{"directory":str(Path.cwd())},"messages": [{"info": {"role": "assistant", "providerID": provider, "modelID": model}}]}))
    sys.exit(0)
Path("received.json").write_text(json.dumps({"args":sys.argv[1:], "pwd":os.environ.get("PWD"), "prompt":sys.stdin.read(), "config":json.loads(os.environ["OPENCODE_CONFIG_CONTENT"])}))
case=os.environ.get("FIXTURE_CASE", "success")
session="ses_test123"
def emit(kind, part=None, **extra):
    print(json.dumps({"type":kind,"sessionID":session,"part":part or {},**extra}),flush=True)
emit("step_start")
if case == "timeout": time.sleep(30)
if case == "zen_denied":
    emit("error", error={"name":"APIError", "data":{"message":"OpenCode's free tier can only be used from within OpenCode", "statusCode":403}})
    sys.exit(1)
if case == "quota":
    emit("error", error={"name":"APIError", "data":{"message":"Rate limit exceeded", "statusCode":429,
        "responseHeaders":{"set-cookie":"PRIVATE-COOKIE"}, "responseBody":"PRIVATE-ACCOUNT-ID"}})
    sys.exit(0)
if case == "denied": emit("tool_use", {"tool":"bash","state":{"status":"error","error":"Permission denied"}})
report={"status":"completed","report":"Done; focused check passed.","handoff":None}
if case == "native": report={"status":"native_required","report":"Browser needed", "handoff":{k:"Browser evidence" for k in ("capability","reason","requested_action","context","expected_result")}}
emit("text", {"text":"plain unstructured answer" if case == "malformed" else json.dumps(report)})
if case != "truncated": emit("step_finish", {"reason":"stop", "cost":0,"tokens":{"input":100,"output":30,"reasoning":5,"cache":{"read":20,"write":0}}})
'''


class OpenCodeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cwd = self.root / "workspace"
        self.cwd.mkdir()
        self.brief = self.root / "brief.md"
        self.brief.write_text("Fix the small bug; do not commit. Literal $(touch INJECTED).")
        self.out = self.root / "run"
        self.exe = self.root / "opencode"
        self.exe.write_text(f"#!{sys.executable}\n" + FAKE)
        self.exe.chmod(0o700)
        self.env = patch.dict(os.environ, {"CODEX_HOME":str(self.root / "codex"),
            "CODEX_THREAD_ID":"00000000-0000-4000-8000-000000000001",
            "OPENROUTER_API_KEY":"fixture-not-a-real-key"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def launch(self, *flags, case="success", model=True, info=CATALOGUE):
        argv = ["delegate", "--backend", "opencode", "--cwd", str(self.cwd),
                "--prompt-file", str(self.brief), "--output-dir", str(self.out), "--once",
                *(["--model", MODEL] if model else []), *flags]
        with patch.object(sys, "argv", argv), patch.object(worker, "model_info", return_value=info), \
                patch.object(worker.shutil, "which", return_value=str(self.exe)), \
                patch.dict(os.environ, {"FIXTURE_CASE":case}), contextlib.redirect_stdout(io.StringIO()) as output:
            code = delegate.run(delegate.parse_args())
        return code, json.loads(output.getvalue())

    def test_capability_and_free_price_gate(self):
        worker.validate_model(MODEL, CATALOGUE)
        for changed in ({"supported_parameters": []}, {"pricing":{"prompt":"0.1","completion":"0"}},
                        {"id":"different:free"}, {"pricing":{}}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                worker.validate_model(MODEL, {**CATALOGUE, **changed})
        for model in ("openrouter/auto", "openrouter/free", "anthropic/opus", "example/coder:free"):
            with self.subTest(model=model), self.assertRaises(ValueError): worker.validate_model(model, CATALOGUE)

    def test_zen_public_launch_and_resume_pin_provider_helpers_and_permissions(self):
        info = {'id': 'free-coder', 'pricing': {'prompt': 0, 'completion': 0},
                'supported_parameters': ['tools'], 'npm': '@ai-sdk/openai-compatible'}
        with patch.dict(os.environ, {'OPENCODE_API_KEY': '', 'XDG_DATA_HOME': str(self.root / 'data')}):
            code, first = self.launch('--model', 'opencode/free-coder', '--mode', 'edit',
                '--allow-command', 'python3 -m unittest *', '--permissions', 'scoped', info=info)
            self.assertEqual(code, 0)
            self.assertEqual(first['provider'], 'opencode')
            self.assertEqual(first['models_used'], ['opencode/free-coder'])
            config = json.loads((self.cwd / 'received.json').read_text())['config']
            self.assertEqual(config['enabled_providers'], ['opencode'])
            self.assertEqual(config['provider']['opencode']['options']['apiKey'], 'public')
            self.assertNotIn('openrouter', config['provider'])
            self.assertEqual(config['permission']['bash'], {'*': 'deny', 'python3 -m unittest *': 'allow'})
            for agent in config['agent'].values(): self.assertEqual(agent['model'], 'opencode/free-coder')
            previous = self.out
            self.out = self.root / 'zen-resume'
            _, resumed = self.launch('--resume-from', str(previous), model=False, info=info)
            self.assertEqual(resumed['session_id'], first['session_id'])
            self.assertEqual(resumed['model_selection']['requested_model'], 'opencode/free-coder')
            self.out = self.root / 'different-provider'
            with self.assertRaisesRegex(ValueError, 'provider differs'):
                self.launch('--resume-from', str(previous))
            self.assertFalse(self.out.exists())

    def test_launch_records_worker_events_and_actual_model(self):
        code, summary = self.launch()
        self.assertEqual(code, 0)
        self.assertEqual(summary["backend"], "opencode")
        self.assertEqual(summary["session_id"], "ses_test123")
        self.assertEqual(summary["models_used"], [MODEL])
        self.assertEqual(summary["usage"]["input"], 100)
        received = json.loads((self.cwd / "received.json").read_text())
        config = received["config"]
        self.assertEqual(config["model"], config["small_model"])
        for name in ("title", "summary", "compaction"):
            self.assertEqual(config["agent"][name]["model"], MODEL)
        self.assertNotIn("fixture-not-a-real-key", (self.out / "request.json").read_text())
        self.assertNotIn("fixture-not-a-real-key", json.dumps(summary))
        self.assertFalse((self.cwd / "INJECTED").exists())
        self.assertIn("--pure", received["args"])
        self.assertEqual(config["permission"]["bash"], "deny")
        self.assertEqual(config["permission"]["edit"], "deny")

    def test_local_worker_resume_pins_connection_and_refuses_endpoint_changes(self):
        import local_models
        profile = {'kind': 'lmstudio', 'base_url': 'http://127.0.0.1:1234/v1',
            'model': 'test/model', 'context_length': 16000, 'output_limit': 2000,
            'tool_call': True, 'api_key_env': None}
        from worker_registry import atomic_json
        atomic_json(local_models.filename(), {'version': 1, 'connections': {'laptop': profile}})
        info = {'id': 'test/model', 'supported_parameters': ['tools'], 'self_hosted': True,
                'local_connection': profile, 'context_length': 16000, 'output_limit': 2000}
        code, first = self.launch('--model', 'local-laptop/test/model', info=info)
        self.assertEqual(code, 0)
        self.assertEqual(first['models_used'], ['local-laptop/test/model'])
        self.assertIn('self-hosted', first['usage']['source'])
        received = json.loads((self.cwd / 'received.json').read_text())
        self.assertEqual(received['config']['enabled_providers'], ['local-laptop'])
        self.assertEqual(received['config']['provider']['local-laptop']['options']['baseURL'], 'http://127.0.0.1:1234/v1')
        for agent in received['config']['agent'].values():
            self.assertEqual(agent['model'], 'local-laptop/test/model')
        previous = self.out
        self.out = self.root / 'local-resume'
        _, resumed = self.launch('--resume-from', str(previous), model=False, info=info)
        self.assertEqual(first['session_id'], resumed['session_id'])
        self.out = self.root / 'changed-endpoint'
        profile['base_url'] = 'http://127.0.0.1:4321/v1'
        atomic_json(local_models.filename(), {'version': 1, 'connections': {'laptop': profile}})
        with self.assertRaisesRegex(ValueError, 'connection changed'):
            self.launch('--resume-from', str(previous), model=False, info=info)
        self.assertFalse(self.out.exists())

    def test_workspace_is_explicit_despite_inherited_pwd(self):
        with patch.dict(os.environ, {"PWD":str(self.root / "wrong-project")}):
            self.launch()
        received = json.loads((self.cwd / "received.json").read_text())
        self.assertEqual(received["pwd"], str(self.cwd.resolve()))
        self.assertEqual(received["args"][received["args"].index("--dir") + 1], str(self.cwd.resolve()))

    def test_resume_preserves_identity_model_and_deduplicates_instructions(self):
        role = self.root / "role.md"
        role.write_text("UNIQUE selected instruction")
        _, first = self.launch("--instructions-file", str(role))
        previous = self.out
        self.out = self.root / "resumed"
        _, second = self.launch("--resume-from", str(previous), "--instructions-file", str(role), model=False)
        received = json.loads((self.cwd / "received.json").read_text())
        self.assertEqual(second["session_id"], first["session_id"])
        self.assertIn("--session", received["args"])
        self.assertNotIn("UNIQUE selected instruction", received["prompt"])
        self.assertEqual(second["model_selection"]["requested_model"], MODEL)

    def test_resume_rejects_other_task_or_backend(self):
        self.launch()
        previous = self.out
        self.out = self.root / "resumed"
        with patch.dict(os.environ, {"CODEX_THREAD_ID":"00000000-0000-4000-8000-000000000002"}), self.assertRaisesRegex(ValueError, "ownership"):
            self.launch("--resume-from", str(previous))
        data = json.loads((previous / "summary.json").read_text())
        data["backend"] = "claude"
        (previous / "summary.json").write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "backend"):
            self.launch("--resume-from", str(previous))

    def test_status_and_handoff_validation(self):
        for case, status, code in (("native","native_required",3), ("malformed","needs_review",1),
                                  ("truncated","needs_review",1), ("denied","needs_review",1),
                                  ("quota","error",1), ("zen_denied","blocked",1), ("timeout","timeout",124)):
            with self.subTest(case=case):
                self.out = self.root / case
                actual_code, summary = self.launch("--timeout", ".2" if case == "timeout" else "5", case=case)
                self.assertEqual(summary["status"], status)
                self.assertEqual(actual_code, code)
                self.assertNotIn("PRIVATE-", json.dumps(summary))
                if case == "native": self.assertTrue(Path(summary["handoff_file"]).is_file())

    def test_scoped_commands_and_full_policy(self):
        self.launch("--mode", "edit", "--allow-command", "python3 -m unittest *", "--permissions", "scoped")
        config = json.loads((self.cwd / "received.json").read_text())["config"]
        self.assertEqual(config["permission"]["bash"], {"*":"deny", "python3 -m unittest *":"allow"})
        self.assertEqual(config["permission"]["task"], "deny")
        self.out = self.root / "full"
        self.launch("--mode", "edit", "--permissions", "full")
        config = json.loads((self.cwd / "received.json").read_text())["config"]
        self.assertEqual(config["permission"]["bash"], "allow")

    def test_rejects_ambiguous_command_and_claude_routing_flags(self):
        for flags in (("--allow-command","python *"), ("--mode","edit","--allow-tool","Bash(python *)"),
                      ("--mode","edit","--allow-command","*")):
            with self.subTest(flags=flags), self.assertRaises(ValueError): self.launch(*flags)
        with self.assertRaises(ValueError): self.launch("--profile", "fast", model=False)

    def test_auth_missing_does_not_start_worker_or_write_artifacts(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY":"", "XDG_DATA_HOME":str(self.root / "missing-data")}), \
                self.assertRaisesRegex(ValueError, "auth login"):
            self.launch()
        self.assertFalse(self.out.exists())
        self.assertFalse((self.cwd / "received.json").exists())

    def test_incompatible_model_does_not_start_worker(self):
        with patch.object(worker, "validate_model", side_effect=ValueError("No tool calling")), \
                self.assertRaisesRegex(ValueError, "tool calling"):
            self.launch()
        self.assertFalse(self.out.exists())

    def test_resume_infers_backend_without_explicit_flag(self):
        self.launch()
        previous = self.out
        with patch.object(sys, "argv", ["delegate", "--cwd", str(self.cwd), "--prompt-file", str(self.brief),
                "--output-dir", str(self.root / "inferred"), "--resume-from", str(previous)]):
            args = delegate.parse_args()
        with patch.object(worker, "run", return_value=17) as launch:
            self.assertEqual(delegate.run(args), 17)
            launch.assert_called_once_with(args)

    def test_stream_rejects_mixed_sessions_and_nonzero_cost(self):
        self.launch()
        events = self.out / "events.jsonl"
        original = events.read_text()
        events.write_text(original + json.dumps({"sessionID":"ses_other", "type":"step_start"}) + "\n")
        with self.assertRaisesRegex(ValueError, "session identity"):
            worker.result_events(events)
        rows = [json.loads(line) for line in original.splitlines()]
        rows[-1]["part"]["cost"] = .01
        events.write_text("\n".join(json.dumps(row) for row in rows))
        self.assertEqual(worker.result_events(events)["status"], "needs_review")

    def test_stream_missing_usage_is_unknown_instead_of_free_zero(self):
        self.launch()
        events = self.out / "events.jsonl"
        rows = [json.loads(line) for line in events.read_text().splitlines()]
        rows[-1]["part"].pop("cost")
        rows[-1]["part"]["tokens"].pop("input")
        events.write_text("\n".join(json.dumps(row) for row in rows))
        usage = worker.result_events(events)["usage"]
        self.assertIsNone(usage["cost_usd"])
        self.assertIsNone(usage["input"])
        self.assertEqual(usage["output"], 30)
        events.write_text(json.dumps({"sessionID": "ses_test123", "type": "step_start"}))
        self.assertIsNone(worker.result_events(events)["usage"]["output"])

    def test_zen_client_restriction_is_blocked_not_a_retry_or_native_handoff(self):
        events = self.root / 'denial.jsonl'
        events.write_text(json.dumps({'sessionID': 'ses_zen', 'type': 'error', 'error': {
            'name': 'APIError', 'data': {'statusCode': 403,
            'message': "OpenCode's free tier can only be used from within OpenCode"}}}))
        result = worker.result_events(events)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['failure_kind'], 'provider_access_denied')
        self.assertIsNone(result['handoff'])
        self.assertIsNone(result['usage']['cost_usd'])

    def test_resume_rejects_actual_session_workspace_mismatch(self):
        self.launch()
        previous = self.out
        data = json.loads((previous / "session.json").read_text())
        data["info"]["directory"] = str(self.root / "wrong-project")
        (previous / "session.json").write_text(json.dumps(data))
        self.out = self.root / "wrong-resume"
        with self.assertRaisesRegex(ValueError, "exported workspace"):
            self.launch("--resume-from", str(previous))


if __name__ == "__main__":
    unittest.main()
