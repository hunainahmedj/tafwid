# ADR-0008: An opt-in local activity log written by silent hooks

- Date: 2026-10-04
- Status: Accepted

## Context

The user wanted to see every agent they run, including each sub-agent, and
wanted it to cost almost no tokens. It also had to work with Tafwid
delegation switched off, because Claude Code and Codex both start their own
sub-agents. [ADR-0005](0005-open-agent-world.md) kept the agent world on
sample data and left live data to [TAF-3](../01-project/backlog.md). This
decision records where live data comes from.

Both hosts can run plugin hooks for session, prompt, tool, permission and
sub-agent events. A hook can run in the background (asynchronously) without
printing anything, so the model never sees it. The data that passes through
these hooks is private: prompts, file paths, commands and session ids.

## Options considered

- **Read the hosts' transcripts:** rich detail, but every transcript holds
  full prompts and output. The formats are private to each host and can
  change without notice. Every reader would have to clean the data itself.
- **Poll the host:** ask each running Claude Code or Codex for its state.
  Neither host offers this for ordinary sessions. Codex's app-server event
  stream only exists when Codex runs as a daemon.
- **A model-side skill:** the coordinator reports its agents through a
  skill. This costs tokens and context on every turn and only works when
  the model remembers to call it.
- **Silent async hooks that write a cleaned local log:** no tokens and no
  model involvement. The plugin cleans the data before it touches disk.
  Each host needs one more set of hooks, and Codex asks the user to trust
  them again.

## Decision

The plugin ships asynchronous, silent observer hooks that append a
sanitised event log on the user's machine. The log is off by default. A
marker file switches it on and off, and each hook exits at once when the
marker is missing. The [activity log module](../04-modules/activity-log.md)
describes the behaviour; the design is in the
[live agent world spec](../superpowers/specs/2026-10-03-live-agent-world-design.md).

The cleaning rules are part of the decision:

- **Ids:** session and agent ids are replaced by HMAC-SHA256 pseudonyms,
  keyed by a private random salt, so raw ids never reach the log.
- **Labels:** only the spawn description is kept, as one line of at most
  80 characters. Prompts, commands, file contents, paths beyond the project
  folder name, and tool output are never written.
- **Permissions:** files are `0600` and the folder is `0700`.
- **Retention:** event files older than 7 days are deleted.

The plugin writes the log and readers only read it. Nothing in the log
refers to the dashboard prototype, and the plugin sends nothing off the
machine.

## Consequences

- **Zero token overhead:** the model never sees the hooks or the log.
- **Codex re-trust:** Codex trusts hooks per handler, and changing
  `hooks.json` makes it ask again. Until the user approves the new
  observer handlers in an interactive `codex` session, non-interactive
  `codex exec` skips them silently and Codex activity is not logged. The
  [README](../../README.md#local-activity-log) makes approval the required
  step after install or upgrade.
- **Hook time:** with the log on, each hook takes about 30 ms; with it off,
  only a shell test runs. The [changelog](../../CHANGELOG.md) for 0.5.0
  holds the measurement. The hooks are asynchronous, so neither time delays
  a turn. To stay inside the budget the hook starts Python with `-S`, so it
  and everything it imports must stay standard-library only.
- **Readers own presentation.** A reader such as the
  [dashboard prototype](../04-modules/dashboard.md) folds the events into
  agents. The released plugin does not include any reader.
- **Delegated runs** are not hooked separately. Readers take them from
  Tafwid's existing run records.
