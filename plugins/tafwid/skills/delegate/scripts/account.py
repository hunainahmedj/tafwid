#!/usr/bin/env python3
"""Set up and inspect named GPT worker accounts through Codex's own login.

Credentials remain in the selected private CODEX_HOME; Tafwid never reads them.
Examples: ``account.py add gpt --name pro2``; ``account.py add gpt business
--name work``; ``account.py check work``; ``account.py confirm work``.
Outputs JSON metadata on success. Exit 0 means command success; exit 2 means
arguments, login, or state need attention. ``--help`` has no side effects.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

import accounts


def _login(row: dict, device_auth: bool = False) -> None:
    """Open native Codex login in the selected home and keep it pending."""
    home = accounts.validate_home(row)
    executable = shutil.which("codex")
    if executable is None:
        raise ValueError("Install the Codex CLI, then run account.py login NAME")
    print(f"Opening Codex sign-in for {row['kind']} account {row['name']} in {row['home']}.",
          file=sys.stderr, flush=True)
    command = [executable, "login"] + (["--device-auth"] if device_auth else [])
    try:
        proc = subprocess.run(command, env=accounts.isolated_env(home),
                              stdout=sys.stderr, stderr=sys.stderr, check=False)
    except OSError:
        raise ValueError("Could not start Codex sign-in; retry account.py login NAME") from None
    if proc.returncode != 0:
        raise ValueError("Codex sign-in did not finish; this account remains pending")


def main(argv: list[str] | None = None) -> int:
    """Parse a visible account action and print sanitized JSON metadata."""
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="Exit 0: action succeeded. Exit 2: fix the reported setup or arguments.\n"
                                            "Sign-in never confirms account identity; the user must confirm it.")
    actions = parser.add_subparsers(dest="action", required=True)
    add = actions.add_parser("add", help="Create a pending account and open Codex sign-in")
    add.add_argument("provider", choices=("gpt",))
    add.add_argument("type", nargs="?", choices=("business",), default="personal")
    add.add_argument("--name", required=True, help="Unique short account name")
    add.add_argument("--device-auth", action="store_true", help="Use Codex device-code login")
    login = actions.add_parser("login", help="Retry sign-in; account stays pending until confirmed again")
    login.add_argument("name")
    login.add_argument("--device-auth", action="store_true")
    check = actions.add_parser("check", help="Check login method without a model request")
    check.add_argument("name")
    actions.add_parser("list", help="List saved account names and states")
    confirm = actions.add_parser("confirm", help="Mark ready after the user's explicit confirmation")
    confirm.add_argument("name")
    args = parser.parse_args(argv)
    try:
        if args.action == "add":
            row = accounts.create(args.name, args.type)
            _login(row, args.device_auth)
            result = accounts.check(row)
        elif args.action == "login":
            row = accounts.get(args.name)
            accounts.validate_home(row)
            row = accounts.mark_pending(args.name)
            _login(row, args.device_auth)
            result = accounts.check(row)
        elif args.action == "check":
            result = accounts.check(accounts.get(args.name))
        elif args.action == "list":
            result = accounts.list_accounts()
        else:
            result = accounts.confirm(args.name)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
