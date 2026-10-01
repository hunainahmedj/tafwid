"""Shared state location and private JSON writes for Tafwid's scripts.

New installations use $CODEX_HOME/tafwid/state, with ~/.codex as the default
Codex home. Existing installations reuse their saved directory in place.
"""

import json
import os
import tempfile
from pathlib import Path


def state_root():
    """Resolve the state directory without creating or moving files.

    Reuse either older layout when it is the only existing state directory.
    Multiple directories raise ValueError to avoid choosing conflicting state.
    """
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    current = home / "tafwid" / "state"
    candidates = (current, home / "state" / "tafwid", home / "state" / "claude-delegate")
    existing = [path for path in candidates if path.exists()]
    if len(existing) > 1:
        raise ValueError(
            "Multiple Tafwid state directories exist. Back up and reconcile them "
            "before launching; Tafwid will not merge histories or permissions "
            "automatically."
        )
    return existing[0] if existing else current


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
