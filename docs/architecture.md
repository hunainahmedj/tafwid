# Architecture and extension points

The repository is a distributable Codex marketplace containing one plugin:

```text
.agents/plugins/marketplace.json
plugins/tafwid/.codex-plugin/plugin.json
plugins/tafwid/skills/delegate/
  SKILL.md             switch and delegation entry point
  scripts/             Python runtime
  assets/dashboard/    static dashboard
  references/          on-demand workflow and detailed guidance
  tests/               isolated Python and JavaScript checks
plugins/tafwid/skills/dashboard/SKILL.md
plugins/tafwid/skills/settings/SKILL.md
plugins/tafwid/skills/scout/SKILL.md
```

The delegate entry point resolves its own directory. Dashboard and settings
resolve the sibling delegate directory and call its shared runtime without
reading its workflow. The full workflow lives in `delegate/references/workflow.md`
and is read only for delegation work. Runtime asset paths are relative to source
files; installation does not require a specific username or checkout.

`session.py` owns the task-local switch. `paths.py` selects state storage.
`settings.py` and `routing.py` own permission and model preferences.
`delegate.py` dispatches backends and implements the **Claude Code** invocation, subscription check,
process lifetime and structured completion contract. `instructions.py` matches
selected files to Claude skills or supplies their contents and records a private
manifest. `worker_registry.py`, `wait.py`, `activity.py` and `dashboard.py` provide
run recording, bounded waits and the local dashboard. `opencode_worker.py` contains
the experimental OpenCode subprocess adapter, OpenRouter/Zen capability/price gates,
tool policy, event interpretation and native session export.

`scout.py` fetches public OpenRouter and Zen metadata, caching normalized free
model candidates for six hours in local state. Zen pricing and capability data
come from models.dev, intersected with Zen's live IDs. Discovery never calls
inference, installs providers or edits routing. Candidate task mappings are
metadata heuristics, not quality evaluations; recorded outcomes are separate.
`opencode_providers.py` keeps provider authentication, live preflight and SDK
configuration separate from the shared OpenCode process/session lifecycle. Zen
uses native public access when no account key is configured, with only the chosen
free model enabled; supported model transports are explicitly allowlisted.

`local_models.py` stores named LM Studio/vLLM connections in private
`local-models.json`. `local-NAME/model` routes the existing OpenCode lifecycle
to that server's OpenAI-compatible API; tools still execute in the local
workspace. Local discovery uses `/v1/models`, user-declared context/tools and
credential references instead of cloud catalogues. It rejects public URLs and
redirects. These checks are not a network sandbox. Resumes reject any changed
connection configuration. Token/rate evidence uses the shared metrics path;
hardware and electricity costs are unmeasured.

`metrics.py` normalizes per-invocation usage and hydrates historical records from
their registered artifacts. File-signature caching avoids reparsing those files
on each refresh. Missing data stays null. `stats.mjs` aggregates only matching
runs for the page totals, all recorded runs for a worker, and separates Claude
API-equivalent costs from OpenCode reported costs. Resumes are never aggregated
from cumulative session exports. Effective throughput is output divided by
elapsed run time, weighted across runs, not wall-clock concurrency throughput
or model decode speed. Neither catalogue nor metrics processing invokes a model.

## Backend boundary

The choice to reuse OpenCode is recorded in
[ADR-0001](decisions/0001-opencode-worker-harness.md).

Backend dispatch is explicit (`--backend claude|opencode`), with Claude as the
default and the original backend retained on resume. Backends share task state,
instruction manifests, permission-policy resolution, worker report validation,
registry and wait tools. Invocation, authentication, tool syntax, session IDs and
event parsing remain backend-specific. OpenCode accepts explicit
OpenRouter free IDs, free Zen IDs, or configured self-hosted IDs; saved model tiers remain
Claude-specific. Provider changes require a new worker; same-provider resumes
retain their selected model and always recheck current provider metadata or the
selected local server. Local capabilities are declared, not inferred from benchmark scores.

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
