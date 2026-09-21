# Provider-aware Delegation and Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make provider setup, delegation and telemetry understandable for users with any supported worker provider, including users without Claude.

**Architecture:** Extend the existing task state and adapters through shared readiness and routing interfaces. Keep the local Python service and modularize its static dashboard into focused views. Observe Codex usage locally without adding model prompts or worker context.

**Tech Stack:** Python 3.10+ standard library, vanilla JavaScript ES modules, HTML/CSS, unittest and Node's built-in test runner; existing Claude Code/OpenCode integrations on macOS/Linux.

**Spec:** [Approved design](../specs/2026-09-21-provider-aware-dashboard-design.md). Read it before this plan; it owns user-visible semantics and scope.

## Global Constraints

- The user approved multiple providers per task with one default and the command order **action, provider, optional model**.
- Claude remains a worker adapter; Codex remains the supported orchestrator in this release.
- Existing workers continue.
- Discovery never silently chooses a supposedly best model or enables paid fallback.
- The dashboard never supplies the parent's permissions.
- Fully specified commands must not trigger redundant preference prompts.
- An omitted model retains saved model routing.
- Hiding account panels never deletes history.
- Runtime uses Python's standard library; no mandatory frontend build system or new inference loop.
- Preserve task-local state, subscription-only Claude execution, free-only hosted OpenCode execution and private local endpoints.
- Use existing task types, model tiers, permission semantics and resume identities; no model-price or context-capacity guesses.
- Never include secrets, full logs, account snapshots or pricing catalogues in worker prompts or routine completion output.
- Tests use temporary homes/fake clients; installation and live checks are separate, explicit rollout steps.

## Review Focus

- Two browser tabs update the same task/settings: stale writes must not discard the newer default or routes (Tasks 1, 3 and 6).
- A task has never launched a worker: setup, orchestrator summary and message selection must still work (Tasks 5 and 6).
- Provider is disabled while auth/model discovery is pending: neither activation nor an automatic launch can undo the newer off state (Tasks 3 and 4).
- A host log rotates, truncates or repeats cumulative usage after a model switch: totals must not jump or leak another task (Task 5).
- A renamed/deleted local connection is still referenced by a task: show an actionable missing-connection state and never choose another server (Tasks 2 and 3).

## Execution order and common commands

Use an isolated worktree at execution time with the using-git-worktrees skill,
starting from this branch's HEAD, not remote main: the quota/snapshot prerequisite
is committed here but not yet published. Preserve unrelated HomeLab work.
Check the current task's delegation switch once at the start of an execution turn.
Do not enable real providers as a side effect of developing this feature.

All paths below are repository-relative. `S` in shell examples denotes
`plugins/tafwid/skills/delegate`; set it explicitly in the same command when used.
Run Python tests with `python3 -m unittest discover -s plugins/tafwid/skills/delegate/tests -p 'test_NAME.py' -v`.
New Python tests follow the existing temporary CODEX_HOME pattern and import
scripts by adding `Path(__file__).resolve().parents[1] / 'scripts'` to `sys.path`.
Each task has a red test, implementation, focused green checks and a commit.
Do not repeat the full suite after every task; run it at integration boundaries.

The work is one coordinated release. Tasks 1–4 provide a testable management/CLI
foundation; Task 5 provides a separately testable observation adapter; Tasks 6–9
integrate them into the user experience. Task 10 is acceptance and local installation.

## File responsibilities

Under `plugins/tafwid/skills/delegate/scripts/`:

| File | Ownership |
| --- | --- |
| `session.py` (modify) | Versioned state, revisioned locked mutations and compatibility reads |
| `providers.py` (new) | Provider identity, harness mapping, connection metadata |
| `readiness.py` (new) | Bounded credential/access checks, normalized evidence and cache |
| `routing.py`, `settings.py` (modify) | Multi-provider configuration, resolution, stale-write protection |
| `setup.py` (new) | Management argument parsing, activation workflow and compact results |
| `delegate.py`, `opencode_worker.py` (modify) | Shared selection and pre-spawn state enforcement |
| `codex_usage.py` (new) | Identity-checked incremental host usage and quota observations |
| `pricing.py` (new) | Exact-model price validation and API-equivalent cost calculation |
| `dashboard.py` (modify), `dashboard_api.py` (new) | Service/static routes and authenticated data/mutation handlers |
| `activity.py` (modify) | Plain-language bounded message previews, reused log identity resolution |

