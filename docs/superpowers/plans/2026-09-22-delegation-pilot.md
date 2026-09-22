# Tafwid Delegation Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended for this plan) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run three reproducible tasks with and without Tafwid, inspect the candidate dashboard in action, and produce an evidence-backed comparison before merge.

**Architecture:** A contributor-only Python runner prepares immutable fixtures, launches measured Codex sessions, evaluates their outputs independently, and writes private trial artifacts. Delegated sessions invoke the pinned candidate runtime through a small wrapper using isolated Tafwid state. A report compares paired outcomes and a visible browser pass exercises the real dashboard.

**Tech Stack:** Python 3.10+ standard library, unittest, Git, installed Codex and Claude Code CLIs, candidate Tafwid Python runtime, approved visible browser tooling.

**Spec:** [Delegation pilot design](../specs/2026-09-22-delegation-pilot-design.md).

## Global Constraints

- Candidate: `f867b2303ede5f0c5c3703e20e673b961328901f` on `feature/provider-dashboard`.
- "Use a small, standard-library Python task-tracker project with synthetic records."
- "Keep the acceptance evaluator outside the agent's editable workspace."
- "Use the candidate runtime directly without changing the user's installed plugin."
- "Keep benchmark state separate from ordinary history."
- "No silent model/provider fallback."
- "15 minutes of active execution per trial and at most two unplanned correction rounds."
- "The CSV follow-up is not a correction round."
- "Preserve failed trials in the denominator; do not silently replace them."
- "Do not add cached input to input, or reasoning to output, if the provider counts them as subsets."
- "Merge, release and installation changes are outside this experiment."
- Ordinary tests use fake executables and temporary homes. Live evaluation is a separate explicit CLI operation, never part of `make test`.
- Implement benchmark tooling natively if the user accepts the recommendation; measured delegation is a separate experimental condition and does not enable this planning task's switch.

## Review Focus

1. Truncated/duplicate completion events: missing usage remains unknown and repeated events are not summed twice (Task 2).
2. Two-phase trials: session usage counters may be cumulative; count each invocation exactly once and verify implementer identity survives resume (Tasks 2–3).
3. An orchestrator exits while its worker is running: identify and stop only trial-owned processes, preserve partial evidence, and prevent overlapping writers (Task 3).
4. An agent modifies public tests or output contains a syntax error: independent acceptance still fails correctly; evaluator failures are separately classified (Task 1).
5. Isolated dashboard state lacks native Codex rollouts or account auth: import only known benchmark-session evidence; explicitly label unavailable account information (Task 4).

## Execution configuration

Read-only discovery found Codex CLI `0.147.0`, saved model `gpt-6-astra`, and effort
`high`. Saved Tafwid task routing selects Claude `opus` for implementation/debugging
at `medium` effort. Freeze these as the initial run configuration; do not change
the user's global settings. Record installed versions again immediately before
the pilot and requested/observed model identities separately. If unavailable,
report the blocker instead of picking another model.

Use a new implementation worktree/branch `codex/delegation-pilot` based on the
candidate commit after plan review. Transfer only the approved spec and plan into
that worktree. The runner must accept an explicit candidate checkout so its own
new commits do not silently change the version being measured. The existing
candidate checkout must remain clean and at the pinned revision during trials.

A parent-controlled private directory outside the Git checkout stores the run
manifest, fresh trial workspaces, JSONL streams, evaluations, screenshots and
isolated Tafwid state. Use restrictive permissions on that directory. No private
paths or transcripts go into tracked examples or public reports automatically.

## File map

Create under `benchmarks/` (contributor tools, outside the distributable plugin):

- `README.md`: offline tests, preparation, live execution, resume, report and walkthrough commands.
- `__init__.py`: package marker.
- `tasks.py`: task IDs, fixture selection, briefs and planned follow-up.
- `fixtures/base/{tasklist.py,README.md,test_smoke.py}`: working list/pagination project.
- `fixtures/pagination/tasklist.py`: intentionally defective override for Task 1.
- `evaluate.py`: independent library/CLI acceptance checks and bounded evaluation subprocess.
- `usage.py`: evidence parsing, normalization, coverage and comparison rules.
- `runner.py`: prepare/run/resume lifecycle, limits, manifests and process ownership.
- `delegate.py`: measured session wrapper for the pinned Tafwid runtime and isolated state.
- `report.py`: paired Markdown report and dashboard evidence staging.
- `tests/test_fixtures.py`, `tests/test_usage.py`, `tests/test_runner.py`, `tests/test_report.py`: offline benchmark-tool regression tests.

