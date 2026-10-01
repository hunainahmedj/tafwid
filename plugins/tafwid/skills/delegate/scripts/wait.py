#!/usr/bin/env python3
"""Observe selected worker runs without model calls.

Supply --run-id once per run and an optional --timeout (0–300 seconds).
Wait up to five minutes by default; return early on completion or an error.
Other tasks need --watch-key RUN_ID=KEY from the launcher's started event.
Legacy --run-dir selection is also supported; do not mix the two selectors.
Observe registry state only; this script does not launch or cancel workers.
"""
import argparse
import json
import math
from pathlib import Path
import sys
import time
import uuid

import session
import run_state as registry

MAX_WAIT_SECONDS = 300


def completion(record):
    """Return only enough evidence to choose the next action, not a transcript."""
    out = Path(record["output_dir"])
    report_path = out / "report.md"
    report = record.get("report_excerpt", "")
    try:
        with report_path.open(encoding="utf-8", errors="replace") as file:
            report = file.read(1001)
    except OSError:
        pass
    return {
        "run_id": record["id"], "output_dir": str(out),
        "title": record.get("title"), "status": record["status"],
        "backend": record.get("backend", "claude"),
        "connection_id": record.get("connection_id", "claude:default"),
        "session_id": record.get("session_id"), "model_selection": record.get("model_selection"),
        "status_note": record.get("status_note"),
        "permission_denials": record.get("permission_denials"),
        "report_excerpt": report[:1000], "report_truncated": len(report) > 1000,
        "report_file": str(out / "report.md") if (out / "report.md").is_file() else None,
    }


def wait_for_runs(run_dirs=(), timeout=MAX_WAIT_SECONDS, *, run_ids=(), watch_keys=None):
    """Wait for any selected run to finish, without launching or stopping workers.

    Prefer run_ids for direct registry lookup. Legacy run_dirs require discovery
    by output directory. Selectors cannot be mixed. A foreign run requires its
    observation key in watch_keys, mapped by run ID. Keys grant no worker control.
    Return compact evidence and identifiers still pending, without the keys.
    """
    if not math.isfinite(timeout) or not 0 <= timeout <= MAX_WAIT_SECONDS:
        raise ValueError(f"--timeout must be between 0 and {MAX_WAIT_SECONDS} seconds")
    task_id = session.current_task_id()
    if not task_id:
        raise ValueError("No Codex task identity; use the original launcher process handle")
    if run_dirs and run_ids:
        raise ValueError("Use --run-id or --run-dir, not both")
    by_id = bool(run_ids)
    if by_id:
        for run_id in run_ids:
            try:
                if str(uuid.UUID(run_id)) != run_id:
                    raise ValueError("Invalid run ID")
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError("Invalid run ID; use the UUID reported by delegate.py") from exc
        targets = list(dict.fromkeys(run_ids))
    else:
        targets = list(dict.fromkeys(str(Path(path).expanduser().resolve()) for path in run_dirs))
    if not targets:
        raise ValueError("At least one --run-id or --run-dir is required")
    watch_keys = {} if watch_keys is None else watch_keys
    if not isinstance(watch_keys, dict):
        raise ValueError("Monitoring keys must be mapped by run ID")
    if watch_keys and not by_id:
        raise ValueError("--watch-key requires --run-id, not --run-dir")
    if any(run_id not in targets or not isinstance(key, str) or not key.strip()
           for run_id, key in watch_keys.items()):
        raise ValueError("Each monitoring key must be nonempty and match a selected run ID")
    started = time.monotonic()
    deadline = started + timeout
    known = {target: target for target in targets} if by_id else {}
    while True:
        # Discover late registration after auth/startup. Once found, read only the
        # selected IDs; heartbeats and unrelated runs do not wake GPT.
        if not by_id and len(known) < len(targets):
            for record in registry.list_runs(task_id):
                path = str(Path(record["output_dir"]).resolve())
                if path in targets and path not in known:
                    known[path] = record["id"]
        ready, pending, errors = [], [], []
        expired = time.monotonic() >= deadline
        for target in targets:
            identity = {"run_id" if by_id else "output_dir": target}
            try:
                record = None
                if target in known:
                    try:
                        record = registry.load_record(known[target])
                    except FileNotFoundError:
                        if not by_id:
                            raise
                if record is None:
                    if expired:
                        errors.append({**identity, "error":
                            "No registered run for this task. Inspect the original launcher handle for a startup error; do not relaunch automatically."})
                    else:
                        pending.append({**identity, "status": "awaiting_registration"})
                    continue
                path = str(Path(record["output_dir"]).resolve())
                if record.get("codex_thread_id") != task_id and not registry.can_watch(record, watch_keys.get(record["id"])):
                    raise ValueError("Run belongs to another task; its monitoring key is required")
                if not by_id and path != target:
                    raise ValueError("Run output directory changed")
                if record.get("status") in registry.ACTIVE:
                    pending.append({"run_id": record["id"], "output_dir": path, "status": record["status"]})
                else:
                    ready.append(completion(record))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append({**identity, "error": str(exc)})
        if ready or errors or expired:
            return {"event": "ready" if ready else "attention" if errors else "waiting",
                    "ready": ready, "pending": pending, "errors": errors,
                    "pending_run_ids": [item["run_id"] for item in pending if "run_id" in item],
                    "pending_dirs": [item["output_dir"] for item in pending if "output_dir" in item],
                    "waited_seconds": round(time.monotonic() - started, 3)}
        # Local I/O polling consumes no model calls. Finish within one second of
        # a terminal registry update, while keeping every host wait bounded.
        time.sleep(min(1, max(0, deadline - time.monotonic())))


