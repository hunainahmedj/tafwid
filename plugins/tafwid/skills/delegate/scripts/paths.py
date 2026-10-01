"""Shared state location and private JSON writes for Tafwid's scripts.

State lives in a host-neutral home, $TAFWID_HOME/state (default ~/.tafwid/state),
shared by Codex and Claude Code coordinators. An existing installation under the
Codex home is used in place until `settings.py migrate` moves it.
"""

import json
import os
import tempfile
from pathlib import Path


def neutral_root():
    """Return the host-neutral state directory without creating it."""
    return Path(os.environ.get("TAFWID_HOME") or Path.home() / ".tafwid").expanduser() / "state"


def legacy_roots():
    """Return the state directories older releases used under the Codex home."""
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    return (home / "tafwid" / "state", home / "state" / "tafwid", home / "state" / "claude-delegate")


def state_root():
    """Resolve the state directory without creating or moving files.

    Use the neutral directory, or the single legacy directory when it is the
    only one that exists. Several candidates raise ValueError rather than
    choosing between conflicting histories.
    """
    neutral = neutral_root()
    legacy = [path for path in legacy_roots() if path != neutral and path.exists()]
    if len(legacy) > 1 or (legacy and neutral.exists()):
        raise ValueError(
            "Multiple Tafwid state directories exist. Back up and reconcile them "
            "before launching; Tafwid will not merge histories or permissions "
            "automatically."
        )
    return legacy[0] if legacy else neutral


def legacy_in_use():
    """Return the legacy directory currently serving as state, or None."""
    root = state_root()
    return None if root == neutral_root() else root


def migration_notice():
    """Describe the available migration for status output, or None."""
    legacy = legacy_in_use()
    if legacy is None:
        return None
    return {"available": True, "from": str(legacy), "to": str(neutral_root()),
            "command": "settings.py migrate"}


def atomic_json(path, data):
    """Atomically replace a JSON file with owner-only access permissions."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".worker-", delete=False) as file:
            temporary = Path(file.name)
            os.chmod(temporary, 0o600)
            json.dump(data, file, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