Modify `Makefile` to expose `test-benchmarks` and include its offline tests in
`test`; modify `CONTRIBUTING.md` to document the opt-in live pilot. No dashboard
product changes are included. Observed candidate defects become explicit findings.

## Task 1: Reproducible fixtures and independent acceptance

**Files:** `benchmarks/__init__.py`, `tasks.py`, fixture files, `evaluate.py`, `tests/test_fixtures.py`.

**Interfaces:**
- `tasks.prepare(task_id: str, destination: Path) -> dict`: reject existing nonempty destinations; return task ID, fixture hash and brief text.
- `tasks.followup(task_id: str) -> str | None`: return the exact CSV follow-up from the spec, otherwise `None`.
- `evaluate.run(task_id: str, workspace: Path, phase: int, timeout: float = 30) -> dict`: return `status`, `checks`, `passed`, `total`, `duration_seconds`; check entries contain `name`, `passed`, and a bounded diagnostic.
- Evaluation statuses are `accepted`, `rejected`, `evaluator_error`, `timeout`. Agent syntax/import errors are rejection; broken evaluator infrastructure is `evaluator_error`.

- [ ] Define `tasklist.py`'s public interface and include it in fixture README: `paginate(records, page=1, page_size=20)`, `select(records, status=None, owner=None, page=1, page_size=20)`, and `export_csv(records, output_path)` for the export task. CLI is `python3 tasklist.py list INPUT --page N --page-size N` plus requested `--status`/`--owner`, and `python3 tasklist.py export INPUT --output OUTPUT`. Successful list output is a JSON array; validation is exit 2 with a diagnostic on stderr.
- [ ] Write failing fixture tests demonstrating the key invariant:

```python
def test_pagination_fixture_is_reproducible_and_fails_acceptance(self):
    first = tasks.prepare('pagination', self.root / 'first')
    second = tasks.prepare('pagination', self.root / 'second')
    self.assertEqual(first['fixture_hash'], second['fixture_hash'])
    result = evaluate.run('pagination', self.root / 'first', phase=1)
    self.assertEqual(result['status'], 'rejected')
    self.assertTrue(any(not check['passed'] for check in result['checks']))
```

- [ ] Run `python3 -m unittest discover -s benchmarks/tests -p test_fixtures.py -v`; verify failure is due to the absent implementation, not test setup.
- [ ] Implement byte-for-byte fixture copying and content hashing with relative filenames in deterministic order. Copy the working base first and apply the pagination override only for that task. Public smoke tests must pass in each starting fixture; target acceptance must fail before work begins.
- [ ] Implement acceptance from the spec: pagination boundaries/validation/nonmutation; combined filtering before pagination; CSV quoting/missing owner and stable status sorting in phase 2. Exercise library and subprocess CLI calls. Check required docs and public regression coverage by inspection; record that evidence separately from automated checks.
- [ ] Keep evaluator code/reference outcomes outside all measured workspaces. Execute the evaluator against a snapshot of output files in a fresh temporary verification directory, with a subprocess timeout and no use of agent-modified public tests as the oracle. This separates evaluation integrity from OS-level containment; do not claim a hostile-code sandbox.
- [ ] Add tests for empty input, booleans as pagination arguments, commas/quotes/newlines in CSV, stable equal-status ordering, agent-modified smoke tests, and syntax errors. Use test-local known-correct variants to show acceptance can pass and targeted mutants to show each requirement can fail.
- [ ] Rerun the fixture tests; inspect the exact task briefs for agreement with the approved spec. Commit the fixture/evaluator changes.

## Task 2: Usage evidence and comparison semantics

**Files:** `benchmarks/usage.py`, `tests/test_usage.py`.

