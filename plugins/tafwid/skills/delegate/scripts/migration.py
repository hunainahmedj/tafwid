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
    try:
        shutil.copytree(source, destination, symlinks=True)
        if _files(source) != _files(destination):
            raise ValueError("Copied state does not match the source; nothing was removed")
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    shutil.rmtree(source)


def _registry(source):
    """Read and validate the account registry before anything moves."""
    path = source / "accounts" / "registry.json"
    if not path.is_file():
        return None, None
    original = path.read_bytes()
    try:
        data = json.loads(original)
    except ValueError:
        data = None
    if (not isinstance(data, dict) or not isinstance(data.get("accounts"), list)
            or any(not isinstance(row, dict) or not isinstance(row.get("home"), str)
                   for row in data["accounts"])):
        raise ValueError("The GPT account registry is malformed; repair it before migrating")
    return original, data


def migrate(dry_run=False):
    """Move the single legacy state directory to the neutral home.

    Refuse while workers run, when a path is redirected, or when the account
    registry is malformed. Rewrite the absolute account homes saved in the
    registry. Any failure after the move restores the original directory.
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
    original, data = _registry(source)
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
            # Homes are rebuilt from their directory names, whatever spelling the old path used.
            for row in data["accounts"]:
                row["home"] = str(destination / "accounts" / "homes" / Path(row["home"]).name)
            paths.atomic_json(destination / "accounts" / "registry.json", data)
    except Exception as exc:
        try:
            _move(destination, source)
            if original is not None:
                (source / "accounts" / "registry.json").write_bytes(original)
        except Exception as undo:
            raise ValueError(f"Migration failed ({exc}) and the state could not be moved back ({undo}). "
                             f"It is now at {destination}; it was at {source}.") from undo
        raise ValueError("Migration failed and the original state was restored: " + str(exc)) from exc
    return {"event": "migrated", **result}
