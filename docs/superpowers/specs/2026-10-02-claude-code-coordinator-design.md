# Claude Code as a Tafwid coordinator

Date: 2026-10-02
Status: Design approved in conversation. Awaiting review of this written spec before implementation planning.

## Goal and scope

Tafwid installs from this repository in both Codex and Claude Code. Whichever host runs it acts as the coordinator with the same features: the task-local switch, settings, worker launch and resume, waiting, the completion hook, and named GPT account setup.

In scope:

- Claude Code marketplace and plugin manifests beside the existing Codex ones.
- A host adapter so the runtime no longer reads Codex-specific signals directly.
- A host-neutral state home shared by both coordinators, with an explicit migration command.
- One hooks file that works on both hosts.
- Host-neutral skill, reference, contract, and error wording.
- Offline tests for both hosts and a manual acceptance run.

Out of scope:

- New worker backends. Workers remain Claude Code and named GPT Codex CLI accounts, available from either coordinator.
- Carrying a task's switch or task settings from a Codex chat to a Claude Code chat. They are different tasks.
- The office dashboard (TAF-3 to TAF-5).

Existing Codex installations must keep working without any user action.

## Decisions made with the user

| Topic | Decision |
| --- | --- |
| Coordinator parity | Claude Code is a full coordinator, not install-only. |
| State home | A new host-neutral location shared by both hosts. |
| Migration | Explicit command. Tafwid never moves state on its own. |
| Workers from Claude Code | Both GPT accounts and Claude Code workers, as on Codex. |
| Architecture | One plugin directory with a host adapter module. |

A Claude Code coordinator that delegates to a Claude Code worker uses the same Claude subscription for both. That saves coordinator context, not allowance. The README states this.

## Probe results

A throwaway probe plugin was run on Claude Code 2.1.287 on 2026-10-02 (`claude plugin validate` plus two one-turn headless sessions). Codex behavior could not be probed in that environment.

| # | Question | Result |
| --- | --- | --- |
| P1 | Does a Bash tool command in Claude Code see the session ID as an environment variable? | Confirmed. `CLAUDE_CODE_SESSION_ID` is set for Bash commands and for hook processes, and equals the hooks' `session_id`. `CLAUDE_PLUGIN_ROOT` is set for hook processes only. |
| P2 | Does one hook command resolve the plugin root on both hosts? | Confirmed on Claude Code for the `bash -c` form below. Unverified on Codex; checked in manual acceptance. |
| P3 | Does Claude Code load a hooks file containing the Codex-only `Interrupt` event and `statusMessage` field? | Confirmed. Validation warns "unknown hook event; entry ignored at runtime" and the other hooks run. |
| P4 | Does a Claude Code `Stop` hook resume the turn on `{"decision": "block", "reason": ...}`? | Confirmed; the next `Stop` input has `stop_hook_active: true`. The 1800-second timeout is unverified and checked in manual acceptance. |
| P5 | Do hook inputs include `session_id` and `permission_mode`? | Confirmed for `UserPromptSubmit` and `Stop`. |
| P6 | Does `claude -p` run when launched from inside a Claude Code session? | Confirmed. The child inherits the parent's `CLAUDE_CODE_SESSION_ID` unless it is removed from its environment. |

If the Codex half of P2 fails in acceptance, stop and return to the user with the alternative: host-specific hook files plus a launcher.

## Host adapter

Add `scripts/host.py`. It is the only module that reads coordinator-identity signals.

- `detect()` returns `"codex"` or `"claude"`.
  - `TAFWID_HOST`, when set to one of those values, wins. It exists for tests and for recovery.
  - Otherwise Codex is detected from `CODEX_THREAD_ID` or the legacy `CODEX_SESSION_ID`, and Claude Code from `CLAUDE_CODE_SESSION_ID`.
  - If both hosts' signals are present it raises `ValueError` with a message naming `TAFWID_HOST`. It never guesses.
  - If neither is present it returns `None`. Missing identity keeps today's meaning: status reports off, and commands that need a task fail with a clear message.
  - Inside a hook process, `host.for_hook()` returns `"claude"` when `CLAUDE_PLUGIN_ROOT` is set and `"codex"` otherwise, because hook processes do not reliably carry the task variables.
- `task_id()` returns the canonical UUID string for the detected host, or `None` when there is no valid identity, matching today's `session.current_task_id()` contract.
- `display_name()` returns `"Codex"` or `"Claude Code"` for messages, and `"the coordinator"` when no host is detected.
- `full_access()` returns whether the coordinator currently reports full access (see Permissions).

`session.current_task_id()` becomes a wrapper over `host.task_id()` so its callers are unchanged.

### Worker environment

Both launchers remove the coordinator's identity variables from the worker's environment: `CODEX_THREAD_ID`, `CODEX_SESSION_ID`, `CLAUDE_CODE_SESSION_ID`, and `TAFWID_HOST`. The GPT launcher already strips `CODEX_*`; the Claude launcher gains the same step. A worker therefore never detects itself as a coordinator.

## State home

