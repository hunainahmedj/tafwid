#!/usr/bin/env python3
"""Opt-in local activity log for the Tafwid dashboard.

CLI: on | off | status. Output is JSON; argument errors exit 2.
The log lives only in the host-neutral home, $TAFWID_HOME/state/world
(default ~/.tafwid/state/world), never in a legacy Codex-home state directory.
The marker file world/enabled is the switch; hooks append sanitised events to
world/events-YYYY-MM-DD.jsonl (local date, mode 0600, pruned after 7 days).
Raw ids are never stored: hash_id keeps the first 16 hex characters of
HMAC-SHA256 under a private random salt in world/salt.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import time

RETENTION_SECONDS = 7 * 86400
ERROR_LOG_LINES = 100
EVENT_VERSION = 1
SALT_BYTES = 32
ERROR_MESSAGE_CHARS = 500


def world_dir():
    """Return the activity log directory without creating it."""
    home = Path(os.environ.get("TAFWID_HOME") or Path.home() / ".tafwid").expanduser()
    return home / "state" / "world"


def _ensure_dir():
    path = world_dir()
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def _marker():
    return world_dir() / "enabled"


def _events_file(now=None):
    """Return the event file for the local calendar date of now."""
    return world_dir() / time.strftime("events-%Y-%m-%d.jsonl", time.localtime(now))


def enabled():
    return _marker().is_file()


def enable():
    path = _ensure_dir()
    descriptor = os.open(path / "enabled", os.O_WRONLY | os.O_CREAT, 0o600)
    os.close(descriptor)
    return status()


def disable():
    try:
        _marker().unlink()
    except FileNotFoundError:
        pass
    return status()


def _count_lines(path):
    try:
        with open(path, "rb") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def status():
    return {"enabled": enabled(), "dir": str(world_dir()),
            "today_events": _count_lines(_events_file())}


def _salt():
    """Return the 32-byte salt, creating it atomically on first use.

    The salt is written to a private temp file and linked into place, so a
    concurrent reader never sees a partial file; the link winner's bytes are
    read back by everyone. A short file (damaged or foreign) is waited on
    briefly and then replaced; a key shorter than 32 bytes is never used.
    """
    directory = _ensure_dir()
    path = directory / "salt"
    try:
        salt = path.read_bytes()
        if len(salt) == SALT_BYTES:
            return salt
    except OSError:
        pass
    import tempfile  # lazy: only first use and repair need it
    descriptor, temp = tempfile.mkstemp(prefix=".salt-", dir=directory)
    try:
        try:
            os.write(descriptor, os.urandom(SALT_BYTES))
        finally:
            os.close(descriptor)
        try:
            os.link(temp, path)
        except FileExistsError:
            pass
        for attempt in range(20):
            salt = path.read_bytes()
            if len(salt) == SALT_BYTES:
                return salt
            time.sleep(0.01)
        os.replace(temp, path)
        return path.read_bytes()
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def hash_id(raw):
    """Return a stable 16-hex-character pseudonym for a raw id."""
    return hmac.new(_salt(), str(raw).encode(), hashlib.sha256).hexdigest()[:16]


def append_event(event):
    """Append one JSON line with version and time; a single write never interleaves."""
    now = time.time()
    line = json.dumps({"v": EVENT_VERSION, "t": now, **event}, separators=(",", ":")) + "\n"
    _ensure_dir()
    descriptor = os.open(_events_file(now), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(descriptor, line.encode())
    finally:
        os.close(descriptor)


def prune(now):
    """Delete event files last modified more than 7 days before now."""
    for path in world_dir().glob("events-*.jsonl"):
        try:
            if now - path.stat().st_mtime > RETENTION_SECONDS:
                path.unlink()
        except OSError:
            pass


def log_error(msg):
    """Append a timestamped line to hook-errors.log, keeping the newest 100.

    This is the last-resort handler for hook failures, so it never raises.
    Messages are capped at 500 characters. Each writer uses its own temp file.
    """
    try:
        import tempfile  # lazy: error logging is rare
        path = _ensure_dir() / "hook-errors.log"
        entry = "%s %s" % (time.strftime("%Y-%m-%dT%H:%M:%S"),
                           " ".join(str(msg).split())[:ERROR_MESSAGE_CHARS])
        try:
            lines = path.read_bytes().decode("utf-8", "replace").splitlines()
        except OSError:
            lines = []
        lines = (lines + [entry])[-ERROR_LOG_LINES:]
        descriptor, temp = tempfile.mkstemp(prefix=".errors-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
            os.replace(temp, path)
        except BaseException:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise
    except Exception:
        pass


def main():
    import argparse  # lazy: only the command line needs it
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("on", "off", "status"))
    args = parser.parse_args()
    result = {"on": enable, "off": disable, "status": status}[args.command]()
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
