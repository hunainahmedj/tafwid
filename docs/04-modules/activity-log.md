# Activity log

## What is it?

An optional diary of what your agents are doing, kept on your own machine.
When it is on, every Claude Code or Codex session writes a short line each
time something happens: a session starts, you send a prompt, an agent uses
a tool, a sub-agent starts or finishes, or a session waits for your
approval. Each line says what kind of thing happened, never the content.
The log is part of the released plugin and is off until you turn it on.

## Why was it built?

You should be able to see every agent at work, including the sub-agents a
coordinator starts, without paying for it in tokens. The log is written by
hooks, small commands the host runs in the background at each event. The
model never sees them, so they add no tokens or context. It works even
when Tafwid delegation is off, because the hosts start their own
sub-agents. [ADR-0008](../05-decisions/0008-opt-in-activity-log.md) records
why hooks were chosen over reading transcripts, polling the host, or a
skill the model calls.

## When is it used?

Only after you switch it on; the [README](../../README.md#local-activity-log)
gives the commands. From then on it records every Claude Code and Codex
session on the machine that has the plugin loaded (on Codex, once you have
approved Tafwid's new hooks). A local viewer reads the log. Today the only
viewer is the [agent world prototype](dashboard.md), which is not part of
the released plugin. Switching the log off stops new lines at once.

## How does it work?

### Switch

The switch is a marker file, `enabled`, in the log folder
`${TAFWID_HOME:-$HOME/.tafwid}/state/world/`. `world.py on` creates it (and
the folder, mode `0700`), `world.py off` removes it, and `world.py status`
prints JSON with `enabled`, `dir` and `today_events`. The log always uses
this host-neutral home, even when Tafwid's other state still lives in a
legacy Codex-home folder, so the shell test in each hook and the Python
code always agree.

### Hooks

`plugins/tafwid/hooks/hooks.json` registers one observer command for ten
events: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`,
`PermissionRequest`, `SubagentStart`, `SubagentStop`, `Stop`, `SessionEnd`
and Claude Code's `Notification`. Each entry is `async: true` with a 5 s
timeout. It first tests for the marker in `bash` and exits at once when it
is missing. Otherwise it runs `python3 -S world_hook.py`. `-S` skips site
packages to keep the hook near 30 ms, so the hook and its imports
(`world.py`, `host.py`) must stay standard-library only.
`scripts/check_package.py` accepts this exact command, and only in async
form, next to the completion-hook commands.

### Host trust

Claude Code runs plugin hooks without a trust step. Codex trusts hooks per
handler: `config.toml` keeps a `trusted_hash` under
`[hooks.state."tafwid@tafwid:hooks/hooks.json:<event>:<group>:<handler>"]`
for each one, and changing `hooks.json` asks for trust again. After an
install of, or upgrade to, 0.5.0, only the earlier completion handlers are
trusted. Non-interactive `codex exec` silently skips untrusted handlers, so
Codex sessions write no events and no error line. The user must approve the
new handlers once in an interactive `codex` session; the
[README](../../README.md#local-activity-log) states this as the required
step. Tafwid never edits the trust settings itself.

Codex runs the `SessionEnd` observer synchronously despite `async: true`,
with its timeout clamped to 3 s, and prints a warning. The hook takes about
30 ms, so this has no visible effect.

### Writing an event

`world_hook.py` reads one payload from stdin and appends at most one line.
It never prints, and it always exits 0. Any exception is reduced to one
line in `hook-errors.log` in the same folder, which keeps the newest 100
lines. On `SessionStart` it deletes event files last modified more than 7
days ago.

### Event line

Lines go to `events-YYYY-MM-DD.jsonl` (local date, mode `0600`), one JSON
object per line, written with a single append:

| Field | Meaning |
| --- | --- |
| `v` | Format version, `1` |
| `t` | Unix time in seconds |
| `host` | `claude` or `codex`, from `host.for_hook` (Claude Code exports the event's own session id) |
| `session` | Pseudonym of the host session id |
| `project` | Base name of the working folder only, at most 100 characters |
| `agent` | Pseudonym of the sub-agent id; `null` for the main session |
| `event` | `session`, `prompt`, `tool`, `permission`, `subagent-start`, `subagent-stop`, `stop`, `session-end` or `notification` |
| `phase` | `pre` or `post` for tool events, otherwise `null` |
| `agentType` | The host's agent type, at most 64 characters |
| `label` | Spawn description, one line, at most 80 characters; spawn events only |
| `action` | Coarse tool kind, below |
| `role` | Role from a `[role: <name>]` tag in the spawn description, which is then removed from the label |
| `status` | `waiting` (permission request or permission notification), `idle` (idle notification or `Stop`), or `done`, `error` or `interrupted` on `SubagentStop` |

Actions come from the tool name and the target's file extension:

| Action | Tools |
| --- | --- |
| `edit-code` | `Edit`, `Write`, `MultiEdit`, `NotebookEdit`, `apply_patch` |
| `edit-docs` | The same tools when every target ends in `.md`, `.mdx`, `.rst` or `.txt` |
| `read` | `Read`, `NotebookRead` |
| `search` | `Grep`, `Glob`, `LS` |
| `run-tests` | `Bash` whose command matches `pytest`, `vitest`, `playwright`, `npm test`, `npm run test`, `make test`, `cargo test` or `go test` |
| `run-command` | Other `Bash` |
| `web` | `WebFetch`, `WebSearch` |
| `spawn` | `Agent`, `Task`, `spawn_agent` |
| `other` | Anything else |

A line stays below 3,500 bytes; if a payload would exceed that, the label
is dropped first, then the agent type, then the project.

### Privacy

- **Pseudonyms:** `session` and `agent` are the first 16 hex characters of
  an HMAC-SHA256 of the raw id. The key is a private 32-byte random `salt`
  in the log folder, created atomically with mode `0600` on first use.
- **Never written:** prompt text, file contents, file paths beyond the
  project folder name, command text, tool input or output, transcript
  paths, and raw ids. The hook reads a command or patch only to choose the
  action, then discards it.
- **Local only:** the plugin sends nothing anywhere. A reader on the same
  machine reads the files; the plugin itself only counts today's lines for
  `world.py status`.

Tafwid's delegated runs are not hooked. A reader can take them from the
run records under `state/workers/`.

## Code location

| Repo / package | Paths |
| --- | --- |
| Tafwid | `plugins/tafwid/skills/delegate/scripts/world.py` (switch, hashing, append, prune, error log), `plugins/tafwid/skills/delegate/scripts/world_hook.py` (payload to event), `plugins/tafwid/hooks/hooks.json` (observer registrations), `scripts/check_package.py` (observer command rule), `plugins/tafwid/skills/delegate/tests/test_world.py`, `plugins/tafwid/skills/delegate/tests/test_world_hook.py`, `plugins/tafwid/skills/delegate/tests/fixtures/world/` (Claude Code and Codex payloads) |

## Decisions

- [ADR-0008 — An opt-in local activity log written by silent hooks](../05-decisions/0008-opt-in-activity-log.md)
- [ADR-0004 — Host adapter and host-neutral state](../05-decisions/0004-host-adapter-and-neutral-state.md)

## Tracker

[TAF-3](../01-project/backlog.md)

## Ownership

See [ownership](../06-admin/ownership.md).
