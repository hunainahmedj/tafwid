# Provider-aware delegation and dashboard redesign

Date: 2026-09-21
Status: Approved for implementation planning on 2026-09-21; execution plan review pending.
Baseline: `1c0cb4e` on `feature/account-usage-snapshots`.

## What and why

Tafwid should guide a new user from selecting worker providers to a useful,
readable dashboard. A user who chooses OpenRouter or local inference should not
need Claude installed or see irrelevant Claude account warnings. The dashboard
should represent the actual orchestrator, distinguish account limits from task
consumption, and keep detailed telemetry out of the main worker view.

The user approved multiple providers per task with one default and the command
order **action, provider, optional model**. The design preserves task isolation,
independent acceptance review, compact worker briefs and existing history.
This document describes intended behavior, not features already shipped.

## Scope and alternatives

Use the existing local Python service, static JavaScript interface and provider
adapters. Separate pages, shared task context and common readiness/routing logic
address the underlying state problem as well as the presentation.

Cosmetic changes to the current single page would leave unconditional Claude
polling and late setup failures. Replacing the dashboard with a framework or a
new hosted service would add packaging and operational work without resolving
those issues. Neither alternative is selected.

Included: provider-aware task state, guided skill setup, early readiness checks,
cross-provider task routing, dashboard navigation/branding, a message picker,
orchestrator telemetry and conditional account panels. Claude remains a worker
adapter; Codex remains the supported orchestrator in this release. The internal
orchestrator boundary must accommodate future hosts without advertising them now.
Cursor support, model quality evaluation, billing changes, remote dashboard
hosting and a new inference loop are outside this change.

## Command contract

The skill interprets these forms and calls a deterministic runtime interface:

| Invocation after `$tafwid:delegate` | Result |
| --- | --- |
| no arguments | Native question prompt for On / Off, then collect missing choices |
| `status` | Compact task status, enabled providers, default and readiness summary |
| `on` | Ask which provider to enable |
| `on claude` | Check Claude readiness, enable it, open the dashboard |
| `on claude opus` | Also set this task's Claude fallback model to Opus |
| `on openrouter MODEL` | Configure and enable OpenRouter through OpenCode |
| `on zen MODEL` | Configure and enable Zen through OpenCode |
| `on local-NAME MODEL` | Enable the named LM Studio/vLLM connection through OpenCode |
| `default claude` | Select already-enabled Claude as this task's default provider |
| `default claude sonnet` | Also set this task's Claude fallback model to Sonnet |
| `default` | Ask which enabled provider should be the default |
| `off claude` | Disable only Claude for this task |
| `off` | Disable every provider for this task |

`claude`, `zen`, `openrouter` and configured `local-NAME` names are canonical
user-facing provider arguments. Normalize hosted model IDs to the existing
adapter formats without guessing models. Selecting LM Studio or vLLM in the
prompt resolves to a named connection; ask for that connection if ambiguous.
Unknown actions/providers produce a short correction with supported choices,
never a launch or a silent interpretation as a different provider.

The parser distinguishes management commands from task assignments. An explicit
instruction such as "use OpenRouter for this review" is a one-shot assignment
and does not alter the saved default or enable persistent delegation.

When the host provides a native question tool, use it for missing arguments.
Ask On / Off first for a bare invocation; ask a provider only when enabling.
Show friendly provider labels and configured local connections. If the host only
supports a single selection, enable one provider per invocation and allow adding
more through subsequent commands or Connections. Do not simulate multi-select.
If question tools are unavailable, use a concise text choice as a compatibility
fallback. Fully specified commands must not trigger redundant preference prompts.

An omitted model retains saved model routing. For a provider with no resolvable
model, model selection is a genuinely missing argument: show configured/cached
capability candidates, and validate the selected model before activation.
Discovery never silently chooses a supposedly best model or enables paid fallback.

## State and routing

Evolve task state to a versioned schema containing the task identity, providers
with individual enabled flags and optional fallback models, and a nullable
default provider. Keep connection definitions, credentials and global model
preferences outside task state. Readiness observations are timestamped evidence,
not stored credentials or permanent authorization.