Under `assets/dashboard/`: retain existing pure `view.mjs`, `stats.mjs` and
`snapshots.mjs`. Create `client.mjs`, `navigation.mjs`, `overview-ui.mjs`,
`workers-ui.mjs`, `usage-ui.mjs`, `connections-ui.mjs`, `message-picker.mjs`.
Reduce `app.js` to bootstrapping; reuse `activity-ui.mjs`. Keep and adapt
`settings-ui.mjs` for model/permission editing. Serve the existing plugin icon.
Create focused tests named in each task; extend the Makefile's Node test glob.

### Task 1: Versioned provider state with safe concurrent mutations

**Files:** Modify `scripts/session.py`, `tests/test_session.py`; create `tests/test_provider_state.py` (all under the delegate skill).

**Interfaces:**
- `empty_state(thread: str) -> dict`
- `read_state(thread: str | None = None) -> dict`: normalize v1 without writing; absent argument uses current process identity.
- `transition(state: dict, action: str, provider: str | None = None, model: str | None = None) -> dict`: pure validated transition.
- `mutate(thread: str, action: str, provider=None, model=None, expected_revision: int | None = None) -> dict`: file lock, reread, compare revision, transition, backup-on-first-upgrade, atomic write.
- `require_enabled(provider: str, thread: str | None = None) -> None`: current-state launch guard.
- Preserve `status()` returning `thread_id` and derived `enabled`, plus provider/default details. No-task status remains off; mutations require a valid task.

State payload:
```python
{
    'version': 2, 'thread_id': thread, 'revision': 0,
    'providers': {},  # provider -> {'enabled': bool, 'model': str | None}
    'default_provider': None,
}
```
Never persist derived `enabled`. `on` on an already enabled provider without
a model preserves its model. `off` with no provider disables all entries and
clears the default. A first enabled provider becomes the default; disabling it
does not select a remaining provider. Increment revision for every accepted
management mutation, including an off command when already off: that revision
invalidates an activation check already in flight. Repeated on remains idempotent
in provider/model selection and service creation, not in its revision counter.

- [ ] **Write failing state-transition tests**, including this pure example:
```python
def test_disabling_default_does_not_promote_other_provider(self):
    state = session.empty_state('12345678-1234-4234-8234-123456789abc')
    state = session.transition(state, 'on', 'claude')
    state = session.transition(state, 'on', 'openrouter', 'openrouter/example/model:free')
    state = session.transition(state, 'off', 'claude')
    self.assertIsNone(state['default_provider'])
    self.assertTrue(state['providers']['openrouter']['enabled'])
```
- [ ] **Run `test_provider_state.py` red.** Verify failure concerns missing state behavior.
- [ ] **Implement transition and persistence.** Use `fcntl.flock` on a sibling lock file and the existing private atomic JSON pattern. Under the lock, reject mismatched `expected_revision` with a dedicated `StateConflict(ValueError)` exception; do not write a backup or state on rejection. Normalize v1 enabled to Claude enabled/default, v1 disabled to no enabled providers. Preserve its original bytes in a private upgrade backup only on the first successful mutation.
```python
if expected_revision is not None and current['revision'] != expected_revision:
    raise StateConflict('Task settings changed; reload before saving')
updated = transition(current, action, provider, model)
```
- [ ] **Add/run regression cases** for v1 true/false, corrupt identity/schema, two interleaved mutations with one stale revision, no environment task ID, mode 0600, invalid model strings, repeated on, and default targeting a disabled provider. Use two subprocesses for the lock/lost-update case, not only a mocked lock.
- [ ] **Commit:** `feat: add task-local provider state and safe migration`.

### Task 2: Provider identity and honest readiness checks

**Files:** Create `scripts/providers.py`, `scripts/readiness.py`, `tests/test_readiness.py`; modify `scripts/delegate.py`, `scripts/opencode_providers.py` to reuse auth classification without changing launch policy.

**Interfaces:**
- `providers.describe(provider: str) -> dict`: `{id, label, harness, kind}`; local references require the exact configured connection.
- `readiness.check(provider: str, model: str | None, cwd: Path) -> dict` with injected subprocess/network functions for tests.
- `ReadinessReader.read(provider, model, cwd, refresh=False) -> dict`: bounded per-identity cache, refresh at most once per 60 seconds absent explicit retry.
- Evidence: `{provider, state, configured, verified, can_enable, checked_at, expires_at, code, message, auth_mode}`. `state` is one of `not_installed`, `not_configured`, `configured`, `verified`, `rejected`, `unsupported`, `unavailable`. No credential values.