**Interfaces:**
- `codex_invocation(events: list[dict]) -> dict`: usage from one CLI invocation, with `input`, `cache_read`, `output`, `reasoning`, `total`, `coverage`, `source`.
- `worker_invocation(summary: dict) -> dict`: normalized usage for one Tafwid run, retaining backend cost semantics, invocation ID and partial status.
- `aggregate(invocations: list[dict]) -> dict`: sum unique invocations; incomplete coverage propagates. Unknown values remain `None`.
- `savings(direct: dict, delegated: dict) -> float | None`: percentage using a documented comparable Codex total only when both totals have complete coverage and the direct denominator is positive.

- [ ] Write tests for complete synthetic native CLI `turn.completed` usage and its precise adapter contract. The initial supported shape is `usage.input_tokens`, `usage.cached_input_tokens`, `usage.output_tokens`; leave absent reasoning unknown. Validate this shape against the actual first measured invocation before publishing comparisons.

```python
def test_codex_cache_is_a_subset_not_extra_tokens(self):
    events = [{'type': 'turn.completed', 'usage': {
        'input_tokens': 100, 'cached_input_tokens': 40, 'output_tokens': 20}}]
    value = usage.codex_invocation(events)
    self.assertEqual(value['total'], 120)
    self.assertEqual(value['cache_read'], 40)
    self.assertIsNone(value['reasoning'])

def test_missing_completion_cannot_produce_savings(self):
    absent = usage.codex_invocation([])
    self.assertIsNone(usage.savings(
        {'total': 120, 'coverage': 'complete'}, absent))
```

- [ ] Run the focused tests and observe them fail before adding the parser.
- [ ] Implement nonnegative finite numeric validation (reject booleans), explicit event/source support and unknown coverage for unrecognized formats. If multiple ambiguous completion events occur within one invocation, do not guess a sum; flag the invocation for reconciliation.
- [ ] Keep separately captured resume invocations as separate units. Do not sum cumulative rollout counters and CLI completion totals together. If a source proves cumulative across resumes, use validated boundary deltas and label the evidence; otherwise mark unknown.
- [ ] Normalize worker usage from the pinned candidate's per-run summary. Retain reported versus API-equivalent cost labels; do not convert subscription quotas to dollars. Explicitly preserve the provider-specific relationship of cache counters to input totals.
- [ ] Add tests for malformed/truncated events, duplicate events/run IDs, missing usage, zero denominator, negative savings, failed partial runs, counter resets and resumed cumulative totals. Add a case with unknown worker cost and complete Codex usage to ensure worker unknowns do not fabricate cost or suppress valid Codex-only accounting.
- [ ] Run the focused tests and commit.

## Task 3: Trial preparation, isolated dispatch and resume

**Files:** `benchmarks/runner.py`, `delegate.py`, `tests/test_runner.py`.

**CLI:**

```text
python3 -m benchmarks.runner prepare --candidate PATH --output PATH
python3 -m benchmarks.runner run --run-dir PATH --task pagination --mode direct --live
python3 -m benchmarks.runner run --run-dir PATH --task pagination --mode delegated --live
python3 -m benchmarks.runner run --run-dir PATH --task filtering --mode delegated --live
python3 -m benchmarks.runner run --run-dir PATH --task filtering --mode direct --live
python3 -m benchmarks.runner run --run-dir PATH --task export --mode direct --live
python3 -m benchmarks.runner run --run-dir PATH --task export --mode delegated --live
```

**Interfaces:**
- `runner.prepare(candidate: Path, output: Path) -> dict`: writes version-1 `manifest.json` with pinned revision/configuration, task hashes, run order and limits; does not launch inference.
- `runner.run_trial(run_dir: Path, task_id: str, mode: str, live: bool) -> dict`: immutable trial identity; returns terminal status and artifact locations. Existing completed trials cannot be overwritten.
- `delegate.py` forwards approved launcher arguments to the pinned candidate with the current measured Codex task identity and benchmark-only `CODEX_HOME`. It rejects candidate/state mismatches and does not mutate the planning task's delegation switch.

- [ ] Write lifecycle tests with fake Codex and Claude executables. Cover manifest creation without model calls, no `--live` refusal, reuse of an existing trial directory, and candidate dirty/revision mismatches.

```python
def test_live_execution_requires_explicit_flag(self):
    with self.assertRaisesRegex(ValueError, 'live'):
        runner.run_trial(self.run_dir, 'pagination', 'direct', live=False)
    self.assertFalse(self.fake_codex_marker.exists())
```