The first successfully enabled provider becomes the default if it is the only
enabled provider and no default exists. Enabling another provider preserves the
existing default. `default PROVIDER` requires an enabled, configured provider;
otherwise return instructions to enable it, without doing so implicitly.
Disabling the default clears the default selection; remaining providers stay
enabled. Unrouted automatic work then requires an explicit default choice rather
than silently switching providers. `off` retains model preferences and routes,
but disables every provider and clears the default. Existing workers continue.

Separate provider routing from model routing:

1. For a new automatic assignment, an explicit provider wins over a saved
   task-type provider rule, which wins over this task's default.
2. The selected provider must be enabled for automatic work. A rule targeting a
   disabled provider reports that conflict; it must not fall through to another.
3. For the selected provider, explicit assignment model wins, then that provider's
   task-type model override, then the task's provider fallback model, then the
   provider's configured tier/default model. Missing selection asks for a model.
4. Explicit one-shot assignments retain the existing `--once` exception to the
   persistent switch, while still requiring readiness and permission checks.
5. Resumes retain their recorded provider and model unless an allowed explicit
   model change is supplied. Changing providers requires a fresh worker. State
   and readiness are rechecked at dispatch, including automatic resumes.

Thus `on claude opus` supplies a provider fallback; it does not erase a saved
documentation model rule. The command response reports this scope explicitly.
Task-type provider/model mappings are editable in Settings; providers excluded
from a task remain visible there as inactive choices with an explanation.
Global preferences are defaults for tasks, never permission to enable a provider.
Keep the existing task types and Fast / Standard / Deep model tiers where configured.

Use one resolver for the skill/runtime, dashboard preview and launchers. Its
compact result records provider, harness, model and selection reason. Preserve
the actual backend/provider in worker records. Enforce provider enablement in
the launcher, not merely in agent instructions, including legacy calls that
omit `--backend`. Recheck immediately before process creation to handle `off`
during a slow preflight. The dashboard never supplies the parent's permissions.

## Readiness and activation

Activation performs bounded checks before updating enabled state. A failed
activation leaves the previous task configuration intact. Categorize outcomes:
not installed, not configured, credentials configured, access verified,
access rejected, unsupported configuration, and check unavailable.

- Claude: locate the CLI, parse native auth status, preserve subscription-only
  policy, and use a non-inference native account check where supported. CLI
  format/version failures are not reported as "not authenticated." Configured
  credentials alone are not proof that a model request will succeed.
- OpenRouter: check OpenCode, credential presence and available non-inference
  credential verification. Check the selected model's live free/tool metadata.
- Zen: check OpenCode and model metadata; distinguish configured-account access
  from the existing public-free mode. Do not demand an API key when the selected
  supported mode does not require one.
- Local connections: check OpenCode, named connection configuration, credential
  reference when required, and the configured server's model listing. Preserve
  private endpoint validation. A server/model listing is not proof of tool quality.

Where a provider/version offers no supported non-inference credential check,
activation may proceed with explicit "credentials configured; access unverified"
evidence. Explicit rejection blocks activation. Transient unavailable checks do
not erase credentials or claim the user is logged out. No probe sends a model
prompt, retrieves credential values into agent context, changes billing mode,
or repairs access by broadening permissions. Tim's reported failure is motivation
for distinct error states, not a diagnosed cause.

After successful `on`, start/reuse the local dashboard and request that the host
open its task-scoped Overview once. A browser-open failure reports a usable link
without reverting successful activation. An `off` or `status` command does not
start a service. Repeated `on` is idempotent and never creates duplicate servers.

## Dashboard structure and visual contract

Use the existing Tafwid branching icon and charcoal/sage palette. Serve bundled
branding assets through explicit static routes, including the favicon. Remove
the starburst brand mark and user-visible Claude-only product language; retain
Claude labels where they identify that actual provider. Preserve private legacy
storage identifiers and compatibility where renaming would risk existing state.

Provide shared navigation to Overview, Workers, Usage, and Connections & Settings.
Keep the selected task and access fragment across page navigation. The service
connection indicator must be distinct from provider readiness and worker status.

