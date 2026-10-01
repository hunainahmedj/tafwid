"""Identify the coordinating host and its task for Tafwid's scripts.

Tafwid is coordinated by Codex or Claude Code. This is the only module that
reads their identity signals. TAFWID_HOST=codex|claude forces one host for
tests and recovery; with it set, only that host's signal is read.
"""
import json
import os
import time
import uuid

import paths

HOSTS = ("codex", "claude")
NAMES = {"codex": "Codex", "claude": "Claude Code"}
SIGNALS = {"codex": ("CODEX_THREAD_ID", "CODEX_SESSION_ID"),
           "claude": ("CLAUDE_CODE_SESSION_ID",)}
IDENTITY_VARIABLES = SIGNALS["codex"] + SIGNALS["claude"] + ("TAFWID_HOST",)
# A marker older than this no longer proves that hooks run or what mode the session is in.
MAX_SEEN_AGE_SECONDS = 24 * 60 * 60


def _signal(name, env):
    """Return the first nonempty identity value for one host."""
    for key in SIGNALS[name]:
        if env.get(key):
            return env[key]
    return None


def detect(env=None):
    """Return "codex", "claude", or None; never choose between two hosts."""
    env = os.environ if env is None else env
    forced = env.get("TAFWID_HOST")
    if forced:
        if forced not in HOSTS:
            raise ValueError("TAFWID_HOST must be codex or claude")
        return forced
    found = [name for name in HOSTS if _signal(name, env)]
    if len(found) > 1:
        raise ValueError("Both Codex and Claude Code task identities are present; "
                         "set TAFWID_HOST to codex or claude")
    return found[0] if found else None


def task_id(env=None):
    """Return the coordinator's task UUID, or None when there is no identity.

    A malformed value raises ValueError so it cannot select an unintended file.
    """
    env = os.environ if env is None else env
    name = detect(env)
    value = _signal(name, env) if name else None
    if not value:
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise ValueError(f"Invalid {NAMES[name]} task identity; cannot select delegation state") from None


def display_name(env=None):
    """Name the coordinator for messages without raising."""
    try:
        return NAMES.get(detect(env), "the coordinator")
    except ValueError:
        return "the coordinator"


def for_hook(env=None):
    """Identify the host inside a hook process, which lacks task variables."""
    env = os.environ if env is None else env
    return "claude" if env.get("CLAUDE_PLUGIN_ROOT") else "codex"


def worker_env(base=None):
    """Copy an environment without coordinator identity, so a worker is never one."""
    base = os.environ if base is None else base
    return {key: value for key, value in base.items() if key not in IDENTITY_VARIABLES}


def seen_path(task_id):
    """Choose the private marker recording that this task's hooks ran."""
    return paths.state_root() / "hook-seen" / (task_id + ".json")


def record_seen(task_id, permission_mode):
    """Record that Claude Code ran Tafwid's prompt hook, with its permission mode."""
    paths.atomic_json(seen_path(task_id), {
        "version": 1, "thread_id": task_id, "seen_at": time.time(),
        "permission_mode": permission_mode if isinstance(permission_mode, str) else None})


def seen(task_id):
    """Return this task's recent hooks-seen marker, or None when missing, old or invalid."""
    if not task_id:
        return None
    try:
        data = json.loads(seen_path(task_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != 1 or data.get("thread_id") != task_id:
        return None
    seen_at = data.get("seen_at")
    if type(seen_at) not in (int, float) or time.time() - seen_at > MAX_SEEN_AGE_SECONDS:
        return None
    return data


def full_access(env=None):
    """Report whether the coordinator currently confirms full access."""
    env = os.environ if env is None else env
    name = detect(env)
    if name == "codex":
        return env.get("CODEX_PERMISSION_PROFILE") == ":danger-full-access"
    if name == "claude":
        marker = seen(task_id(env))
        return bool(marker) and marker.get("permission_mode") == "bypassPermissions"
    return False
