---
name: delegate
description: Use when the user manages Tafwid delegation, assigns work to Claude Code or a named GPT account, or continues with delegation enabled. Works when Codex or Claude Code is the coordinator.
---

# Tafwid delegation

Use Tafwid to manage and delegate tasks for the current chat session to
external workers. Your goal is to coordinate their work efficiently,
reducing your token usage and keeping unnecessary work out of your context.
You remain responsible for accepting their results. Review enough to
confirm the task’s requirements are met, reusing valid worker evidence
rather than repeating their work.

## Scripts

You have a few scripts available. The paths below are relative to the directory containing this `SKILL.md`. Use their absolute paths when running commands.

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

Invoking the delegate skill with no arguments means status.

The script identifies the current chat automatically and saves its setting
on disk. Enabling delegation checks the harness's installation and
authentication status. If the command fails, report the error instead of
assuming delegation was enabled.

If status or settings output contains a `migration` field, tell the user once
that `scripts/settings.py migrate` can move saved state to the shared location,
and continue.

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

Enable only the connections the user chooses for this task. Record one exact enabled connection for each worker assignment. If routing is unclear, ask the user. If a selected GPT account is unavailable, stop that assignment and offer setup through the `tafwid:account` skill. Never substitute another connection. Follow [the GPT account guide](references/gpt-accounts.md) for sign-in and worker rules.
