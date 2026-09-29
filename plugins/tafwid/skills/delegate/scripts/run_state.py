"""Private run status and heartbeat used by the launcher and completion waiter."""
import hashlib
import hmac
import json
import os
import secrets
import sys
import threading
import time
import uuid
import paths

ACTIVE = {"starting", "running"}


def state_root():
    return paths.state_root()


def effective(record):
    record = dict(record)
    if record.get("status") in ACTIVE and time.time() - record.get("updated_at", 0) > 15:
        record["status"] = "interrupted"
        record["status_note"] = "The launcher stopped reporting. Inspect the worker artifacts before retrying."
        record["ended_at"] = record.get("updated_at")
    return record


def load_record(run_id):
    if str(uuid.UUID(run_id)) != run_id:
        raise ValueError("Invalid run ID")
    path = state_root() / "workers" / (run_id + ".json")
    if path.is_symlink():
        raise ValueError("Invalid run record")
    record = json.loads(path.read_text())
    if not isinstance(record, dict) or record.get("id") != run_id or not isinstance(record.get("output_dir"), str):
        raise ValueError("Invalid run record")
    return effective(record)


def list_runs(thread_id=None):
    rows = []
    for path in (state_root() / "workers").glob("*.json"):
        try:
            row = load_record(path.stem)
            if thread_id and row.get("codex_thread_id") != thread_id:
                continue
            rows.append(row)
        except (OSError, ValueError, TypeError):
            continue
    return rows


def can_watch(record, key):
    """Check a run-specific observation key without granting worker control.

    Only the key's SHA-256 digest is stored on disk. Older records without a
    digest remain observable only by their owning task.
    """
    expected = record.get("watch_key_hash")
    if not isinstance(expected, str) or len(expected) != 64 or not isinstance(key, str) or not key:
        return False
    actual = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return hmac.compare_digest(expected.encode("utf-8"), actual.encode("ascii"))


class Tracker:
    def __init__(self, out, task_id, session_id, title, selection, cwd, permissions=None,
                 backend="claude", connection_id="claude:default"):
        """Create a run and a private observation key for an assigned monitor."""
        self.id = str(uuid.uuid4())
        self.watch_key = secrets.token_hex(32)
        self.path = state_root() / "workers" / (self.id + ".json")
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.warned = False
        now = time.time()
        self.record = {"version": 1, "id": self.id, "title": title, "status": "starting", "backend": backend,
                       "connection_id": connection_id,
                       "session_id": session_id, "codex_thread_id": task_id,
                       "watch_key_hash": hashlib.sha256(self.watch_key.encode("ascii")).hexdigest(),
                       "model_selection": selection, "models_used": [], "cwd": cwd,
                       "permissions": permissions,
                       "output_dir": str(out), "launcher_pid": os.getpid(),
                       "started_at": now, "updated_at": now, "ended_at": None}

    def save(self):
        self.record["updated_at"] = time.time()
        try:
            paths.atomic_json(self.path, self.record)
        except OSError as exc:
            # Monitoring must never change the success/failure of a Claude task.
            if not self.warned:
                print("Run status recording unavailable: " + str(exc), file=sys.stderr)
                self.warned = True

    def heartbeat(self):
        while not self.stop.wait(2):
            with self.lock:
                self.save()

    def __enter__(self):
        with self.lock:
            self.save()
        self.thread = threading.Thread(target=self.heartbeat, daemon=True)
        self.thread.start()
        return self

    def running(self, pid):
        with self.lock:
            self.record.update(status="running", worker_pid=pid)
            self.save()

    def finish(self, summary):
        with self.lock:
            self.record.update({key: summary[key] for key in
                ("status", "session_id", "models_used", "permission_denials", "claude_exit_code", "permissions",
                 "report_excerpt", "report_truncated") if key in summary})
            self.record["ended_at"] = time.time()
            self.save()

    def __exit__(self, exc_type, exc, traceback):
        self.stop.set()
        self.thread.join(timeout=3)
        if self.record["status"] in ACTIVE:
            self.record["status_note"] = str(exc) if exc else "Launcher exited without a result."
            self.finish({"status": "interrupted" if exc_type is KeyboardInterrupt else "error"})
