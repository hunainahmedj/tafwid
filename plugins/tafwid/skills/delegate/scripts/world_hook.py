#!/usr/bin/env python3
"""Observer hook: turn one Claude Code or Codex hook payload into one activity event.

Reads a single JSON payload from stdin and appends one sanitised line to the
opt-in activity log (see world.py). Nothing is printed and the exit status is
always 0, so the hook can never disturb a session. Only derived labels are
kept: the action comes from the tool name and the target's extension, and the
raw input, prompts, paths, output and ids are discarded or hashed.
"""
import json
import os
import re
import sys
import time

import host
import world

EVENT_KINDS = {
    "SessionStart": "session", "UserPromptSubmit": "prompt", "PreToolUse": "tool",
    "PostToolUse": "tool", "PermissionRequest": "permission", "SubagentStart": "subagent-start",
    "SubagentStop": "subagent-stop", "Stop": "stop", "SessionEnd": "session-end",
    "Notification": "notification",
}
ROLES = ("coordinator", "implementer", "reviewer", "documenter", "researcher", "tester")
DOC_EXTENSIONS = (".md", ".mdx", ".rst", ".txt")
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit", "apply_patch")
SPAWN_TOOLS = ("Agent", "Task", "spawn_agent")
LABEL_CHARS = 80
SHORT_CHARS = 64
SOURCE_CHARS = 2000
SCAN_CHARS = 200000
MAX_LINE_BYTES = 3500
ENVELOPE_BYTES = 64  # the "v" and "t" keys that world.append_event adds
STOP_STATUS = {"completed": "done", "error": "error", "interrupted": "interrupted"}
NOTIFICATION_STATUS = {"permission_prompt": "waiting", "idle_prompt": "idle"}

ROLE_TAG = re.compile(r"\[role:\s*([A-Za-z-]*)\s*\]", re.IGNORECASE)
PATCH_FILE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File:\s*(.+?)\s*$", re.MULTILINE)
TEST_RUNNER = re.compile(
    r"\b(?:pytest|vitest|playwright)\b|\bnpm\s+(?:run\s+)?test\b|\bmake\s+test\b"
    r"|\bcargo\s+test\b|\bgo\s+test\b")


