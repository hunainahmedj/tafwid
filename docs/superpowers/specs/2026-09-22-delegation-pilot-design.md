# Tafwid delegation pilot

Date: 2026-09-22
Status: Approved for implementation planning after the compact brief review.
Candidate: `feature/provider-dashboard` at `f867b2303ede5f0c5c3703e20e673b961328901f`.

## Purpose

Watch the candidate Tafwid release perform real work before merging. Compare
Codex working directly with Codex delegating through Tafwid, measuring Codex
usage, worker usage, elapsed time, correctness, recovery and dashboard usability.
The user agreed to a pilot with a bug fix, a small feature, and a correction/resume
task. The user approved the compact brief and proceeding; no live evaluations have run.

The first result is six measured trials (three tasks in two modes), a visible
dashboard walkthrough, and a comparison report. These are an initial diagnostic
sample, not a statistically reliable estimate of typical savings or error rate.
Preserve the task definitions and execution recipe for later repetitions.

## Controlled workload

Use a small, standard-library Python task-tracker project with synthetic records.
Each task has its own immutable starting snapshot, public brief and smoke tests.
Keep the acceptance evaluator outside the agent's editable workspace. Run it
against the produced files in a fresh verification environment; do not trust
worker-written test results as acceptance evidence. Do not provide the reference
implementation or another trial's output to either mode.

The fixture project keeps this first experiment easy to reset and inspect. Its
results describe these workloads; a later suite should add representative real
project work before making broad performance claims.

### Task 1: repair pagination

Starting state: a task-list library and JSON CLI with a pagination defect at page
boundaries. The public smoke tests cover only the first page.

Brief: "Fix task-list pagination. Pages are one-based. Return up to page_size
records in their original order, with no skipped or duplicated records between
pages. Empty input and pages beyond the end return an empty list. Reject a page
or page_size that is not a positive integer; booleans are invalid. Preserve the
CLI's documented JSON output and add regression coverage."

Acceptance: exact-multiple and partial final pages, empty input, out-of-range
pages, invalid arguments, unchanged input records, and library/CLI agreement.
All acceptance checks derive from this brief; there are no hidden requirements.

### Task 2: add task filtering

Starting state: a working task-list library/CLI with pagination but no filtering.

Brief: "Add filtering by status and owner to the task-list library and CLI.
Supported statuses are todo, doing and done. Filters combine with AND and run
before pagination. An omitted filter imposes no restriction; owner matching is
exact and case-sensitive. Preserve input order and existing behavior when no
filters are supplied. Invalid statuses produce the CLI's documented validation
error. Update the usage documentation and tests."

Acceptance: each filter alone, combined filters, no matches, filtering before
pagination, invalid status, existing behavior, and documented CLI invocation.
Codex must inspect the implementation and run relevant checks in both modes.

### Task 3: complete and resume an export task

Starting state: a working task-list library/CLI without CSV export.

Initial brief: "Add CSV export with columns id,title,status,owner in that order.
Use a header row, preserve record order, correctly quote commas, quotes and
newlines, and export a missing owner as an empty field. Support an output file
through the CLI. Add tests and usage documentation."

At the end of the initial turn, deliver this same follow-up in both modes:
"Update export ordering: sort by status (todo, doing, done), preserving the
original order among tasks with the same status. Keep the remaining CSV behavior
unchanged and add regression tests."

This deliberately staged requirement guarantees a resume exercise without
depending on a model making a mistake. Record it as planned follow-up, not an
error. The direct mode resumes its Codex session. The delegated mode resumes
its Codex session and the same implementer worker through Tafwid. Verify worker
session continuity, new run recording and retained instructions. Acceptance checks
both phases; unplanned corrections are recorded separately.

## Two execution modes

Direct: Codex implements, reviews and verifies the task without worker agents.
Delegated: Codex prepares a bounded brief, invokes the candidate Tafwid runtime,
reviews the worker's changes and verifies the task. Corrections use the same
implementer; any independent worker reviewer must use a distinct session.

Use the same explicit Codex model, effort, task brief, starting files, acceptance
rules and available project tools for each pair. Record any unavoidable differences
in permissions or tools. Measure Tafwid instruction loading and orchestration as
part of the delegated mode. Use the candidate runtime directly without changing
the user's installed plugin. Keep benchmark state separate from ordinary history.

