#!/usr/bin/env python3
"""Manage worker settings for this task, or global defaults with --global.

CLI: show; set --policy scoped|full|inherit and/or --harness claude.
A task copies global defaults on first use, then keeps its own settings on disk.
Model routes are preserved; delegate.py --model overrides them for one worker.
Output is JSON. --help does not read or write settings.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
import sys
import uuid

import harnesses
import host
import paths
import routing

POLICIES = ("scoped", "full", "inherit")


def settings_file(task_id=None):
    """Return a global or task settings path; reject invalid task identities."""
    if task_id is None:
        return paths.state_root() / "settings.json"
    try:
        task_id = str(uuid.UUID(task_id))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid Codex task identity; cannot select settings") from None
    return paths.state_root() / "tasks" / task_id / "settings.json"


def defaults():
    """Return fresh defaults without reading or creating files."""
    return {"version": 3, "harness": harnesses.DEFAULT_HARNESS,
            "permission_policy": "scoped", "models": routing.defaults()}


def validate(data):
    """Validate settings, adding missing fields from older formats in memory."""
    if (not isinstance(data, dict) or type(data.get("version")) is not int
            or data.get("permission_policy") not in POLICIES):
        raise ValueError("Invalid worker settings")
    fields = {"version", "permission_policy"}
    version = data["version"]
    if version in (2, 3):
        fields.add("models")
    if version == 3:
        fields.add("harness")
    if version not in (1, 2, 3) or set(data) != fields:
        raise ValueError("Invalid worker settings schema")
    normalized = {**defaults(), **data, "version": 3}
    name = normalized["harness"]
    if not isinstance(name, str) or name not in harnesses.ADAPTERS:
        raise ValueError("Unsupported worker harness in settings")
    routing.validate(normalized["models"])
    return normalized


@contextmanager
def settings_lock(target):
    """Serialize initialization and updates so parallel workers share one snapshot."""
    target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    descriptor = os.open(target.with_suffix(".lock"), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def read(task_id=None, *, initialize=True):
    """Read global defaults or this task's saved snapshot.

    A missing task snapshot is initialized once from global defaults. Pass
    initialize=False to preview it without writes, for readiness checks.
    Corrupt snapshots raise an error; they never fall back to global settings.
    """
    target = settings_file(task_id)
    try:
        return validate(json.loads(target.read_text(encoding="utf-8")))
    except FileNotFoundError:
        if task_id is None:
            return defaults()
        if not initialize:
            return read()
    with settings_lock(target):
        # Another process may have initialized or changed this task while waiting.
        data = read(task_id, initialize=False)
        if not target.exists():
            paths.atomic_json(target, validate(data))
        return data


def save(data, task_id=None):
    """Save settings for the selected scope, preserving routes on legacy updates."""
    normalized = validate(data)
    target = settings_file(task_id)
    with settings_lock(target):
        if data["version"] < 3:
            current = read(task_id, initialize=False)
            normalized["harness"] = current["harness"]
            if data["version"] == 1:
                normalized["models"] = current["models"]
        paths.atomic_json(target, normalized)
    return normalized


def update(task_id=None, *, policy=None, harness=None):
    """Change only requested fields, preserving the latest routes and other choices."""
    if policy is not None and policy not in POLICIES:
        raise ValueError("Invalid worker permission policy")
    if harness is not None and harness not in harnesses.ADAPTERS:
        raise ValueError("Unsupported worker harness")
    target = settings_file(task_id)
    with settings_lock(target):
        data = read(task_id, initialize=False)
        if policy is not None:
            data["permission_policy"] = policy
        if harness is not None:
            data["harness"] = harness
        paths.atomic_json(target, validate(data))
    return data


def resolve(override=None, config=None):
    """Map the selected policy to worker permissions using the coordinator's live signal."""
    policy = override if override is not None else (config if config is not None else read())["permission_policy"]
    if policy not in POLICIES:
        raise ValueError("Invalid worker permission policy")
    parent_full = host.full_access()
    name = host.display_name()
    effective = "full" if policy == "full" or (policy == "inherit" and parent_full) else "scoped"
    reason = {"full": "Full access selected by the user", "scoped": "Scoped command allowances selected"}.get(policy)
    if policy == "inherit":
        reason = (f"{name} currently reports full access" if parent_full else
                  f"Full access is not confirmed by {name}; using scoped allowances")
    return {"policy": policy, "effective": effective,
            "claude_mode": "bypassPermissions" if effective == "full" else "dontAsk",
            "source": "override" if override is not None else "settings",
            "coordinator_full_access": parent_full, "reason": reason}


def main():
    """Read or update this task's settings, with global changes explicitly selected."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 scripts/settings.py show
  python3 scripts/settings.py set --policy scoped
  python3 scripts/settings.py show --global
  python3 scripts/settings.py set --policy inherit --global

Without --global, use the current Codex task identity from the host environment.
First use saves a task snapshot; later global edits do not affect it. No task
identity is required for --global. Settings do not modify already-running workers.
Success prints JSON and exits 0; settings errors exit 1; argument errors exit 2.
""",
    )
    parser.add_argument("action", choices=("show", "set"), help="read or update settings")
    parser.add_argument("--global", dest="global_defaults", action="store_true",
                        help="read or change defaults for new tasks, instead of this task")
    parser.add_argument("--policy", choices=POLICIES, help="permission policy to save")
    parser.add_argument("--harness", choices=tuple(harnesses.ADAPTERS), help="worker harness to save")
    args = parser.parse_args()
    if args.action == "set" and args.policy is None and args.harness is None:
        parser.error("set requires --policy or --harness")
    if args.action == "show" and (args.policy is not None or args.harness is not None):
        parser.error("show does not accept --policy or --harness")
    try:
        task_id = None
        if not args.global_defaults:
            # Import here to keep the settings store independent of session writes.
            from session import current_task_id
            task_id = current_task_id()
            if task_id is None:
                raise ValueError("No Codex task identity; use --global for global defaults")
        result = (read(task_id) if args.action == "show" else
                  update(task_id, policy=args.policy, harness=args.harness))
        if args.action == "show" and paths.migration_notice():
            result = {**result, "migration": paths.migration_notice()}
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
