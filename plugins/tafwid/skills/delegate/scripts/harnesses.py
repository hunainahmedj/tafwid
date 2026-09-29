"""Route readiness checks to the selected worker harness.

Adapters expose check_ready(cwd=None). They return launch metadata on success
or raise ValueError with an actionable message. Checks must not launch workers,
install software, or initiate login. Add future adapters to ADAPTERS.
"""

import claude_code

DEFAULT_HARNESS = "claude"
ADAPTERS = {"claude": claude_code}


def check_ready(harness=None, *, cwd=None):
    """Check a named harness, or the default, without changing session state."""
    name = DEFAULT_HARNESS if harness is None else harness
    if name not in ADAPTERS:
        raise ValueError(f"Unsupported worker harness: {name}")
    return ADAPTERS[name].check_ready(cwd=cwd)
