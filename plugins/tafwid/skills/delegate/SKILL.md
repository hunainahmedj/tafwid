---
name: delegate
description: Use when the user requests Tafwid delegation on/off/status, assigns work to a Claude Code worker, or continues work with this task's delegation enabled.
---

# Tafwid delegation

Use Tafwid to manage and delegate tasks for the current chat session to
external workers. Your goal is to coordinate their work efficiently,
reducing your token usage and keeping unnecessary work out of your context.
You remain responsible for accepting their results. Review enough to
confirm the task’s requirements are met, reusing valid worker evidence
rather than repeating their work.

## Scripts

You have the a few scripts availible to you. The paths below are relative to the directory containing this `SKILL.md`. Use their absolute paths when running commands.

| Script | Purpose |
|---|---|
| `scripts/session.py` | Enable or disable delegation for this chat, read its status, or select the worker harness when enabling it—for example, `on claude`. Checks harness readiness before enabling. |
| `scripts/settings.py` | Read or change this chat’s worker settings, or global defaults. |
| `scripts/delegate.py` | Launch a worker or resume an existing worker with a new assignment. |
| `scripts/wait.py` | Wait for workers to finish and report completion or problems without making model requests. |

Each script supports `--help` for its arguments and usage.

## Session control

Use `scripts/session.py` to handle the user’s delegation commands and
report the result.

It takes a positional command: `on`, `off`, or `status`.
With `on`, you can also specify the worker harness.

```bash
python3 scripts/session.py on claude  # Enable delegation using Claude Code.
python3 scripts/session.py on         # Enable using this chat's saved harness.
python3 scripts/session.py off        # Stop new dispatches; running workers continue.
python3 scripts/session.py status     # Read this chat's delegation setting.
python3 scripts/session.py --help     # Show arguments and usage.
```

A bare `$tafwid:delegate` invocation means status.

The script identifies the current chat automatically and saves its setting
on disk. Enabling delegation checks the harness's installation and
authentication status. If the command fails, report the error instead of
assuming delegation was enabled.

## Settings

Use `scripts/settings.py` when the user asks to view or change settings.
Run `--help` for available commands.

Changes apply to the current chat by default. Use `--global` only when
the user explicitly requests changes to defaults for new chats.

## Delegating work

For assigning, continuing or accepting worker tasks, read
[the workflow](references/workflow.md).

The workflow explains how to prepare the task, configure and launch
the worker, wait for completion, and accept the result.

For Claude-specific tools and permissions, also read
[the Claude Code guide](references/claude-code.md).
