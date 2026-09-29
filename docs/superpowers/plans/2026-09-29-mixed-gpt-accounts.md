# Mixed GPT Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a Tafwid task enable Claude and several named GPT accounts, then route each bounded worker assignment to one selected connection.

**Architecture:** A private account registry owns GPT CLI homes and login readiness. A task-local connection pool stores immutable connection IDs. The launcher resolves one connection per run and invokes either the existing Claude path or a new Codex CLI adapter; monitoring and acceptance remain shared.

**Tech Stack:** Python 3.10+, standard library, Codex CLI, Claude Code CLI, `unittest`, JSON state and JSONL worker events.

**Spec:** `docs/superpowers/specs/2026-09-29-multiple-gpt-accounts-design.md`

## Global Constraints

- Keep Claude working, including existing settings and saved run records.
- Keep credentials, raw worker data, and account homes outside Git; never read or print `auth.json` contents.
- Every automatic run names a connection in the task's enabled pool; never switch destinations after failure.
- Pool setup and explicit per-run routing ship now; automatic task splitting and balancing stay outside this release.
- `business` is user-confirmed metadata, not an assertion about a contract or workspace policy.
- Keep setup interactive: announce sign-in, use Codex's own login, ask the user to confirm account and workspace.
- Preserve the exact prompt copy approved in the spec. Present any new prompt-bearing diff to the user before editing that file.
- Give every new public script a purpose and privacy docstring, useful function docstrings, examples, outputs, exit codes, and side-effect-free `--help`.
- Tests use temporary homes and fake executables; do not make real model requests or change the installed plugin.
- Run `make test` and `python3 scripts/check_package.py` after runtime and package changes.

## File map

| File | Responsibility |
| --- | --- |
| `plugins/tafwid/skills/delegate/scripts/accounts.py` | Private account registry, isolated environment, and Codex login-method readiness. |
| `plugins/tafwid/skills/delegate/scripts/account.py` | Documented CLI for add, login retry, check, list, and confirmation. |
| `plugins/tafwid/skills/delegate/scripts/connections.py` | Task pool, legacy migration, connection resolution, and per-connection enablement. |
| `plugins/tafwid/skills/delegate/scripts/session.py` | User-facing on/off/status CLI over the pool. |
| `plugins/tafwid/skills/delegate/scripts/codex_cli.py` | Codex command construction, output schema, and JSONL/final-result validation. |
| `plugins/tafwid/skills/delegate/scripts/delegate.py` | Select one backend, launch or resume, save compact artifacts. |
| `plugins/tafwid/skills/delegate/scripts/run_state.py` | Backend-neutral run records for the existing waiter and hook. |
| `plugins/tafwid/skills/delegate/scripts/wait.py` | Include connection identity in compact completion evidence. |
| `plugins/tafwid/skills/account/SKILL.md`, `agents/openai.yaml` | Interactive account skill, using approved wording. |
| `plugins/tafwid/skills/delegate/SKILL.md`, `references/workflow.md`, `references/gpt-accounts.md` | Short agent guidance for pool routing and GPT workers. |
| `README.md`, `docs/architecture.md`, `docs/account-setup.md`, `docs/migration.md`, `CHANGELOG.md`, `VERSION`, `plugins/tafwid/.codex-plugin/plugin.json`, `scripts/check_package.py` | User guidance, compatibility, and package metadata. |

## Review Focus

1. An inherited API credential or workload-identity variable must not change the selected GPT account; Task 1 tests the child environment and readiness method.
2. A symlinked or duplicate account home must not redirect login or overwrite an existing account; Task 1 tests both.
3. An old enabled Claude task must keep Claude enabled after migration, while an old off task stays off; Task 3 tests both.
4. A resumed GPT run must reject a changed account ID even when the nickname matches; Task 5 tests that identity check.
5. Two workers finishing near the same time must remain distinguishable and observable through the waiter and hook; Task 6 tests concurrent run records.

---