def main():
    """Parse wait options and report ready, waiting, attention or error as JSON."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 scripts/wait.py --run-id <run-uuid> --timeout 300
  python3 scripts/wait.py --run-id <first-run-uuid> --run-id <second-run-uuid>
  python3 scripts/wait.py --run-id <run-uuid> --watch-key <run-uuid>=<watch-key>
  python3 scripts/wait.py --run-dir /private/run-1  # Legacy directory selection

Uses the current Codex chat identity from the environment. A different task needs
that run's watch_key from delegate.py's started event. Repeat --watch-key RUN_ID=KEY
for multiple foreign runs. Keys allow observation only and are never returned.
Without a key, only the current task's runs can be observed. Legacy directory
selection is owner-only. delegate.py emits the started event while the worker is active.
JSON events: ready (inspect worker status), waiting (window elapsed), or attention
(inspect errors). Continue with pending_run_ids to avoid repeating handled results.
pending_dirs remains available for legacy callers. Do not mix IDs and directories.
Exit 0 means observation succeeded, not that the worker passed acceptance.
Invalid arguments or observation exceptions exit 2. --help makes no state changes.
""",
    )
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--run-id", action="append",
                          help="Run UUID from delegate.py; repeat to wait for any of several runs")
    selector.add_argument("--run-dir", type=Path, action="append",
                          help="Legacy: exact invocation output directory; repeat for several runs")
    parser.add_argument("--watch-key", action="append", default=[], metavar="RUN_ID=KEY",
                        help="Read-only monitoring grant from delegate.py for a selected run; repeatable")
    parser.add_argument("--timeout", type=float, default=MAX_WAIT_SECONDS,
                        help=f"Wait up to 0–{MAX_WAIT_SECONDS} seconds; 0 returns one snapshot (default: {MAX_WAIT_SECONDS})")
    args = parser.parse_args()
    try:
        watch_keys = {}
        for value in args.watch_key:
            run_id, separator, key = value.partition("=")
            if not separator or not key.strip() or run_id in watch_keys:
                raise ValueError("Use --watch-key RUN_ID=KEY once per selected run")
            watch_keys[run_id] = key
        print(json.dumps(wait_for_runs(args.run_dir or (), args.timeout,
                                       run_ids=args.run_id or (), watch_keys=watch_keys), ensure_ascii=False))
        # The waiter succeeded even if a worker failed: inspect each ready status.
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"event": "error", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
