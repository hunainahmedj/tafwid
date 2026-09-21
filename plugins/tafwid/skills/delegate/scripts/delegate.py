#!/usr/bin/env python3
"""Run a bounded coding worker and emit a compact result for Codex."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import uuid
import session as delegation_session
import worker_registry
import settings as worker_settings
import routing
import instructions as worker_instructions

OVERRIDES = (
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
)
# Profiles pick a model and its effort. They grant no tool, permission, or budget.
PROFILES = routing.PROFILES
EFFORTS = ("low", "medium", "high", "xhigh", "max")
CONTRACT = """You are a Claude Code worker for a bounded Codex task.
Follow the brief, AGENTS.md/CLAUDE.md and selected instructions once. Retain them on resume unless replaced;
recover missing context from source files without loading equivalent copies.
Codex owns planning/dispatch; no replanning or nested workers unless requested.
Stay in scope. Commits, pushes, deploys, messaging and account/tool configuration changes
require explicit brief authorization. Report denied steps; never evade permissions.
If a required capability is unavailable, finish independent work, pause dependent work and return
native_required: capability, reason/attempts, exact requested action, context (URL/file/app/state),
expected evidence. Handoffs never authorize bypassing permissions or safety rules.
Respect requested browser/environment; no silent substitutes, invented observations or pending-as-done.
Other blockers: blocked. Use completed only for finished assignments. Return structured report
and handoff (null unless native_required).
Follow assigned check ownership; preserve required gates. Reuse checks for unchanged relevant
code/environment. For optional retries state the relevant change, new diagnostic hypothesis or transient evidence.
Report (~250 words): outcome, files/findings with locations, risks/unverified work, and Checks: command/cwd/environment,
result, tested revision+dirty-diff reference, later edits, unresolved failures/next owner; link long logs.
No checks: say so. Passing earlier checks does not verify later edits; Codex retains acceptance review.

TASK BRIEF:
"""
HANDOFF_FIELDS = ("capability", "reason", "requested_action", "context", "expected_result")
OUTPUT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["completed", "native_required", "blocked"]},
        "report": {"type": "string", "minLength": 1},
        "handoff": {"anyOf": [
            {"type": "null"},
            {"type": "object", "additionalProperties": False,
             "properties": {name: {"type": "string", "minLength": 1} for name in HANDOFF_FIELDS},
             "required": list(HANDOFF_FIELDS)},
        ]},
    },
    "required": ["status", "report", "handoff"],
}


def worker_output(data):
    """Reject missing/contradictory completion or handoff claims."""
    output = data.get("structured_output")
    if not isinstance(output, dict) or not isinstance(output.get("report"), str) or not output["report"].strip():
        raise ValueError("Missing valid structured worker report")
    state = output.get("status")
    if state not in ("completed", "native_required", "blocked") or "handoff" not in output:
        raise ValueError("Missing valid worker status or handoff field")
    handoff = output["handoff"]
    if state == "native_required":
        if not isinstance(handoff, dict) or any(not isinstance(handoff.get(key), str) or not handoff[key].strip() for key in HANDOFF_FIELDS):
            raise ValueError("Incomplete native handoff; ask the worker for the missing details")
    elif handoff is not None:
        raise ValueError("Worker supplied a handoff without native_required status")
    return state, output["report"], handoff


def nonblank(flag, value):
    """Keep an explicitly supplied but empty selector from passing as an omission."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError(f"{flag} was supplied without a value")
    return value


def recorded_selection(previous):
    """Reuse only well-formed selection metadata from the run being resumed."""
    prior = previous.get("model_selection")
    if not isinstance(prior, dict):
        return None
    kept = {key: value.strip() for key, value in prior.items()
            if isinstance(value, str) and value.strip()}
    if kept.get("profile") not in PROFILES:
        kept.pop("profile", None)
    if kept.get("effort") not in EFFORTS:
        kept.pop("effort", None)
    if kept.get("task_type") not in routing.TASKS:
        kept.pop("task_type", None)
    return kept


