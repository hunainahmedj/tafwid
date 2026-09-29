"""Route readiness checks to the selected worker harness.

Claude exposes check_ready(cwd=None); GPT requires a named account. Both return launch metadata on success
or raise ValueError with an actionable message. Checks must not launch workers,
install software, or initiate login. Add future adapters to ADAPTERS.
"""

import claude_code
import codex_cli

DEFAULT_HARNESS = "claude"
ADAPTERS = {"claude": claude_code, "gpt": codex_cli}


def check_ready(harness=None, *, cwd=None, account=None):
    """Check a named harness, or the default, without changing session state."""
    name = DEFAULT_HARNESS if harness is None else harness
    if name not in ADAPTERS:
        raise ValueError(f"Unsupported worker harness: {name}")
    if name == "gpt":
        if account is None:
            raise ValueError("A named GPT account is required")
        return codex_cli.check_ready(account, cwd=cwd)
    return claude_code.check_ready(cwd=cwd)
