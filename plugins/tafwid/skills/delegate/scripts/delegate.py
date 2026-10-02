#!/usr/bin/env python3
"""Launch or resume a Claude or named GPT worker and emit a JSON result.

Requires named options --cwd, --prompt-file and --output-dir for every run.
Use --resume-from for a follow-up task.
Run with --help for the full CLI; help does not launch a worker.
A started event on stderr provides run_id and a read-only watch_key before
completion. Stdout contains only the final JSON summary.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import uuid
import session as delegation_session
import run_state
import settings as worker_settings
import routing
import harnesses
import host
import connections
import accounts
import codex_cli

# Profiles pick a model and its effort. They grant no tool, permission, or budget.
PROFILES = routing.PROFILES
EFFORTS = ("low", "medium", "high", "xhigh", "max")
CONTRACT = """You are a Claude Code worker for a bounded task assigned by a coordinator.
Follow the task brief and applicable workspace rules.
The coordinator owns planning/dispatch; no replanning or nested workers unless requested.
Stay in scope. Commits, pushes, deploys, messaging and account/tool configuration changes
require explicit brief authorization. Report denied steps; never evade permissions.
If a required capability is unavailable, finish independent work and report blocked
with the missing capability and remaining work. Respect the requested browser/environment;
no silent substitutes, invented observations or pending-as-done claims.
Use completed only for finished assignments. Return a structured status and report.
Follow assigned check ownership; preserve required gates. Reuse checks for unchanged relevant
code/environment. For optional retries state the relevant change, new diagnostic hypothesis or transient evidence.
Report (~250 words): outcome, files/findings with locations, risks/unverified work, and Checks: command/cwd/environment,
result, tested revision+dirty-diff reference, later edits, unresolved failures/next owner; link long logs.
No checks: say so. Passing earlier checks does not verify later edits; The coordinator retains acceptance review.

TASK BRIEF:
"""
OUTPUT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["completed", "blocked"]},
        "report": {"type": "string", "minLength": 1},
    },
    "required": ["status", "report"],
}


def worker_output(data):
    """Validate the worker's status and nonempty report before accepting its claim."""
    output = data.get("structured_output")
    if not isinstance(output, dict) or set(output) != {"status", "report"}:
        raise ValueError("Expected structured worker status and report")
    if not isinstance(output["report"], str) or not output["report"].strip():
        raise ValueError("Missing valid structured worker report")
    if output["status"] not in ("completed", "blocked"):
        raise ValueError("Invalid worker status")
    return output["status"], output["report"]


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
    """Parse launch options without starting a worker or changing saved settings."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples (replace paths with your workspace and private files):
  python3 scripts/delegate.py --once --cwd /workspace --prompt-file /private/task.md --output-dir /private/run-1 --task-type implementation --mode edit
  python3 scripts/delegate.py --once --connection gpt:work --cwd /workspace --prompt-file /private/task.md --output-dir /private/gpt-run --mode read
  python3 scripts/delegate.py --once --cwd /workspace --prompt-file /private/follow-up.md --output-dir /private/run-2 --resume-from /private/run-1 --mode edit

Without --once, this chat's delegation switch must be on. Every invocation needs
a new output directory. Output is compact JSON; full reports stay in that directory.
Stderr emits a started event with run_id, worker_pid and watch_key after launch.
The owner uses wait.py --run-id RUN_ID. To assign monitoring to another task,
give it RUN_ID and WATCH_KEY for wait.py --run-id RUN_ID --watch-key RUN_ID=WATCH_KEY.
The key allows observation of that run only; do not send it to the worker.
Stdout remains a single final JSON summary; the key is not saved in run artifacts.
Completion still requires acceptance review. See references/workflow.md for usage.
""",
    )
    parser.add_argument("--cwd", type=Path, required=True, help="Workspace or isolated worktree")
    parser.add_argument("--prompt-file", type=Path, required=True, help="UTF-8 task brief; never shell-expanded")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for private run artifacts")
    parser.add_argument("--connection", help="Exact worker destination: claude or gpt:NAME")
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
    choice.add_argument("--model", help="Explicit model ID or Claude alias; mutually exclusive with task-type/profile")
    parser.add_argument("--effort", choices=EFFORTS, help="Reasoning effort; overrides the profile default")
    parser.add_argument("--title", help="Short task title recorded with the run")
    parser.add_argument("--role", help="Worker role recorded with the selection (default: worker)")
    parser.add_argument("--selection-reason", help="Why this model was chosen; recorded for audit")
    parser.add_argument("--once", action="store_true",
                        help="Explicit one-shot delegation without changing the current task's switch")
    parser.add_argument("--timeout", type=float, default=900, help="Task timeout in seconds (default: 900)")
    return parser.parse_args()


def stop_group(proc):
    """Interrupt a worker and its commands, then kill the remaining group."""
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