def resolve_selection(args, prior, config):
    """Record which model this run asks for, why, and where that choice came from."""
    prior = prior or {}
    role = nonblank("--role", args.role) or prior.get("role")
    reason = nonblank("--selection-reason", args.selection_reason)
    model = nonblank("--model", args.model)
    effort = args.effort
    task_type = args.task_type
    if task_type or args.profile:
        profile, model, profile_effort, source = routing.select(
            config["models"], profile=args.profile, task_type=task_type)
        effort = effort or profile_effort
        generated = (f"{task_type} routed to {model} via {source}" if task_type else
                     f"{profile} profile requested for this run")
    elif model:
        profile, source = None, "explicit"
        generated = f"model {model} requested for this run"
    elif prior.get("requested_model") or prior.get("effort"):
        profile, source = prior.get("profile"), "resume"
        task_type = prior.get("task_type")
        model = prior.get("requested_model")
        kept = model or "Claude's default model"
        if effort:
            generated = f"resumed worker kept on {kept} with {effort} effort"
        else:
            effort = prior.get("effort")
            # A retained selection keeps its original justification; a new one never does.
            generated = prior.get("reason") or f"resumed worker kept on {kept}"
    elif effort:
        profile, source = None, "explicit"
        generated = f"{effort} effort requested on Claude's default model"
    else:
        profile, source = None, "default"
        generated = "no model requested; Claude's default applies"
    return {"profile": profile, "task_type": task_type, "requested_model": model, "effort": effort,
            "role": role or "worker", "reason": reason or generated, "source": source}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("claude", "opencode"),
                        help="Worker harness; defaults to Claude, or the resumed run's backend")
    parser.add_argument("--allow-command", action="append", default=[],
                        help="OpenCode scoped shell command pattern (edit mode); repeatable")
    parser.add_argument("--cwd", type=Path, required=True, help="Workspace or isolated worktree")
    parser.add_argument("--prompt-file", type=Path, required=True, help="UTF-8 task brief; never shell-expanded")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for private run artifacts")
    parser.add_argument("--mode", choices=("read", "edit"), default="read",
                        help="Read: file inspection and skills/tool discovery. Edit: also Edit/Write. Plugins use existing permissions.")
    parser.add_argument("--allow-tool", action="append", default=[],
                        help="Scoped Bash rule (edit mode) or exact mcp__server__tool name; repeatable")
    parser.add_argument("--permissions", choices=worker_settings.POLICIES,
                        help="User-requested override of the saved worker permission policy")
    parser.add_argument("--resume-from", type=Path, help="Previous output directory, in the same workspace")
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--task-type", choices=tuple(routing.TASKS),
                        help="Apply saved model routing for this type of task")
    choice.add_argument("--profile", choices=tuple(PROFILES),
                        help="Use the saved fast, standard, or deep tier model")
    choice.add_argument("--model", help="Explicit Claude alias or model ID; otherwise use Claude's default")
    parser.add_argument("--effort", choices=EFFORTS, help="Reasoning effort; overrides the profile default")
    parser.add_argument("--title", help="Short task title displayed in the workers dashboard")
    parser.add_argument("--role", help="Worker role recorded with the selection (default: worker)")
    parser.add_argument("--selection-reason", help="Why this model was chosen; recorded for audit")
    parser.add_argument("--once", action="store_true",
                        help="Explicit one-shot delegation without changing the current task's switch")
    parser.add_argument("--instructions-file", type=Path, action="append", default=[],
                        help="Selected role/skill file; deduplicated, or matched to an equivalent Claude skill")
    parser.add_argument("--timeout", type=float, default=900, help="Task timeout in seconds (default: 900)")
    return parser.parse_args()


def stop_group(proc):
    """Interrupt Claude and its commands, then kill anything still in that group."""
    try:
        os.killpg(proc.pid, signal.SIGINT)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def check_auth(claude, cwd):
    active = [name for name in OVERRIDES if os.environ.get(name)]
    if active:
        raise ValueError("Subscription-only launcher: resolve these environment overrides first: " + ", ".join(active))
    auth = subprocess.run([claude, "auth", "status"], cwd=cwd,
                          capture_output=True, text=True, timeout=30)
    if auth.returncode:
        raise ValueError("Claude login check failed. Run `claude auth login` in your terminal.")
    try:
        data = json.loads(auth.stdout)
    except json.JSONDecodeError:
        raise ValueError("Claude auth status did not return JSON; check the installed CLI.") from None
    if (not isinstance(data, dict) or data.get("loggedIn") is not True
            or data.get("authMethod") != "claude.ai"
            or data.get("apiProvider") != "firstParty"
            or data.get("subscriptionType") not in ("pro", "max", "team", "enterprise")
            or data.get("apiKeySource")):
        raise ValueError("Expected a Claude subscription login. Run `claude auth login`; do not select API billing.")
    # This is configuration evidence only. Expired credentials can still pass it.
    return data["subscriptionType"]