- [ ] Run the focused tests and confirm expected failures.
- [ ] Implement trial manifests containing mode/task/phase, fixture and prompt hashes, candidate commit, requested/observed models, tool versions, limits, UTC timestamps, monotonic durations, session/run identities, evaluation outcomes and usage evidence. Raw events are private JSONL; shareable manifests omit credential values and private configuration dumps.
- [ ] Launch Codex using argv arrays with `exec --json`, explicit `-m gpt-6-astra`, explicit `-c model_reasoning_effort="high"`, and `--sandbox workspace-write`. Keep the user's existing auth context; never copy credential files into benchmark state. Remove inherited parent task identity from the outer launch environment. Resume by the exact returned session ID, never `--last`. Use only flags confirmed in local CLI help.
- [ ] Give each mode a fresh workspace outside the Tafwid repository's inherited instructions. Supply the same project task brief and verification requirements. Mode instructions say to implement directly without other agents, or delegate through the exact candidate wrapper and retain independent Codex review. Explicitly state the fixture work is already authorized and needs no further design/plan approval. Record loaded instruction/config differences; do not silently advertise identical environments if personal plugins add asymmetric instructions.
- [ ] For delegated mode, load the candidate's actual workflow as measured context. Use Claude `opus`, `medium` effort, edit mode and explicit scoped permissions for required project commands. Use one-shot dispatch for the authorized benchmark worker; the wrapper keeps task-local identity intact. Record routing and any additional tool restrictions. Use benchmark-local settings rather than copying all personal configuration.
- [ ] Support normal non-inference preflight and normal account authentication without changing user settings. Any nested worker permission/network limitation is a failed infrastructure trial with diagnostics; do not silently switch to unrestricted access or another provider. Add only the specific benchmark state directory to allowed writable paths when required.
- [ ] Run independent evaluation after a turn. If rejected, supply bounded failure diagnostics and resume the same Codex session, at most twice. Deliver export's planned phase-2 instruction only after phase 1 is accepted. Keep evaluation and review time in active elapsed time. Reuse the same Tafwid implementer and verify recorded session continuity after every correction.
- [ ] Enforce the single 900-second active budget across all phases/corrections. Save process ownership metadata for the runner, Codex and spawned workers; on timeout/interruption, terminate only trial-owned processes and confirm no worker still writes before evaluating/snapshotting. Preserve partial results. Test with fake workers that outlive the orchestrator or ignore termination.
- [ ] Add tests for exact-session resume, planned-versus-unplanned follow-ups, all-failed trials, quota/auth failure stopping, malformed model events, orchestration completing without the required delegation, and altered workspace/candidate identities. A delegated trial without real worker evidence is invalid, not a zero-token success.
- [ ] Run all benchmark tests and commit the runner/dispatch changes.

## Task 4: Comparison report and visible dashboard evidence

**Files:** `benchmarks/report.py`, `tests/test_report.py`, `README.md`.

**Interfaces:**
- `report.render(manifest: dict, trials: list[dict]) -> str`: Markdown with per-task paired outcomes, source coverage, denominators, usage, elapsed time and findings.
- `report.stage_dashboard(run_dir: Path, session_id: str) -> dict`: stage only that verified benchmark Codex rollout in the isolated dashboard home and return dashboard start instructions. Reject unknown identities and symlink escapes.

- [ ] Write report tests before implementation:

```python
def test_failed_trial_remains_visible_without_false_savings(self):
    text = report.render(self.manifest, [self.accepted_direct, self.failed_delegated])
    self.assertIn('failed', text.lower())
    self.assertIn('unknown', text.lower())
    self.assertNotIn('100% saved', text)
```