def run_gpt(args, *, task_id, cwd, prompt, previous, selected):
    """Run one named Codex CLI worker in its private account environment."""
    if args.task_type or args.profile or args.effort or args.allow_tool:
        raise ValueError("GPT assignments do not use Claude task routes, effort, or tool allowances")
    if args.permissions not in (None, "scoped"):
        raise ValueError("GPT workers use read-only or workspace-write sandbox permissions")
    account = accounts.get(selected["name"])
    if selected["id"] != "gpt:" + account["id"]:
        raise ValueError("GPT account identity changed; start a new assignment")
    if previous and previous.get("connection_id") != selected["id"]:
        raise ValueError("Resume account identity differs from the original run")
    if previous and previous.get("backend") != "gpt":
        raise ValueError("Resume backend differs from the original run")
    if previous and previous.get("mode") != args.mode:
        raise ValueError("Resume mode differs from the original run")
    session_id = str(uuid.UUID(previous["session_id"])) if previous else None
    readiness = harnesses.check_ready("gpt", cwd=cwd, account=account)
    title = nonblank("--title", args.title) or prompt.strip().splitlines()[0].lstrip("# ")[:100]
    model = nonblank("--model", args.model) or (previous or {}).get("requested_model")
    selection = {"requested_model": model, "role": nonblank("--role", args.role) or "worker",
                 "reason": nonblank("--selection-reason", args.selection_reason) or
                 ("explicit model" if model else "selected Codex CLI default")}
    out = args.output_dir.expanduser().resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    (out / "brief.md").write_text(prompt, encoding="utf-8")
    (out / "input.txt").write_text(codex_cli.CONTRACT + "\n\nTASK BRIEF:\n" + prompt, encoding="utf-8")
    schema = out / "schema.json"
    schema.write_text(json.dumps(codex_cli.OUTPUT_SCHEMA), encoding="utf-8")
    events = out / "events.jsonl"
    final_message = out / "final.json"
    stderr_path = out / "stderr.log"
    command = codex_cli.build_command(readiness["executable"], cwd=cwd, schema=schema,
                                      mode=args.mode, model=model, session_id=session_id,
                                      output=final_message)
    (out / "request.json").write_text(json.dumps({"cwd": str(cwd), "command": command,
        "connection_id": selected["id"], "model_selection": selection, "mode": args.mode}, indent=2))
    permissions = {"effective": "read-only" if args.mode == "read" else "workspace-write",
                   "approval": "never"}
    with run_state.Tracker(out, task_id, session_id, title, selection, str(cwd),
                           permissions=permissions, backend="gpt", connection_id=selected["id"]) as tracker:
        if not args.once:
            current = connections.resolve(task_id, selected["selector"])
            if current["id"] != selected["id"]:
                raise ValueError("Connection changed before launch")
        harnesses.check_ready("gpt", cwd=cwd, account=account)
        status, report, code = "needs_review", "", None
        with (out / "input.txt").open("rb") as stdin, events.open("wb") as stdout, stderr_path.open("wb") as stderr:
            proc = subprocess.Popen(command, cwd=cwd, env=accounts.isolated_env(Path(account["home"])),
                                    stdin=stdin, stdout=stdout, stderr=stderr, start_new_session=True)
            tracker.running(proc.pid)
            print(json.dumps({"event": "started", "run_id": tracker.id,
                              "watch_key": tracker.watch_key, "worker_pid": proc.pid,
                              "output_dir": str(out)}), file=sys.stderr, flush=True)
            try:
                code = proc.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                stop_group(proc)
                code, status = 124, "timeout"
                report = "Codex worker timed out; inspect its private artifacts and working tree."
            except KeyboardInterrupt:
                stop_group(proc)
                code, status = 130, "interrupted"
                report = "Codex worker was interrupted; inspect its private artifacts and working tree."
        if not report:
            parsed = codex_cli.parse_result(events, final_message, exit_code=code,
                                            expected_session_id=session_id)
            status, report = parsed["status"], parsed["report"]
            session_id = parsed["session_id"]
        else:
            session_id = codex_cli.started_session(events) or session_id
        (out / "report.md").write_text(report + "\n", encoding="utf-8")
        summary = {"status": status, "backend": "gpt", "connection_id": selected["id"],
                   "connection": selected["selector"], "account_kind": selected["kind"],
                   "session_id": session_id, "coordinator_task_id": task_id,
                   "coordinator_host": host.detect(), "cwd": str(cwd),
                   "mode": args.mode, "requested_model": model, "model_selection": selection,
                   "run_id": tracker.id, "models_used": [], "permissions": permissions,
                   "codex_exit_code": code, "report_file": str(out / "report.md"),
                   "result_file": str(final_message), "stderr_file": str(stderr_path),
                   "report_excerpt": report[:3000], "report_truncated": len(report) > 3000}
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        tracker.finish(summary)
        print(json.dumps(summary, ensure_ascii=False))
        return 0 if status == "completed" else code if code in (124, 130) else 1