| View | Primary content |
| --- | --- |
| Overview | Task title, delegation state, compact orchestrator card, enabled providers, active workers and attention items |
| Workers | Search/filter controls, active/completed worker groups, run history and exchanges |
| Usage | Orchestrator and worker consumption/context, cost provenance, eligible account windows and filtered comparisons |
| Connections & Settings | Available providers, readiness/setup actions, per-task enablement/default selection, model routes and permissions |

Overview must put active work above detailed historical statistics. The compact
orchestrator card shows harness, recorded model, last-observed status and concise
token/context metrics with an activity link. Activity opens a focused view with
its own search/filter controls. Do not use a wide prose-filled banner or imply
that a tool return is acceptance review.

Use consistent alignment, restrained borders, visible focus styles, short labels
and readable empty states. Keep methodological explanations in help/details on
Usage rather than repeating paragraphs on Overview. On narrow screens, navigation
and cards reflow without page overflow; figures and status remain legible.

Replace the native Starting message select with a bounded searchable picker.
Group rows by local date, show time and a short plain-language preview, highlight
selection, and provide a constrained scroll area. Decode HTML entities and render
Markdown link labels without their filesystem/URL targets in previews; strip known
injected wrappers. Render all text as text, never HTML. Preserve the stable message
identifier and original timestamp. Support keyboard opening, arrow navigation,
Enter selection, Escape dismissal, focus restoration and an accessible label.
Use a mobile-sized dialog/sheet presentation with the same selection semantics.

Workers and Usage share the chosen message/time filters. Retain the distinction
between run-start filtering and response-completion sampling; label them where
relevant. Deep links using existing fragment fields continue to select the same
task/filter/message. Newly generated links include an explicit view; old filtered
links resolve to Workers so previously shared filters remain useful.

## Provider visibility and collection

For a selected task, show/poll Claude account limits only when Claude is enabled
and has successful subscription connection evidence. For All tasks, include it
only if at least one saved task enables Claude and connection evidence exists.
Worker model/role/search filters never change account-wide limits. Disabled or
unconfigured providers appear only in Connections/setup, not as quota warnings.

After a previously connected provider loses access, stop quota polling on rejection
and show a connection problem/last-known state rather than current quota. A transient
refresh failure may show stale values while the selected provider remains enabled.
Fresh setup retry is explicit; do not repeatedly run authentication commands every
two seconds. An already-running worker remains visible and its recorded usage is
retained after its provider is disabled. Hiding account panels never deletes history.

Enforce polling eligibility server-side as well as in the UI. Use bounded cached
readiness observations and the existing refresh throttles. Do not check/install
every available harness just because the dashboard opens. Connections can request
a deliberate check of the chosen provider without enabling it.

## Orchestrator metrics

Introduce a Codex observation adapter behind a host-neutral orchestrator interface.
Resolve the selected task's host/model from recorded evidence, not from a worker's
model, the server process environment, or the label "GPT." Read token-count and
context-window metadata from the same identity-validated local task log used for
activity. No inference prompts or worker brief additions are needed.

Consumption uses differences of cumulative counters where valid, rejecting negative
resets and duplicate observations. Missing preceding samples make boundary totals
partial; never attribute an entire cumulative history to the latest message. Preserve
model changes, compaction and cache semantics. Cached input is a subset when the
host reports it that way; reasoning is not added twice to output. Native child
workers are separate observations; do not present parent-only data as all GPT use.

Show last/peak context only from capacity and occupancy evidence supported by the
host format. Label unknown/partial values. Keep account allowance windows separate
from task consumption and show observation times/reset windows. Prefer a supported
read-only native quota interface for current data; timestamped local limit events
are the fallback and must be marked recorded/stale. If neither is available, show
Unavailable. Do not require the orchestrating GPT to poll tools periodically for
the dashboard. The app tool verified during design establishes feasibility, not a
Python API contract; runtime integration needs a compatibility check before release.

API-equivalent cost uses an exact model price entry with provenance, retrieval date,
currency and correct cached-input/output rates. Obtain published prices from the
provider's official sources and cache outside task prompts. Unknown/unpublished
models show unavailable; never substitute a similarly named model. Report priced
coverage for partially estimable periods. Subscription fees/allowance are not API
charges, and local hardware/electricity cost remains unmeasured.

