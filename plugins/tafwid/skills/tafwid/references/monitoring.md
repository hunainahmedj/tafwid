# Completion waiting

The launcher is already quiet while Claude runs and prints a compact result when it exits. Its separate registry heartbeat keeps the dashboard current. Waiting should not require GPT to read those heartbeats or worker transcripts.

## One worker

Keep the launcher process handle. If independent work is available, do it; otherwise wait for completion with the host tool. In this Codex runtime, `exec_command` can initially wait up to 30 seconds and `write_stdin` can then wait 60 seconds with empty `chars`. Both return early on process completion. Do not issue repeated one-second waits or short `functions.wait` calls around a longer-running tool: give each tool its appropriate wait budget, capped at 60 seconds, while respecting user-input interruptions and required progress updates.

## Several workers, or a recovered run

Use the exact invocation directories recorded at dispatch, not all historical runs or a copied conversation ID:

```bash
python3 "${TAFWID_SKILL_DIR}/scripts/wait.py" \
  --run-dir /absolute/path/to/implementation-run \
  --run-dir /absolute/path/to/independent-review-run \
  --timeout 60
```

The helper watches existing registry entries inside the current Codex task. It performs small local checks without model calls and returns within about a second of detecting a terminal result. It also tolerates registration happening after the wait starts. It neither launches nor interrupts a worker, changes settings, nor renews the worker timeout.

Keep the helper's own process handle if the host yields before it finishes; wait for that same helper rather than starting another copy. When `functions.exec` wraps a 60-second host wait, give the wrapper and any `functions.wait` call up to 60 seconds too. Do not turn one long wait into repeated short model-visible waits.

Interpret the returned JSON:

- `event: ready`: inspect every item in `ready`. Each retains the worker's actual outcome (`completed`, `native_required`, `blocked`, `needs_review`, `error`, `timeout`, or `interrupted`), a short report excerpt, and available artifact paths. `completed` still requires acceptance review. Handle a native handoff through the normal procedure; report quota/authentication errors without retrying automatically.
- `event: waiting`: no selected worker finished within the wait window. Do useful independent work or wait again at the same long interval. This is not a worker timeout or evidence of a hang.
- `event: attention`, or a nonempty `errors` array: monitoring could not verify a selected run. Inspect its original launcher handle and artifacts. A startup/auth failure can occur before registration. Do not keep waiting indefinitely or launch a replacement merely because no record exists.

Continue waiting only for `pending_dirs`; this avoids repeatedly delivering a result already handled. Each resume has a new output directory and must be added explicitly. A zero-second snapshot is for an explicit status request or diagnosis, not a monitoring loop. The helper's exit code zero means observation succeeded; worker success comes from each item's `status`.

If a record says the launcher stopped reporting, its heartbeat was lost. That does not prove the underlying Claude process stopped. Investigate before resuming or starting another writer. The helper can return cached reports after temporary artifacts disappear, but a missing handoff file requires recovering the exact handoff before acting.

There is no background subscription that can wake an idle Codex turn here. Keep the active turn waiting, or use a separately authorized scheduling mechanism if the user asks to check back later. Do not create a supervisor GPT agent, send messages to this or another task, or create a recurring automation just to implement worker monitoring.
