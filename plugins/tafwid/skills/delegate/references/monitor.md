# Monitor delegated runs

Watch only the runs assigned to you. Do not review code, run tests, read worker
transcripts, or send unchanged status updates.

Use the supplied absolute path to `wait.py`. Pass each worker's `run_id` with
`--run-id` and, when watching another task's run, its `run_id=watch_key` with
`--watch-key`. Run the script with `--timeout 300`.

In Codex, use one `functions.exec` call to start `wait.py` with `exec_command`
and wait on its process handle with `write_stdin`. If `wait.py` returns `waiting`,
repeat inside that same call using only `pending_run_ids`. Request a five-minute
yield for the enclosing call and each process wait; use the host's longest
supported wait if shorter. Do not start another `wait.py` process while the
first is running or poll its handle every 30 seconds.

When `wait.py` returns, notify the coordinator of completed runs or errors with
their run IDs, statuses, and report paths. If it returns `waiting`, or other runs
remain pending, run it again with only `pending_run_ids` and their matching keys.
Keep monitoring until no assigned runs remain pending. Do not send monitoring
keys back in notifications.
