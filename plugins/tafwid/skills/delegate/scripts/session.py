#!/usr/bin/env python3
"""Read or change automatic delegation for the current Codex chat.

CLI: session.py {on,off,status} [harness]. The harness is optional for on only.
Run session.py --help for examples, task identity, output and exit codes.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
import harnesses
import paths
import settings
import connections


def current_task_id():
    """Return the host's task UUID, or None when no task identity is available.

    Prefer CODEX_THREAD_ID over the legacy CODEX_SESSION_ID. Reject malformed
    values with ValueError so they cannot select an unintended state file.
    """
    value = os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID")
    if not value:
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise ValueError("Invalid Codex task identity; cannot select delegation state") from None


def state_path(task_id):
    """Return the private state-file path for an already validated task ID."""
    return paths.state_root() / (task_id + ".json")


def status():
    """Read this task's switch without writing files or checking the harness.

    Return thread_id and enabled. Missing identity or saved state means off;
    malformed saved state raises ValueError instead of being treated as enabled.
    """
    return connections.read(current_task_id())


def set_enabled(enabled, harness=None):
    """Save the selected task harness and switch only after readiness succeeds."""
    task_id = current_task_id()
    if task_id is None:
        raise ValueError("No Codex task identity; cannot save a session switch. Use an explicit one-shot task instead.")
    target = state_path(task_id)
    if enabled:
        selected = harness or settings.read(task_id, initialize=False)["harness"]
        connections.enable(task_id, selected)
        if selected == "claude":
            settings.update(task_id, harness="claude")
    else:
        connections.disable(task_id, harness)
    return {"thread_id": task_id, "enabled": connections.read(task_id)["enabled"]}


def main():
    """Parse the session action and report its result."""
    os.umask(0o077)
    parser = argparse.ArgumentParser(
        description="Read or change automatic delegation for the current Codex chat.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 session.py status   Read the setting without changing it.
  python3 session.py on       Check harness readiness, then enable delegation.
  python3 session.py on claude  Check and save Claude as this task's harness.
  python3 session.py off      Disable new dispatches; running workers continue.

Task identity:
  Read from CODEX_THREAD_ID, falling back to CODEX_SESSION_ID.
  Use the identity provided by Codex; there is no chat-ID argument.
  With no identity, status reports disabled with thread_id: null;
  on/off fail. A chat with no saved setting defaults to disabled.

Output and exit codes:
  Success: JSON with thread_id and enabled on stdout; exit 0.
  State/identity/readiness errors: JSON with error on stderr; exit 2.
  A readiness failure leaves the previous setting unchanged.
  Off and status do not check installation or authentication.
  Missing/invalid arguments: usage text on stderr; exit 2.
  --help prints this help and exits 0 without changing settings.
""",
    )
    parser.add_argument(
        "action", choices=("on", "off", "status"),
        help="required action: on enables, off disables, status reads the setting",
    )
    parser.add_argument("harness", nargs="?", help="claude or gpt for a named account")
    parser.add_argument("name", nargs="?", help="account name after gpt")
    args = parser.parse_args()
    action = args.action
    if args.name and args.harness != "gpt":
        parser.error("an account name follows gpt")
    if args.harness == "gpt" and not args.name:
        parser.error("gpt requires an account name")
    if args.harness not in (None, "claude", "gpt"):
        parser.error("use claude or gpt NAME")
    try:
        if action == "status":
            if args.harness is not None:
                parser.error("status takes no connection")
            result = status()
        else:
            selector = "gpt:" + args.name if args.harness == "gpt" else args.harness
            result = set_enabled(action == "on", selector)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