- [ ] Implement a report with one paired row per task: acceptance, Codex input/cached input/output, worker usage by provider, active elapsed time, first-attempt result and correction counts. Show complete successful paired comparisons separately from failed/incomplete attempts; retain both in the report. Show savings only when compatible coverage permits; do not collapse quality and speed into a single score.
- [ ] Stage only known trial rollouts from the native Codex home into isolated dashboard `sessions` storage, verifying the leading session identity. Do not import unrelated history or credentials. Mirror complete lines during the visible live pass and keep the original evidence private; test truncation and changing source identity.
- [ ] Start the exact candidate dashboard using the isolated home. Open it visibly using the available approved browser skill. Its account-quota panel may be unavailable because benchmark state intentionally does not contain account credentials; record that limitation rather than copying auth or claiming a product defect.
- [ ] Write the walkthrough checklist: desktop 1440×1000 and mobile 390×844; Connections/default; running/completed worker; filters; details; usage labels/unknowns; planned resume; keyboard focus; overflow; off preserving history. Record reproducible observations/screenshots and whether each came from live work or deterministic setup-only actions.
- [ ] Add tests for partial usage, unmatched trial pairs, invalid staged identities, no unrelated transcript copying, and combined totals that accidentally double-count cache/reasoning. Run focused tests and commit.

## Task 5: Offline integration and instrumentation acceptance

**Files:** `Makefile`, `CONTRIBUTING.md`, `benchmarks/README.md`, benchmark tests.

- [ ] Add `test-benchmarks` and wire its fake-only suite into normal checks:

```make
.PHONY: test-benchmarks
test-benchmarks:
	$(PYTHON) -m unittest discover -s benchmarks/tests -v
```

- [ ] Document the exact CLI above, configuration, private artifacts, fake/live distinction, and how to replay a trial with a new repetition ID rather than overwriting results. Add an offline end-to-end test running fake direct/delegated trials through preparation, resume, evaluation and report generation.
- [ ] Run `make test` in the implementation worktree, including package integrity and candidate runtime/dashboard tests. Run `git diff --check`. Tests must neither call real providers nor modify the installed plugin. Commit the integration documentation and check wiring.
- [ ] Perform the required independent implementation review using the execution method selected by the user, then address findings and rerun only affected checks plus required final gates. A fresh review agent is for benchmark-tool acceptance, not a measured trial; exclude its usage from experimental totals.

## Task 6: Live pilot and findings

**Files:** private run artifacts and report; intentionally sanitized summary only if suitable for the repository.

- [ ] Resolve candidate checkout and verify clean pinned commit; capture tool versions. Perform readiness checks using the existing supported authentication. Prepare the private run directory and all fixture hashes before the first inference call.
- [ ] Run the pagination pair first using the CLI order above. Show the dashboard during the delegated trial. Validate that recorded Codex completion usage, worker per-run usage, task identity, acceptance results and elapsed boundaries are all present and interpreted correctly. Compare dashboard observations only within their actual coverage window; do not require a delta-only dashboard to equal a complete native total.
- [ ] If instrumentation is incompatible, preserve these attempts as diagnostic/invalid trials, fix it, and rerun the whole pair with fresh identities. Report the diagnostic attempts separately; never replace one member silently or label synthetic evidence live.
- [ ] Once instrumentation is valid, run filtering delegated/direct, then export direct/delegated. Deliver export's scripted follow-up, and finish desktop/mobile walkthrough evidence. Keep browser/human pauses separate from active task time.
- [ ] Render the private comparison report; inspect all six terminal outcomes and evaluator evidence. Explain small-sample limits, any missing metrics, model identity drift, permission differences and unresolved failures. Distinguish observed task failures from plugin regressions.
- [ ] Present the result table, usage/time differences, dashboard findings and whether the pilot found blockers to merge. Do not merge, push, release or change the installed plugin. If a provider blocks live execution, report the exact completed/blocked subset and preserve a runnable replay command.

## Plan self-review

The tasks cover fixture reproducibility, both execution modes, independent
acceptance, planned and unplanned resumes, token semantics, bounded execution,
private state, actual dashboard inspection and a final report. All five Review
Focus conditions have explicit offline tests assigned above. The initial live pair
is also the instrumentation validation point; the remaining four trials depend on
that evidence. UI observations are reported separately from task acceptance and
quantitative benchmark results. No new provider, billing claim or release change
is part of this plan.

## Execution handoff

Recommended: native implementation in this task, followed by one independent
review. The runner, measurement adapter and reporter share contracts; keeping
implementation together reduces coordination overhead for this small pilot.
Subagent-driven implementation remains an alternative if the user prefers a
fresh implementer and reviewer for each task. This choice governs building the
benchmark tools; it does not change the direct/delegated experimental conditions.