Before live execution, resolve and record the intended Codex configuration and
Tafwid worker routing, requested and observed model IDs where available, harness
versions, relevant instruction hashes, permissions, fixture hash and candidate
revision. Freeze these across the pilot. No silent model/provider fallback.

Run trials sequentially in fresh workspaces and fresh sessions, alternating which
mode goes first across tasks. A two-phase trial retains its own sessions between
phases. Do not reuse another trial's conversation or edited files. Record start
times and exposed cache usage; provider-side caching cannot be guaranteed cold.

Initial proposed limits: 15 minutes of active execution per trial and at most two
unplanned correction rounds. The CSV follow-up is not a correction round. Stop on
quota/authentication failures and record the outcome. These limits bound work,
not subscription billing or token spending. Final model/provider selection and
the concrete launch recipe belong in the implementation plan before execution.

## Measurement and scoring

- Codex: input, cached input, output and reasoning usage with source and coverage.
- Workers: the same available usage fields, separately by provider/model and run;
  include implementer resumes and any reviewer calls.
- Do not add cached input to input, or reasoning to output, if the provider counts
  them as subsets. Preserve provider semantics and unknown fields.
- Report Codex reduction as `(direct - delegated) / direct`, only for comparable,
  complete, nonzero-denominator measurements. Report input/output breakdowns and
  any total's definition. Negative savings remain visible.
- Report worker usage alongside Codex usage. Cross-provider token sums are a
  descriptive volume, not equivalent cost or subscription quota consumption.
- Measure monotonic elapsed time from prompt submission through final acceptance,
  including delegation, waits, review and corrections. Record dashboard inspection
  or human pauses separately and exclude them consistently from active time.
- Record acceptance pass/fail, first-attempt outcome, failed checks, unplanned
  correction rounds, runtime failures, timeouts and incomplete trials separately.
  Preserve failed trials in the denominator; do not silently replace them.
- Distinguish task defects from authentication, rate-limit, harness and evaluator
  failures. A worker's `completed` status is not a correctness score.

Capture evidence from the measured sessions, not this planning conversation or
account-wide quota percentages. The candidate dashboard derives token deltas from
observations and can lack an initial baseline. Reconcile its observations with
complete native run totals when available; otherwise mark coverage partial and
withhold percentage savings. Check the actual native event format during the
runner's instrumentation validation before trusting any comparison.

## Dashboard walkthrough

Use the candidate dashboard against benchmark-specific state and actual delegated
runs. Show provider/default setup, worker launch, running/completed states, run
details, usage, filters and the two-phase resume history. Check disabling delegation
preserves existing history without launching an extra worker.

Perform visible desktop and mobile passes. Record whether each user journey can be
completed, confusing labels, missing/error states, keyboard behavior, overflow and
whether displayed usage matches its stated scope. Attribute worker elapsed time
and end-to-end task elapsed time correctly. Keep a brief issue list with steps to
reproduce and local screenshots. Automated checks support this review; they do not
establish human usability on their own. The user can add observations while watching.

## Artifacts and boundaries

Version the fixture source, briefs, evaluator, manifest format and replay commands.
Keep raw run artifacts, transcripts and local configuration outside tracked files.
Provide a compact Markdown comparison table with links to private local evidence,
dashboard findings and an explicit merge recommendation with remaining uncertainty.
Export only intentionally sanitized results into repository documentation.

For this pilot, compare delegation off/on using the candidate version. Comparing
the previous and candidate plugin versions, repeated statistical experiments,
provider/model matrices, CI performance thresholds and a benchmark dashboard are
follow-ups. Merge, release and installation changes are outside this experiment.

## Completion criteria

All three fixtures can be reset and rerun independently. Both modes have recorded
outcomes for every task, including unsuccessful trials. The evaluator checks the
same requirements in both modes. Every metric states its source and coverage.
The report explains which conclusions the evidence supports, identifies observed
regressions, and includes the desktop/mobile walkthrough results. Any blocked live
trial is reported explicitly; synthetic data is never presented as live evidence.
