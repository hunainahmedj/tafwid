"""OpenCode subprocess adapter for explicitly selected OpenRouter and Zen free models.

No API key is written to artifacts. Claude's subscription adapter is independent.
OpenCode permissions are tool controls, not an operating-system sandbox.
"""
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid
import metrics

import instructions
import session as delegation_session
import settings
import worker_registry

from opencode_providers import model_info, validate_model, check_auth, provider_id, provider_config


def configuration(model, info, mode, permissions, commands, agent):
    policy = {"*": "deny", "read": "allow", "glob": "allow", "grep": "allow",
              "list": "allow", "edit": "allow" if mode == "edit" else "deny",
              "bash": "deny", "task": "deny", "question": "deny", "skill": "deny",
              "external_directory": "deny", "doom_loop": "deny"}
    if mode == "edit" and permissions["effective"] == "full":
        policy["bash"] = "allow"
        policy["external_directory"] = "allow"
    elif commands:
        policy["bash"] = {"*": "deny", **{command: "allow" for command in commands}}
    provider = provider_id(model)
    # Pin both the main worker and the built-in auxiliary agents. A unique agent
    # avoids accidentally inheriting a user agent's model/permission overrides.
    agents = {name: {"model": model, "permission": {"*": "deny"}}
              for name in ("title", "summary", "compaction")}
    agents[agent] = {"model": model, "mode": "primary", "steps": 30, "permission": policy}
    return {"$schema": "https://opencode.ai/config.json", "model": model, "small_model": model,
            "enabled_providers": [provider], "share": "disabled", "autoupdate": False,
            "permission": policy, "agent": agents, "formatter": False, "lsp": False,
            "provider": {provider: provider_config(model, info)}}


def result_events(path, expected_session=None):
    """Fail closed on truncated streams, tool failures and malformed reports."""
    from delegate import worker_output
    texts, errors, sessions = [], [], set()
    finish, denials, tool_errors = None, 0, 0
    access_denied = False
    usage = {key: None for key in ("input", "output", "reasoning", "cache_read", "cache_write", "cost_usd")}
    missing = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError("Invalid OpenCode event")
        if event.get("sessionID"):
            sessions.add(event["sessionID"])
        kind, part = event.get("type"), event.get("part") or {}
        if kind == "step_start":
            finish = None
        elif kind == "text":
            texts.append(part.get("text", ""))
        elif kind == "error":
            error = event.get("error") or {}
            data = error.get("data") or {}
            access_denied = access_denied or data.get('statusCode') == 403
            # HTTP headers/bodies may contain cookies, account identifiers and
            # credentials. Keep raw events private; summarize only the diagnosis.
            errors.append(f"{error.get('name', 'OpenCode error')} ({data.get('statusCode', 'unknown')}): "
                          + str(data.get("message") or "Inspect private events.jsonl for details")[:1500])
        elif kind == "tool_use" and part.get("state", {}).get("status") == "error":
            tool_errors += 1
            if re.search(r"permission|denied|rejected", part["state"].get("error", ""), re.I):
                denials += 1
        elif kind == "step_finish":
            finish = part.get("reason")
            tokens = part.get("tokens") or {}
            values = {key: tokens.get(key) for key in ("input", "output", "reasoning")}
            values.update({"cache_" + key: (tokens.get("cache") or {}).get(key) for key in ("read", "write")})
            values["cost_usd"] = part.get("cost")
            for key, value in values.items():
                value = metrics.number(value)
                if value is None:
                    missing.add(key)
                else:
                    usage[key] = (usage[key] or 0) + value
    if len(sessions) != 1 or (expected_session and sessions != {expected_session}):
        raise ValueError("Missing or conflicting OpenCode session identity")
    session = sessions.pop()
    if not re.fullmatch(r"ses_[A-Za-z0-9]+", session):
        raise ValueError("Invalid OpenCode session identity")
    report = "\n".join(texts)
    status, handoff = "needs_review", None
    if errors:
        status, report = "blocked" if access_denied else "error", "\n".join(errors)
        if access_denied:
            report += "\nProvider access was denied. No automatic retry, credential change or model fallback. Inspect provider support before another attempt."
    elif finish != "stop":
        report = "OpenCode did not report a complete final step. Inspect events.jsonl.\n" + report
    else:
        try:
            final = texts[-1].strip()
            if final.startswith("```json\n") and final.endswith("```"):
                final = final[8:-3].strip()
            status, report, handoff = worker_output({"structured_output": json.loads(final)})
            if status == "completed" and (denials or tool_errors):
                status = "needs_review"
        except (ValueError, IndexError, TypeError):
            report = "Missing valid structured worker report. Inspect events.jsonl.\n" + report
    if (usage["cost_usd"] or 0) > 0:
        status = "needs_review"
        report = "Unexpected nonzero OpenCode cost metadata; investigate before another dispatch.\n" + report
    for key in missing:
        usage[key] = None
    usage['partial'] = bool(missing or finish != 'stop')
    result = {"status": status, "session_id": session, "report": report, "handoff": handoff,
              "permission_denials": denials, "usage": usage}
    if access_denied:
        result['failure_kind'] = 'provider_access_denied'
    return result


