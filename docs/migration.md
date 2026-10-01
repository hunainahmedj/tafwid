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

State lookup is shared by the switch, settings and launcher:

- Neither directory exists: use `state/tafwid`.
- Only `state/tafwid` exists: use it.
- Only `state/claude-delegate` exists: reuse it without rewriting records.
- Both exist: stop with a conflict error. Back up and reconcile the directories;
  Tafwid will not guess which permissions, task switches or history should win.

Do not move a live state directory or remove active run artifacts. Version 0.4
adds an explicit migration command; v0.1 deliberately reuses the
legacy state instead of silently relocating it.

## From Tafwid 0.1

Upgrade the marketplace, reinstall `tafwid@tafwid`, and start a new task.
The former `$tafwid:tafwid` entry becomes `$tafwid:delegate`. Use
`scripts/settings.py` to view routing and change permissions. The shared
runtime moves from `skills/tafwid` to `skills/delegate`; resolve paths from the
loaded delegate skill rather than retaining an old cache path. Existing task
state and history do not move. Already-running workers retain their instructions.

## From Tafwid 0.2

Version 0.3 adds `$tafwid:account` and task-local connection pools. Upgrade and
start a new task to load both skills. An existing enabled switch is read as a
pool containing Claude; an off switch stays off. Old Claude run summaries remain
readable. Named GPT accounts require separate visible sign-in and confirmation;
Tafwid does not import or copy the ordinary Codex login.

## From Tafwid 0.3

Version 0.4 adds Claude Code as a coordinator and a host-neutral state home,
`~/.tafwid/state` (`TAFWID_HOME` overrides `~/.tafwid`). Upgrade and start a new task.

An existing installation keeps using its directory under the Codex home; nothing
moves on its own. `session.py status` and `settings.py show` report a `migration`
field while that is the case. To move it, finish or pause running workers, then:

    python3 scripts/settings.py migrate --dry-run
    python3 scripts/settings.py migrate

Named GPT accounts move with the directory and stay signed in. If the neutral
directory and a legacy directory both exist, scripts stop with a conflict error;
back up and reconcile them. Run records now name their owner as
`coordinator_task_id`; older records are still read.

A Codex task and a Claude Code session are different tasks. Accounts, global
defaults and run history are shared; the on/off switch and task settings are not.
