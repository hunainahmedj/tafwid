# OpenCode free workers: OpenRouter and Zen (experimental)

For a user-selected LM Studio or vLLM server, read [local model setup](local-models.md).
Local connections use `local-NAME/model` instead of the hosted-provider gates below;
the shared permissions, waiting, reporting and acceptance rules still apply.

Read only when dispatching an OpenCode worker. Requires OpenCode with `run
--pure --format json`, `export`, and inline configuration support (tested with
1.18.31). Authenticate in the user's terminal with `opencode auth login`, select
OpenRouter, and enter the key there. `OPENROUTER_API_KEY` is also supported. Never
request a key in chat or put it in a task brief, settings, or run artifact.

For Zen, use an explicit `opencode/model-id`, such as `opencode/big-pickle`
when it is currently listed as free. If a Zen account is configured via
`opencode auth login` → OpenCode Zen or `OPENCODE_API_KEY`, the harness uses it.
Otherwise it tries OpenCode's native public-access path for free models. A public
request can still be rate limited or rejected; no login or paid fallback occurs
automatically. Do not ask for a key merely because none is configured.

```sh
python3 "${TAFWID_SKILL_DIR}/scripts/delegate.py" --backend opencode --once \
  --cwd /absolute/workspace --prompt-file /private/brief.md \
  --output-dir /private/run-1 --model openrouter/provider/model:free \
  --title "Fix the focused bug" --role implementer --mode edit \
  --allow-command 'python3 -m unittest *'
```

Replace `--model` with `opencode/big-pickle` to use that Zen model instead.
Choose an actual current model, not the example placeholder. The launcher checks
OpenRouter's live catalogue, or Zen's live IDs plus current models.dev metadata,
for zero input/output pricing and tool calling before
dispatch. An unavailable catalogue or incompatible model stops launch; no silent
fallback. For example, a free variant without `tools` cannot execute this workflow,
even when its paid/base model can. OpenRouter inference is remote and needs an API
key even for free models. Quotas and capacity limits still apply.

`--backend opencode` selects the harness; `openrouter/` or `opencode/` selects the provider; the
remaining model ID selects the model. This first adapter uses explicit model
selection. Saved task-type/tier mappings in Settings remain Claude-specific.
Do not select another harness automatically because Claude is blocked.

Permissions reuse the saved Scoped / Full / Follow Codex preference. Read mode
allows file inspection. Edit mode also permits file changes. Scoped shell use
requires `--allow-command` patterns using OpenCode's wildcard syntax; Claude's
`--allow-tool 'Bash(...)'` syntax is rejected. Full edit allows shell commands and
external directories. Nested workers, interactive questions, skills, MCP and web
tools are not granted by this adapter. Use structured `native_required` for
unavailable browser/computer actions. Permission rules are not an OS sandbox.

Free runs use `--pure` to disable external OpenCode plugins, pin the main model,
small model and title/summary/compaction models to the same free ID, and set
OpenRouter's zero-price provider filter with provider fallback disabled. Only the
selected model is allowlisted. Zen has no equivalent documented per-request
price ceiling: it uses a fresh listing/metadata check and the exact model ID.
Free promotions and catalogue data can change; neither metadata checks nor
reported zero cost constitute a guaranteed billing cap. This is
a controlled initial adapter: selected workflow instructions are supplied through
`--instructions-file`, deduplicated and retained on verified resumes; installed
OpenCode skills are not invoked. Project instructions can still be read by the
harness. Managed restrictions retain precedence. Do not claim a billing cap from
local cost metadata alone.

Resume with `--resume-from /private/run-1` and a fresh output directory. The launcher
retains the recorded backend/model and verifies Codex task and workspace ownership.
Changing from OpenRouter to Zen or vice versa requires a fresh worker. Every
resume rechecks live pricing/capabilities; stale scout data cannot authorize it.
Reapply mode and command allowances; current permission settings are re-evaluated.
Never use global `--continue`. There is no launcher-level automatic retry loop;
OpenCode may retry transient API failures within the overall task timeout.
Provider HTTP 403 is reported as `blocked` with `provider_access_denied`; preserve
the diagnostic and stop. Do not spoof headers/client identity, repeatedly retry,
or switch accounts/models to bypass an access restriction. Zen has produced
client-restriction errors even in a native OpenCode CLI trial; a successful first
run does not guarantee a usable resume.

The same registry, compact wait tool and dashboard track these workers. Raw events
are private `events.jsonl`; the exact session export is `session.json`. The final
answer must satisfy Tafwid's status/report/handoff JSON contract. Missing or
truncated output and tool errors require review. Codex must inspect changed files
and acceptance evidence regardless of a worker's `completed` claim.

`usage` records this run's main-worker step tokens/cost; `models_used` comes from
the exported session history, including earlier resumes. Neither is guaranteed to
include auxiliary calls. Missing exported model evidence is unknown. Never equate
worker tokens with measured GPT savings or skip acceptance review to improve the
numbers.

Provider policies differ for free models. Before sending private project content,
consult the selected provider's terms; the built-in acceptance trials use synthetic
fixtures. Zen's current free offers and data-use conditions are documented on
[OpenCode Zen](https://opencode.ai/docs/zen/). This adapter does not create accounts,
change billing settings or enable auto-reload.
