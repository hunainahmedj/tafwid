"""Local state locations, including the pre-Tafwid installation."""
import os
from pathlib import Path


def state_root():
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    current = home / "state" / "tafwid"
    legacy = home / "state" / "claude-delegate"
    if current.exists() and legacy.exists():
        raise ValueError("Both Tafwid and legacy state directories exist. Back up and reconcile them before launching; Tafwid will not merge histories or permissions automatically.")
    return legacy if legacy.exists() else current
