#!/usr/bin/env python3
"""Wait quietly for any selected Claude run in the current Codex task."""
import argparse
import json
import math
from pathlib import Path
import sys
import time

import session
import worker_registry as registry


def completion(record):
    """Return only enough evidence to choose the next action, not a transcript."""
    out = Path(record["output_dir"])
    report = registry.read_document(out, "report.md") or record.get("documents", {}).get("report", "")
    return {
        "run_id": record["id"], "output_dir": str(out),
        "title": record.get("title"), "status": record["status"],
        "session_id": record.get("session_id"), "model_selection": record.get("model_selection"),
        "status_note": record.get("status_note"),
        "permission_denials": record.get("permission_denials"),
        "report_excerpt": report[:1000], "report_truncated": len(report) > 1000,
        "report_file": str(out / "report.md") if (out / "report.md").is_file() else None,
        "handoff_file": str(out / "handoff.json") if (out / "handoff.json").is_file() else None,
    }


def wait_for_runs(run_dirs, timeout=60):
    if not math.isfinite(timeout) or not 0 <= timeout <= 60:
        raise ValueError("--timeout must be between 0 and 60 seconds")
    task_id = session.current_task_id()
    if not task_id:
        raise ValueError("No Codex task identity; use the original launcher process handle")
    targets = list(dict.fromkeys(str(Path(path).expanduser().resolve()) for path in run_dirs))
    if not targets:
        raise ValueError("At least one --run-dir is required")
    started = time.monotonic()
    deadline = started + timeout
    known = {}
    while True:
        # Discover late registration after auth/startup. Once found, read only the
        # selected IDs; dashboard heartbeats and unrelated runs do not wake GPT.
        if len(known) < len(targets):
            for record in registry.list_runs(task_id):
                path = str(Path(record["output_dir"]).resolve())
                if path in targets and path not in known:
                    known[path] = record["id"]
        ready, pending, errors = [], [], []
        expired = time.monotonic() >= deadline
        for path in targets:
            if path not in known:
                if expired:
                    errors.append({"output_dir": path, "error":
                        "No registered run for this task. Inspect the original launcher handle for a startup error; do not relaunch automatically."})
                else:
                    pending.append({"output_dir": path, "status": "awaiting_registration"})
                continue
            try:
                record = registry.load_record(known[path])
                if record.get("codex_thread_id") != task_id or str(Path(record["output_dir"]).resolve()) != path:
                    raise ValueError("Run ownership or output directory changed")
                if record.get("status") in registry.ACTIVE:
                    pending.append({"run_id": record["id"], "output_dir": path, "status": record["status"]})
                else:
                    ready.append(completion(record))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append({"output_dir": path, "error": str(exc)})
        if ready or errors or expired:
            return {"event": "ready" if ready else "attention" if errors else "waiting",
                    "ready": ready, "pending": pending, "errors": errors,
                    "pending_dirs": [item["output_dir"] for item in pending],
                    "waited_seconds": round(time.monotonic() - started, 3)}
        # Local I/O polling consumes no model calls. Finish within one second of
        # a terminal registry update, while keeping every host wait bounded.
        time.sleep(min(1, max(0, deadline - time.monotonic())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, action="append", required=True,
                        help="Exact invocation output directory; repeat to wait for any of several runs")
    parser.add_argument("--timeout", type=float, default=60,
                        help="Wait up to 0–60 seconds; 0 returns one snapshot (default: 60)")
    args = parser.parse_args()
    try:
        print(json.dumps(wait_for_runs(args.run_dir, args.timeout), ensure_ascii=False))
        # The waiter succeeded even if a worker failed: inspect each ready status.
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"event": "error", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