### Task 1: Private GPT account registry and isolated login checks

**Files:**
- Create: `plugins/tafwid/skills/delegate/scripts/accounts.py`
- Test: `plugins/tafwid/skills/delegate/tests/test_accounts.py`

**Interfaces:**
- Produces: `create(name: str, kind: str) -> dict`, `get(name: str) -> dict`, `list_accounts() -> list[dict]`, `isolated_env(home: Path, base: Mapping[str, str] | None = None) -> dict[str, str]`, `check(account: dict) -> dict`, `confirm(name: str) -> dict`.
- `kind` is `personal` or `business`; stored records contain `id` (UUID), `name`, `kind`, `home`, and `status` (`pending` or `ready`).
- `check` returns the account record plus `login_method` (`chatgpt` or `unavailable`) and a concise `reason`; it never reads token contents or makes a model call.

- [ ] **Step 1: Write failing tests** for two personal names plus one Business name, duplicate/reserved names, owner-only separate homes, a symlinked home, missing CLI, missing auth cache, ChatGPT login, API login, and inherited `OPENAI_API_KEY`, `CODEX_API_KEY`, `CODEX_ACCESS_TOKEN`, `OPENAI_FEDERATION_RULE_ID`, and `OPENAI_IDENTITY_TOKEN_FILE`. Assert the fake CLI sees only its selected `CODEX_HOME` and no listed override. Assert the caller's default Codex home is untouched.
- [ ] **Step 2: Run** `python3 -m unittest plugins/tafwid/skills/delegate/tests/test_accounts.py -v`; expect failures for missing `accounts` interfaces.
- [ ] **Step 3: Implement** the interfaces in `accounts.py`. Accept lowercase ASCII nicknames matching `[a-z][a-z0-9_-]{0,31}`. Use `paths.state_root()/accounts`, atomic JSON writes, UUID directories, `0700` directories, a dedicated `config.toml` selecting file credentials, and `codex login status` in `isolated_env`. Require a regular `auth.json` file to establish file storage, without opening it. Preserve ordinary build environment variables while stripping inherited `OPENAI_*` and `CODEX_*` authentication selectors, then set only the target `CODEX_HOME`; preserve certificate paths explicitly. `confirm` rechecks the login method before saving `ready`.
- [ ] **Step 4: Run** the focused test command; expect all Task 1 tests to pass.
- [ ] **Step 5: Commit** the registry and tests with `git commit -m "feat: add private GPT account registry"`.

### Task 2: Interactive account command

**Files:**
- Create: `plugins/tafwid/skills/delegate/scripts/account.py`
- Test: `plugins/tafwid/skills/delegate/tests/test_account_cli.py`

**Interfaces:**
- Consumes: Task 1 `accounts` functions.
- Produces: `account.py add gpt [business] --name NAME`, `account.py login NAME [--device-auth]`, `account.py check NAME`, `account.py list`, and `account.py confirm NAME`. `add` creates a pending record and starts Codex login in its home; `confirm` is called only after the user's explicit answer in the skill.

- [ ] **Step 1: Write failing fake-CLI tests** that assert `add` invokes `codex login` in the new home, leaves an account pending, `login` retries the same home, `check` and `list` make no model call, `confirm` requires ChatGPT login, and `--help` creates nothing. Include private marker text in fake CLI output and assert it never enters public JSON errors.
- [ ] **Step 2: Run** `python3 -m unittest plugins/tafwid/skills/delegate/tests/test_account_cli.py -v`; expect missing-command failures.
- [ ] **Step 3: Implement** `main(argv: list[str] | None = None) -> int` with `argparse` subcommands. Include a module docstring with purpose, privacy boundary, examples, outputs, and exit codes; add function docstrings. Make login visibly interactive through the calling terminal. Return pending until `confirm`; never select the account for a task here.
- [ ] **Step 4: Run** the focused tests; expect pass.
- [ ] **Step 5: Commit** with `git commit -m "feat: add interactive GPT account setup command"`.