- [ ] **Write a fake-client regression test** for a failed check that is not a failed login:
```python
def test_timeout_does_not_claim_signed_out(self):
    with patch('readiness.subprocess.run', side_effect=subprocess.TimeoutExpired('claude', 10)):
        result = readiness.check('claude', None, self.home)
    self.assertEqual(result['state'], 'unavailable')
    self.assertFalse(result['verified'])
    self.assertNotIn('not authenticated', result['message'].lower())
```
Fixture PATH contains the fake executable so the test reaches subprocess execution.
- [ ] **Run `test_readiness.py` red.**
- [ ] **Implement mapping and bounded checks.** Reuse Claude subscription/environment policy, its non-inference quota control, OpenCode auth sources, live model price/tool checks and local `/v1/models` validation. Move shared Claude auth parsing out of the launcher to avoid import cycles. Keep native raw auth/control data in-process only.
```python
def can_activate(evidence):
    return evidence['state'] in ('configured', 'verified') and evidence['configured']
```
`configured` means credentials/configuration are present but a supported access
probe does not exist; explicit network/probe failure is `unavailable` and does
not establish new activation. An already-enabled provider retains its state on
a transient failure. Zen public-free mode counts as configured without a key.
- [ ] **Test exact outcomes** for missing CLI, bad JSON/version, explicit auth rejection, wrong billing overrides, key-present-but-unverified, Zen public mode, absent local credential file, renamed connection and valid server with selected model missing. Assert no prompt messages, secrets or environment values in results. Cache must invalidate on provider/model/connection configuration changes, and rejection must not auto-retry within the cache interval.
- [ ] **Run focused readiness, Claude and OpenCode auth tests green; commit:** `feat: check provider readiness before activation`.

### Task 3: Shared provider/model routes enforced by launchers

**Files:** Modify `scripts/routing.py`, `scripts/settings.py`, `scripts/delegate.py`, `scripts/opencode_worker.py`; create `tests/test_provider_routing.py`; extend `tests/test_settings.py`, `tests/test_delegate.py`, `tests/test_opencode.py`.

**Interfaces:**
- Settings v3: `{version:3, revision:int, permission_policy, models, provider_routes, provider_models}`. Keep legacy Claude `models`; `provider_routes` maps existing task IDs to nullable provider IDs; `provider_models` maps non-Claude provider IDs to `{profiles:{fast,standard,deep}, tasks:{task_id:model_or_null}}`, nullable model values allowed until configured.
- `settings.save(data, expected_revision=None) -> dict`: lock, merge only owned legacy fields, reject stale v3 writes with `SettingsConflict(ValueError)`.
- `routing.resolve_route(state, config, *, task_type=None, profile=None, provider=None, model=None, once=False) -> dict` returns `{provider, backend, model, effort, source}` or a specific selection error.
- New launcher `--provider` complements existing `--backend`; contradictory selectors fail. Resume identity is loaded before resolving a new default.

- [ ] **Write the precedence test using valid default settings and a configured task route:**
```python
def test_explicit_provider_wins_but_does_not_mutate_default(self):
    state = session.transition(session.empty_state(self.thread), 'on', 'claude')
    state = session.transition(state, 'on', 'openrouter', 'openrouter/example/model:free')
    config = settings.read()
    picked = routing.resolve_route(state, config, task_type='implementation', provider='openrouter')
    self.assertEqual(picked['backend'], 'opencode')
    self.assertEqual(picked['model'], 'openrouter/example/model:free')
    self.assertEqual(state['default_provider'], 'claude')
```
- [ ] **Run `test_provider_routing.py` red.**
- [ ] **Implement settings upgrade and pure resolver.** Provider order: explicit, task rule, task default. Model order: explicit, selected provider's task override, task's provider fallback, provider tier. Never use Claude tier values as OpenCode models. Keep model scope/pricing/tool verification in the selected adapter.
```python
chosen = provider or config['provider_routes'].get(task_type) or state['default_provider']
if not chosen:
    raise ValueError('Choose a default provider or an explicit provider')
if not once and not state['providers'].get(chosen, {}).get('enabled'):
    raise ValueError('Selected provider is disabled for this task')
```
- [ ] **Integrate launchers.** Infer provider from an explicit old-style OpenCode model when unambiguous; verify conflict with explicit provider. Preserve existing `--once` compatibility and recorded resume provider/model. Before automatic process creation, call `require_enabled` again. A missing local connection fails before any alternative URL/model selection.
- [ ] **Test disabled routes, explicit one-shot use, missing default/model, profile/task selector conflicts, changed settings on resume, wrong-provider resume, local connection deletion, stale v3 save and old v1/v2 settings updates preserving provider routes.** Extend the existing slow-auth fixture so an off event prevents the eventual spawn. Assert permission resolution remains sourced from the launch process.
- [ ] **Run routing/settings/launcher tests green; commit:** `feat: route delegated work across enabled providers`.