New default: `~/.tafwid/state`. `TAFWID_HOME` overrides the `~/.tafwid` part.

`paths.state_root()` still creates and moves nothing. Resolution order:

1. The neutral directory, if it exists.
2. Exactly one legacy directory (`$CODEX_HOME/tafwid/state`, `$CODEX_HOME/state/tafwid`, `$CODEX_HOME/state/claude-delegate`). It is used in place.
3. Otherwise the neutral directory.

It raises `ValueError`, as today, when more than one legacy directory exists, and also when the neutral directory and any legacy directory both exist. A legacy path that is the same directory as the neutral one is not a conflict.

`paths.legacy_in_use()` reports whether case 2 applies. `session.py status` and `settings.py show` add a `"migration"` field to their JSON output when it does; the skill tells the coordinator to mention it once. No other script prints the notice.

The redirect checks in `accounts.py` that are hard-coded to `$CODEX_HOME`, `$CODEX_HOME/tafwid`, and `$CODEX_HOME/state` apply instead to the parents of whichever root `state_root()` returns. The message "Codex state path is redirected" becomes "Tafwid state path is redirected".

### Migration command

`settings.py migrate [--dry-run]`.

1. Resolve the source with the rules above. If the neutral directory is already in use, report "nothing to migrate" and exit 0.
2. Refuse when the destination exists, when the source or destination is a symlink, or when any run record is active according to `run_state.effective`.
3. `--dry-run` prints source, destination, and counts of accounts, task files, and run records, then stops.
4. Create `~/.tafwid` with mode `0700`. Move the directory with `os.rename`. When that fails across filesystems, copy with preserved modes, verify the file list and sizes, then remove the source.
5. Rewrite each account's absolute home path in `accounts/registry.json` from the old root to the new one, using `paths.atomic_json`.
6. On any failure after the move, move the directory back, restore the registry, and exit nonzero with the reason.

Signed-in GPT account homes move with the directory, so no account needs a new sign-in. The command prints a JSON result naming both paths.

## Run and task records

New records write `coordinator_task_id` and `coordinator_host`. They no longer write `codex_thread_id`.

Readers use one helper, `run_state.owner(record)`, which returns `coordinator_task_id` and falls back to `codex_thread_id`. It replaces the direct field reads in `delegate.py` (resume ownership), `completion_hook.py` (arm ownership), and `run_state.list_runs`. Existing run history and resumes therefore keep working.

Per-task files (`<task>.json`, `tasks/<task>/settings.json`, `hook-waits/<task>.json`) keep their `thread_id` key and layout. Task IDs from both hosts are UUIDs, so they do not collide.

## Hooks and completion

### Hooks file

Keep the single `plugins/tafwid/hooks/hooks.json`; both hosts load it automatically. Each command becomes:

```
bash -c 'exec python3 "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/delegate/scripts/completion_hook.py" <action>'
```

The explicit `bash -c` makes the command independent of whether a host substitutes the variable as text, exports it, or runs hook commands through a shell.

| Event | Action | Codex | Claude Code |
| --- | --- | --- | --- |
| `Stop` | `hook` | Waits for armed workers | Same |
| `UserPromptSubmit` | `disarm` | Clears the armed marker | Clears it and records the hooks-seen marker |
| `Interrupt` | `disarm` | Clears the armed marker | Not a Claude Code event; ignored with a validation warning |

Claude Code fires no hook when the user interrupts a turn, and `Stop` does not run on an interrupt. A leftover armed marker is harmless because the next prompt clears it. `ARM_MAX_AGE_SECONDS` (24 hours) only discards markers from abandoned sessions; a shorter limit let a slow end of turn expire a valid arm, so the coordinator was never resumed.

### Stop hook

`on_stop` keeps its logic. It stops setting `CODEX_THREAD_ID` in the process environment; `wait.wait_for_runs` gains an optional `task_id` argument and `on_stop` passes the event's `session_id`. The host for the hook process comes from `host.for_hook()`.

### Hook availability

`completion_hook.hook_status()` dispatches on the host.

- Codex: unchanged. It queries `codex app-server` for trusted, enabled Tafwid hooks.
- Claude Code: there is no inventory to query. The `UserPromptSubmit` handler writes `hook-seen/<task>.json` containing `{"version": 1, "thread_id": ..., "seen_at": ..., "permission_mode": ...}`. `hook_status()` returns active only when that marker exists for the current task. Otherwise it returns inactive with the reason "Tafwid hooks have not run in this Claude Code session".

When inactive, `arm` returns `unavailable` and the workflow uses `wait.py`, as it does on Codex without hook trust.

### Waiting without hooks

`wait.MAX_WAIT_SECONDS` is 300, below Claude Code's Bash command limit, so `wait.py` needs no code change. `references/monitor.md` gains a Claude Code part: run `wait.py` with a Bash timeout above 300 seconds and repeat while it reports pending run IDs.

## Permissions

The `inherit` policy keeps its name, so saved settings stay valid. `settings.resolve()` calls `host.full_access()`:

- Codex: `CODEX_PERMISSION_PROFILE == ":danger-full-access"`, as today.
- Claude Code: the hooks-seen marker for the current task records `permission_mode` equal to `bypassPermissions`. With no marker, it is false.

The marker reflects the mode at the user's last prompt. If the user lowers the mode mid-turn, `inherit` can still resolve to `full` until the next prompt. `references/claude-code.md` documents this beside the `inherit` row.

The result field `codex_full_access` becomes `coordinator_full_access`. The reason strings name the detected host through `host.display_name()`.

## Wording

"Codex" stays where it means the GPT worker CLI, Codex sign-in, or `CODEX_HOME` for account homes. It becomes "the coordinator" where it means the orchestrating host:

- `skills/delegate/SKILL.md` and `skills/account/SKILL.md`. Skill mentions read "the `tafwid:account` skill", because Codex invokes it as `$tafwid:account` and Claude Code as `/tafwid:account`.
- `references/workflow.md`, `references/claude-code.md`, `references/monitor.md`.
- The Claude worker contract in `delegate.py` and the GPT contract in `codex_cli.py`.
- Error and help text such as "Delegation is off for this Codex task" and "Invalid Codex task identity".
- Script docstrings that describe the coordinator as Codex.

## Packaging

Add:

- `.claude-plugin/marketplace.json` at the repository root: marketplace `tafwid`, owner `hunainahmedj`, one plugin `tafwid` with source `./plugins/tafwid`.
- `plugins/tafwid/.claude-plugin/plugin.json`: `name`, `version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords`. Skills and hooks load from their default locations.

Claude Code installation:

```
/plugin marketplace add hunainahmedj/tafwid
/plugin install tafwid@tafwid
```

The Codex manifest's description and `longDescription` become host-neutral, and its keywords gain `claude-code`.

`scripts/check_package.py` additionally asserts that both Claude manifests exist and parse, that their names are `tafwid`, that the plugin source is `./plugins/tafwid`, that the Claude and Codex plugin versions both equal `VERSION`, that `scripts/host.py` exists, and that every hook command uses the `bash -c` dual plugin-root form.

`VERSION` and both plugin manifests go to `0.4.0`.

## Documentation

- `README.md`: host-neutral introduction, requirements for each coordinator, a Claude Code install section, the skill table with both invocation forms, the same-subscription note, and the new state location.
- `AGENTS.md`: "Tafwid is a Codex plugin" becomes a plugin for Codex and Claude Code; the manifest-version rule names all manifests.
- `docs/migration.md`: the neutral state home and `settings.py migrate`.
- `docs/04-modules/delegation.md`, `docs/04-modules/accounts.md`, `docs/03-architecture/system.md`, `docs/02-workspace/repos.md`: host adapter, state home, hooks.
- `docs/05-decisions/0004-host-adapter-and-neutral-state.md`: the decisions in this spec and the alternatives rejected (separate plugin directories; an explicit `--host` flag passed by the skill).
- `docs/01-project/backlog.md`: TAF-6 for this work.
- `CHANGELOG.md`: a 0.4.0 entry.

## Testing

Offline tests keep using temporary homes and fake worker executables. No test makes a model request or touches the developer's installed plugin.

- `tests/test_host.py`: detection for each host, both signals, no signal, `TAFWID_HOST` override, malformed IDs.
- `tests/test_paths.py`: neutral default, single legacy reuse, neutral-plus-legacy error, `TAFWID_HOME`.
- `tests/test_settings.py`: `migrate` success, dry run, destination exists, active run refusal, registry path rewrite, rollback on failure; `inherit` on each host with and without the marker.
- `tests/test_completion_hook.py`: Claude-shaped `Stop` and `UserPromptSubmit` events, marker write, `hook_status` on Claude Code, `arm` unavailable without a marker.
- `tests/test_delegate.py`, `tests/test_delegate_gpt.py`: new record fields, resume from a legacy `codex_thread_id` record, identity variables absent from the worker environment.
- Existing Codex tests pass with only the renamed fields changed.

`make test` stays the gate. `claude plugin validate ./plugins/tafwid` is a documented manual step in `CONTRIBUTING.md`, not a CI step, because CI has no Claude Code CLI.

### Manual acceptance

Run on the developer's machine after the offline suite passes:

1. Install from the local repository in Claude Code; both skills are listed.
2. `/tafwid:delegate on claude`, then status, in a new Claude Code session.
3. One real one-shot assignment to a named GPT account and one to a Claude worker; each returns a compact report.
4. Arm the completion hook, end the turn, and confirm Claude Code resumes when the worker finishes.
5. With hooks disabled, confirm `arm` reports `unavailable` and `wait.py` works.
6. Reinstall in Codex and repeat steps 2 to 4 there.
7. Run `settings.py migrate --dry-run`, then `migrate`, and confirm accounts list as ready from both hosts without a new sign-in.

## Risks

- The Codex half of P2 and the long `Stop` timeout in P4 are unverified until manual acceptance.
- `inherit` on Claude Code can lag one prompt behind a permission-mode change.
- A user with hooks disabled in Claude Code gets no completion resume and no `inherit` full access. Both degrade to the safe path.