def run(args):
    """Launch or resume a worker using the options returned by parse_args.

    Validate task ownership, permissions and harness readiness before launch.
    Emit the run ID and observation key on stderr at startup, then save private run artifacts and
    print a compact JSON summary on stdout. Return 0 for
    completion, 124 for timeout, 130 for interruption, or 1 for other outcomes
    requiring attention. Setup errors propagate to main for JSON reporting.
    """
    task_id = delegation_session.current_task_id()
    if not args.once and not connections.read(task_id)["enabled"]:
        raise ValueError("Delegation is off for this task. Enable it with session.py on, or use --once for an explicit one-shot request.")
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
    session, prior, previous = None, None, None
    if args.resume_from:
        previous = json.loads((args.resume_from.expanduser() / "summary.json").read_text())
        if previous.get("backend", "claude") not in ("claude", "gpt"):
            raise ValueError("Only Claude Code workers can be resumed; this run belongs to a retired backend")
        if not run_state.owner(previous) or run_state.owner(previous) != task_id:
            raise ValueError("Resume has missing or different task ownership; start a fresh worker")
        if Path(previous["cwd"]).resolve() != cwd:
            raise ValueError("Resume workspace differs from the original run")
        session = str(uuid.UUID(previous["session_id"]))
        prior = recorded_selection(previous)
    selector = args.connection or (previous.get("connection", "claude") if previous else None)
    selected = connections.resolve(task_id, selector, once=args.once)
    if previous and previous.get("backend", "claude") != selected["provider"]:
        raise ValueError("Resume connection differs from the original run")
    if previous and previous.get("connection_id", "claude:default") != selected["id"]:
        raise ValueError("Resume connection identity differs from the original run")
    if selected["provider"] == "gpt":
        return run_gpt(args, task_id=task_id, cwd=cwd, prompt=prompt,
                       previous=previous, selected=selected)
    config = worker_settings.read(task_id)
    if config["harness"] != "claude":
        raise ValueError("Only Claude Code has a worker launcher; no fallback will be used")
    permissions = worker_settings.resolve(args.permissions, config)
    selection = resolve_selection(args, prior, config)
    title = nonblank("--title", args.title) or prompt.strip().splitlines()[0].lstrip("# ")[:100]
    readiness = harnesses.check_ready(config["harness"], cwd=cwd)
    claude = readiness["executable"]
    subscription = readiness["subscription_type"]
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
    (out / "input.txt").write_text(CONTRACT + prompt, encoding="utf-8")
    with run_state.Tracker(out, task_id, session, title, selection, str(cwd), permissions=permissions) as tracker:
        status, report, code, denials = "error", "", None, 0
        models_used = []
        with (out / "input.txt").open("rb") as stdin, (out / "result.json").open("wb") as stdout, (out / "stderr.log").open("wb") as stderr:
            if not args.once:
                try:
                    active = connections.resolve(task_id, "claude")
                except ValueError:
                    raise ValueError("Claude connection was turned off before launch; no worker started") from None
                if active["id"] != "claude:default":
                    raise ValueError("Claude connection changed before launch; no worker started")
            proc = subprocess.Popen(command, cwd=cwd, stdin=stdin, stdout=stdout, stderr=stderr,
                                    env=host.worker_env(), start_new_session=True)
            tracker.running(proc.pid)
            try:
                print(json.dumps({"event": "started", "run_id": tracker.id,
                                  "watch_key": tracker.watch_key,
                                  "worker_pid": proc.pid, "output_dir": str(out)}),
                      file=sys.stderr, flush=True)
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
                report = data.get("result") or "Claude returned no report; inspect result.json."
                if not isinstance(report, str):
                    report = json.dumps(report)
                session = data.get("session_id") or session
                denials = len(data.get("permission_denials") or [])
                if code == 0 and data.get("is_error") is False and data.get("subtype") == "success":
                    try:
                        status, report = worker_output(data)
                        if status == "completed" and denials:
                            status = "needs_review"
                    except ValueError as exc:
                        status = "needs_review"
                        report = str(exc) + ". Inspect result.json.\n" + report
            except (ValueError, TypeError):
                report = "Claude returned missing or invalid result JSON. Inspect result.json and stderr.log."
        (out / "report.md").write_text(report + "\n", encoding="utf-8")
        summary = {"status": status, "backend": "claude", "connection_id": "claude:default",
                   "session_id": session, "cwd": str(cwd),
                   "coordinator_task_id": task_id, "coordinator_host": host.detect(),
                   "model_selection": selection, "run_id": tracker.id,
                   "models_used": models_used, "permissions": permissions,
                   "subscription_type": subscription, "claude_exit_code": code,
                   "permission_denials": denials, "report_file": str(out / "report.md"),
                   "result_file": str(out / "result.json"), "stderr_file": str(out / "stderr.log"),
                   "report_excerpt": report[:3000], "report_truncated": len(report) > 3000}
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        tracker.finish(summary)
        print(json.dumps(summary, ensure_ascii=False))
        if status == "completed":
            return 0
        return code if code in (124, 130) else 1


def main():
    """Parse CLI options, protect new files, and return the launcher's exit code.

    Report setup errors as JSON on stderr with exit code 2. Argument parsing
    handles --help and invalid options before any worker is launched.
    """
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