### Task 3: Task-local connection pool and legacy migration

**Files:**
- Create: `plugins/tafwid/skills/delegate/scripts/connections.py`
- Modify: `plugins/tafwid/skills/delegate/scripts/session.py`
- Test: `plugins/tafwid/skills/delegate/tests/test_session.py`
- Test: `plugins/tafwid/skills/delegate/tests/test_connections.py`

**Interfaces:**
- Consumes: Task 1 `accounts.get` and `accounts.check`; existing `claude_code.check_ready`.
- Produces: `read(task_id: str | None) -> dict`, `enable(task_id: str, selector: str) -> dict`, `disable(task_id: str, selector: str | None) -> dict`, and `resolve(task_id: str | None, selector: str | None, *, once: bool = False) -> dict`.
- Selectors are `claude` or `gpt:NAME`; stored IDs are `claude:default` or `gpt:<account-uuid>`. `read` returns `thread_id`, derived `enabled`, and a `connections` list. Automatic `resolve` with multiple enabled connections and no selector raises a clear ambiguity error.

- [ ] **Step 1: Write failing tests** for `on claude`, `on gpt NAME`, both together, two GPT accounts together, `off gpt NAME`, `off claude`, `off` all, one-shot resolution, ambiguous automatic routing, readiness failure preserving the previous pool, and the two legacy migration cases in Review Focus. Keep existing task-isolation and no-identity cases.
- [ ] **Step 2: Run** `python3 -m unittest plugins/tafwid/skills/delegate/tests/test_session.py plugins/tafwid/skills/delegate/tests/test_connections.py -v`; expect pool tests to fail.
- [ ] **Step 3: Implement** the pool in `connections.py` and adapt `session.py` parsing. Keep `session.py on` as a Claude-compatible alias. Read version-1 switches as Claude-only or off; write version-2 pool state atomically. Recheck a named connection before adding it. Make `status` read-only. Preserve `settings.py` Claude model routes and its existing schema.
- [ ] **Step 4: Run** the focused tests and `test_settings.py`; expect pass.
- [ ] **Step 5: Commit** with `git commit -m "feat: support task-local connection pools"`.

### Task 4: Codex CLI worker adapter

**Files:**
- Create: `plugins/tafwid/skills/delegate/scripts/codex_cli.py`
- Test: `plugins/tafwid/skills/delegate/tests/test_codex_cli.py`

**Interfaces:**
- Consumes: Task 1 `accounts.isolated_env` and `accounts.check`.
- Produces: `check_ready(account: dict, *, cwd: Path | None = None) -> dict`, `build_command(executable: str, *, cwd: Path, schema: Path, mode: str, model: str | None, session_id: str | None, output: Path) -> list[str]`, and `parse_result(events: Path, final_message: Path, *, exit_code: int, expected_session_id: str | None = None) -> dict`.
- `parse_result` returns `status`, `report`, `session_id`, and `models_used`; status is `completed`, `blocked`, or `needs_review`. The schema has only required `status` (`completed|blocked`) and nonempty `report`.

- [ ] **Step 1: Write failing tests** for fresh and resumed commands, read/edit sandbox settings, explicit model, JSONL `thread.started` and `turn.completed`, `turn.failed`, malformed lines, missing final message, wrong thread ID, invalid structured status, and nonzero exit context. Assert resume applies the same sandbox/approval settings through config overrides.
- [ ] **Step 2: Run** `python3 -m unittest plugins/tafwid/skills/delegate/tests/test_codex_cli.py -v`; expect missing-adapter failures.
- [ ] **Step 3: Implement** `codex_cli.py` with `check_ready` using Task 1's login check, the exact worker prompt from the spec, `--json`, `--output-schema`, `-o`, stdin brief, and `codex exec resume` for follow-ups. Use `--sandbox read-only|workspace-write` plus `--ask-for-approval never` for fresh runs and equivalent `-c` settings on resume. Reject unrestricted GPT permissions. Keep model selection on the selected CLI's default unless explicitly requested.
- [ ] **Step 4: Run** the focused tests; expect pass.
- [ ] **Step 5: Commit** with `git commit -m "feat: add Codex CLI worker adapter"`.

