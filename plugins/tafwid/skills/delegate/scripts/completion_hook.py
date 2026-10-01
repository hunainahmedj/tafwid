#!/usr/bin/env python3
"""Arm a one-time Stop hook to wait for this chat's Tafwid workers.

CLI: completion_hook.py {status,arm,hook,disarm} [--run-id UUID ...].
`status` checks that this installed plugin's Stop hook is enabled and trusted.
`arm` records selected runs for the next Stop event; it never launches workers.
The hook waits locally and resumes the coordinator only for completion or attention.
"""

import argparse
import json
from pathlib import Path
import select
import subprocess
import sys
import time
import uuid

import host
import paths
import run_state
import session
import wait


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
HOOK_FILE = PLUGIN_ROOT / "hooks" / "hooks.json"
HOOK_WAIT_SECONDS = 1700
ARM_MAX_AGE_SECONDS = 120


def _response(process, request_id, timeout=5):
    """Read the selected JSON-RPC response, ignoring notifications."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = max(0, deadline - time.monotonic())
        ready, _, _ = select.select([process.stdout], [], [], remaining)
        if not ready:
            break
        line = process.stdout.readline()
        if not line:
            break
        value = json.loads(line)
        if value.get("id") == request_id:
            return value
    raise TimeoutError("Codex hook inventory did not respond")


def _send(process, value):
    """Send one newline-delimited JSON-RPC message."""
    process.stdin.write(json.dumps(value) + "\n")
    process.stdin.flush()


def hook_status():
    """Return whether this chat's completion hooks can resume the coordinator."""
    if host.detect() == "claude":
        if host.seen(host.task_id()):
            return {"active": True}
        return {"active": False, "reason": "Tafwid hooks have not run in this Claude Code session; "
                "check that the plugin is enabled and hooks are not disabled"}
    return _codex_hook_status()


def _codex_hook_status():
    """Return whether this installed plugin's Stop hook is enabled and trusted in Codex."""
    process = subprocess.Popen(["codex", "app-server", "--stdio"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, bufsize=1)
    try:
        _send(process, {"method": "initialize", "id": 1, "params": {
            "clientInfo": {"name": "tafwid_hook_status", "title": "Tafwid Hook Status", "version": "0.2.0"},
            "capabilities": {"experimentalApi": True}}})
        initialized = _response(process, 1)
        if "error" in initialized:
            raise ValueError("Codex hook inventory initialization failed")
        _send(process, {"method": "initialized", "params": {}})
        _send(process, {"method": "hooks/list", "id": 2,
                        "params": {"cwds": [str(Path.cwd())]}})
        result = _response(process, 2)
        if "error" in result:
            raise ValueError("Codex hook inventory failed")
        trusted = set()
        for entry in result.get("result", {}).get("data", []):
            for hook in entry.get("hooks", []):
                if (hook.get("enabled") is True and hook.get("trustStatus") == "trusted"
                        and hook.get("source") == "plugin"
                        and hook.get("pluginId", "").split("@", 1)[0] == "tafwid"
                        and Path(hook.get("sourcePath", "")).resolve() == HOOK_FILE):
                    trusted.add(hook.get("eventName"))
        if {"stop", "interrupt", "userPromptSubmit"} <= trusted:
            return {"active": True}
        return {"active": False, "reason": "Tafwid completion hooks are not all enabled and trusted for this workspace"}
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def arm_path(task_id):
    """Choose this chat's private one-time hook handoff file."""
    return paths.state_root() / "hook-waits" / (task_id + ".json")


def arm(run_ids):
    """Validate worker ownership and hook readiness before arming a Stop wait."""
    task_id = session.current_task_id()
    if not task_id:
        raise ValueError("No chat identity from the coordinator")
    if not run_ids:
        raise ValueError("At least one --run-id is required")
    state = hook_status()
    if not state["active"]:
        arm_path(task_id).unlink(missing_ok=True)
        return {"event": "unavailable", "reason": state["reason"]}
    selected = []
    for run_id in dict.fromkeys(run_ids):
        record = run_state.load_record(run_id)
        if run_state.owner(record) != task_id:
            raise ValueError("Cannot arm another chat's worker")
        selected.append(run_id)
    paths.atomic_json(arm_path(task_id), {
        "version": 1, "thread_id": task_id, "run_ids": selected,
        "armed_at": time.time()})
    return {"event": "active", "run_ids": selected}


def disarm(event):
    """Clear this chat's pending handoff; on Claude Code, record that hooks run."""
    task_id = event.get("session_id")
    try:
        task_id = str(uuid.UUID(task_id))
    except (TypeError, ValueError):
        return
    arm_path(task_id).unlink(missing_ok=True)
    if host.for_hook() == "claude":
        host.record_seen(task_id, event.get("permission_mode"))


def on_stop(event):
    """Block only an explicitly armed Stop event until a worker needs attention."""
    task_id = event.get("session_id")
    try:
        task_id = str(uuid.UUID(task_id))
    except (TypeError, ValueError):
        return {}
    marker = arm_path(task_id)
    try:
        state = json.loads(marker.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if (state.get("version") != 1 or state.get("thread_id") != task_id
            or not isinstance(state.get("run_ids"), list)
            or time.time() - state.get("armed_at", 0) > ARM_MAX_AGE_SECONDS):
        marker.unlink(missing_ok=True)
        return {}
    deadline = time.monotonic() + HOOK_WAIT_SECONDS
    pending = state["run_ids"]
    while pending:
        result = wait.wait_for_runs(run_ids=pending, task_id=task_id,
                                    timeout=min(wait.MAX_WAIT_SECONDS, max(0, deadline - time.monotonic())))
        if result["ready"] or result["errors"]:
            marker.unlink(missing_ok=True)
            ready = [{"run_id": row["run_id"], "status": row["status"],
                      "output_dir": row["output_dir"]} for row in result["ready"]]
            return {"decision": "block", "reason": "Tafwid worker update: " + json.dumps({
                "ready": ready, "errors": result["errors"],
                "pending_run_ids": result["pending_run_ids"]})}
        if time.monotonic() >= deadline:
            marker.unlink(missing_ok=True)
            return {"decision": "block", "reason": "Tafwid workers are still running after the hook wait limit. "
                    "Use wait.py with these run IDs: " + ", ".join(result["pending_run_ids"])}
        pending = result["pending_run_ids"]
    marker.unlink(missing_ok=True)
    return {}


def main():
    """Dispatch the CLI action and print compact JSON for the coordinator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "arm", "hook", "disarm"))
    parser.add_argument("--run-id", action="append", default=[],
                        help="Worker run ID from delegate.py; repeat for multiple workers")
    args = parser.parse_args()
    try:
        if args.action == "status":
            result = hook_status()
        elif args.action == "arm":
            result = arm(args.run_id)
        elif args.action == "hook":
            result = on_stop(json.load(sys.stdin))
        else:
            disarm(json.load(sys.stdin))
            result = {}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, TimeoutError) as exc:
        print(json.dumps({"event": "error", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
