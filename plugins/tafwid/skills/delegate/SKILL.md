---
name: delegate
description: Use when the user requests Tafwid delegation on/off/status, assigns work to a Claude Code worker, or continues substantial work with this task's delegation enabled.
---

# Tafwid delegation

Resolve `TAFWID_SKILL_DIR` to the absolute directory containing this loaded
`SKILL.md`. Use absolute paths or set the variable in the same shell invocation;
never guess a personal skill path or a plugin-cache version.

For on/off/status, run only the corresponding command and report the result:

```bash
python3 "${TAFWID_SKILL_DIR}/scripts/session.py" status
# Substitute on or off when requested.
```

A bare invocation shows status. Use the current process's task identity. State
defaults to off; never infer it from a repository or another conversation.
Off prevents new automatic dispatches without cancelling running workers.
Existing legacy state is reused; do not relocate it or repair a conflict by
discarding settings/history.

For assigning, resuming, or reviewing delegated work, read
[the worker workflow](references/workflow.md) once and follow it. Check status
before choosing an execution approach. Codex retains acceptance review; the
implemented worker backend is Claude Code. An explicit one-shot request does
not enable persistent delegation. If a switch request also includes work,
complete the switch first, then follow the workflow for that work.

Dashboard and preferences requests use `$tafwid:dashboard` and `$tafwid:settings`.
They do not require loading the worker workflow.