## Components and data boundaries

- `session.py`: versioned task state, atomic updates and provider enablement.
- A shared provider/readiness module: safe checks and normalized connection states.
- `routing.py` / `settings.py`: versioned provider/model defaults and resolution.
- `delegate.py` / `opencode_worker.py`: enforce resolved selection and current state.
- A Codex telemetry adapter: bounded, cached usage-only observations for known tasks.
- `dashboard.py`: authenticated task/context, settings and telemetry endpoints;
  explicit static routes and existing loopback/Host/Origin protections.
- Dashboard modules: shared navigation/state, provider setup, orchestrator summary,
  workers, usage and accessible message picker. Keep page-specific rendering out
  of a growing monolithic `app.js`.
- Skill entry point: compact command dispatch and missing-argument prompting rules;
  detailed setup/workflow documentation loads only when needed.

Task writes from dashboard requests require an explicit validated task identity.
The dashboard's launching task must not become the target of every later mutation.
Read-only historical task views remain available after deletion of a switch file.
No secrets, raw auth responses, full transcripts or provider catalogues enter new
agent completion context. Preserve existing safe credential references and local
state permissions. User-visible telemetry is not injected into worker prompts.

## Compatibility and rollout

Read legacy task on/off state without destructive migration. Enabled legacy tasks
normalize to Claude enabled/default, with readiness initially unchecked; disabled
tasks stay off. Persist the new schema on an explicit mutation, using atomic writes
and preserving a private recoverable copy. Invalid/conflicting state fails visibly.
Preserve legacy Claude tier/task settings, permissions, recorded runs, native session
IDs and credentials. Old settings submissions update only their owned fields and
cannot erase new provider mappings. The new runtime rejects unsupported schema
writes. Already-installed old binaries cannot be retroactively made safe writers;
retire old switch/launcher entry points before mutating the upgraded state and
document that rollback requires the preserved copy. Do not claim every old plugin
remains compatible.

Update command examples, setup/migration references and dashboard documentation
when implementation lands. The current public docs continue describing shipped
behavior until then. The installed dashboard must restart from the updated runtime
after installation; installing files alone does not update a running service.
Existing worker processes continue; never stop them as part of a dashboard refresh.
The public release must use matching version manifests and communicate changed
bare-invocation behavior. Existing old `provider on` phrases may be understood as
natural language, but all documented examples use `action provider model`.

## Acceptance and validation

1. Fresh install with no Claude shows Tafwid branding and provider setup, and does
   not spawn a Claude process or quota request. OpenRouter/local-only tasks work.
2. Bare invocation uses native question prompts when available; `on claude opus`
   avoids redundant questions. `off` and `status` never prompt for a provider.
3. Authentication/readiness failures occur before activation and distinguish
   explicit rejection, missing configuration, unsupported CLI and network failure.
4. Two providers can be enabled, the default changed explicitly, and task-type
   rules/one-shot overrides obey the documented precedence. Disabled-provider routes
   block instead of falling back. Off during preflight prevents automatic dispatch.
5. Existing task state, routes, permissions and resumed workers survive upgrade;
   stale dashboard submissions cannot discard newer settings.
6. Successful activation starts/reuses the dashboard once and requests opening
   the task Overview. Browser failure leaves state correct and provides the link.
7. Claude panels/polling obey selected-task and All-tasks eligibility. Historical
   worker data remains visible after disabling Claude.
8. Orchestrator model/token/context/cost evidence is separate from workers and
   subscription quota. Tests cover duplicate counters, counter resets, model
   switches, missing baselines and unknown prices/capacity.
9. The message picker removes path/markup noise, retains exact boundary identity,
   supports keyboard interaction and remains usable on mobile. Existing deep links
   and latest-message tracking retain their meaning.
10. Run package/plugin validation and appropriate Python/JavaScript regressions.
    Perform visible desktop/mobile passes for every page, first-run setup, no-Claude
    state, multi-provider state, worker activity, unavailable metrics and picker
    interaction. Test with isolated fixtures; any live check reports its precise
    scope without claiming authenticated inference from configuration evidence.

Implementation planning follows written-spec review. No product/runtime changes
or new provider activation are authorized by this document alone.