### Task 4: Deterministic setup actions and dashboard activation

**Files:** Create `scripts/setup.py`, `tests/test_setup.py`; modify `scripts/session.py` CLI entry only.

**Interfaces:**
- `parse_management(words: list[str]) -> dict`: `{action, provider, model, missing}`; no args has missing `action`, on/default require provider; off/status do not.
- `SetupService(check, start_dashboard).execute(thread, action, provider=None, model=None, cwd=None, expected_revision=None) -> dict`.
- Result `{status:'ok'|'needs_input'|'blocked'|'conflict', state, missing, readiness, dashboard_url, message}` with compact normalized fields. Python prints a URL, the host skill opens it; Python never automates an arbitrary browser.
- `setup.py` management CLI uses process task identity. `session.py on/off/status` remains a compatibility entry into the same management service; bare low-level on returns missing provider instead of bypassing setup.

- [ ] **Write parser and orchestration tests:**
```python
def test_complete_command_needs_no_question(self):
    parsed = setup.parse_management(['on', 'claude', 'opus'])
    self.assertEqual(parsed['missing'], [])
    self.assertEqual((parsed['action'], parsed['provider'], parsed['model']), ('on', 'claude', 'opus'))

def test_off_requires_no_provider(self):
    self.assertEqual(setup.parse_management(['off'])['missing'], [])
```
- [ ] **Run `test_setup.py` red.**
- [ ] **Implement activation ordering.** Snapshot revision; resolve missing model input; check readiness outside the state lock; mutate under expected revision; start/reuse dashboard after successful activation. If state changes during checks return conflict, not an automatic retry that could undo off. `default` and off do not activate or authenticate a new provider. A dashboard startup/open failure is a warning after saved activation, not a false activation failure.
```python
before = session.read_state(thread)
if expected_revision is not None and expected_revision != before['revision']:
    return {'status': 'conflict', 'state': before, 'message': 'Reload changed task settings'}
evidence = self.check(provider, model, cwd)
if not evidence['can_enable']:
    return {'status': 'blocked', 'readiness': evidence, 'state': before}
after = session.mutate(thread, 'on', provider, model, expected_revision=before['revision'])
```
- [ ] **Test first/default enablement, no duplicate server, off/status with a crashing check stub, failed check preserving byte-identical state, dashboard failure retaining enabled state, and off during preflight including when the initial state was already off.** Setup returns only provider/readiness summaries, not auth source contents or full model lists.
- [ ] **Run focused tests green; commit:** `feat: add guided delegation setup runtime`.

### Task 5: Codex usage observations and exact-model cost evidence

**Files:** Create `scripts/codex_usage.py`, `scripts/pricing.py`, `tests/test_codex_usage.py`, `tests/test_pricing.py`; modify `scripts/activity.py` only to share identity-checked path resolution.

**Interfaces:**
- `CodexUsageReader.read(thread: str) -> dict` returns `{thread_id, harness:'codex', model, status, samples, quota, coverage, observed_at}`.
- Usage sample: `{id, at, model, input, cache_read, output, reasoning, context_tokens, context_limit, context_percent, coverage}`; input includes cached input if host does, reasoning is a subset of output when reported that way.
- `counter_delta(previous: dict | None, current: dict) -> dict | None`: reject negative deltas; no baseline produces unknown consumption.
- `pricing.estimate(sample: dict, catalogue: dict) -> dict`: `{usd:float|None, priced:bool, source:str|None, as_of:str|None}`.
- Exact price entries: `{input_per_million, cached_input_per_million, output_per_million, currency:'USD', source, as_of}` under exact model keys. Unverified entries are rejected.

