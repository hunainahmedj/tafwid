# Architecture and extension points

The repository is a distributable Codex marketplace containing one plugin:

```text
.agents/plugins/marketplace.json
plugins/tafwid/.codex-plugin/plugin.json
plugins/tafwid/skills/tafwid/
  SKILL.md             controller guidance
  scripts/             Python runtime
  assets/dashboard/    static dashboard
  references/          optional detailed guidance
  tests/               isolated Python and JavaScript checks
```

The installed skill resolves its own directory. Runtime asset paths are relative
to source files; installation does not require a specific username or checkout.

`session.py` owns the task-local switch. `paths.py` selects state storage.
`settings.py` and `routing.py` own permission and model preferences.
`delegate.py` implements the **Claude Code** invocation, subscription check,
process lifetime and structured completion contract. `instructions.py` matches
selected files to Claude skills or supplies their contents and records a private
manifest. `worker_registry.py`, `wait.py`, `activity.py` and `dashboard.py` provide
run recording, bounded waits and the local dashboard.

## Backend boundary

The product name is neutral; the current invocation, instruction discovery,
permission modes and model catalog are still Claude-specific. There is no generic
adapter interface yet. Extract that interface alongside the second working
backend, rather than inventing untested abstractions now.

An additional backend must define executable/API availability, authentication,
model selection, tool permissions, resume identity, cancellation, outcomes and
usage evidence. Preserve task/workspace ownership and keep secrets outside run
summaries. A CLI coding agent and a raw model API are different integrations:
OpenRouter requires an execution/tool loop, not just swapping a model name.

Provider billing and permissions must be explicit. Claude subscription-only
checks must not become an API-key fallback. Free-model routing must not silently
fall back to paid models. The exact semantics will be implemented and tested with
each adapter.

## Local state and limitations

Fresh installs use `$CODEX_HOME/state/tafwid` (default `~/.codex`). Legacy installs
reuse `state/claude-delegate`; see [migration](migration.md). Records may contain
source paths, task briefs, generated code and excerpts of diagnostic output.
These belong to the user's local state, never the release artifact.

The activity view reads local Codex log formats, and Follow Codex currently uses
an observed process environment signal. These integrations are version-sensitive;
missing full-access evidence falls back to Scoped. A dashboard completion record
is not proof of acceptance. The legacy dashboard health identifier is retained
for compatibility with an already-running local service.
