# From claude-delegate to Tafwid

Finish or pause orchestration before switching the controller to a new skill.
Already-running Claude processes continue with their original instructions.

1. Back up your personal skill and `$CODEX_HOME/state/claude-delegate` outside any
   public repository. Do not publish either state directory or cached run logs.
2. Install Tafwid as described in the README. Installation does not remove the
   old personal skill or rewrite global instructions.
3. In global/project `AGENTS.md`, replace the old skill name with `tafwid:delegate` and
   fixed `~/.codex/skills/claude-delegate/scripts/...` launch paths with commands
   resolved from the installed Tafwid skill directory. Do not hard-code a plugin
   cache version. Load the delegate entry point before checking the task-local switch.
4. Start a new Codex task and invoke `$tafwid:delegate`. New tasks still default to off;
   an existing task keeps its switch because its task ID is unchanged.
5. Retire the old skill only after verifying status, settings and history. Keep
   legacy state in place. Tafwid reuses it rather than copying it.

State lookup is shared by the switch, settings, launcher and dashboard:

- Neither directory exists: use `state/tafwid`.
- Only `state/tafwid` exists: use it.
- Only `state/claude-delegate` exists: reuse it without rewriting records.
- Both exist: stop with a conflict error. Back up and reconcile the directories;
  Tafwid will not guess which permissions, task switches or history should win.

An already-running dashboard retains its original assets. Finish with that
instance and stop its recorded server process, or restart the machine, before
starting the Tafwid dashboard to see the new branding. Merely installing the
plugin does not stop the service or revoke its current local access token.

Do not move a live state directory or remove active run artifacts. A later
release may provide an explicit migration command; v0.1 deliberately reuses the
legacy state instead of silently relocating it.

## From Tafwid 0.1

Upgrade the marketplace, reinstall `tafwid@tafwid`, and start a new task.
The former `$tafwid:tafwid` entry becomes `$tafwid:delegate`; use
`$tafwid:dashboard` and `$tafwid:settings` for their dedicated tasks. The shared
runtime moves from `skills/tafwid` to `skills/delegate`; resolve paths from the
loaded delegate skill rather than retaining an old cache path. Existing task
state and history do not move. Already-running workers retain their instructions.