- [ ] **Write counter and cost tests:**
```python
def test_counter_reset_is_not_new_consumption(self):
    self.assertIsNone(codex_usage.counter_delta({'input_tokens':100}, {'input_tokens':20}))

def test_unpublished_model_has_no_estimated_price(self):
    result = pricing.estimate({'model':'unpriced-exact-model', 'input':100, 'cache_read':20, 'output':10}, {})
    self.assertIsNone(result['usd'])
    self.assertFalse(result['priced'])
```
- [ ] **Run new tests red.**
- [ ] **Implement bounded incremental reading.** Reuse task identity checks, refuse symlinks/out-of-root files, cap each read at 8 MiB and lines at 1 MiB, retain at most 2048 usage samples per task and 64 tasks. Mark truncated history partial. File replacement/truncation resets parser/counter baseline. Retry incomplete final JSON lines; never include reasoning text or user content in telemetry. Repeated cumulative counters produce no second charge. Attribute deltas across a model change only when per-response evidence establishes the model; otherwise keep model/cost unknown.
```python
uncached = sample['input'] - sample['cache_read']
if uncached < 0:
    return {'usd': None, 'priced': False, 'source': None, 'as_of': None}
usd = (uncached * rates['input_per_million'] + sample['cache_read'] * rates['cached_input_per_million']
       + sample['output'] * rates['output_per_million']) / 1_000_000
```
- [ ] **Wire quota observation.** Inspect the installed Codex app-server schema using `codex app-server generate-json-schema --help` and its documented output option, then locate the read-only account/rate-limit method. If supported, use only initialize and quota-read messages with bounded lifetime, no thread/model creation. Capture fake protocol fixtures without credentials. On unsupported versions use recorded rate-limit events with observation age and stale status. Never call the orchestrating agent periodically. No published price for the current model is an expected unavailable state; verify official prices before shipping any catalogue entry.
- [ ] **Test no-worker tasks, missing baseline, duplicate counts, model change, compaction, rotated/mismatched logs, concurrent tasks, cached-input accounting, reasoning subset, unknown capacity, primary/secondary/named rate limits, stale reset and offline/unsupported quota protocol.** Fixtures contain synthetic metadata only. Aggregate parent usage separately from any native child metadata.
- [ ] **Run Codex usage/pricing/activity tests green; commit:** `feat: observe orchestrator usage without inference`.

### Task 6: Authenticated task-aware APIs and conditional collection

**Files:** Create `scripts/dashboard_api.py`, `tests/test_dashboard_api.py`; modify `scripts/dashboard.py`, `scripts/account_usage.py`, `tests/test_dashboard.py`.

**Interfaces:** `DashboardAPI` is constructed with state/readiness/setup/host-usage/account readers; `handle(method, path, query, body) -> (status_code, payload)` consumes validated JSON. Keep transport authorization/content limits in `dashboard.py`.

Routes:
```text
GET  /api/context?thread=UUID       -> state, known task title, provider summaries
POST /api/delegation               -> thread, action, provider?, model?, revision
POST /api/providers/check          -> thread, provider, model?, revision
GET  /api/orchestrator?thread=UUID  -> CodexUsageReader result
GET  /api/account-usage?thread=UUID -> eligible account evidence or hidden state
GET  /api/account-usage?scope=all   -> evidence only if any saved task is eligible
GET/POST /api/settings             -> versioned settings from Task 3
```
Do not return a quota body for an ineligible task. Existing `/api/activity` and
`/api/messages` allow a registered worker task, saved task state or the explicitly
registered dashboard launch task; UUID syntax alone is not authorization to scan
all logs. Validate requested identity against log metadata before observation.

