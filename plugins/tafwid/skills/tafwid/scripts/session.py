#!/usr/bin/env python3
"""Persist Claude delegation on/off for the current Codex task, never the repo."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
import paths


def current_task_id():
    value = os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID")
    if not value:
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise ValueError("Invalid Codex task identity; cannot select delegation state") from None


def state_path(task_id):
    return paths.state_root() / (task_id + ".json")


def status():
    task_id = current_task_id()
    default = {"thread_id": task_id, "enabled": False}
    if task_id is None:
        return default
    try:
        data = json.loads(state_path(task_id).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    if (not isinstance(data, dict) or data.get("version") != 1
            or data.get("thread_id") != task_id or type(data.get("enabled")) is not bool):
        raise ValueError("Invalid delegation state; explicitly set on/off to repair this task's state")
    return {"thread_id": task_id, "enabled": data["enabled"]}


def set_enabled(enabled):
    task_id = current_task_id()
    if task_id is None:
        raise ValueError("No Codex task identity; cannot save a session switch. Use an explicit one-shot task instead.")
    target = state_path(task_id)
    target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    data = {"version": 1, "thread_id": task_id, "enabled": enabled,
            "updated_at": datetime.now(timezone.utc).isoformat()}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         prefix=".switch-", delete=False) as file:
            temporary = Path(file.name)
            json.dump(data, file, indent=2)
        os.replace(temporary, target)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return {"thread_id": task_id, "enabled": enabled}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("on", "off", "status"))
    action = parser.parse_args().action
    try:
        result = status() if action == "status" else set_enabled(action == "on")
        print(json.dumps(result))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