def _patch_paths(tool_input):
    """Return the file paths named by a patch or a file_path field, then discard the input."""
    for key in ("file_path", "notebook_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return [value]
    paths = []
    for value in tool_input.values():
        if isinstance(value, str):
            paths += PATCH_FILE.findall(value[:SCAN_CHARS])
    return paths


def classify_action(tool_name, tool_input):
    """Return a coarse action label from the tool name and target extension."""
    if isinstance(tool_input, str):  # Codex may send the patch text or command bare
        tool_input = {"command": tool_input}
    elif not isinstance(tool_input, dict):
        tool_input = {}
    if tool_name in SPAWN_TOOLS:
        return "spawn"
    if tool_name in EDIT_TOOLS:
        paths = _patch_paths(tool_input)
        if paths and all(os.path.splitext(path)[1].lower() in DOC_EXTENSIONS for path in paths):
            return "edit-docs"
        return "edit-code"
    if tool_name in ("Read", "NotebookRead"):
        return "read"
    if tool_name in ("Grep", "Glob", "LS"):
        return "search"
    if tool_name == "Bash":
        command = tool_input.get("command")
        if isinstance(command, list) and all(isinstance(part, str) for part in command):
            command = " ".join(command)  # Codex may send an argv list
        if isinstance(command, str) and TEST_RUNNER.search(command[:SCAN_CHARS]):
            return "run-tests"
        return "run-command"
    if tool_name in ("WebFetch", "WebSearch"):
        return "web"
    return "other"


def extract_role(text):
    """Return the role named by [role: <name>] tags and the text with every tag removed.

    The last valid tag wins; an unknown role name is ignored but still stripped.
    """
    role = None
    for name in ROLE_TAG.findall(text):
        if name.lower() in ROLES:
            role = name.lower()
    cleaned = re.sub(r"[ \t]{2,}", " ", ROLE_TAG.sub("", text)).strip()
    return role, cleaned


def _short(value, limit):
    """Collapse a value to one line of at most limit characters, or None when empty."""
    if not isinstance(value, str):
        return None
    return " ".join(value[:SOURCE_CHARS].split())[:limit] or None


def _host_keys(host_name, claude, codex):
    return claude if host_name == "claude" else codex if host_name == "codex" else claude + codex


def _spawn_details(tool_input, host_name):
    """Return (label, agent_type, role) for a spawn tool call."""
    agent_type = None
    for key in _host_keys(host_name, ("subagent_type",), ("agent_type", "role")):
        agent_type = _short(tool_input.get(key), SHORT_CHARS)
        if agent_type:
            break
    text = ""
    for key in _host_keys(host_name, ("description",), ("message", "prompt")):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            text = value[:SOURCE_CHARS]
            break
    role, text = extract_role(text)
    if host_name != "claude":
        text = next((line for line in text.splitlines() if line.strip()), "")
    return _short(text, LABEL_CHARS), agent_type, role


def _project(cwd):
    if not isinstance(cwd, str):
        return None
    return _short(re.split(r"[\\/]", cwd.rstrip("\\/"))[-1], 100)


def _status(name, payload):
    if name == "PermissionRequest":
        return "waiting"
    if name == "Stop":
        return "idle"
    if name == "Notification":
        return NOTIFICATION_STATUS.get(payload.get("notification_type"))
    if name == "SubagentStop":
        return STOP_STATUS.get(payload.get("stop_reason"), "done")
    return None


def detect_host(payload):
    """Name the host the way hooks do: Claude Code exports the event's own session id."""
    session = payload.get("session_id")
    if isinstance(session, str) and session:
        return host.for_hook(session)
    return "unknown"


def fit_event(event):
    """Keep the serialised line under the size limit, dropping the label first."""
    for key in ("label", "agentType", "project"):
        size = len(json.dumps(event, separators=(",", ":")).encode()) + ENVELOPE_BYTES
        if size <= MAX_LINE_BYTES:
            break
        event[key] = None
    return event


def to_event(payload, host_name):
    """Convert a hook payload into an event dict, or None when it is not recorded."""
    name = payload.get("hook_event_name")
    kind = EVENT_KINDS.get(name) if isinstance(name, str) else None
    session = payload.get("session_id")
    if kind is None or not isinstance(session, str) or not session:
        return None
    agent_id = payload.get("agent_id")
    event = {
        "host": host_name,
        "session": world.hash_id(session),
        "project": _project(payload.get("cwd")),
        "agent": world.hash_id(agent_id) if isinstance(agent_id, str) and agent_id else None,
        "event": kind,
        "phase": {"PreToolUse": "pre", "PostToolUse": "post"}.get(name),
        "agentType": _short(payload.get("agent_type"), SHORT_CHARS),
        "label": None,
        "action": None,
        "role": None,
        "status": _status(name, payload),
    }
    if kind in ("tool", "permission"):
        tool_input = payload.get("tool_input")
        event["action"] = classify_action(payload.get("tool_name"), tool_input)
        if event["action"] == "spawn" and event["phase"] == "pre":
            details = _spawn_details(tool_input if isinstance(tool_input, dict) else {}, host_name)
            event["label"], event["agentType"], event["role"] = details
    return fit_event(event)


def main(stdin):
    """Record one event from stdin; silent, and always returns 0."""
    try:
        if not world.enabled():
            return 0
        payload = json.loads(stdin.read())
        if not isinstance(payload, dict):
            raise ValueError("payload is not a JSON object")
        event = to_event(payload, detect_host(payload))
        if event is not None:
            world.append_event(event)
            if payload.get("hook_event_name") == "SessionStart":
                world.prune(time.time())
    except Exception as error:
        world.log_error("world_hook: %s: %s" % (type(error).__name__, error))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin))