- [ ] **Write a spy-based no-Claude test:**
```python
def test_off_task_never_queries_claude(self):
    account = Mock()
    api = self.api_for_off_task(account_reader=account)
    status, body = api.handle('GET', '/api/account-usage', {'thread':self.thread}, None)
    self.assertEqual(status, 200)
    self.assertFalse(body['visible'])
    account.read.assert_not_called()
```
`api_for_off_task` is a test fixture constructing the real handler with temporary
state and injected readers; it must not mock the eligibility decision itself.
- [ ] **Run `test_dashboard_api.py` red.**
- [ ] **Implement routes and eligibility.** Selected task enabled plus successfully connected Claude evidence is required; All tasks scans only validated switch records. A transient failure after success is stale; explicit rejection hides current quota and stops automatic polling. Readiness cache misses do not invoke every provider. POST checks are deliberate and task-scoped; activation is the shared SetupService.
```python
visible = bool(state['providers'].get('claude', {}).get('enabled') and connection['connected'])
if not visible:
    return 200, {'visible': False, 'reason': 'not_enabled_or_connected'}
return 200, {'visible': True, **account_reader.read()}
```
`connection['connected']` is derived from the last successful subscription evidence;
clear it on explicit rejection/account identity change, preserve it through a
transient unavailable check. Persist no raw account identity or credentials.
- [ ] **Test selected-vs-launch task mutation, invalid/missing UUID, unrelated logs, first-run task without workers, stale revision -> 409, foreign Host/Origin -> 403, missing bearer -> 401, oversize body -> 413, unsupported media -> 415 and valid static icon/module responses.** Keep generic safe error messages while returning actionable normalized readiness codes.
- [ ] **Run dashboard/API/account tests green; commit:** `feat: expose task-aware setup and telemetry APIs`.

### Task 7: Branded navigation and provider settings views

**Files:** Modify `assets/dashboard/index.html`, `settings.html`, `app.js`, `style.css`, `settings-ui.mjs`; create `client.mjs`, `navigation.mjs`, `overview-ui.mjs`, `workers-ui.mjs`, `connections-ui.mjs`, `tests/dashboard-navigation.test.mjs`; update static route allowlist in `scripts/dashboard.py`.

**Interfaces:**
- `client.api(path, options={}) -> Promise<object>` reads local fragment bearer without logging it.
- `navigation.resolveView(params: URLSearchParams) -> 'overview'|'workers'|'usage'|'connections'` and `linkFor(view, params) -> string` preserve task/filter fragment fields.
- Each view exports `mount(root, context) -> {update(data), destroy()}`; context supplies `api`, current filters/task and explicit change callbacks. Destroy cancels timers/listeners and ignores stale asynchronous results.
- `connections-ui.mjs` uses `/api/delegation` and `/api/providers/check`, with displayed task UUID bound to every write and current revision.

- [ ] **Write pure navigation tests:**
```javascript
test('old filtered links remain worker views', () => {
  assert.equal(resolveView(new URLSearchParams('period=message&message=29153')), 'workers');
});
test('new links retain task and message identity', () => {
  const link = linkFor('usage', new URLSearchParams('thread=task&conversation=chosen&message=7'));
  assert.equal(new URLSearchParams(link.split('#')[1]).get('message'), '7');
});
```
- [ ] **Run `node --test plugins/tafwid/skills/delegate/tests/dashboard-navigation.test.mjs` red.**
- [ ] **Implement shared shell and focused views.** Use `<img src="/brand/icon.png" alt="">` and an explicit favicon route backed by `plugins/tafwid/assets/icon.png`. Shared navigation is a semantic nav with current-page indication. Move worker list/detail handlers into `workers-ui.mjs`, keep activity module, and put active work/attention above history on Overview. Default new setup link uses `view=overview`; legacy `/settings` selects Connections & Settings.
- [ ] **Implement provider/settings controls.** Provider cards show harness, readiness, selected model, task enablement and default badge. Explicit checks and on/default/off use shared endpoints. Preserve unsaved draft fields on 409 and offer reload; don't erase draft automatically. Only enable buttons for actionable inputs. Settings model pickers display inactive routes rather than silently deleting them.
```javascript
await api('/api/delegation', {method:'POST', body:JSON.stringify({
  thread:context.thread, action:'default', provider:selectedProvider, revision:state.revision
})});
```
- [ ] **Run navigation tests plus existing dashboard tests.** Start a synthetic local server and visibly inspect desktop/mobile navigation, logo, first-run/no-Claude Overview, provider readiness/default selection and stale-tab conflict. Verify heading/card alignment, keyboard focus, no horizontal overflow and no background account fetch on Overview for an off task.
- [ ] **Commit:** `feat: organize Tafwid dashboard into focused views`.

### Task 8: Message picker and orchestrator/usage presentation

**Files:** Create `assets/dashboard/message-picker.mjs`, `usage-ui.mjs`, `tests/message-picker.test.mjs`, `tests/orchestrator-view.test.mjs`; modify `scripts/activity.py`, `tests/test_activity.py`, `assets/dashboard/overview-ui.mjs`, `style.css`, `snapshots.mjs`, `activity-ui.mjs`.

