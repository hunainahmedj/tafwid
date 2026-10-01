"""Move a legacy Tafwid state directory to the host-neutral home on request.

Used by `settings.py migrate`. Nothing here runs implicitly: reads keep using a
legacy directory in place until the user asks for the move.
"""
import errno
import json
import os
from pathlib import Path
import shutil

import paths
import run_state


def _files(root):
    """List relative regular-file paths and sizes for copy verification."""
    return sorted((str(path.relative_to(root)), path.stat().st_size)
                  for path in root.rglob("*") if path.is_file() and not path.is_symlink())


def _move(source, destination):
    """Rename, or copy and verify across filesystems before removing the source."""
    try:
        os.rename(source, destination)
        return
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
    shutil.copytree(source, destination, symlinks=True)
    if _files(source) != _files(destination):
        shutil.rmtree(destination)
        raise ValueError("Copied state does not match the source; nothing was removed")
    shutil.rmtree(source)


def migrate(dry_run=False):
    """Move the single legacy state directory to the neutral home.

    Refuse while workers run or when a path is redirected. Rewrite the absolute
    account homes saved in the registry. Any failure after the move restores
    the original directory before raising.
    """
    source = paths.legacy_in_use()
    destination = paths.neutral_root()
    if source is None:
        return {"event": "nothing_to_migrate", "state_root": str(paths.state_root())}
    if source.is_symlink() or destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError("Tafwid state path is redirected; migration stopped")
    if destination.exists():
        raise ValueError("The destination state directory already exists; migration stopped")
    active = [row["id"] for row in run_state.list_runs() if row.get("status") in run_state.ACTIVE]
    if active:
        raise ValueError("Workers are still running; wait for them before migrating: " + ", ".join(sorted(active)))
    registry = source / "accounts" / "registry.json"
    original = registry.read_bytes() if registry.is_file() else None
    result = {"source": str(source), "destination": str(destination),
              "accounts": len(list((source / "accounts" / "homes").glob("*"))),
              "tasks": len(list((source / "tasks").glob("*"))),
              "runs": len(list((source / "workers").glob("*.json")))}
    if dry_run:
        return {"event": "dry_run", **result}
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(destination.parent, 0o700)
    _move(source, destination)
    try:
        if original is not None:
            data = json.loads(original)
            prefix = str(source) + os.sep
            for row in data["accounts"]:
                if isinstance(row.get("home"), str) and row["home"].startswith(prefix):
                    row["home"] = str(destination / row["home"][len(prefix):])
            paths.atomic_json(destination / "accounts" / "registry.json", data)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        _move(destination, source)
        (source / "accounts" / "registry.json").write_bytes(original)
        raise ValueError("Migration failed and the original state was restored: " + str(exc)) from exc
    return {"event": "migrated", **result}
