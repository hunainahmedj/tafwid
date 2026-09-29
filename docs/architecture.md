# Architecture

Tafwid has one skill entry point: `delegate`. It uses the Python
runtime under `plugins/tafwid/skills/delegate/scripts`.

| Module | Responsibility |
| --- | --- |
| `session.py` | Read or change the current task's delegation switch and check the selected harness before enabling it. |
| `delegate.py` | Validate a brief, launch or resume a worker, and save a compact result. |
| `harnesses.py` and `claude_code.py` | Isolate harness readiness, command construction and result handling. Claude Code is the only supported harness. |
| `wait.py` | Wait for selected runs in the current task. |
| `completion_hook.py` | Arm a one-time wait at the next Codex Stop event. |
| `run_state.py` | Keep small run records and a launcher heartbeat for waiting. |
| `settings.py` | Validate saved model routing and permission policy. |
| `routing.py` | Resolve task types, tiers and explicit selections. |
| `paths.py` | Resolve private state paths and write JSON atomically. |

The launcher sends the task brief and a common reporting contract to Claude.
Workers return a status (`completed` or `blocked`) and a report. The launcher also
reports errors, timeouts, interruptions and results needing review. Codex owns
acceptance; a successful process exit alone is insufficient.

Each run gets a new private output directory containing the brief, request,
input, raw result, stderr, report and summary. Resumes preserve the Claude session
and require the same Codex task and workspace. Model selection is retained unless
explicitly overridden; permissions are checked again on every launch.

The waiter observes small local run records without model calls. It can return
when a worker finishes, including one that completed before the wait started.
It does not launch, cancel or extend workers. A stale heartbeat means the launcher
stopped reporting, not proof that Claude stopped.

The packaged Stop, Interrupt and UserPromptSubmit hooks are declared in
`plugins/tafwid/hooks/hooks.json`. After Codex trusts them, `completion_hook.py arm`
records selected run IDs for this task's next Stop event. Codex may continue useful
work before ending its turn. At Stop, the hook checks for that one-time record: if
none exists, it exits immediately; if present, it waits locally until a selected
worker finishes or needs attention, or until its bounded safety limit, then
resumes Codex. Interrupt and new-prompt
events clear an abandoned record. The hook does not launch a worker or make model
requests. If hook trust is unavailable, `wait.py` remains the fallback.

Task switches, settings and run records live under the current Codex home's state
directory, normally `tafwid/state`. Existing legacy state is reused; conflicting
state roots cause an error.
The runtime does not inspect Codex conversations or account usage.

Tests use temporary state directories and fake Claude processes. No real worker
or installed-plugin changes are required for ordinary verification.
