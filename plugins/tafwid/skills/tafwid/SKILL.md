---
name: tafwid
description: Use when the user requests delegation on/off/status, the Tafwid workers dashboard, a Claude Code worker, or substantial work with this Codex task's delegation switch enabled.
---

# Tafwid

Codex owns task selection, acceptance, review and communication. Delegate substantial bounded work to Claude Code; small tasks may cost less natively. Work explicitly delegated to Claude uses Claude workers, not GPT subagents.

The implemented backend is Claude Code. Resolve `TAFWID_SKILL_DIR` to the absolute directory containing this loaded `SKILL.md`; plugin installations may live in a versioned cache. Use that directory for all bundled commands, never a guessed personal skill path.

## Task-local switch

Translate “delegation on”, “delegation off”, and “delegation status” into the matching command:

```bash
python3 "${TAFWID_SKILL_DIR}/scripts/session.py" on
# Replace on with off or status as requested.
```

State defaults to off and lives at `$CODEX_HOME/state/tafwid/<task-id>.json` (default home: `~/.codex`). Existing installations reuse `state/claude-delegate` when it is the only state directory; keep it in place to preserve settings/history. If both directories exist, resolve the conflict before launching. Identity comes from `CODEX_THREAD_ID`, falling back to `CODEX_SESSION_ID`. It survives compaction and reopening this task. Other tasks, including forks with new IDs, default off even in the same repository. Never infer state from a copied conversation or directory. Missing identity cannot enable persistent delegation.

Check `session.py status` before choosing an execution approach for substantial work and before dispatching workers. When on, route suitable implementation and review tasks through Claude. When off, use the ordinary workflow. A specific user request to use Claude once permits `--once`; it does not flip the switch. Do not use `--once` merely to bypass an off switch. Off prevents new dispatches; it does not terminate an already running worker.

## Workflow and instruction handoff

Preserve the user's workflow; no plugin is required. Select worker-relevant skill/role files with `--instructions-file`; do not also paste or reload them. The launcher resolves equivalent Claude skills and deduplicates supplied/resumed instructions. Manifests stay on disk; [delivery details](references/instructions.md) are for troubleshooting. Claude's hooks remain independent. Only for an active Superpowers workflow, read [its optional adapter](references/superpowers.md) and preserve its review/verification stages.

## Prepare a bounded task

- Inspect only enough context to define the deliverable. Let Claude do the detailed investigation.
- Brief: objective/acceptance criteria; workspace/owned files; instruction paths/user constraints; authorized actions; check owners/commands; expected report. Assign focused checks to the worker, acceptance to Codex, and any final broad suite to one owner after review corrections. Claude does not inherit this chat.
- Include applicable user, parent, and repository `AGENTS.md`/`CLAUDE.md` paths. Claude loads its normal configuration, but does not inherit Codex's chat, plugin installation, or tools. Forward exact browser/environment preferences and known capability gaps in the brief. Use trusted workspaces: normal Claude startup hooks run.
- Record existing changes before editing. Use a separate worktree when workers or people could touch the same files. A worktree starts from a commit; explicitly provide relevant uncommitted context. Serial work in the current checkout is suitable when ownership is clear.
- Keep briefs and run artifacts outside the repository in a private temporary directory or local cache. Every invocation needs a new output directory.

## Select the worker

Codex chooses the task type and role for each worker. Read [model selection](references/model-selection.md) and inspect `scripts/settings.py show` to learn the current user choices. Prefer `--task-type` so the launcher applies the saved model for that kind of work. Pass `--role` and a brief `--selection-reason`, and announce the resolved model before dispatch. Role labels describe the assignment; they do not select a named Claude plugin agent. Supply a role template when the selected workflow requires one.

The Settings page has editable Fast / Standard / Deep defaults and per-task model overrides. Initial defaults are Sonnet / Opus / Fable; never treat these names as fixed once the user changes settings. Task overrides take precedence over their tier default. Use `--profile` for a deliberate tier choice or escalation, and `--model` for an explicitly requested alias or exact model ID. Explain intentional departures from the saved task route; do not silently discard the user's override. Keep Codex as controller and use fresh Claude sessions for independent reviews.

## Launch

Use the bundled [launcher](scripts/delegate.py) (Python 3, macOS/Linux). For example, after writing the brief:

```bash
python3 "${TAFWID_SKILL_DIR}/scripts/delegate.py" \
  --once \
  --cwd /absolute/path/to/worktree \
  --prompt-file /absolute/path/to/brief.md \
  --output-dir /absolute/path/to/run-1 \
  --title "Implement the requested feature" \
  --task-type implementation --role implementer \
  --selection-reason 'Implementation from a prose specification' \
  --mode edit \
  --allow-tool 'Bash(python3 -m unittest *)'
```

Default `--mode read` exposes built-in file inspection, Skill, and ToolSearch. `edit` adds Edit/Write. Add scoped `--allow-tool 'Bash(command ...)'` rules only for authorized shell actions in edit mode; under Scoped, Bash is unavailable otherwise. Exact MCP tool names can also be allowed, for example `--allow-tool mcp__server__tool`, using names actually discovered in Claude. Existing Claude/plugin permissions remain in effect; read mode is not a sandbox for plugin hooks or external tools. With the default Scoped policy, the launcher does not broadly preapprove shell or MCP tools. The permission settings below can enable Claude’s full-access mode; parent execution and organization restrictions still apply.

The example is an explicitly requested one-shot task. Omit `--once` for automatic delegation while this task's switch is on; the launcher checks state before starting Claude. A resumed worker must belong to the same Codex task and workspace.

Task types and profiles resolve saved settings to explicit Claude model flags; `--model` selects an alias or exact model ID instead. The three selectors are mutually exclusive. `--effort` can override the profile's effort where supported. Legacy calls with no selector preserve Claude's default, but skill-driven dispatch must select explicitly. A resume with no task/model/profile selector preserves its recorded model and effort even after settings change; pass a selector explicitly to reroute it. The launcher checks subscription login and rejects API/provider environment overrides without printing their values. Do not use `--bare`, extract OAuth credentials, or fall back to API billing. Existing account-level extra usage settings can still affect billing; this launcher does not change them or guarantee a spending cap.

Keep the asynchronous process handle and output directory. Default timeout is 900 seconds; adjust with `--timeout`. Do not duplicate quiet runs.

## Wait for workers

After dispatch, do independent useful work or wait for a result. For one run with a retained process handle, use the host's completion wait; with `exec_command` / `write_stdin`, use a 30-second initial yield when nothing else is ready, then 60-second waits (`yield_time_ms: 60000`). A short initial yield is useful to obtain a handle for independent work, not a reason to keep polling every second. Respect any shorter host limit. Do not replace waiting with repeated log reads, process inspection, or dashboard checks unless there is a concrete diagnostic question.

For several runs or recovery after compaction, read [completion waiting](references/monitoring.md) and use `scripts/wait.py` with the exact output directories. It waits locally for any selected run to finish or need attention, returning compact evidence. Wait at most 60 seconds per host call; a quiet wait is not a worker failure. Keep the user informed at the required cadence without reopening unchanged logs. The dashboard's heartbeat runs independently and needs no GPT supervision.

On completion, inspect the reported outcome and relevant evidence, then perform the normal acceptance review below. On failure or `native_required`, handle that outcome immediately. Neither waiting nor a heartbeat proves tests are making progress. This adapter does not provide an unsolicited wake-up after a Codex turn ends; keep the task active while waiting. Never assume a notification subscription exists merely because a worker was launched.

## Worker permission settings

The user controls the default for future launches and resumes through **Settings → Worker permissions** in the dashboard, or the bundled CLI:

```bash
python3 "${TAFWID_SKILL_DIR}/scripts/settings.py" show
# Only change the policy when the user requests it:
python3 "${TAFWID_SKILL_DIR}/scripts/settings.py" set --policy inherit
```

- `scoped` (default): Claude `dontAsk` mode with the task's explicit allowances.
- `full`: Claude `bypassPermissions` mode; edit workers get Bash without needing scoped command allowances. This removes Claude's normal approval prompts for available tools, including connected MCP tools, subject to host and organization restrictions.
- `inherit` (**Follow Codex**): recheck the launch process's `CODEX_PERMISSION_PROFILE` every invocation. The currently supported full-access signal is exactly `:danger-full-access`. Anything else, including an absent signal, uses Scoped. Never infer access from old logs, the dashboard's environment, a copied task ID, or a worker brief. This is a conservative adapter for an observed Codex environment signal, not a stable public permissions API.

