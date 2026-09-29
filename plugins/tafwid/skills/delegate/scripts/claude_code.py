"""Read-only installation and subscription checks for Claude Code.

Used when enabling delegation and before each launch or resume. No model request
is made. Reported login configuration does not prove that credentials are still
valid; an expired session can fail when a worker actually runs.
"""

import json
import os
import shutil
import subprocess

OVERRIDES = (
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
)


def check_ready(*, cwd=None):
    """Return executable and subscription_type, or raise ValueError with next steps.

    Resolve Claude from PATH and run only ``claude auth status`` in cwd (the
    current directory by default). Reject API/provider overrides without
    exposing their values. Authentication output stays private.
    """
    executable = shutil.which("claude")
    if not executable:
        raise ValueError(
            "Claude Code is not on PATH. Install Claude Code or add it to PATH, "
            "then run `claude auth login` and retry."
        )
    active = [name for name in OVERRIDES if os.environ.get(name)]
    if active:
        raise ValueError(
            "Claude requires a subscription login. Resolve these environment "
            "overrides first: " + ", ".join(active)
        )
    try:
        auth = subprocess.run(
            [executable, "auth", "status"], cwd=cwd,
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise ValueError(
            "Claude authentication check timed out. Run `claude auth status` "
            "in your terminal to diagnose it, then retry."
        ) from None
    except (OSError, UnicodeError):
        raise ValueError(
            "Could not run or read `claude auth status`. Check the Claude Code "
            "installation in your terminal, then retry."
        ) from None
    if auth.returncode:
        raise ValueError(
            "Claude login check failed. Run `claude auth login` in your terminal."
        )
    try:
        data = json.loads(auth.stdout)
    except json.JSONDecodeError:
        raise ValueError(
            "Claude auth status did not return JSON; check the installed CLI."
        ) from None
    if (
        not isinstance(data, dict)
        or data.get("loggedIn") is not True
        or data.get("authMethod") != "claude.ai"
        or data.get("apiProvider") != "firstParty"
        or data.get("subscriptionType") not in ("pro", "max", "team", "enterprise")
        or data.get("apiKeySource")
    ):
        raise ValueError(
            "Expected a Claude subscription login. Run `claude auth login`; "
            "do not select API billing."
        )
    return {"executable": executable, "subscription_type": data["subscriptionType"]}
