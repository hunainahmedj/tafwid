"""Private worker records shared by the launcher and read-only dashboard."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import uuid
import paths
import metrics

ACTIVE = {"starting", "running"}
DOCUMENTS = {"brief": "brief.md", "input": "input.txt", "report": "report.md", "stderr": "stderr.log"}
LIMIT = 65536


def state_root():
    return paths.state_root()


def atomic_json(path, data):
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


def read_document(out, filename):
    path = Path(out) / filename
    try:
        if path.is_symlink() or not path.is_file():
            return ""
        with path.open("rb") as file:
            size = path.stat().st_size
            if filename == "stderr.log" and size > LIMIT:
                file.seek(-LIMIT, 2)
            data = file.read(LIMIT).decode("utf-8", errors="replace")
        return data + ("\n\n[Display limited to 64 KiB; full artifact remains on disk.]" if size > LIMIT else "")
    except OSError:
        return ""


def documents(record):
    cached = record.get("documents", {})
    return {key: read_document(record["output_dir"], filename) or cached.get(key, "")
            for key, filename in DOCUMENTS.items()}


def effective(record):
    record = dict(record)
    if record.get("status") in ACTIVE and time.time() - record.get("updated_at", 0) > 15:
        record["status"] = "interrupted"
        record["status_note"] = "The launcher stopped reporting. Inspect the worker artifacts before retrying."
        record["ended_at"] = record.get("updated_at")
    return record


def load_record(run_id):
    # A browser supplies an opaque run ID, never a filesystem path.
    if str(uuid.UUID(run_id)) != run_id:
        raise ValueError("Invalid run ID")
    path = state_root() / "workers" / (run_id + ".json")
    if path.is_symlink():
        raise ValueError("Invalid run record")
    record = json.loads(path.read_text())
    if not isinstance(record, dict) or record.get("id") != run_id or not isinstance(record.get("output_dir"), str):
        raise ValueError("Invalid run record")
    record = effective(record)
    record['usage'] = metrics.for_record(record)
    return record


def conversation_titles(thread_ids):
    """Resolve only requested names from Codex's local append-only title index.

    A missing index or an incomplete last line must not hide worker history.
    This reads metadata only; conversation transcripts are never inspected.
    """
    names = {}
    wanted = set(thread_ids) - {None, ""}
    if not wanted:
        return {}
    try:
        with (state_root().parents[1] / "session_index.jsonl").open(encoding="utf-8") as file:
            for line in file:
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        continue
                    key, title = row.get("id"), row.get("thread_name")
                    if not isinstance(key, str) or key not in wanted or not isinstance(title, str) or not title.strip():
                        continue
                    stamp = row.get("updated_at")
                    stamp = stamp if isinstance(stamp, str) else ""
                    if key not in names or stamp >= names[key][0]:
                        names[key] = (stamp, title)
                except (ValueError, TypeError):
                    continue
    except (OSError, UnicodeError):
        pass
    return {key: item[1] for key, item in names.items()}


def list_runs(thread_id=None):
    rows = []
    for path in (state_root() / "workers").glob("*.json"):
        try:
            row = load_record(path.stem)
            if thread_id and row.get("codex_thread_id") != thread_id:
                continue
            row.pop("documents", None)
            row.pop("instruction_manifest", None)
            rows.append(row)
        except (OSError, ValueError, TypeError):
            continue
    titles = conversation_titles(row.get("codex_thread_id") for row in rows)
    for row in rows:
        row["conversation_title"] = titles.get(row.get("codex_thread_id"))
    return sorted(rows, key=lambda row: row.get("started_at", 0), reverse=True)


def details(run_id):
    row = load_record(run_id)
    row["documents"] = documents(row)
    row["conversation_title"] = conversation_titles([row.get("codex_thread_id")]).get(row.get("codex_thread_id"))
    history = []
    for candidate in list_runs(row.get("codex_thread_id")):
        same_session = (row.get("session_id") and candidate.get("session_id") == row["session_id"]
                        and candidate.get("backend", "claude") == row.get("backend", "claude")
                        and candidate.get("codex_thread_id") == row.get("codex_thread_id"))
        if candidate["id"] == run_id or same_session:
            try:
                item = load_record(candidate["id"])
                item["documents"] = documents(item)
                item["conversation_title"] = row["conversation_title"]
                history.append(item)
            except (OSError, ValueError, TypeError):
                continue
    row["runs"] = sorted(history, key=lambda item: (item.get("started_at", 0), item["id"]))
    return row


class Tracker:
    def __init__(self, out, task_id, session_id, title, selection, cwd, permissions=None,
                 instruction_manifest=None, backend="claude"):
        self.id = str(uuid.uuid4())
        self.path = state_root() / "workers" / (self.id + ".json")
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.warned = False
        now = time.time()
        self.record = {"version": 1, "id": self.id, "title": title, "status": "starting", "backend": backend,
                       "session_id": session_id, "codex_thread_id": task_id,
                       "model_selection": selection, "models_used": [], "cwd": cwd,
                       "permissions": permissions,
                       "output_dir": str(out), "launcher_pid": os.getpid(),
                       "started_at": now, "updated_at": now, "ended_at": None}
        if instruction_manifest is not None:
            self.record["instruction_manifest"] = instruction_manifest

    def save(self):
        self.record["updated_at"] = time.time()
        try:
            atomic_json(self.path, self.record)
        except OSError as exc:
            # Monitoring must never change the success/failure of a Claude task.
            if not self.warned:
                print("Dashboard recording unavailable: " + str(exc), file=sys.stderr)
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
                 "backend", "worker_exit_code", "usage", "usage_scope") if key in summary})
            self.record["ended_at"] = time.time()
            self.record["documents"] = documents(self.record)
            self.save()

    def __exit__(self, exc_type, exc, traceback):
        self.stop.set()
        self.thread.join(timeout=3)
        if self.record["status"] in ACTIVE:
            self.record["status_note"] = str(exc) if exc else "Launcher exited without a result."
            self.finish({"status": "interrupted" if exc_type is KeyboardInterrupt else "error"})


def import_run(out, title=None):
    """Import only a caller-specified previous run, idempotently."""
    out = Path(out).expanduser().resolve(strict=True)
    summary = json.loads((out / "summary.json").read_text())
    if not isinstance(summary, dict) or not summary.get("status") or not summary.get("session_id"):
        raise ValueError("Not a completed launcher artifact directory")
    if summary["status"] in ACTIVE:
        raise ValueError("Import completed runs only")
    run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(out)))
    end = (out / "summary.json").stat().st_mtime
    request = out / "request.json"
    selection = summary.get("model_selection") or {}
    # Older runs recorded the actual --model only in their argv.
    if not selection and request.exists():
        command = json.loads(request.read_text()).get("command", [])
        if "--model" in command:
            selection = {"requested_model": command[command.index("--model") + 1], "role": "worker"}
    record = {"version": 1, "id": run_id, "title": title or out.name, "status": summary["status"],
              "backend": summary.get("backend", "claude"),
              "session_id": summary["session_id"], "codex_thread_id": summary.get("codex_thread_id"),
              "model_selection": selection, "models_used": summary.get("models_used", []),
              "permissions": summary.get("permissions"),
              "cwd": summary.get("cwd", ""), "output_dir": str(out), "imported": True,
              "started_at": request.stat().st_mtime if request.exists() else end,
              "updated_at": end, "ended_at": end,
              "documents": {"report": summary.get("report_excerpt", "")}}
    record["documents"] = documents(record)
    atomic_json(state_root() / "workers" / (run_id + ".json"), record)
    return run_id