**Interfaces:**
- `clean_preview(text: str) -> str` in `activity.py`: decode entities, replace Markdown links with their labels, preserve wrapper filtering and 240-character cap.
- `message-picker.mount(root, {messages, selected, onSelect}) -> {update, destroy}`; selection emits original message line ID, never an array index.
- Pure `searchMessages(messages, query) -> array`, `usage-ui.orchestratorTotals(samples, range, catalogue) -> dict`, `overview-ui.orchestratorSummary(data) -> dict` for DOM-independent tests.
- Metrics state carries `coverage`, `observed_at`, `priced_samples` and `samples`; empty is unknown, never zero consumption without evidence.

- [ ] **Write message and summary tests:**
```python
def test_preview_keeps_skill_label_without_path(self):
    text = 'Use [$archivist:walkthrough](/private/skill/SKILL.md)&#x20; please'
    self.assertEqual(activity.clean_preview(text), 'Use $archivist:walkthrough please')
```
```javascript
test('message search preserves identity', () => {
  const rows = [{line:7, preview:'Work on slice 2', timestamp:100}];
  assert.equal(searchMessages(rows, 'slice')[0].line, 7);
});
test('unknown orchestrator model stays unknown', () => {
  assert.equal(orchestratorSummary({model:null, coverage:'unavailable'}).modelLabel, 'Model not recorded');
});
```
- [ ] **Run new tests red.**
- [ ] **Implement picker as a labelled dialog/popover with search, date groups and constrained list height.** Use real buttons/options and textContent. Arrow keys move active option, Enter commits original ID, Escape closes and returns focus. Mobile uses the same dialog behavior with viewport-contained layout. Maintain selected ID when filtering and explain when an old boundary is unavailable.
- [ ] **Implement compact orchestrator card and Usage view.** Separate host consumption/context from worker summaries and entire-account windows. Reuse sample filtering and known/partial coverage. Display exact-model price provenance in details, not as a subscription charge. Move existing snapshots and run totals off Overview. Poll only mounted view data; account windows require server eligibility. Account reset countdown is local, no inference.
```javascript
card.append(node('span', 'model', summary.modelLabel));
card.append(node('span', 'metric', summary.tokensLabel));
// node() creates an element and assigns textContent; never inject log text as HTML.
```
- [ ] **Test encoded entities, skill links, literal markup, long Unicode text, no matching messages, missing selected ID, stale asynchronous task responses and duplicated token samples.** Visibly exercise picker with keyboard and touch-sized mobile layout, context decreases, partial pricing, unknown model, expired limits, and unchanged account totals while worker filters change.
- [ ] **Run activity, message-picker, orchestrator-view and existing snapshot tests green; commit:** `feat: clarify orchestrator metrics and message selection`.

### Task 9: Skill entry behavior and documentation

**Files:** Modify `skills/delegate/SKILL.md`, `skills/dashboard/SKILL.md`, `skills/settings/SKILL.md`, delegate `references/workflow.md`, `references/model-selection.md`, `references/dashboard.md`, `references/opencode.md`; add delegate `references/setup.md`; update `README.md`, `docs/migration.md`, `docs/architecture.md`, `docs/roadmap.md`, `CHANGELOG.md`, audit and next decision record if architecture changes warrant it. Add `tests/test_management_contract.py` and scenario notes to the plan's acceptance record.

**Interfaces:** Entry point interprets management syntax through `setup.py`; bare invocation asks action through the host native question tool, then only missing provider/model. Detailed setup reference loads only for setup; assignment loads existing workflow. Task status checks remain cheap and do not invoke setup questions.