### Task 5: Route and resume workers by exact connection

**Files:**
- Modify: `plugins/tafwid/skills/delegate/scripts/delegate.py`
- Modify: `plugins/tafwid/skills/delegate/scripts/harnesses.py`
- Modify: `plugins/tafwid/skills/delegate/scripts/run_state.py`
- Test: `plugins/tafwid/skills/delegate/tests/test_delegate.py`

**Interfaces:**
- Consumes: Task 3 `connections.resolve`, Task 4 `codex_cli` functions, existing Claude readiness and routing.
- Produces: `delegate.py --connection claude|gpt:NAME` and `run_state.Tracker(..., backend: str = "claude", connection_id: str = "claude:default")`; run summaries contain `backend` and `connection_id`, with legacy Claude summaries still readable. A resume always uses the prior immutable connection ID and worker session ID.

- [ ] **Step 1: Write failing fake-worker tests** for GPT success, blocked, malformed output, quota failure, timeout, one-shot selection, ambiguous pool, disabled connection, explicit model, Claude+GPT coexistence, and a changed account ID behind the same nickname on resume. Assert no failure launches another backend, no resume changes workspace or owner task, and secret markers do not enter public summaries.
- [ ] **Step 2: Run** `python3 -m unittest plugins/tafwid/skills/delegate/tests/test_delegate.py -v`; expect new tests to fail and old Claude tests to pass.
- [ ] **Step 3: Implement** `--connection` selection in `delegate.py`, preserve the Claude path, and dispatch GPT through Task 4. Extend `harnesses.check_ready(harness=None, *, cwd=None, account=None)` to route GPT through `codex_cli.check_ready`. Reject Claude-only `--task-type`, `--profile`, `--effort`, and `--allow-tool` when selecting GPT. Check identity and readiness before making the output directory and immediately before launch. Save compact summaries with exact connection IDs and private raw events; make `run_state.Tracker` record both backends.
- [ ] **Step 4: Run** the focused tests and `test_harnesses.py`; expect pass.
- [ ] **Step 5: Commit** with `git commit -m "feat: route workers to exact connections"`.

### Task 6: Backend-neutral monitoring and concurrent runs

**Files:**
- Modify: `plugins/tafwid/skills/delegate/scripts/wait.py`
- Test: `plugins/tafwid/skills/delegate/tests/test_wait.py`
- Test: `plugins/tafwid/skills/delegate/tests/test_completion_hook.py`

**Interfaces:**
- Consumes: Task 5 summaries and Tracker records with `backend` and `connection_id`.
- Produces: waiter completion evidence that includes both values while accepting older records without them.

- [ ] **Step 1: Write failing tests** for one Claude and one GPT run owned by the same task, simultaneous completion, correct backend/connection in waiter output, hook arming with both run IDs, and old records lacking connection IDs.
- [ ] **Step 2: Run** `python3 -m unittest plugins/tafwid/skills/delegate/tests/test_wait.py plugins/tafwid/skills/delegate/tests/test_completion_hook.py -v`; expect new tests to fail.
- [ ] **Step 3: Implement** compact waiter fields and any needed hook summary wiring. Keep the same hook wait logic and watch-key ownership rules. Do not load worker transcripts into hook output.
- [ ] **Step 4: Run** the focused tests; expect pass.
- [ ] **Step 5: Commit** with `git commit -m "feat: monitor mixed worker connections"`.

### Task 7: Skills, human guidance, and package verification

