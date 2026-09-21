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
if sys.argv[1:3] == ["plugin", "list"]:
    Path("plugin-list-called").write_text("yes")
    print(os.environ.get("FIXTURE_PLUGINS", "[]"))
    sys.exit(0)
if "auth" in sys.argv:
    if case == "slow_auth":
        Path("auth-started").write_text("ready")
        time.sleep(1)
    print(json.dumps({"loggedIn": True, "authMethod": "api_key" if case == "api" else "claude.ai",
                      "apiProvider": "firstParty", "subscriptionType": "max"}))
    sys.exit(0)
prompt = sys.stdin.read()
Path("received.json").write_text(json.dumps({"args": sys.argv[1:], "prompt": prompt}))
time.sleep(float(os.environ.get("FIXTURE_DELAY", "0")))
if case == "timeout":
    time.sleep(30)
if case == "malformed":
    print("not json")
    sys.exit(0)
structured = {"status": "completed", "report": "Done. " + "x" * 10000, "handoff": None}
if case in ("native", "native_denied"):
    structured = {"status": "native_required", "report": "Implementation finished; visual check pending.",
        "handoff": {"capability": "browser", "reason": "Chrome connection unavailable",
        "requested_action": "Open http://localhost:3000 in the requested Chrome browser and check the menu",
        "context": "Server is running; use the existing checkout. No form submission is needed.",
        "expected_result": "Desktop and mobile screenshots plus observations"}}
if case == "blocked":
    structured = {"status": "blocked", "report": "Acceptance criteria are missing.", "handoff": None}
if case == "invalid_handoff":
    structured = {"status": "native_required", "report": "Need help", "handoff": None}