Settings are private and global to this Codex home at `$CODEX_HOME/state/tafwid/settings.json`; they do not toggle delegation or modify running workers. Resuming a session re-evaluates the current policy instead of carrying forward its previous permission level. `--permissions scoped|full|inherit` is a per-run override; use it only for the user's explicit requested override. Never change the policy automatically to recover from a denial. Invalid saved settings stop a launch with an error.

Full access preserves task scope, instructions, review/handoffs, subscription billing and host/managed restrictions. Read mode keeps inspection/skill/discovery tools; full-access edit adds Bash. Read mode does not sandbox plugins/MCP. Inspect `permissions` in request/summary/registry metadata; older runs show Not recorded.

## Workers dashboard

Give every launch a short, descriptive `--title`. The launcher automatically records each invocation in a local registry, including its task, role, selected model, heartbeat, outcome, and artifact location. The dashboard groups runs of the same Claude session within a conversation as one worker, with separate attempts and recorded exchanges in its history. Recording works even when the dashboard is closed.

For “open/show the workers dashboard”, run:

```bash
python3 "${TAFWID_SKILL_DIR}/scripts/dashboard.py" start
```

Open the returned URL in a Codex browser tab. The dashboard updates automatically and initially selects the current conversation. It shows conversation names and supports combined filters, search, and sorting across recorded workers. A coordinator’s View activity opens public Codex messages and tool-call evidence from its local task log; this does not expose internal reasoning or infer review acceptance. Viewing activity does not change the delegation switch or model selection, and needs no GPT supervisor agents. Open **Settings** to edit model routing and worker permissions; saves apply across conversations in this Codex home. See [dashboard operations](references/dashboard.md) for filter behavior, history imports, storage, and limitations.

## Review and continue

Read compact JSON; open `report.md`, `result.json` or logs as needed. Checks: command/cwd/environment, result, tested revision+dirty-diff reference, later edits, unresolved failures/next owner. Link private evidence in follow-ups; missing evidence is unknown, not a pass.

Reuse checks only when relevant code/environment still match; HEAD alone misses dirty changes. Inspect the diff and perform acceptance review. Relevant edits or dependency/environment changes require reassessing checks. Preserve required CI/workflow gates and requested independent verification. For optional retries, state the change, diagnostic hypothesis or transient evidence; otherwise report the blocker. `completed` is not acceptance.

Check `model_selection` in the request/summary and `models_used` in the summary. The latter lists usage metadata, which can include helper models; it does not identify spawned agents or prove which model performed the main work. When verifying routing, inspect assistant model fields only in the exact worker session's transcript. Record intended and observed models separately; investigate unexpected substitutions before claiming a routing test passed.

When status is `native_required` (exit code 3), read `handoff_file` and follow [the native handoff procedure](references/native-handoff.md). Codex performs the authorized unavailable step with its own tools, records the evidence, and resumes the same Claude worker with the result. This does not turn delegation off. Do not mark the whole task complete while a handoff is pending. `blocked` means the worker reported another unresolved blocker; `needs_review` covers permission denials or invalid structured reports.

For corrections, write a short follow-up brief and invoke the launcher with the same workspace and `--resume-from /absolute/path/to/run-1`, using a new `--output-dir`. Reapply the task's mode and, for Scoped, shell allowances; permissions are re-evaluated from current settings. Never use global `--continue`, which can select another conversation.

On `needs_review`, inspect the recorded permission denials. On errors, quota limits, or authentication failures, report the blocker; do not repeatedly retry or switch billing. `auth status` can report a stored login while a real request fails; an expired session needs `claude auth login` in the user's terminal. After timeouts or interruption, inspect partial changes before deciding whether to resume or start again.

Return the outcome, verification, and remaining limitations to the user. Keep worker transcripts out of Codex context; delegate whole tasks and review concise evidence to preserve the usage savings.

## Maintenance

Run `python3 -m unittest discover -s tests -v` from this skill directory for offline launcher checks, and `node --test tests/dashboard-view.test.mjs` for dashboard filtering and sorting. A live read/edit/resume exercise in a temporary workspace is needed to verify the current Claude login and CLI integration. Model/effort flags and profile routing were verified on Claude Code 2.1.273; check `claude --help` on older installations.

References: [programmatic CLI](https://code.claude.com/docs/en/headless), [subscription usage notice](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan). Billing rules may change; recheck when diagnosing billing.
