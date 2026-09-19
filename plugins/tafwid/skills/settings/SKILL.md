---
name: settings
description: Use when the user wants to view or change Tafwid model tiers, task-type routing, or worker permission preferences.
---

# Tafwid settings

Resolve `TAFWID_SKILL_DIR` to the sibling `../delegate` directory relative to
this loaded `SKILL.md`. Use absolute paths or set the variable in the same shell
invocation. To inspect current choices:

```bash
python3 "${TAFWID_SKILL_DIR}/scripts/settings.py" show
```

For a bare invocation, opening settings, or editing model routing, run
`python3 "${TAFWID_SKILL_DIR}/scripts/dashboard.py" start`. Change only the
returned URL's path from `/` to `/settings`, preserving its private fragment.
Open it in Codex with `open_in_codex` (browser target), or the available browser
tool. Apply requested edits through the Settings page and verify Save succeeded.
Opening the page alone does not change preferences. Do not publish its token.

For an explicitly requested permission change, the CLI also supports:

```bash
python3 "${TAFWID_SKILL_DIR}/scripts/settings.py" set --policy scoped
```

Policies: `scoped` uses explicit allowances; `full` bypasses Claude approval
prompts for available tools; `inherit` follows confirmed Codex full access and
otherwise stays scoped. Change only requested preferences; never broaden
permissions to recover from a denial. Settings apply across this Codex home.

Task overrides beat tier defaults. New workers use saved routing; resumed
workers keep their model unless explicitly rerouted, but recheck permissions.
Running workers keep their current configuration. Preferences do not toggle
delegation; use `$tafwid:delegate` for on/off/status.

Read [model selection](../delegate/references/model-selection.md) only for
routing detail. The delegation workflow is unnecessary for settings-only work.
