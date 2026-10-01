#!/usr/bin/env python3
"""Read or change this task's pool of worker connections.

CLI: session.py on [claude|gpt NAME], off [claude|gpt NAME], or status.
Run session.py --help for examples, task identity, output and exit codes.
"""
import argparse
import json
import os
import sys
import host
import paths
import settings
import connections


def current_task_id():
    """Return the coordinator's task UUID, or None when no identity is available.

    Malformed values raise ValueError so they cannot select an unintended state file.
    """
    return host.task_id()


def state_path(task_id):
    """Return the private state-file path for an already validated task ID."""
    return paths.state_root() / (task_id + ".json")


def status():
    """Read this task's pool and current login availability without writes.

    Return thread_id, enabled, and connections. Missing identity or state means off;
    malformed saved state raises ValueError instead of being treated as enabled.
    """
    result = connections.describe(current_task_id())
    notice = paths.migration_notice()
    if notice:
        result["migration"] = notice
    return result


def set_enabled(enabled, harness=None):
    """Add or remove a task connection, checking readiness before enabling."""
    task_id = current_task_id()
    if task_id is None:
        raise ValueError("No task identity from the coordinator; cannot save a session switch. Use an explicit one-shot task instead.")
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
        description="Read or change automatic delegation for the current chat.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 session.py status   Read the setting without changing it.
  python3 session.py on       Add this task's saved Claude harness.
  python3 session.py on claude  Add Claude to this task's pool.
  python3 session.py on gpt work  Add a ready named GPT account.
  python3 session.py off gpt work  Remove one connection.
  python3 session.py off      Disable new dispatches; running workers continue.

Task identity:
  Codex: CODEX_THREAD_ID, falling back to CODEX_SESSION_ID.
  Claude Code: CLAUDE_CODE_SESSION_ID.
  Use the identity provided by the coordinator; there is no chat-ID argument.
  With no identity, status reports disabled with thread_id: null;
  on/off fail. A chat with no saved setting defaults to disabled.

Output and exit codes:
  Success: JSON with thread_id and enabled; status also lists connections.
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