**Files:**
- Create: `plugins/tafwid/skills/account/SKILL.md`
- Create: `plugins/tafwid/skills/account/agents/openai.yaml`
- Create: `plugins/tafwid/skills/delegate/references/gpt-accounts.md`
- Create: `docs/account-setup.md`
- Modify: `plugins/tafwid/skills/delegate/SKILL.md`
- Modify: `plugins/tafwid/skills/delegate/references/workflow.md`
- Modify: `README.md`, `docs/architecture.md`, `docs/migration.md`, `CHANGELOG.md`
- Modify: `VERSION`, `plugins/tafwid/.codex-plugin/plugin.json`, `scripts/check_package.py`
- Test: `plugins/tafwid/skills/delegate/tests/test_account_cli.py`

**Interfaces:**
- Consumes: Tasks 1–6 commands and summaries.
- Produces: `$tafwid:account` and updated `$tafwid:delegate` entries, user setup documentation, version `0.3.0`, and package validation for both skills.

- [ ] **Step 1: Write failing package tests** by updating `check_package.py` expectations for both skill entries, the account script, GPT guide, and version consistency between `VERSION` and the plugin manifest. Add a test that every public script's `--help` returns without login or state writes.
- [ ] **Step 2: Run** `python3 scripts/check_package.py` and `python3 -m unittest plugins/tafwid/skills/delegate/tests/test_account_cli.py -v`; expect new package/help checks to fail.
- [ ] **Step 3: Compare prompt copy** in the spec and below with the exact intended file diff. Present any changed wording to the user and wait for approval before editing that wording.
- [ ] **Step 4: Add** the account skill and the approved short delegate, workflow, and GPT-guide text.
- [ ] **Step 5: Update** version to `0.3.0` in `VERSION` and `plugins/tafwid/.codex-plugin/plugin.json`; update package checker, README, architecture, migration, and changelog. Keep the installed plugin untouched. Describe the private-home, Business coordinator, and login-check limits plainly.
- [ ] **Step 6: Run** `make test` and `python3 scripts/check_package.py`; expect all tests and packaging checks to pass.
- [ ] **Step 7: Commit** with `git commit -m "docs: guide mixed account delegation"`.

## Prompt copy for user review

The spec already contains the exact new Codex worker instruction, account skill body, account skill metadata, delegate skill paragraph and frontmatter change, and human-facing setup questions. This plan proposes only the following additional text in prompt-bearing files:

`plugins/tafwid/skills/delegate/references/workflow.md`:

> A task can enable Claude and several named GPT accounts. Name one enabled connection for every worker assignment. Use `--connection claude` or `--connection gpt:NAME` when launching. If the user's allocation is unclear, ask which connection should do each assignment. Never reroute a failed assignment. Use separate worktrees when workers could edit the same files.

The existing model-selector introduction in that file will be replaced with:

> Claude assignments can use the saved task-type or profile model routes below. GPT assignments use the selected account's Codex CLI default unless the user requests a specific GPT model with `--model`.

`plugins/tafwid/skills/delegate/references/gpt-accounts.md`:

> # GPT account workers
>
> Use `$tafwid:account` to add a named GPT account. The user completes sign-in and confirms the account and workspace. A login check reports the authentication method; it cannot identify the account or show remaining usage.
>
> For each GPT assignment, use its exact enabled connection. Read mode uses a read-only sandbox. Edit mode uses workspace-write. A resume keeps the same account, task, and workspace. If an account is unavailable, stop that assignment and report what the user needs to fix.

`plugins/tafwid/skills/account/SKILL.md`, after the approved account-skill paragraph:

> The account script is `../delegate/scripts/account.py` relative to this skill. Resolve its absolute path before running it. Use `--help` for arguments and exit codes.

Any further prompt-bearing wording requires a separate exact-diff review before implementation.

## Final verification

- [ ] Run `make test` and `python3 scripts/check_package.py` after the final edit; record the revision and dirty diff for acceptance.
- [ ] Inspect `git diff --check`, `git status --short`, and the changed prompt-bearing files against approved copy.
- [ ] Confirm tests used fake workers and private temporary homes. Do not run a real login or inference smoke test without a separate user request.
