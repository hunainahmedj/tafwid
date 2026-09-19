#!/usr/bin/env python3
"""User-selected model and permission defaults for future Claude worker launches."""
import argparse
import json
import os
import sys
import worker_registry as registry
import routing

POLICIES = ("scoped", "full", "inherit")


def settings_file():
    return registry.state_root() / "settings.json"


def validate(data):
    if (not isinstance(data, dict) or type(data.get("version")) is not int
            or data.get("permission_policy") not in POLICIES):
        raise ValueError("Invalid worker settings")
    version = data["version"]
    if version == 1 and set(data) == {"version", "permission_policy"}:
        return {**data, "version": 2, "models": routing.defaults()}
    if version != 2 or set(data) != {"version", "permission_policy", "models"}:
        raise ValueError("Invalid worker settings schema")
    routing.validate(data["models"])
    return data


def read():
    try:
        return validate(json.loads(settings_file().read_text(encoding="utf-8")))
    except FileNotFoundError:
        return {"version": 2, "permission_policy": "scoped", "models": routing.defaults()}


def save(data):
    normalized = validate(data)
    if data["version"] == 1:
        # Older dashboard tabs only edit permissions; do not erase saved routes.
        normalized["models"] = read()["models"]
    registry.atomic_json(settings_file(), normalized)
    return normalized


def resolve(override=None, config=None):
    # The launch process's signal is used, never the dashboard environment or old logs.
    policy = override if override is not None else (config if config is not None else read())["permission_policy"]
    if policy not in POLICIES:
        raise ValueError("Invalid worker permission policy")
    parent_full = os.environ.get("CODEX_PERMISSION_PROFILE") == ":danger-full-access"
    effective = "full" if policy == "full" or (policy == "inherit" and parent_full) else "scoped"
    reason = {"full": "Full access selected by the user", "scoped": "Scoped command allowances selected"}.get(policy)
    if policy == "inherit":
        reason = ("Current Codex process reports full access" if parent_full else
                  "Codex full access is not confirmed; using scoped allowances")
    return {"policy": policy, "effective": effective,
            "claude_mode": "bypassPermissions" if effective == "full" else "dontAsk",
            "source": "override" if override is not None else "settings",
            "codex_full_access": parent_full, "reason": reason}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("show", "set"))
    parser.add_argument("--policy", choices=POLICIES)
    args = parser.parse_args()
    if args.action == "set" and args.policy is None:
        parser.error("set requires --policy")
    if args.action == "show" and args.policy is not None:
        parser.error("show does not accept --policy")
    try:
        result = save({"version": 1, "permission_policy": args.policy}) if args.action == "set" else read()
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
