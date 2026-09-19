---
name: dashboard
description: Use when the user wants to open Tafwid's workers dashboard or inspect worker runs, exchanges, filters, or recorded orchestrator activity.
---

# Tafwid dashboard

Resolve `TAFWID_SKILL_DIR` to the sibling `../delegate` directory relative to
this loaded `SKILL.md`. Use absolute paths or set the variable in the same shell
invocation. Run:

```bash
python3 "${TAFWID_SKILL_DIR}/scripts/dashboard.py" start
```

Open the returned URL in Codex with `open_in_codex` (browser target), or the
available browser tool. Preserve its private token and task filter; do not
publish the URL. Repeated starts reuse the server. Viewing does not enable
delegation, launch workers, or change preferences.

For filters, history imports, exchanges, or activity interpretation, read
[dashboard operations](../delegate/references/dashboard.md) as needed. Counts
group runs by worker session. Completion is not proof of Codex acceptance;
activity contains recorded public messages and tools, not internal reasoning.

Use `$tafwid:settings` for preferences. The delegation workflow is unnecessary
for dashboard-only requests.
