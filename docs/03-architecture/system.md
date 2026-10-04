# Architecture

Tafwid has two skill entry points: `delegate` and `account`. They use the Python
runtime under `plugins/tafwid/skills/delegate/scripts`. The same plugin directory
serves a Codex or a Claude Code coordinator; `host.py` is the only module that reads
which one is running. Both hosts' variables present at once is an error resolved
with `TAFWID_HOST`.

| Module | Responsibility |
| --- | --- |
| `host.py` | Detect the coordinator (Codex or Claude Code) and its task; scrub worker environments; record Claude Code hook activity. |
| `session.py` and `connections.py` | Read or change the current task's connection pool and resolve exact destinations. |
| `account.py` and `accounts.py` | Open Codex sign-in in private GPT homes and check login method. |
| `delegate.py` | Validate a brief, launch or resume a worker, and save a compact result. |
| `harnesses.py`, `claude_code.py`, and `codex_cli.py` | Check readiness and handle Claude or GPT worker commands and results. |
| `wait.py` | Wait for selected runs in the current task. |
| `completion_hook.py` | Arm a one-time wait at the coordinator's next Stop event. |
| `run_state.py` | Keep small run records and a launcher heartbeat for waiting. |
| `settings.py` | Validate saved model routing and permission policy. |
| `routing.py` | Resolve task types, tiers and explicit selections. |
| `paths.py` | Resolve private state paths and write JSON atomically. |
| `migration.py` | Move a legacy state directory to the host-neutral home on request. |
| `world.py` and `world_hook.py` | Switch the opt-in activity log and turn one hook payload into one sanitised event line. |

The launcher sends the task brief and a reporting contract to the selected worker.
Workers return a status (`completed` or `blocked`) and a report. The launcher also
reports errors, timeouts, interruptions and results needing review. The coordinator owns
acceptance; a successful process exit alone is insufficient.

Each run gets a new private output directory containing the brief, request,
input, raw result, stderr, report and summary. Resumes preserve the worker session
and exact connection and require the same coordinator task and workspace. Model selection is retained unless
explicitly overridden; permissions are checked again on every launch.

The waiter observes small local run records without model calls. It can return
when a worker finishes, including one that completed before the wait started.
It does not launch, cancel or extend workers. A stale heartbeat means the launcher
stopped reporting, not proof that the worker stopped.

The packaged hooks are declared in `plugins/tafwid/hooks/hooks.json`, which both
hosts load. Each command runs through `bash -c` and accepts either host's
plugin-root variable. The completion hooks are on Stop, Interrupt and
UserPromptSubmit. `completion_hook.py arm`
records selected run IDs for this task's next Stop event, once hooks are usable:
on Codex after the user trusts them, and on Claude Code once the prompt hook has
recorded a hooks-seen marker for the session. The coordinator may continue useful
work before ending its turn. At Stop, the hook checks for that one-time record: if
none exists, it exits immediately; if present, it waits locally until a selected
worker finishes or needs attention, or until its bounded safety limit, then
resumes the coordinator. New-prompt events, and Interrupt on Codex, clear an
abandoned record. The hook does not launch a worker or make model requests. If
hooks are unavailable, `wait.py` remains the fallback.

On Claude Code the hooks-seen marker also records the session's permission mode,
which is how the `inherit` permission policy learns that the coordinator has full
access. Codex reports that through its permission profile. A marker older than
24 hours proves neither. Hook actions always exit successfully, so a state or
input error can never reject a prompt or keep the coordinator from stopping.

The same file registers ten asynchronous observer hooks (SessionStart,
UserPromptSubmit, PreToolUse, PostToolUse, PermissionRequest, SubagentStart,
SubagentStop, Stop, SessionEnd and Notification) for the
[activity log](../04-modules/activity-log.md). Each is gated by the marker file
`${TAFWID_HOME:-$HOME/.tafwid}/state/world/enabled` and exits at once without
it. They print nothing, never block, and do not interact with the completion
hooks. The boundary is one-way: the plugin only writes the log under
`state/world/`, a local reader such as the dashboard prototype only reads it,
and the plugin sends nothing off the machine.

Task switches, settings and run records live in a host-neutral state directory,
`~/.tafwid/state` (`TAFWID_HOME` overrides `~/.tafwid`), shared by both
coordinators. A single existing directory under the Codex home is used in place
until `settings.py migrate` moves it; conflicting state roots cause an error.
Run records name their owner as `coordinator_task_id` with `coordinator_host`;
the older `codex_thread_id` field is still read.
Named GPT homes live below the private `accounts` state directory. Each has
file-based CLI credentials selected through its own `CODEX_HOME`. Tafwid checks
the login method without opening credentials. The task pool stores immutable
connection IDs, while run records keep the chosen ID and backend. Worker
processes start without the coordinator's identity variables.
The runtime does not inspect coordinator conversations or account usage.

Tests use temporary state directories and fake Claude and Codex processes. No real worker
or installed-plugin changes are required for ordinary verification.


## Dashboard prototype boundary

The [dashboard module](../04-modules/dashboard.md) describes the prototype,
which lives outside the plugin under `prototypes/`. Its local bridge reads
the activity log and the run records under `state/workers/` without writing
anything, and serves a folded view on `127.0.0.1`
([TAF-3](../01-project/backlog.md)); the
[prototype README](../../prototypes/agent-world/README.md#live-activity)
explains optional sharing on the user's own tailnet and what that exposes.
Nothing is served publicly. The prototypes never call the runtime, launch
workers or make model requests.