def exported_models(executable, session, cwd, env, out):
    """Inspect only this session; do not infer actual models from a CLI flag."""
    try:
        with (out / "session.json").open("wb") as target, (out / "export-stderr.log").open("wb") as error:
            result = subprocess.run([executable, "export", session], cwd=cwd, env=env,
                                    stdout=target, stderr=error, timeout=20)
        if result.returncode:
            return []
        data = json.loads((out / "session.json").read_text())
        return sorted({info["providerID"] + "/" + info["modelID"]
                       for row in data.get("messages", []) if isinstance(row, dict)
                       for info in [row.get("info", {})] if info.get("role") == "assistant"
                       and isinstance(info.get("providerID"), str) and isinstance(info.get("modelID"), str)})
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return []


def run(args):
    from delegate import CONTRACT, OUTPUT_SCHEMA, nonblank, stop_group
    task_id = delegation_session.current_task_id()
    if not args.once and not delegation_session.status()["enabled"]:
        raise ValueError("Delegation is off for this Codex task; enable it or use --once")
    cwd = args.cwd.expanduser().resolve(strict=True)
    if not cwd.is_dir() or not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError("Expected a workspace directory and a positive finite timeout")
    prompt = args.prompt_file.expanduser().resolve(strict=True).read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError("Task brief is empty")
    if args.allow_tool or args.task_type or args.profile:
        raise ValueError("OpenCode uses --model and --allow-command; Claude routing profiles and tool rules do not apply")
    commands = args.allow_command
    if commands and args.mode != "edit":
        raise ValueError("Shell allowances require --mode edit")
    if any(not re.fullmatch(r"[A-Za-z0-9_./-][^\n\r]*", command) for command in commands):
        raise ValueError("Use a scoped OpenCode command pattern starting with an executable")
    previous, session_id, prior = {}, None, None
    if args.resume_from:
        previous = json.loads((args.resume_from.expanduser() / "summary.json").read_text())
        if previous.get("backend") != "opencode":
            raise ValueError("Resume backend differs from OpenCode")
        if previous.get("codex_thread_id") != task_id:
            raise ValueError("Resume has different Codex task ownership")
        if Path(previous["cwd"]).resolve() != cwd:
            raise ValueError("Resume workspace differs from the original run")
        exported = args.resume_from.expanduser() / "session.json"
        if exported.is_file():
            try:
                actual = json.loads(exported.read_text()).get("info", {}).get("directory")
                if actual and Path(actual).resolve() != cwd:
                    raise ValueError("OpenCode exported workspace differs from the requested workspace; start a fresh worker")
            except (json.JSONDecodeError, AttributeError, TypeError):
                raise ValueError("Cannot verify the previous OpenCode exported workspace") from None
        session_id = previous.get("session_id")
        if not isinstance(session_id, str) or not re.fullmatch(r"ses_[A-Za-z0-9]+", session_id):
            raise ValueError("No valid OpenCode session to resume")
        prior = instructions.prior_manifest(args.resume_from, previous)
    old = previous.get("model_selection") or {}
    model = nonblank("--model", args.model) or old.get("requested_model")
    provider = provider_id(model)
    if session_id and provider_id(old.get("requested_model")) != provider:
        raise ValueError("Resume provider differs; start a fresh worker for a different provider")
    info = model_info(model)
    validate_model(model, info)
    local_connection = info.get('local_connection')
    if session_id and local_connection != previous.get('local_connection'):
        raise ValueError('Local connection changed; start a fresh worker for a different endpoint or configuration')
    executable = shutil.which("opencode")
    if not executable:
        raise ValueError("OpenCode is not on PATH; install it before dispatch")
    auth_source = check_auth(provider)
    permissions = settings.resolve(args.permissions)
    permissions.pop("claude_mode", None)
    permissions["opencode_mode"] = "explicit tool rules"
    selection = {"requested_model": model, "profile": None, "task_type": None,
                 "role": nonblank("--role", args.role) or old.get("role") or "worker",
                 "effort": args.effort or old.get("effort"),
                 "source": "explicit" if args.model else "resume",
                 "reason": nonblank("--selection-reason", args.selection_reason) or (
                     'Self-hosted ' + local_connection['kind'] + ' via ' + provider if local_connection else
                     "Explicit free model on " + ("OpenCode Zen" if provider == "opencode" else "OpenRouter"))}
    title = nonblank("--title", args.title) or prompt.strip().splitlines()[0].lstrip("# ")[:100]
    instruction_text, manifest = instructions.prepare(args.instructions_file, prompt, prior)
    out = args.output_dir.expanduser().resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    agent = "tafwid-" + uuid.uuid4().hex
    config = configuration(model, info, args.mode, permissions, commands, agent)
    if auth_source == "public":
        config["provider"][provider]["options"]["apiKey"] = "public"
    env = dict(os.environ)
    # The free worker is deliberately a controlled, plugin-free runner. Forward
    # selected workflow instructions once instead of invoking installed skills.
    for key in ("OPENCODE_CONFIG", "OPENCODE_CONFIG_DIR", "OPENCODE_PERMISSION"):
        env.pop(key, None)
    env.update(OPENCODE_CONFIG_CONTENT=json.dumps(config), OPENCODE_DISABLE_AUTOUPDATE="true",
               OPENCODE_DISABLE_LSP_DOWNLOAD="true", OPENCODE_AUTO_SHARE="false", PWD=str(cwd))
    command = [executable, "run", "--pure", "--format", "json", "--model", model,
               "--agent", agent, "--title", title, "--dir", str(cwd)]
    if selection["effort"]:
        command += ["--variant", selection["effort"]]
    if session_id:
        command += ["--session", session_id]
    contract = CONTRACT.replace("Claude Code", "OpenCode")
    contract = contract.replace("TASK BRIEF:\n", "Return your final answer as a single JSON object matching: " + json.dumps(OUTPUT_SCHEMA, separators=(",", ":")) + "\nTASK BRIEF:\n")
    (out / "brief.md").write_text(prompt, encoding="utf-8")
    (out / "input.txt").write_text(contract + prompt + instruction_text, encoding="utf-8")
    request = {"backend": "opencode", "cwd": str(cwd), "command": command, "config": config,
               "model_selection": selection, "title": title, "permissions": permissions,
               "auth_source": auth_source, "model_capabilities": info}
    (out / "request.json").write_text(json.dumps(request, indent=2), encoding="utf-8")
    manifest.update(session_id=session_id, codex_thread_id=task_id, cwd=str(cwd))
    with worker_registry.Tracker(out, task_id, session_id, title, selection, str(cwd),
                                 permissions=permissions, instruction_manifest=manifest, backend="opencode") as tracker:
        result = {"status": "error", "session_id": session_id, "report": "", "handoff": None,
                  "permission_denials": 0, "usage": {}}
        with (out / "input.txt").open("rb") as stdin, (out / "events.jsonl").open("wb") as stdout, (out / "stderr.log").open("wb") as stderr:
            if not args.once and not delegation_session.status()["enabled"]:
                raise ValueError("Delegation was turned off before launch; no worker started")
            proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=stdin, stdout=stdout, stderr=stderr,
                                    start_new_session=True)
            tracker.running(proc.pid)
            try:
                code = proc.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                stop_group(proc)
                code = 124
            except KeyboardInterrupt:
                stop_group(proc)
                code = 130
        try:
            result = result_events(out / "events.jsonl", session_id)
        except (ValueError, TypeError, AttributeError, KeyError):
            result["report"] = "Missing or invalid OpenCode events. Inspect events.jsonl and stderr.log."
        if code in (124, 130):
            result.update(status="timeout" if code == 124 else "interrupted", handoff=None,
                          report="OpenCode stopped before completion; inspect partial workspace changes before retrying.")
        elif code != 0 and result['status'] != 'blocked':
            result.update(status="error", handoff=None)
        session_id = result["session_id"]
        if local_connection:
            result['usage']['source'] = 'OpenCode steps; self-hosted ' + local_connection['kind']
            result['usage']['scope'] = 'Current run main-worker steps; self-hosted inference, hardware/electricity unmeasured'
        models = exported_models(executable, session_id, cwd, env, out) if session_id and code not in (124, 130) else []
        # Exports include the resumed session's history, so models are explicitly
        # session-wide evidence rather than claims about just the latest run.
        if not args.resume_from and any(item != model for item in models):
            result["status"] = "needs_review"
            result["report"] = "Unexpected model in session export; investigate routing.\n" + result["report"]
        report, handoff = result.pop("report"), result.pop("handoff")
        (out / "report.md").write_text(report + "\n", encoding="utf-8")
        if handoff is not None:
            (out / "handoff.json").write_text(json.dumps(handoff, indent=2), encoding="utf-8")
        manifest["session_id"] = session_id
        (out / "instructions.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        summary = {**result, "backend": "opencode", "provider": provider, "cwd": str(cwd),
                   "local_connection": local_connection,
                   "codex_thread_id": task_id, "model_selection": selection, "dashboard_run_id": tracker.id,
                   "models_used": models, "models_used_scope": "exported session history; helpers may be absent",
                   "usage_scope": "current run's emitted main-worker steps; helpers may be absent",
                   "permissions": permissions, "worker_exit_code": code,
                   "report_file": str(out / "report.md"), "result_file": str(out / "events.jsonl"),
                   "stderr_file": str(out / "stderr.log"),
                   "handoff_file": str(out / "handoff.json") if handoff is not None else None,
                   "report_excerpt": report[:3000], "report_truncated": len(report) > 3000}
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        tracker.finish(summary)
        print(json.dumps(summary, ensure_ascii=False))
        return 0 if result["status"] == "completed" else 3 if result["status"] == "native_required" else code if code in (124, 130) else 1