payload = {"type": "result", "subtype": "success", "is_error": case == "expired",
 "result": "OAuth session expired" if case == "expired" else "Done. " + "x" * 10000,
 "session_id": sys.argv[sys.argv.index("--resume") + 1] if "--resume" in sys.argv else sys.argv[sys.argv.index("--session-id") + 1],
 "permission_denials": [{"tool_name": "Bash", "tool_input": {"command": "pytest"}}] if case in ("denied", "native_denied") else []}
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
        self.env["CLAUDE_CONFIG_DIR"] = str(self.root / "claude-config")
        self.env["CODEX_THREAD_ID"] = "00000000-0000-4000-8000-000000000001"
        self.env.pop("CODEX_SESSION_ID", None)

    def run_cli(self, *extra, case="success", once=True):
        return subprocess.run([sys.executable, str(SCRIPT), "--cwd", str(self.cwd),
            "--prompt-file", str(self.prompt), "--output-dir", str(self.out),
            *(["--once"] if once else []), *extra],
            env={**self.env, "FIXTURE_CASE": case}, text=True, capture_output=True, timeout=15)

    def test_usage_is_saved_for_dashboard_without_increasing_completion_context(self):
        result = self.run_cli(case="usage")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((self.out / "summary.json").read_text())
        self.assertEqual(summary["usage"]["output"], 150)
        self.assertEqual(summary["usage"]["cost_usd"], .41)
        self.assertNotIn("usage", json.loads(result.stdout))

    def test_wait_observes_real_launcher_results_without_relaunching(self):
        for case, expected in (("success", "completed"), ("native", "native_required"),
                               ("quota", "error"), ("expired", "error"), ("timeout", "timeout")):
            with self.subTest(case=case):
                self.out = self.root / ("wait-" + case)
                command = [sys.executable, str(SCRIPT), "--cwd", str(self.cwd),
                    "--prompt-file", str(self.prompt), "--output-dir", str(self.out),
                    "--once", "--timeout", ".3" if case == "timeout" else "5"]
                with subprocess.Popen(command, env={**self.env, "FIXTURE_CASE": case,
                        "FIXTURE_DELAY": ".15"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        text=True) as launcher:
                    observed = subprocess.run([sys.executable, str(SCRIPT.with_name("wait.py")),
                        "--run-dir", str(self.out), "--timeout", "4"], env=self.env,
                        text=True, capture_output=True, timeout=6)
                    stdout, stderr = launcher.communicate(timeout=6)
                self.assertEqual(observed.returncode, 0, observed.stderr)
                event = json.loads(observed.stdout)
                self.assertEqual(event["event"], "ready", event)
                ready = event["ready"][0]
                self.assertEqual(ready["status"], expected)
                self.assertEqual(ready["run_id"], json.loads(stdout)["dashboard_run_id"])
                self.assertEqual(event["pending_dirs"], [])
                if case == "quota":
                    self.assertIn("session limit", ready["report_excerpt"])
                if case == "native":
                    self.assertEqual(json.loads(Path(ready["handoff_file"]).read_text())["capability"], "browser")

    def save_policy(self, policy):
        path = Path(self.env["CODEX_HOME"]) / "state/tafwid/settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": 1, "permission_policy": policy}))
        return path

    def test_instruction_delivery_deduplicates_files_and_keeps_manifest_off_stdout(self):
        role = self.root / "role.md"
        role.write_text("UNIQUE ROLE: verify the exact changed behavior.\n")
        run = self.run_cli("--instructions-file", str(role), "--instructions-file", str(role))
        self.assertEqual(run.returncode, 0, run.stderr)
        prompt = json.loads((self.cwd / "received.json").read_text())["prompt"]
        self.assertEqual(prompt.count("UNIQUE ROLE"), 1)
        manifest = json.loads((self.out / "instructions.json").read_text())
        self.assertEqual(len(manifest["instructions"]), 1)
        self.assertEqual(manifest["instructions"][0]["delivery"], "inline")
        self.assertNotIn("fingerprint", run.stdout)
        self.assertNotIn("instruction_manifest", prompt)
        self.assertFalse((self.cwd / "plugin-list-called").exists())

    def test_instruction_resume_retains_unchanged_and_sends_changed_copy(self):
        role = self.root / "role.md"
        role.write_text("RULE V1: focused verification.\n")
        first = self.run_cli("--instructions-file", str(role))
        self.assertEqual(first.returncode, 0, first.stderr)
        original = self.out
        self.out = self.root / "resume-instructions"
        second = self.run_cli("--resume-from", str(original), "--instructions-file", str(role))
        self.assertEqual(second.returncode, 0, second.stderr)
        prompt = json.loads((self.cwd / "received.json").read_text())["prompt"]
        self.assertNotIn("RULE V1", prompt)
        self.assertEqual(json.loads((self.out / "instructions.json").read_text())["instructions"][0]["delivery"], "retained")
        previous = self.out
        role.write_text("RULE V2: corrected verification.\n")
        self.out = self.root / "changed-instructions"
        third = self.run_cli("--resume-from", str(previous), "--instructions-file", str(role))
        self.assertEqual(third.returncode, 0, third.stderr)
        prompt = json.loads((self.cwd / "received.json").read_text())["prompt"]
        self.assertIn("RULE V2", prompt)
        self.assertIn("replaces", prompt)

    def test_failed_worker_does_not_cause_instructions_to_be_skipped_on_resume(self):
        role = self.root / "role.md"
        role.write_text("REQUIRED AFTER AUTH RECOVERY\n")
        self.run_cli("--instructions-file", str(role), case="expired")
        previous = self.out
        self.out = self.root / "recovered-instructions"
        run = self.run_cli("--resume-from", str(previous), "--instructions-file", str(role))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("REQUIRED AFTER AUTH RECOVERY", json.loads((self.cwd / "received.json").read_text())["prompt"])

    def test_older_resume_directory_cannot_suppress_a_reverted_policy(self):
        role = self.root / "role.md"
        role.write_text("Policy A")
        first = self.run_cli("--instructions-file", str(role))
        self.assertEqual(first.returncode, 0, first.stderr)
        oldest = self.out
        role.write_text("Policy B")
        self.out = self.root / "newer-policy"
        second = self.run_cli("--resume-from", str(oldest), "--instructions-file", str(role))
        self.assertEqual(second.returncode, 0, second.stderr)
        role.write_text("Policy A")
        self.out = self.root / "revert-policy"
        third = self.run_cli("--resume-from", str(oldest), "--instructions-file", str(role))
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertIn("Policy A", json.loads((self.cwd / "received.json").read_text())["prompt"])

    def test_matching_native_skill_is_referenced_and_changed_dependency_forces_source(self):
        source = self.root / "codex-skill"
        source.mkdir()
        body = "---\nname: checking\ndescription: Check things\n---\nUNIQUE CHECKING BODY. See [rules](rules.md).\n"
        (source / "SKILL.md").write_text(body)
        (source / "rules.md").write_text("Required rule A")
        plugin = self.root / "native-plugin"
        target = plugin / "skills/checking"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(body)
        (target / "rules.md").write_text("Required rule A")
        self.env["FIXTURE_PLUGINS"] = json.dumps([{"id": "tools@market", "enabled": True,
            "version": "1.2", "installPath": str(plugin), "scope": "user"}])
        first = self.run_cli("--instructions-file", str(source / "SKILL.md"))
        self.assertEqual(first.returncode, 0, first.stderr)
        prompt = json.loads((self.cwd / "received.json").read_text())["prompt"]
        self.assertIn("tools:checking", prompt)
        self.assertNotIn("UNIQUE CHECKING BODY", prompt)
        record = json.loads((self.out / "instructions.json").read_text())["instructions"][0]
        self.assertEqual(record["delivery"], "native")
        self.assertEqual(record["native_version"], "1.2")
        (target / "rules.md").write_text("Different rule B")
        self.out = self.root / "different-native-skill"
        second = self.run_cli("--instructions-file", str(source / "SKILL.md"))
        self.assertEqual(second.returncode, 0, second.stderr)
        prompt = json.loads((self.cwd / "received.json").read_text())["prompt"]
        self.assertIn("UNIQUE CHECKING BODY", prompt)
        self.assertNotIn("Use Skill", prompt)

    def test_empty_instruction_selection_has_no_discovery_or_extra_prompt_section(self):
        run = self.run_cli()
        self.assertEqual(run.returncode, 0, run.stderr)
        prompt = json.loads((self.cwd / "received.json").read_text())["prompt"]
        self.assertNotIn("Superpowers", prompt)
        self.assertNotIn("WORKER INSTRUCTIONS", prompt)
        self.assertFalse((self.cwd / "plugin-list-called").exists())

    def test_disabled_or_unreadable_plugin_inventory_uses_selected_source(self):
        source = self.root / "selected"
        source.mkdir()
        (source / "SKILL.md").write_text("---\nname: checking\n---\nAlways include this policy.\n")
        plugin = self.root / "plugins"
        native = plugin / "skills/checking"
        native.mkdir(parents=True)
        (native / "SKILL.md").write_text((source / "SKILL.md").read_text())
        cases = ["[]", "not-json", json.dumps([{"id": "tools@market", "enabled": False,
                                               "installPath": str(plugin)}])]
        for index, inventory in enumerate(cases):
            self.env["FIXTURE_PLUGINS"] = inventory
            self.out = self.root / f"inventory-{index}"
            run = self.run_cli("--instructions-file", str(source / "SKILL.md"))
            self.assertEqual(run.returncode, 0, run.stderr)
            prompt = json.loads((self.cwd / "received.json").read_text())["prompt"]
            self.assertIn("Always include this policy.", prompt)
            self.assertNotIn("Use Skill", prompt)

    def test_claude_personal_skill_can_be_selected_without_any_plugin(self):
        path = Path(self.env["CLAUDE_CONFIG_DIR"]) / "skills/checking/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("---\nname: checking\n---\nClaude-only selected policy.\n")
        run = self.run_cli("--instructions-file", str(path))
        self.assertEqual(run.returncode, 0, run.stderr)
        prompt = json.loads((self.cwd / "received.json").read_text())["prompt"]
        self.assertIn("Use Skill checking", prompt)
        self.assertNotIn("Claude-only selected policy.", prompt)

    def test_missing_resume_manifest_redelivers_and_registry_retains_audit(self):
        role = self.root / "role.md"
        role.write_text("Persistent audit policy.\n")
        first = self.run_cli("--instructions-file", str(role))
        self.assertEqual(first.returncode, 0, first.stderr)
        summary = json.loads(first.stdout)
        record = Path(self.env["CODEX_HOME"]) / "state/tafwid/workers" / (summary["dashboard_run_id"] + ".json")
        stored = json.loads(record.read_text())["instruction_manifest"]
        self.assertEqual(stored["instructions"][0]["delivery"], "inline")
        (self.out / "instructions.json").unlink()
        previous = self.out
        self.out = self.root / "legacy-resume"
        resumed = self.run_cli("--resume-from", str(previous), "--instructions-file", str(role))
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertIn("Persistent audit policy.", json.loads((self.cwd / "received.json").read_text())["prompt"])

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
        records = list((Path(self.env["CODEX_HOME"]) / "state/tafwid/workers").glob("*.json"))
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
        self.save_policy("scoped")
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

    def test_explicit_worker_instructions_reach_claude_literally(self):
        role = self.root / "role.md"
        role.write_text("Implementer: run the failing test first.\nLiteral $(touch ROLE_INJECTION).\n")
        verification = self.root / "verification.md"
        verification.write_text("Verify the acceptance criteria before reporting completion.\n")
        run = self.run_cli("--instructions-file", str(role), "--instructions-file", str(verification))
        self.assertEqual(run.returncode, 0, run.stderr)
        prompt = json.loads((self.cwd / "received.json").read_text())["prompt"]
        self.assertIn(role.read_text(), prompt)
        self.assertIn(verification.read_text(), prompt)
        self.assertFalse((self.cwd / "ROLE_INJECTION").exists())

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

    def test_legacy_run_without_task_ownership_cannot_be_resumed(self):
        self.assertEqual(self.run_cli().returncode, 0)
        previous = self.out
        summary = self.summary()
        del summary["codex_thread_id"]
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

    def test_completed_launch_is_registered_for_dashboard(self):
        run = self.run_cli("--title", "Review fixture", "--profile", "standard", "--role", "reviewer")
        self.assertEqual(run.returncode, 0, run.stderr)
        summary = self.summary()
        path = Path(self.env["CODEX_HOME"]) / "state/tafwid/workers" / (summary["dashboard_run_id"] + ".json")
        record = json.loads(path.read_text())
        self.assertEqual(record["title"], "Review fixture")
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["session_id"], summary["session_id"])
        self.assertEqual(record["codex_thread_id"], self.env["CODEX_THREAD_ID"])
        self.assertEqual(record["model_selection"]["requested_model"], "opus")
        self.assertIn("Done.", record["documents"]["report"])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_dashboard_tracks_a_running_worker_before_result_exists(self):
        proc = subprocess.Popen([sys.executable, str(SCRIPT), "--once", "--cwd", str(self.cwd),
            "--prompt-file", str(self.prompt), "--output-dir", str(self.out), "--timeout", "2"],
            env={**self.env, "FIXTURE_CASE": "timeout"}, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 4
            records = []
            while time.monotonic() < deadline:
                records = list((Path(self.env["CODEX_HOME"]) / "state/tafwid/workers").glob("*.json"))
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

    def test_native_handoff_is_preserved_and_not_marked_complete(self):
        for case in ("native", "native_denied"):
            with self.subTest(case=case):
                self.out = self.root / case
                run = self.run_cli(case=case)
                self.assertEqual(run.returncode, 3, run.stderr)
                summary = self.summary()
                self.assertEqual(summary["status"], "native_required")
                handoff = json.loads(Path(summary["handoff_file"]).read_text())
                self.assertEqual(handoff["capability"], "browser")
                self.assertIn("Chrome", handoff["requested_action"])
                self.assertIn("native_required", run.stdout)
                self.assertLess(len(run.stdout), 5000)

    def test_blocked_worker_is_not_marked_complete(self):
        run = self.run_cli(case="blocked")
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(self.summary()["status"], "blocked")

    def test_native_result_resumes_same_worker_without_turning_switch_off(self):
        enabled = subprocess.run([sys.executable, str(STATE), "on"], env=self.env,
                                 capture_output=True, text=True)
        self.assertEqual(enabled.returncode, 0, enabled.stderr)
        self.assertEqual(self.run_cli(case="native", once=False).returncode, 3)
        previous = self.out
        session = self.summary()["session_id"]
        native_result = previous / "native-result.md"
        native_result.write_text("Completed: Codex checked the menu in Chrome. Desktop and mobile passed.\n")
        self.prompt.write_text("Codex completed the requested browser check. Read " + str(native_result) + " and finish your report.")
        self.out = self.root / "resumed-after-native"
        run = self.run_cli("--resume-from", str(previous), once=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.summary()["session_id"], session)
        self.assertEqual(self.summary()["status"], "completed")
        self.assertIsNone(self.summary()["handoff_file"])
        received = json.loads((self.cwd / "received.json").read_text())
        self.assertIn(str(native_result), received["prompt"])
        state = subprocess.run([sys.executable, str(STATE), "status"], env=self.env,
                               capture_output=True, text=True)
        self.assertTrue(json.loads(state.stdout)["enabled"])

    def test_missing_structured_report_or_incomplete_handoff_needs_review(self):
        for case in ("missing_structured", "invalid_handoff"):
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

    def save_model_routes(self, deep="fable", final_review=None):
        config = {"version": 2, "permission_policy": "scoped", "models": {
            "profiles": {"fast": "sonnet", "standard": "opus", "deep": deep},
            "tasks": {name: None for name in ("mechanical", "investigation", "implementation", "debugging",
                      "documentation", "testing", "task_review", "architecture", "final_review")}}}
        config["models"]["tasks"]["final_review"] = final_review
        path = Path(self.env["CODEX_HOME"]) / "state/tafwid/settings.json"
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

    def test_resume_keeps_model_until_explicitly_rerouted(self):
        self.save_model_routes(final_review="fable")
        first = self.run_cli("--task-type", "final_review")
        self.assertEqual(first.returncode, 0, first.stderr)
        previous = self.out
        self.save_model_routes(final_review="opus")
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
