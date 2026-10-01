"""Task-local pool of exact Claude and named GPT worker connections."""

from datetime import datetime, timezone
import json

import accounts
import claude_code
import paths


def _path(task_id: str):
    """Select one validated task's private switch file."""
    if not task_id or "/" in task_id or ".." in task_id:
        raise ValueError("Invalid Codex task identity")
    return paths.state_root() / (task_id + ".json")


def _claude():
    """Build the stable Claude connection descriptor."""
    return {"id": "claude:default", "selector": "claude", "provider": "claude",
            "name": "claude", "kind": "personal"}


def _gpt(account):
    """Build a descriptor with the immutable account ID."""
    return {"id": "gpt:" + account["id"], "selector": "gpt:" + account["name"],
            "provider": "gpt", "name": account["name"], "kind": account["kind"]}


def read(task_id: str | None) -> dict:
    """Read a task pool, interpreting version-1 switches as Claude-only."""
    default = {"thread_id": task_id, "enabled": False, "connections": []}
    if task_id is None:
        return default
    try:
        data = json.loads(_path(task_id).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    if not isinstance(data, dict) or data.get("thread_id") != task_id:
        raise ValueError("Invalid delegation state; explicitly set on/off to repair this task's state")
    if data.get("version") == 1 and type(data.get("enabled")) is bool:
        rows = [_claude()] if data["enabled"] else []
    elif data.get("version") == 2 and isinstance(data.get("connections"), list):
        rows = data["connections"]
        if any(not isinstance(row, dict) or not isinstance(row.get("id"), str)
               or not isinstance(row.get("selector"), str) for row in rows):
            raise ValueError("Invalid delegation connection pool")
    else:
        raise ValueError("Invalid delegation state; explicitly set on/off to repair this task's state")
    return {"thread_id": task_id, "enabled": bool(rows), "connections": rows}


def describe(task_id: str | None) -> dict:
    """Show current login availability without changing the saved pool."""
    pool = read(task_id)
    shown = []
    for row in pool["connections"]:
        item = dict(row)
        try:
            if row["provider"] == "claude":
                claude_code.check_ready()
                item["availability"] = "ready"
            elif row["provider"] == "gpt":
                account = accounts.get(row["name"])
                if "gpt:" + account["id"] != row["id"]:
                    item["availability"] = "unavailable"
                elif account["status"] != "ready":
                    item["availability"] = "pending"
                else:
                    item["availability"] = ("ready" if accounts.check(account)["login_method"] == "chatgpt"
                                            else "unavailable")
            else:
                item["availability"] = "unavailable"
        except (OSError, ValueError, KeyError, TypeError):
            item["availability"] = "unavailable"
        shown.append(item)
    return {**pool, "connections": shown}


def _write(task_id: str, rows: list[dict]) -> dict:
    """Persist a version-2 pool atomically."""
    data = {"version": 2, "thread_id": task_id, "connections": rows,
            "updated_at": datetime.now(timezone.utc).isoformat()}
    paths.atomic_json(_path(task_id), data)
    return {"thread_id": task_id, "enabled": bool(rows), "connections": rows}


def _select(selector: str, *, ready: bool) -> dict:
    """Resolve a display selector and optionally recheck its login."""
    if selector == "claude":
        if ready:
            claude_code.check_ready()
        return _claude()
    if selector.startswith("gpt:") and selector[4:]:
        account = accounts.get(selector[4:])
        if account["status"] != "ready":
            raise ValueError(f"GPT account {account['name']} is pending; use account.py to finish setup")
        if ready and accounts.check(account)["login_method"] != "chatgpt":
            raise ValueError(f"GPT account {account['name']} needs Codex sign-in; run account.py check {account['name']}")
        return _gpt(account)
    raise ValueError("Use claude or gpt:NAME as a connection selector")


def enable(task_id: str, selector: str) -> dict:
    """Add one ready connection while keeping the existing pool on failure."""
    selected = _select(selector, ready=True)
    rows = read(task_id)["connections"]
    rows = [row for row in rows if row["id"] != selected["id"]] + [selected]
    return _write(task_id, rows)


def disable(task_id: str, selector: str | None) -> dict:
    """Remove one connection or disable the whole pool without login checks."""
    if selector is None:
        return _write(task_id, [])
    rows = read(task_id)["connections"]
    if selector == "claude":
        rows = [row for row in rows if row["id"] != "claude:default"]
    elif selector.startswith("gpt:"):
        rows = [row for row in rows if row["selector"] != selector]
    else:
        raise ValueError("Use claude or gpt:NAME as a connection selector")
    return _write(task_id, rows)


def resolve(task_id: str | None, selector: str | None, *, once: bool = False) -> dict:
    """Choose one exact destination; never infer a route from a mixed pool."""
    rows = read(task_id)["connections"] if not once else []
    if selector is not None:
        selected = _select(selector, ready=False)
        if once or any(row["id"] == selected["id"] for row in rows):
            return selected
        raise ValueError(f"Connection {selector} is not enabled for this task")
    if once:
        return _claude()
    if len(rows) == 1:
        return rows[0]
    if not rows:
        raise ValueError("Delegation is off for this Codex task")
    raise ValueError("Several connections are enabled; specify --connection for this assignment")