- [ ] **Write a runtime contract test** with the real CLI/fake provider:
```python
def test_bare_cli_requests_action_without_enabling(self):
    result = subprocess.run([sys.executable, str(self.setup_script)], env=self.env,
                            capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    self.assertEqual(data['status'], 'needs_input')
    self.assertIn('action', data['missing'])
    self.assertFalse(session.status()['enabled'])
```
Keep `self.env` and in-process CODEX_HOME/task patches identical in this fixture.
- [ ] **Run the runtime contract test and verify its result, then update the skill instructions and exercise the changed prompt behavior:**
```text
Management grammar: action [provider] [model]. A bare invocation collects On/Off
with the host question tool. Collect only fields reported missing by setup.py.
Use text choices only when native questions are unavailable. Successful on opens
the returned dashboard URL once through the host's browser-opening tool.
An argument-complete command does not require preference reconfirmation.
```
Do not make the native question tool name specific to one host in shared runtime.
For Codex, use its available request-user-input tool. Preserve one-shot assignment
semantics and independent acceptance review.
- [ ] **Exercise actual skill behavior** with isolated temporary homes and fake providers: bare, on only, complete on/provider/model, default, provider off, all off, status, unsupported provider, missing model and supplied work assignment. Use the writing-skills workflow's behavioral evaluation if available; record what was actually observed. String-search tests alone do not prove prompt UX. Do not dispatch a paid/live worker merely to test the entry point.
- [ ] **Update documentation** to reference the single setup/dashboard homes and exact new semantics, including stale/unknown data, host telemetry coverage, local connection references, legacy writer retirement and dashboard restart. Avoid presenting planned hosts/providers as implemented.
- [ ] **Run contract/package/link checks green; commit:** `docs: explain provider-aware setup and dashboard usage`.

### Task 10: Integrated acceptance, review and local rollout

**Files:** Modify `Makefile`, `.github/workflows/ci.yml` if needed for new test discovery, `VERSION`, `.codex-plugin/plugin.json` under the plugin, release notes and documentation audit. Create `tests/test_provider_journey.py` under the delegate skill.

**Interfaces:** Existing `make test` remains the full offline gate; Node command expands to `node --test plugins/tafwid/skills/delegate/tests/*.test.mjs`. Use the exact version `0.3.0` for this behavioral/state upgrade in every release manifest. Local cachebuster suffix stays out of release sources.

- [ ] **Write the integrated journey test** using a real temporary HTTP server and fake harness processes: off -> enable Claude -> enable OpenRouter -> change default -> select task route -> launch fake worker -> off while pending -> no next spawn -> retained worker history. Verify an unrelated task is byte-identical and no-Claude setup never calls the Claude executable.
- [ ] **Run the journey red, fix only demonstrated integration gaps, then green.** Require worker registry backend/model identity to match the resolver, not only the UI selection.
- [ ] **Run complete verification:**
```bash
python3 scripts/check_package.py
python3 -m unittest discover -s plugins/tafwid/skills/delegate/tests -v
node --test plugins/tafwid/skills/delegate/tests/*.test.mjs
git diff --check
```
Use direct recipe commands if the system make launcher is unavailable; do not
accept an OS license or alter unrelated machine setup. Validate the plugin using
the installed plugin-creator validator and its required Python environment.
- [ ] **Perform visible desktop/mobile acceptance** at 1440x1000 and 390x844: Overview, Workers, Usage, Connections; first-run/no-Claude; multiple providers/default; keyboard picker; narrow long titles; partial/unknown metrics; account rejection; stale edits; legacy deep links. Preserve synthetic screenshots outside Git, record actual outcomes and limitations in the audit.
- [ ] **Obtain independent whole-change review** of migration, provider gating, launcher races, quota privacy, counter attribution and keyboard/mobile UX. Address concrete findings and repeat affected tests. No branch completion claim before the full final checks on the reviewed code.
- [ ] **Commit release/documentation state**, then locally install with the plugin-creator flow after verifying the user's marketplace path. Compare installed source files to the accepted commit, restart only the verified old dashboard process, preserve worker processes, and open the updated task Overview. Real provider activation remains a user choice; do not turn it on for a smoke test.
- [ ] **Report local commit, checks, installed version and remaining limits.** Do not push/merge/publish without authorization for this new release.

## Plan self-review and handoff

Coverage: commands/state/readiness/routing are Tasks 1–4; telemetry and costs are
Task 5; conditional account collection and safe API writes are Task 6; all ten UX
requests are represented across Tasks 7–9; migration, tests and rollout close in
Task 10. Review Focus scenarios each have an owning task and a test case.
Interfaces use provider IDs independently of harness IDs; both fake clients and
live adapters preserve that distinction. No extra supervisor agent or periodic
GPT polling is introduced.

Recommended execution: native implementation in this task, followed by independent
whole-change review. State, routing, setup and UI share interfaces, so keeping one
implementation context reduces repeated loading while retaining final review.
Subagent-driven task/review cycles remain available if the user prefers them.
Implementation begins only after the user reviews this plan and selects execution.