def run(args):
    backend = getattr(args, "backend", None)
    if args.resume_from:
        previous = json.loads((args.resume_from.expanduser() / "summary.json").read_text())
        prior_backend = previous.get("backend", "claude")
        if backend and backend != prior_backend:
            raise ValueError("Resume backend differs from the original run")
        backend = prior_backend
    if backend == "opencode":
        import opencode_worker
        return opencode_worker.run(args)
    if backend not in (None, "claude"):
        raise ValueError("Unknown worker backend")
    if getattr(args, "allow_command", []):
        raise ValueError("--allow-command requires --backend opencode; Claude uses --allow-tool")
    task_id = delegation_session.current_task_id()
    if not args.once and not delegation_session.status()["enabled"]:
        raise ValueError("Delegation is off for this Codex task. Enable it with session.py on, or use --once for an explicit one-shot request.")
    cwd = args.cwd.expanduser().resolve(strict=True)
    if not cwd.is_dir():
        raise ValueError("--cwd must be a directory")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError("--timeout must be a positive finite number")
    prompt = args.prompt_file.expanduser().resolve(strict=True).read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError("Task brief is empty")
    shell_rules = [rule for rule in args.allow_tool if rule.startswith("Bash(")]
    if shell_rules and args.mode != "edit":
        raise ValueError("Shell allowances require --mode edit; read mode has no shell")
    for rule in args.allow_tool:
        if not (re.fullmatch(r"Bash\([A-Za-z0-9_./-][^,\n\r]*\)", rule)
                or re.fullmatch(r"mcp__[A-Za-z0-9_-]+__[A-Za-z0-9_-]+", rule)):
            raise ValueError("Use a scoped Bash(command ...) rule or exact MCP tool name; no unrestricted tool wildcards")
    session, prior, prior_instructions = None, None, None
    if args.resume_from:
        previous = json.loads((args.resume_from.expanduser() / "summary.json").read_text())
        if "codex_thread_id" not in previous or previous["codex_thread_id"] != task_id:
            raise ValueError("Resume has missing or different Codex task ownership; start a fresh worker")
        if Path(previous["cwd"]).resolve() != cwd:
            raise ValueError("Resume workspace differs from the original run")
        session = str(uuid.UUID(previous["session_id"]))
        prior = recorded_selection(previous)
        prior_instructions = worker_instructions.prior_manifest(args.resume_from, previous)
    config = worker_settings.read()
    permissions = worker_settings.resolve(args.permissions, config)
    selection = resolve_selection(args, prior, config)
    title = nonblank("--title", args.title) or prompt.strip().splitlines()[0].lstrip("# ")[:100]
    claude = shutil.which("claude")
    if not claude:
        raise ValueError("Claude Code is not on PATH")
    subscription = check_auth(claude, cwd)
    instruction_text, instruction_manifest = worker_instructions.prepare(
        args.instructions_file, prompt, prior_instructions, claude=claude, cwd=cwd)
    out = args.output_dir.expanduser().resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    (out / "brief.md").write_text(prompt, encoding="utf-8")
    tools = ["Read", "Glob", "Grep", "Skill", "ToolSearch"]
    if args.mode == "edit":
        tools += ["Edit", "Write"]
    if shell_rules or (args.mode == "edit" and permissions["effective"] == "full"):
        tools.append("Bash")
    allowed = [tool for tool in tools if tool != "Bash"] + args.allow_tool
    command = [claude, "-p", "--output-format", "json",
               "--permission-mode", permissions["claude_mode"], "--tools", ",".join(tools),
               "--json-schema", json.dumps(OUTPUT_SCHEMA)]
    if permissions["effective"] == "scoped":
        command += ["--allowedTools", ",".join(allowed)]
    if selection["requested_model"]:
        command += ["--model", selection["requested_model"]]
    if selection["effort"]:
        command += ["--effort", selection["effort"]]
    if session:
        command += ["--resume", session]
    else:
        session = str(uuid.uuid4())
        command += ["--session-id", session]
    (out / "request.json").write_text(json.dumps(
        {"cwd": str(cwd), "command": command, "model_selection": selection, "title": title, "permissions": permissions}, indent=2))
    instruction_manifest.update(session_id=session, codex_thread_id=task_id, cwd=str(cwd))
    (out / "instructions.json").write_text(json.dumps(instruction_manifest, indent=2), encoding="utf-8")
    (out / "input.txt").write_text(CONTRACT + prompt + instruction_text, encoding="utf-8")
    with worker_registry.Tracker(out, task_id, session, title, selection, str(cwd), permissions=permissions,
                                 instruction_manifest=instruction_manifest) as tracker:
        status, report, code, denials = "error", "", None, 0
        handoff, models_used = None, []
        run_usage = {}
        with (out / "input.txt").open("rb") as stdin, (out / "result.json").open("wb") as stdout, (out / "stderr.log").open("wb") as stderr:
            if not args.once and not delegation_session.status()["enabled"]:
                raise ValueError("Delegation was turned off before launch; no worker started")
            proc = subprocess.Popen(command, cwd=cwd, stdin=stdin, stdout=stdout, stderr=stderr,
                                    start_new_session=True)
            tracker.running(proc.pid)
            try:
                code = proc.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                stop_group(proc)
                code, status = 124, "timeout"
                report = "Claude task timed out; inspect the working tree before retrying. Partial changes may exist."
            except KeyboardInterrupt:
                stop_group(proc)
                code, status = 130, "interrupted"
                report = "Claude task interrupted; inspect the working tree before retrying."
        if not report:
            try:
                data = json.loads((out / "result.json").read_text(encoding="utf-8"))
                if not isinstance(data, dict) or data.get("type") != "result":
                    raise ValueError("Expected Claude result object")
                # Every model the run billed, helpers included: usage evidence, not the worker's identity.
                usage = data.get("modelUsage")
                models_used = sorted(usage) if isinstance(usage, dict) else []
                import metrics
                run_usage = metrics.claude_usage(data)
                report = data.get("result") or "Claude returned no report; inspect result.json."
                if not isinstance(report, str):
                    report = json.dumps(report)
                session = data.get("session_id") or session
                denials = len(data.get("permission_denials") or [])
                if code == 0 and data.get("is_error") is False and data.get("subtype") == "success":
                    try:
                        status, report, handoff = worker_output(data)
                        if status == "completed" and denials:
                            status = "needs_review"
                    except ValueError as exc:
                        status = "needs_review"
                        report = str(exc) + ". Inspect result.json.\n" + report
            except (ValueError, TypeError):
                report = "Claude returned missing or invalid result JSON. Inspect result.json and stderr.log."
        (out / "report.md").write_text(report + "\n", encoding="utf-8")
        if handoff is not None:
            (out / "handoff.json").write_text(json.dumps(handoff, indent=2), encoding="utf-8")
        summary = {"status": status, "session_id": session, "cwd": str(cwd),
                   "codex_thread_id": task_id, "model_selection": selection, "dashboard_run_id": tracker.id,
                   "models_used": models_used, "permissions": permissions, "usage": run_usage,
                   "subscription_type": subscription, "claude_exit_code": code,
                   "permission_denials": denials, "report_file": str(out / "report.md"),
                   "result_file": str(out / "result.json"), "stderr_file": str(out / "stderr.log"),
                   "handoff_file": str(out / "handoff.json") if handoff is not None else None,
                   "report_excerpt": report[:3000], "report_truncated": len(report) > 3000}
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        tracker.finish(summary)
        # Dashboard telemetry stays on disk; normal completion messages stay compact.
        print(json.dumps({key: value for key, value in summary.items() if key != 'usage'}, ensure_ascii=False))
        if status == "completed":
            return 0
        if status == "native_required":
            return 3
        return code if code in (124, 130) else 1


def main():
    # Artifacts may contain private source code. This process changes no user config.
    os.umask(0o077)
    args = parse_args()
    try:
        return run(args)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
