"""Exercise the real launcher against an offline Claude process fixture."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "delegate.py"
STATE = SCRIPT.with_name("session.py")
OVERRIDES = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
             "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")
FAKE = r'''
import json, os, sys, time
from pathlib import Path
case = os.environ.get("FIXTURE_CASE", "success")
if "auth" in sys.argv:
    if case == "slow_auth":
        Path("auth-started").write_text("ready")
        time.sleep(1)
    print(json.dumps({"loggedIn": True, "authMethod": "api_key" if case == "api" else "claude.ai",
                      "apiProvider": "firstParty", "subscriptionType": "max"}))
    sys.exit(0)
prompt = sys.stdin.read()
Path("received.json").write_text(json.dumps({"args": sys.argv[1:], "prompt": prompt,
    "identity": {k: os.environ.get(k) for k in ("CODEX_THREAD_ID", "CODEX_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "TAFWID_HOST")}}))
time.sleep(float(os.environ.get("FIXTURE_DELAY", "0")))
if case == "timeout":
    time.sleep(30)
if case == "malformed":
    print("not json")
    sys.exit(0)
structured = {"status": "completed", "report": "Done. " + "x" * 10000}
if case == "blocked":
    structured = {"status": "blocked", "report": "Acceptance criteria are missing."}
if case == "invalid_status":
    structured = {"status": "unknown", "report": "Need help"}
payload = {"type": "result", "subtype": "success", "is_error": case == "expired",
 "result": "OAuth session expired" if case == "expired" else "Done. " + "x" * 10000,
 "session_id": sys.argv[sys.argv.index("--resume") + 1] if "--resume" in sys.argv else sys.argv[sys.argv.index("--session-id") + 1],
 "permission_denials": [{"tool_name": "Bash", "tool_input": {"command": "pytest"}}] if case == "denied" else []}
if case == "usage":
    payload["usage"] = {"input_tokens": 400, "output_tokens": 150}
    payload["total_cost_usd"] = 0.41
    payload["modelUsage"] = {"claude-sonnet-5": {"outputTokens": 120, "costUSD": 0.4},
                             "claude-haiku-4-5": {"outputTokens": 30, "costUSD": 0.01}}
if case == "bad_usage":
    payload["modelUsage"] = "claude-sonnet-5"
if case == "quota":
    payload.update(is_error=True, result="You've hit your session limit; resets at 08:20")
if case != "missing_structured":
    payload["structured_output"] = structured
print(json.dumps(payload))
'''


class DelegationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cwd = self.root / "workspace"
        self.cwd.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake = self.bin / "claude"
        fake.write_text(f"#!{sys.executable}\n" + FAKE)
        fake.chmod(0o700)
        self.prompt = self.root / "brief.txt"
        self.prompt.write_text("Fix the bug. Literal $(touch INJECTED) and `touch INJECTED2`.\n")
        self.out = self.root / "run"
        self.env = {k: v for k, v in os.environ.items() if k not in OVERRIDES}
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env["PATH"]
        self.env["CODEX_HOME"] = str(self.root / "codex")
        self.env["TAFWID_HOME"] = str(self.root / "codex" / "tafwid")
        self.env["TAFWID_HOST"] = "codex"
        self.env["CLAUDE_CONFIG_DIR"] = str(self.root / "claude-config")
        self.env["CODEX_THREAD_ID"] = "00000000-0000-4000-8000-000000000001"
        self.env.pop("CODEX_SESSION_ID", None)

    def run_cli(self, *extra, case="success", once=True):
        return subprocess.run([sys.executable, str(SCRIPT), "--cwd", str(self.cwd),
            "--prompt-file", str(self.prompt), "--output-dir", str(self.out),
            *(["--once"] if once else []), *extra],
            env={**self.env, "FIXTURE_CASE": case}, text=True, capture_output=True, timeout=15)

    def test_worker_environment_has_no_coordinator_identity(self):
        self.env["CLAUDE_CODE_SESSION_ID"] = "00000000-0000-4000-8000-000000000009"
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads((self.cwd / "received.json").read_text())["identity"]
        self.assertEqual(set(identity.values()), {None})

    def test_resume_accepts_a_legacy_ownership_field(self):
        first = self.run_cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        path = self.out / "summary.json"
        summary = json.loads(path.read_text())
        summary["codex_thread_id"] = summary.pop("coordinator_task_id")
        summary.pop("coordinator_host")
        path.write_text(json.dumps(summary))
        previous, self.out = self.out, self.root / "resumed-legacy"
        resumed = self.run_cli("--resume-from", str(previous))
        self.assertEqual(resumed.returncode, 0, resumed.stderr)

    def test_removed_provider_options_fail_before_launch(self):
        for extra in (("--backend", "opencode"), ("--allow-command", "python *"),
                      ("--instructions-file", "/unused/role.md")):
            with self.subTest(extra=extra):
                result = self.run_cli(*extra)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("unrecognized arguments", result.stderr)
                self.assertFalse(self.out.exists())
                self.assertFalse((self.cwd / "received.json").exists())

    def test_retired_worker_cannot_resume_as_claude(self):
        previous = self.root / "previous"
        previous.mkdir()
        summary = {"backend": "retired", "session_id": str(uuid.uuid4()),
                   "codex_thread_id": self.env["CODEX_THREAD_ID"], "cwd": str(self.cwd)}
        path = previous / "summary.json"
        path.write_text(json.dumps(summary))
        result = self.run_cli("--resume-from", str(previous))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Only Claude Code workers can be resumed", result.stderr)
        self.assertEqual(json.loads(path.read_text()), summary)
        self.assertFalse(self.out.exists())
        self.assertFalse((self.cwd / "received.json").exists())

    def test_raw_usage_is_preserved_without_increasing_completion_context(self):
        result = self.run_cli(case="usage")
        self.assertEqual(result.returncode, 0, result.stderr)
        raw = json.loads((self.out / "result.json").read_text())
        self.assertEqual(raw["usage"]["output_tokens"], 150)
        self.assertEqual(raw["total_cost_usd"], .41)
        self.assertNotIn("usage", json.loads(result.stdout))

    def test_wait_observes_real_launcher_results_without_relaunching(self):
        for case, expected in (("success", "completed"), ("blocked", "blocked"),
                               ("quota", "error"), ("expired", "error"), ("timeout", "timeout")):
            with self.subTest(case=case):
                self.out = self.root / ("wait-" + case)
                command = [sys.executable, str(SCRIPT), "--cwd", str(self.cwd),
                    "--prompt-file", str(self.prompt), "--output-dir", str(self.out),
                    "--once", "--timeout", ".3" if case == "timeout" else "5"]
                with subprocess.Popen(command, env={**self.env, "FIXTURE_CASE": case,
                        "FIXTURE_DELAY": ".15"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        text=True) as launcher:
                    started = json.loads(launcher.stderr.readline())
                    self.assertEqual(started["event"], "started")
                    uuid.UUID(started["run_id"])
                    self.assertGreater(started["worker_pid"], 0)
                    self.assertEqual(started["output_dir"], str(self.out.resolve()))
                    self.assertIsNone(launcher.poll(), "Run ID must be available while worker is active")
                    observed = subprocess.run([sys.executable, str(SCRIPT.with_name("wait.py")),
                        "--run-id", started["run_id"], "--timeout", "4"], env=self.env,
                        text=True, capture_output=True, timeout=6)
                    stdout, stderr = launcher.communicate(timeout=6)
                self.assertEqual(observed.returncode, 0, observed.stderr)
                event = json.loads(observed.stdout)
                self.assertEqual(event["event"], "ready", event)
                ready = event["ready"][0]
                self.assertEqual(ready["status"], expected)
                self.assertEqual(ready["run_id"], json.loads(stdout)["run_id"])
                self.assertEqual(ready["run_id"], started["run_id"])
                self.assertEqual(event["pending_run_ids"], [])
                self.assertEqual(event["pending_dirs"], [])
                if case == "quota":
                    self.assertIn("session limit", ready["report_excerpt"])

    def test_launcher_grants_monitor_access_without_exposing_key_to_worker(self):
        command = [sys.executable, str(SCRIPT), "--once", "--cwd", str(self.cwd),
                   "--prompt-file", str(self.prompt), "--output-dir", str(self.out)]
        with subprocess.Popen(command, env={**self.env, "FIXTURE_DELAY": "1"},
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as launcher:
            started = json.loads(launcher.stderr.readline())
            self.assertTrue(started.get("watch_key"), "Started event must grant monitoring access")
            monitor_env = {**self.env, "CODEX_THREAD_ID": "00000000-0000-4000-8000-000000000002"}
            observed = subprocess.run([sys.executable, str(SCRIPT.with_name("wait.py")),
                "--run-id", started["run_id"], "--watch-key",
                f'{started["run_id"]}={started["watch_key"]}', "--timeout", "4"],
                env=monitor_env, capture_output=True, text=True, timeout=6)
            stdout, stderr = launcher.communicate(timeout=6)
        self.assertEqual(launcher.returncode, 0, stderr)
        self.assertEqual(observed.returncode, 0, observed.stderr)
        data = json.loads(observed.stdout)
        self.assertEqual(data["ready"][0]["status"], "completed", data)
        self.assertEqual(json.loads(stdout)["coordinator_task_id"], self.env["CODEX_THREAD_ID"])
        self.assertEqual(json.loads(stdout)["coordinator_host"], "codex")
        record_path = Path(self.env["CODEX_HOME"]) / "tafwid/state/workers" / (started["run_id"] + ".json")
        for content in (stdout, observed.stdout, record_path.read_text(),
                        *(p.read_text() for p in self.out.iterdir() if p.is_file()),
                        (self.cwd / "received.json").read_text()):
            self.assertNotIn(started["watch_key"], content)
        previous = self.out
        self.out = self.root / "monitor-resume"
        self.env = monitor_env
        (self.cwd / "received.json").unlink()
        resumed = self.run_cli("--resume-from", str(previous))
        self.assertEqual(resumed.returncode, 2, resumed.stderr)
        self.assertIn("task ownership", resumed.stderr)
        self.assertFalse(self.out.exists())
        self.assertFalse((self.cwd / "received.json").exists())

    def save_policy(self, policy, task=False):
        root = Path(self.env["CODEX_HOME"]) / "tafwid/state"
        path = (root / "tasks" / self.env["CODEX_THREAD_ID"] / "settings.json"
                if task else root / "settings.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": 1, "permission_policy": policy}))
        return path

    def test_full_access_edit_has_shell_and_audited_permission_mode(self):
        self.save_policy("full")
        run = self.run_cli("--mode", "edit")
        self.assertEqual(run.returncode, 0, run.stderr)
        argv = json.loads((self.cwd / "received.json").read_text())["args"]
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "bypassPermissions")
        self.assertIn("Bash", argv[argv.index("--tools") + 1].split(","))
        self.assertNotIn("--allowedTools", argv)
        summary = json.loads(run.stdout)
        permission = summary["permissions"]
        self.assertEqual(permission["effective"], "full")
        self.assertEqual(permission["source"], "settings")
        self.assertEqual(json.loads((self.out / "request.json").read_text())["permissions"], permission)
        records = list((Path(self.env["CODEX_HOME"]) / "tafwid/state/workers").glob("*.json"))
        self.assertEqual(json.loads(records[0].read_text())["permissions"], permission)

    def test_inherit_requires_current_exact_full_access_signal(self):
        self.save_policy("inherit")
        for index, signal in enumerate((":danger-full-access", ":workspace-write", "custom-full-access", "")):
            with self.subTest(signal=signal):
                self.out = self.root / f"inherit-{index}"
                self.env["CODEX_PERMISSION_PROFILE"] = signal
                run = self.run_cli("--mode", "edit")
                self.assertEqual(run.returncode, 0, run.stderr)
                expected = "full" if index == 0 else "scoped"
                self.assertEqual(json.loads(run.stdout)["permissions"]["effective"], expected)

    def test_resume_rechecks_permissions_and_explicit_scoped_override(self):
        self.save_policy("full")
        first = self.run_cli("--mode", "edit")
        self.assertEqual(first.returncode, 0, first.stderr)
        previous = self.out
        self.out = self.root / "resumed"
        self.save_policy("scoped", task=True)
        resumed = self.run_cli("--mode", "edit", "--resume-from", str(previous))
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(json.loads(resumed.stdout)["permissions"]["effective"], "scoped")
        self.save_policy("full")
        self.out = self.root / "override"
        override = self.run_cli("--permissions", "scoped", "--mode", "edit")
        self.assertEqual(override.returncode, 0, override.stderr)
        self.assertEqual(json.loads(override.stdout)["permissions"]["effective"], "scoped")
        self.assertEqual(json.loads(override.stdout)["permissions"]["source"], "override")

    def test_inherited_full_access_does_not_survive_restricted_resume(self):
        self.save_policy("inherit")
        self.env["CODEX_PERMISSION_PROFILE"] = ":danger-full-access"
        first = self.run_cli("--mode", "edit")
        self.assertEqual(first.returncode, 0, first.stderr)
        previous = self.out
        self.out = self.root / "restricted-resume"
        self.env.pop("CODEX_PERMISSION_PROFILE")
        resumed = self.run_cli("--mode", "edit", "--resume-from", str(previous))
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        argv = json.loads((self.cwd / "received.json").read_text())["args"]
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "dontAsk")
        self.assertNotIn("Bash", argv[argv.index("--tools") + 1].split(","))
        self.assertEqual(json.loads(resumed.stdout)["session_id"], json.loads(first.stdout)["session_id"])

    def test_full_read_worker_retains_inspection_tools_only(self):
        self.save_policy("full")
        run = self.run_cli()
        self.assertEqual(run.returncode, 0, run.stderr)
        argv = json.loads((self.cwd / "received.json").read_text())["args"]
        self.assertNotIn("Bash", argv[argv.index("--tools") + 1].split(","))
        self.assertNotIn("Write", argv[argv.index("--tools") + 1].split(","))

    def test_invalid_saved_policy_stops_before_worker_launch(self):
        self.save_policy("typo")
        run = self.run_cli()
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse((self.cwd / "received.json").exists())

    def test_automatic_delegation_requires_this_tasks_switch(self):
        run = self.run_cli(once=False)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("off", run.stderr)
        self.assertFalse((self.cwd / "received.json").exists())
        enabled = subprocess.run([sys.executable, str(STATE), "on"], env=self.env,
                                 capture_output=True, text=True)
        self.assertEqual(enabled.returncode, 0, enabled.stderr)
        run = self.run_cli(once=False)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_once_does_not_enable_future_delegation(self):
        self.assertEqual(self.run_cli().returncode, 0)
        self.out = self.root / "second"
        run = self.run_cli(once=False)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("off", run.stderr)

    def test_resume_rejects_another_codex_task_even_in_same_workspace(self):
        self.assertEqual(self.run_cli().returncode, 0)
        previous = self.out
        self.out = self.root / "another-task"
        (self.cwd / "received.json").unlink()
        self.env["CODEX_THREAD_ID"] = "00000000-0000-4000-8000-000000000002"
        run = self.run_cli("--resume-from", str(previous))
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse((self.cwd / "received.json").exists())


    def test_off_during_authentication_prevents_pending_worker(self):
        enabled = subprocess.run([sys.executable, str(STATE), "on"], env=self.env,
                                 capture_output=True, text=True)
        self.assertEqual(enabled.returncode, 0, enabled.stderr)
        proc = subprocess.Popen([sys.executable, str(SCRIPT), "--cwd", str(self.cwd),
            "--prompt-file", str(self.prompt), "--output-dir", str(self.out)],
            env={**self.env, "FIXTURE_CASE": "slow_auth"}, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not (self.cwd / "auth-started").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((self.cwd / "auth-started").exists())
            disabled = subprocess.run([sys.executable, str(STATE), "off"], env=self.env,
                                      capture_output=True, text=True)
            self.assertEqual(disabled.returncode, 0, disabled.stderr)
            stdout, stderr = proc.communicate(timeout=10)
            self.assertNotEqual(proc.returncode, 0, stdout)
            self.assertIn("off", stderr)
            self.assertFalse((self.cwd / "received.json").exists())
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()

    def test_removing_claude_from_mixed_pool_prevents_pending_claude_launch(self):
        enabled = subprocess.run([sys.executable, str(STATE), "on"], env=self.env,
                                 capture_output=True, text=True)
        self.assertEqual(enabled.returncode, 0, enabled.stderr)
        state = Path(self.env["CODEX_HOME"]) / "tafwid/state" / (self.env["CODEX_THREAD_ID"] + ".json")
        pool = json.loads(state.read_text())
        pool["connections"].append({"id": "gpt:other-id", "selector": "gpt:other",
                                    "provider": "gpt", "name": "other", "kind": "personal"})
        state.write_text(json.dumps(pool))
        proc = subprocess.Popen([sys.executable, str(SCRIPT), "--connection", "claude",
            "--cwd", str(self.cwd), "--prompt-file", str(self.prompt),
            "--output-dir", str(self.out)], env={**self.env, "FIXTURE_CASE": "slow_auth"},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not (self.cwd / "auth-started").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((self.cwd / "auth-started").exists())
            disabled = subprocess.run([sys.executable, str(STATE), "off", "claude"],
                                      env=self.env, capture_output=True, text=True)
            self.assertEqual(disabled.returncode, 0, disabled.stderr)
            self.assertTrue(json.loads(disabled.stdout)["enabled"], "GPT stays enabled")
            stdout, stderr = proc.communicate(timeout=10)
            self.assertNotEqual(proc.returncode, 0, stdout)
            self.assertFalse((self.cwd / "received.json").exists())
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()

    def test_legacy_run_without_task_ownership_cannot_be_resumed(self):
        self.assertEqual(self.run_cli().returncode, 0)
        previous = self.out
        summary = self.summary()
        del summary["coordinator_task_id"]
        (previous / "summary.json").write_text(json.dumps(summary))
        self.out = self.root / "legacy-resume"
        (self.cwd / "received.json").unlink()
        run = self.run_cli("--resume-from", str(previous))
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse((self.cwd / "received.json").exists())

    def summary(self):
        return json.loads((self.out / "summary.json").read_text())

    def sent_args(self):
        return json.loads((self.cwd / "received.json").read_text())["args"]

    def sent_flag(self, name):
        args = self.sent_args()
        return args[args.index(name) + 1] if name in args else None

    def test_success_is_compact_but_full_report_is_saved(self):
        run = self.run_cli()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertLess(len(run.stdout), 5000)
        self.assertEqual(self.summary()["status"], "completed")
        self.assertGreater(len((self.out / "report.md").read_text()), 10000)
        self.assertEqual(self.out.stat().st_mode & 0o777, 0o700)

    def test_completed_launch_records_private_wait_state(self):
        run = self.run_cli("--title", "Review fixture", "--profile", "standard", "--role", "reviewer")
        self.assertEqual(run.returncode, 0, run.stderr)
        summary = self.summary()
        path = Path(self.env["CODEX_HOME"]) / "tafwid/state/workers" / (summary["run_id"] + ".json")
        record = json.loads(path.read_text())
        self.assertEqual(record["title"], "Review fixture")
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["session_id"], summary["session_id"])
        self.assertEqual(record["coordinator_task_id"], self.env["CODEX_THREAD_ID"])
        self.assertEqual(record["model_selection"]["requested_model"], "opus")
        self.assertIn("Done.", record["report_excerpt"])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_wait_state_tracks_running_worker_before_result_exists(self):
        proc = subprocess.Popen([sys.executable, str(SCRIPT), "--once", "--cwd", str(self.cwd),
            "--prompt-file", str(self.prompt), "--output-dir", str(self.out), "--timeout", "2"],
            env={**self.env, "FIXTURE_CASE": "timeout"}, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 4
            records = []
            while time.monotonic() < deadline:
                records = list((Path(self.env["CODEX_HOME"]) / "tafwid/state/workers").glob("*.json"))
                if records and json.loads(records[0].read_text())["status"] == "running":
                    break
                time.sleep(0.02)
            self.assertTrue(records)
            self.assertEqual(json.loads(records[0].read_text())["status"], "running")
            self.assertFalse((self.out / "summary.json").exists())
            proc.communicate(timeout=10)
            self.assertEqual(json.loads(records[0].read_text())["status"], "timeout")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()

    def test_prompt_is_literal_and_read_mode_has_no_shell_or_write_tools(self):
        run = self.run_cli()
        self.assertEqual(run.returncode, 0, run.stderr)
        received = json.loads((self.cwd / "received.json").read_text())
        self.assertIn(self.prompt.read_text(), received["prompt"])
        self.assertFalse((self.cwd / "INJECTED").exists())
        self.assertFalse((self.cwd / "INJECTED2").exists())
        args = received["args"]
        self.assertEqual(set(args[args.index("--tools") + 1].split(",")), {"Read", "Glob", "Grep", "Skill", "ToolSearch"})
        self.assertNotIn("--safe-mode", args)
        self.assertNotIn("--strict-mcp-config", args)
        self.assertNotIn("--mcp-config", args)


    def test_blocked_worker_is_not_marked_complete(self):
        run = self.run_cli(case="blocked")
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(self.summary()["status"], "blocked")


    def test_missing_structured_report_or_invalid_status_needs_review(self):
        for case in ("missing_structured", "invalid_status"):
            with self.subTest(case=case):
                self.out = self.root / case
                run = self.run_cli(case=case)
                self.assertNotEqual(run.returncode, 0)
                self.assertEqual(self.summary()["status"], "needs_review")

    def test_exact_plugin_tool_can_be_allowed_without_enabling_bash(self):
        run = self.run_cli("--allow-tool", "mcp__chrome_devtools__take_screenshot")
        self.assertEqual(run.returncode, 0, run.stderr)
        args = json.loads((self.cwd / "received.json").read_text())["args"]
        self.assertNotIn("Bash", args[args.index("--tools") + 1].split(","))
        self.assertIn("mcp__chrome_devtools__take_screenshot", args[args.index("--allowedTools") + 1])

    def test_broad_plugin_tool_wildcard_is_rejected(self):
        run = self.run_cli("--allow-tool", "mcp__chrome_devtools__*")
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse((self.cwd / "received.json").exists())

    def test_edit_mode_passes_only_requested_shell_allowance(self):
        run = self.run_cli("--mode", "edit", "--allow-tool", "Bash(python3 -m unittest *)")
        self.assertEqual(run.returncode, 0, run.stderr)
        args = json.loads((self.cwd / "received.json").read_text())["args"]
        self.assertIn("Bash(python3 -m unittest *)", args[args.index("--allowedTools") + 1])
        self.assertNotIn("--dangerously-skip-permissions", args)

    def test_rejects_shell_in_read_mode(self):
        run = self.run_cli("--allow-tool", "Bash(pytest *)")
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse((self.cwd / "received.json").exists())

    def test_rejects_api_environment_without_leaking_value(self):
        self.env["ANTHROPIC_API_KEY"] = "fixture-secret-do-not-print"
        run = self.run_cli()
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("ANTHROPIC_API_KEY", run.stdout + run.stderr)
        self.assertNotIn("fixture-secret", run.stdout + run.stderr)
        self.assertFalse((self.cwd / "received.json").exists())

    def test_rejects_api_auth_before_starting_task(self):
        run = self.run_cli(case="api")
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse((self.cwd / "received.json").exists())

    def test_runtime_auth_error_is_failure_even_with_zero_cli_exit(self):
        run = self.run_cli(case="expired")
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(self.summary()["status"], "error")
        self.assertIn("OAuth", run.stdout)

    def test_denials_require_review_instead_of_silent_success(self):
        run = self.run_cli(case="denied")
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(self.summary()["status"], "needs_review")
        self.assertEqual(self.summary()["permission_denials"], 1)

    def test_malformed_output_is_failure(self):
        run = self.run_cli(case="malformed")
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(self.summary()["status"], "error")

    def test_timeout_is_not_completion(self):
        run = self.run_cli("--timeout", "0.3", case="timeout")
        self.assertEqual(run.returncode, 124, run.stderr)
        self.assertEqual(self.summary()["status"], "timeout")

    def test_resume_uses_recorded_session(self):
        self.assertEqual(self.run_cli().returncode, 0)
        session = self.summary()["session_id"]
        previous = self.out
        self.out = self.root / "followup"
        run = self.run_cli("--resume-from", str(previous))
        self.assertEqual(run.returncode, 0, run.stderr)
        args = json.loads((self.cwd / "received.json").read_text())["args"]
        self.assertEqual(args[args.index("--resume") + 1], session)

    def test_timeout_retains_session_for_recovery(self):
        run = self.run_cli("--timeout", "0.3", case="timeout")
        self.assertEqual(run.returncode, 124)
        session = self.summary()["session_id"]
        self.assertIsNotNone(session, "An interrupted first run must retain its session ID")
        uuid.UUID(session)
        previous = self.out
        self.out = self.root / "recovery"
        run = self.run_cli("--resume-from", str(previous))
        self.assertEqual(run.returncode, 0, run.stderr)
        args = json.loads((self.cwd / "received.json").read_text())["args"]
        self.assertEqual(args[args.index("--resume") + 1], session)

    def test_resume_rejects_a_different_workspace(self):
        self.assertEqual(self.run_cli().returncode, 0)
        previous = self.out
        self.out = self.root / "followup"
        self.cwd = self.root / "other"
        self.cwd.mkdir()
        run = self.run_cli("--resume-from", str(previous))
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse((self.cwd / "received.json").exists())

    def test_existing_output_directory_is_not_overwritten(self):
        self.out.mkdir()
        sentinel = self.out / "summary.json"
        sentinel.write_text("keep me")
        run = self.run_cli()
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(sentinel.read_text(), "keep me")

    def save_model_routes(self, deep="fable", final_review=None, task=False):
        config = {"version": 2, "permission_policy": "scoped", "models": {
            "profiles": {"fast": "sonnet", "standard": "opus", "deep": deep},
            "tasks": {name: None for name in ("mechanical", "investigation", "implementation", "debugging",
                      "documentation", "testing", "task_review", "architecture", "final_review")}}}
        config["models"]["tasks"]["final_review"] = final_review
        root = Path(self.env["CODEX_HOME"]) / "tafwid/state"
        path = (root / "tasks" / self.env["CODEX_THREAD_ID"] / "settings.json"
                if task else root / "settings.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config))

    def test_task_override_and_tier_default_reach_actual_claude_argv(self):
        self.save_model_routes(final_review="opus")
        for index, task, model, source in ((0, "architecture", "fable", "task_default"),
                                           (1, "final_review", "opus", "task_override")):
            with self.subTest(task=task):
                self.out = self.root / f"routed-{index}"
                run = self.run_cli("--task-type", task, "--role", "reviewer")
                self.assertEqual(run.returncode, 0, run.stderr)
                argv = json.loads((self.cwd / "received.json").read_text())["args"]
                self.assertEqual(argv[argv.index("--model") + 1], model)
                selection = json.loads(run.stdout)["model_selection"]
                self.assertEqual(selection["task_type"], task)
                self.assertEqual(selection["source"], source)
                self.assertEqual(selection["effort"], "high")

    def test_configured_tier_changes_legacy_profile_dispatch(self):
        self.save_model_routes(deep="opus")
        run = self.run_cli("--profile", "deep")
        self.assertEqual(run.returncode, 0, run.stderr)
        argv = json.loads((self.cwd / "received.json").read_text())["args"]
        self.assertEqual(argv[argv.index("--model") + 1], "opus")

    def test_later_workers_and_resume_ignore_other_tasks_global_changes(self):
        self.save_model_routes(deep='opus')
        path = Path(self.env['CODEX_HOME']) / 'tafwid/state/settings.json'
        config = json.loads(path.read_text())
        config['permission_policy'] = 'full'
        path.write_text(json.dumps(config))
        self.assertEqual(self.run_cli('--profile', 'deep', '--mode', 'edit').returncode, 0)
        previous = self.out
        self.save_model_routes(deep='sonnet')
        self.out = self.root / 'later-worker'
        result = self.run_cli('--profile', 'deep', '--mode', 'edit')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.sent_flag('--model'), 'opus')
        self.assertEqual(self.sent_flag('--permission-mode'), 'bypassPermissions')
        self.out = self.root / 'after-global-change-resume'
        result = self.run_cli('--resume-from', str(previous), '--mode', 'edit')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.sent_flag('--model'), 'opus')
        self.assertEqual(self.sent_flag('--permission-mode'), 'bypassPermissions')
        self.env['CODEX_THREAD_ID'] = '00000000-0000-4000-8000-000000000002'
        self.out = self.root / 'new-task'
        result = self.run_cli('--profile', 'deep', '--mode', 'edit')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.sent_flag('--model'), 'sonnet')
        self.assertEqual(self.sent_flag('--permission-mode'), 'dontAsk')

    def test_run_overrides_do_not_change_task_snapshot(self):
        first = self.run_cli('--profile', 'standard', '--permissions', 'full')
        self.assertEqual(first.returncode, 0, first.stderr)
        path = Path(self.env['CODEX_HOME']) / 'tafwid/state/tasks' / self.env['CODEX_THREAD_ID'] / 'settings.json'
        self.assertTrue(path.exists())
        before = path.read_bytes()
        self.out = self.root / 'default-worker'
        result = self.run_cli('--profile', 'standard')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.sent_flag('--permission-mode'), 'dontAsk')
        self.assertEqual(path.read_bytes(), before)

    def test_resume_keeps_model_until_explicitly_rerouted(self):
        self.save_model_routes(final_review="fable")
        first = self.run_cli("--task-type", "final_review")
        self.assertEqual(first.returncode, 0, first.stderr)
        previous = self.out
        self.save_model_routes(final_review="opus", task=True)
        self.out = self.root / "retained"
        run = self.run_cli("--resume-from", str(previous))
        self.assertEqual(run.returncode, 0, run.stderr)
        selection = json.loads(run.stdout)["model_selection"]
        self.assertEqual(selection["requested_model"], "fable")
        self.assertEqual(selection["task_type"], "final_review")
        self.out = self.root / "rerouted"
        run = self.run_cli("--resume-from", str(previous), "--task-type", "final_review")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["model_selection"]["requested_model"], "opus")

    def test_explicit_model_remains_available_with_saved_routing(self):
        self.save_model_routes(deep="opus")
        run = self.run_cli("--model", "fable", "--effort", "high")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["model_selection"]["requested_model"], "fable")

    def test_each_profile_resolves_to_its_documented_model_and_effort(self):
        for profile, model, effort in (("fast", "sonnet", None),
                                       ("standard", "opus", "medium"),
                                       ("deep", "fable", "high")):
            with self.subTest(profile=profile):
                self.out = self.root / ("profile-" + profile)
                run = self.run_cli("--profile", profile)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(self.sent_flag("--model"), model)
                self.assertEqual(self.sent_flag("--effort"), effort)
                selection = self.summary()["model_selection"]
                self.assertEqual(selection["profile"], profile)
                self.assertEqual(selection["requested_model"], model)
                self.assertEqual(selection["effort"], effort)
                self.assertEqual(selection["source"], "profile")
                self.assertEqual(selection["role"], "worker")
                self.assertTrue(selection["reason"].strip())

    def test_explicit_effort_overrides_the_profile_default(self):
        run = self.run_cli("--profile", "deep", "--effort", "max")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.sent_flag("--model"), "fable")
        self.assertEqual(self.sent_flag("--effort"), "max")
        selection = self.summary()["model_selection"]
        self.assertEqual(selection["profile"], "deep")
        self.assertEqual(selection["effort"], "max")
        self.assertEqual(selection["source"], "profile")

    def test_explicit_model_and_effort_reach_claude_and_the_audit_record(self):
        run = self.run_cli("--model", "claude-opus-5", "--effort", "low")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.sent_flag("--model"), "claude-opus-5")
        self.assertEqual(self.sent_flag("--effort"), "low")
        selection = self.summary()["model_selection"]
        self.assertIsNone(selection["profile"])
        self.assertEqual(selection["requested_model"], "claude-opus-5")
        self.assertEqual(selection["effort"], "low")
        self.assertEqual(selection["source"], "explicit")
        request = json.loads((self.out / "request.json").read_text())
        self.assertEqual(request["model_selection"], selection)

    def test_run_without_a_selector_uses_claudes_default_model(self):
        run = self.run_cli()
        self.assertEqual(run.returncode, 0, run.stderr)
        args = self.sent_args()
        self.assertNotIn("--model", args)
        self.assertNotIn("--effort", args)
        selection = self.summary()["model_selection"]
        self.assertIsNone(selection["profile"])
        self.assertIsNone(selection["requested_model"])
        self.assertIsNone(selection["effort"])
        self.assertEqual(selection["role"], "worker")
        self.assertEqual(selection["source"], "default")

    def test_role_and_reason_are_recorded_without_widening_tool_access(self):
        run = self.run_cli("--profile", "deep", "--role", "reviewer",
                           "--selection-reason", "Architecture review needs the strongest model")
        self.assertEqual(run.returncode, 0, run.stderr)
        selection = self.summary()["model_selection"]
        self.assertEqual(selection["role"], "reviewer")
        self.assertEqual(selection["reason"], "Architecture review needs the strongest model")
        args = self.sent_args()
        self.assertEqual(set(args[args.index("--tools") + 1].split(",")),
                         {"Read", "Glob", "Grep", "Skill", "ToolSearch"})
        self.assertNotIn("--dangerously-skip-permissions", args)

    def test_profile_and_model_cannot_be_requested_together(self):
        run = self.run_cli("--profile", "deep", "--model", "claude-opus-5")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("--profile", run.stderr)
        self.assertFalse((self.cwd / "received.json").exists())

    def test_unknown_profile_or_effort_is_rejected_before_launch(self):
        for flag, value in (("--profile", "turbo"), ("--effort", "extreme")):
            with self.subTest(flag=flag):
                self.out = self.root / ("unknown" + flag)
                run = self.run_cli(flag, value)
                self.assertNotEqual(run.returncode, 0)
                self.assertFalse((self.cwd / "received.json").exists())

    def test_blank_selection_values_are_rejected_before_launch(self):
        for flag, value in (("--model", "   "), ("--role", " "), ("--selection-reason", "")):
            with self.subTest(flag=flag):
                self.out = self.root / ("blank" + flag)
                run = self.run_cli(flag, value)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn(flag, run.stdout + run.stderr)
                self.assertFalse((self.cwd / "received.json").exists())

    def test_resume_keeps_the_selected_model_and_role_by_default(self):
        self.assertEqual(self.run_cli("--profile", "deep", "--role", "implementer").returncode, 0)
        previous = self.out
        self.out = self.root / "resumed-selection"
        run = self.run_cli("--resume-from", str(previous))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.sent_flag("--model"), "fable")
        self.assertEqual(self.sent_flag("--effort"), "high")
        selection = self.summary()["model_selection"]
        self.assertEqual(selection["profile"], "deep")
        self.assertEqual(selection["requested_model"], "fable")
        self.assertEqual(selection["role"], "implementer")
        self.assertEqual(selection["source"], "resume")

    def test_resume_preserves_a_model_recorded_before_profile_mapping_changed(self):
        self.assertEqual(self.run_cli("--model", "opus", "--effort", "high").returncode, 0)
        previous = self.out
        summary = self.summary()
        summary["model_selection"].update(profile="deep", source="profile")
        (previous / "summary.json").write_text(json.dumps(summary))
        self.out = self.root / "legacy-profile-resume"
        run = self.run_cli("--resume-from", str(previous))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.sent_flag("--model"), "opus")
        self.assertEqual(self.sent_flag("--effort"), "high")
        self.assertEqual(self.summary()["model_selection"]["source"], "resume")

    def test_resume_can_switch_to_a_different_profile(self):
        self.assertEqual(self.run_cli("--profile", "deep", "--selection-reason",
                                      "architecture work").returncode, 0)
        previous = self.out
        self.out = self.root / "downshifted"
        run = self.run_cli("--resume-from", str(previous), "--profile", "fast")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.sent_flag("--model"), "sonnet")
        self.assertIsNone(self.sent_flag("--effort"))
        selection = self.summary()["model_selection"]
        self.assertEqual(selection["profile"], "fast")
        self.assertIsNone(selection["effort"])
        self.assertEqual(selection["source"], "profile")
        self.assertNotIn("architecture work", selection["reason"])

    def test_resume_effort_override_keeps_the_inherited_model(self):
        self.assertEqual(self.run_cli("--profile", "standard").returncode, 0)
        previous = self.out
        self.out = self.root / "harder-resume"
        run = self.run_cli("--resume-from", str(previous), "--effort", "max")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.sent_flag("--model"), "opus")
        self.assertEqual(self.sent_flag("--effort"), "max")
        selection = self.summary()["model_selection"]
        self.assertEqual(selection["profile"], "standard")
        self.assertEqual(selection["effort"], "max")
        self.assertEqual(selection["source"], "resume")

    def test_resume_keeps_an_effort_only_selection_on_the_default_model(self):
        self.assertEqual(self.run_cli("--effort", "high", "--role", "reviewer",
                                      "--selection-reason", "deep reading on the default model").returncode, 0)
        previous = self.out
        self.out = self.root / "resumed-effort-only"
        run = self.run_cli("--resume-from", str(previous))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.sent_flag("--effort"), "high")
        self.assertNotIn("--model", self.sent_args())
        selection = self.summary()["model_selection"]
        self.assertIsNone(selection["profile"])
        self.assertIsNone(selection["requested_model"])
        self.assertEqual(selection["effort"], "high")
        self.assertEqual(selection["role"], "reviewer")
        self.assertEqual(selection["reason"], "deep reading on the default model")
        self.assertEqual(selection["source"], "resume")

    def test_resume_can_change_the_effort_of_a_default_model_worker(self):
        self.assertEqual(self.run_cli("--effort", "low", "--selection-reason",
                                      "quick triage").returncode, 0)
        previous = self.out
        self.out = self.root / "reworked-effort"
        run = self.run_cli("--resume-from", str(previous), "--effort", "max")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.sent_flag("--effort"), "max")
        self.assertNotIn("--model", self.sent_args())
        selection = self.summary()["model_selection"]
        self.assertIsNone(selection["requested_model"])
        self.assertEqual(selection["effort"], "max")
        self.assertEqual(selection["source"], "resume")
        self.assertNotIn("quick triage", selection["reason"])

    def test_new_model_on_resume_clears_the_earlier_profile_effort(self):
        self.assertEqual(self.run_cli("--profile", "deep").returncode, 0)
        previous = self.out
        self.out = self.root / "switched-model"
        run = self.run_cli("--resume-from", str(previous), "--model", "claude-sonnet-5")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.sent_flag("--model"), "claude-sonnet-5")
        self.assertIsNone(self.sent_flag("--effort"))
        selection = self.summary()["model_selection"]
        self.assertIsNone(selection["profile"])
        self.assertIsNone(selection["effort"])
        self.assertEqual(selection["source"], "explicit")

    def test_resume_of_a_run_without_selection_metadata_requests_no_model(self):
        self.assertEqual(self.run_cli().returncode, 0)
        previous = self.out
        summary = self.summary()
        del summary["model_selection"]
        (previous / "summary.json").write_text(json.dumps(summary))
        self.out = self.root / "legacy-selection"
        run = self.run_cli("--resume-from", str(previous))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn("--model", self.sent_args())
        self.assertEqual(self.summary()["model_selection"]["source"], "default")

    def test_models_used_reports_sorted_usage_keys(self):
        run = self.run_cli("--profile", "standard", case="usage")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.summary()["models_used"], ["claude-haiku-4-5", "claude-sonnet-5"])

    def test_absent_or_malformed_usage_metadata_leaves_the_result_usable(self):
        for case in ("success", "bad_usage"):
            with self.subTest(case=case):
                self.out = self.root / ("usage-" + case)
                run = self.run_cli(case=case)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(self.summary()["status"], "completed")
                self.assertEqual(self.summary()["models_used"], [])

    def test_timeout_summary_still_records_the_requested_selection(self):
        run = self.run_cli("--profile", "deep", "--timeout", "0.3", case="timeout")
        self.assertEqual(run.returncode, 124, run.stderr)
        summary = self.summary()
        self.assertEqual(summary["status"], "timeout")
        self.assertEqual(summary["model_selection"]["requested_model"], "fable")
        self.assertEqual(summary["models_used"], [])


if __name__ == "__main__":
    unittest.main()
