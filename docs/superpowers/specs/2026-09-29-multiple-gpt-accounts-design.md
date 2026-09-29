# Multiple GPT accounts in Tafwid

Date: 2026-09-29
Status: Written design for user review. No runtime or prompt changes are authorized by this document alone.

## Goal and scope

Tafwid can assign bounded work from the current Codex task to Codex CLI workers signed into named ChatGPT accounts. The user can add more than one personal GPT account and more than one Business GPT account. A Tafwid task can enable a pool of connections, including GPT accounts and the existing Claude connection. Each worker assignment records one exact destination from that pool. A readiness, login, permission, model, or usage failure never reroutes an assignment to another connection.

The connection pool is the foundation for a later cluster spanning Claude, multiple GPT accounts, local LLMs, and OpenCode Zen. Future adapters join the same pool without changing its task or run identity rules. This release implements named GPT accounts and coexistence with the current Claude connection. It allows separate, explicitly routed assignments to run concurrently across that pool. Automatic task splitting, worker allocation, and usage-based balancing belong to a later release; Zen and local LLMs are not yet supported.

The setup is visible and interactive. The user completes Codex's own login flow and confirms the intended account and workspace before Tafwid marks the connection ready. The current Codex login is left alone. Tafwid stores no passwords, token contents, account emails, or account usage snapshots.

`business` is a user-confirmed account type, not proof of a contract, workspace policy, or data-processing guarantee. A future policy layer may use the stored type, but this release makes no plan-specific compliance claim or automatic policy decision. The user chooses the destination account for the task's data.

Account routing affects the worker. The current coordinator account already receives the user's request, writes the brief, and reviews the result. A person who must keep Business data out of a personal account must start the coordinating Codex task while signed into the Business account. A private Codex home selects CLI authentication; it is not a separate macOS user or a filesystem isolation boundary.

## User commands and interaction

Add a separate `$tafwid:account` skill for setup and inspection. Keep `$tafwid:delegate` for task assignment. Both skills use the same local Python runtime.

| User command | Meaning |
| --- | --- |
| `$tafwid:account add gpt` | Add a personal GPT account. Ask for a unique nickname. |
| `$tafwid:account add gpt business` | Add a Business GPT account. Ask for a unique nickname. |
| `$tafwid:account list` | Show nicknames, types, and ready/pending status without inspecting credentials. |
| `$tafwid:account check NAME` | Check the named CLI login method without making a model request. |
| `$tafwid:delegate on gpt NAME` | Enable that ready GPT account in this task's connection pool. |
| `$tafwid:delegate on claude` | Enable the current Claude connection alongside any enabled GPT accounts. |
| `$tafwid:delegate off gpt NAME` | Remove one GPT account from new automatic assignments; running workers continue. |
| `$tafwid:delegate off claude` | Remove Claude from new automatic assignments; running workers continue. |
| `$tafwid:delegate off` | Disable all new automatic assignments; running workers continue. |
| `$tafwid:delegate status` | Show the selected pool and its ready, pending, or unavailable connections. |
| One-shot assignment to `gpt NAME` | Run once without changing the task's enabled pool. |

The account skill asks for a nickname when omitted. Nicknames are unique across account types and cannot be `gpt`, `personal`, `business`, or `claude`. A task pool records immutable connection IDs as well as display nicknames and types. Renaming or replacing a connection cannot redirect an existing task silently. `on gpt` with multiple ready accounts asks which to add; with one ready account it still states the account being added. A missing account offers the setup flow and waits for the user's answer. It does not launch login as a side effect of an ordinary delegation request.

The existing Claude login is represented as one connection in the pool. Adding a GPT account does not disable it. The connection model has provider and account-type fields so future Claude, Zen, and local adapters can register their own named connections. No future adapter is treated as ready before it exists and passes its own readiness check.

For each assignment, the coordinator or user names one enabled destination, such as `claude`, `gpt pro-main`, or `gpt work`. A request to spread independent work among selected connections can be carried out with several explicit assignments and separate output directories. This release does not assign destinations automatically. If the user's requested allocation is unclear, the coordinator asks how to divide the work. One connection can handle more than one assignment; a task can have workers on different platforms at the same time. Concurrent edits to the same files use separate worktrees or serialized assignments.

The account skill announces the type, nickname, and private Codex home before it runs `codex login`. The user signs in through Codex's browser flow, or chooses its device-code flow if needed. After `codex login` exits, the runtime checks `codex login status` from that same home. A clearly reported ChatGPT login method qualifies for user confirmation; API-key, access-token, workload-identity, failed, or ambiguous status remains pending. The user then confirms that the browser sign-in used the intended account and workspace. Only an explicit confirmation marks the connection ready. Cancellation leaves it unavailable for delegation. The skill can explain how to retry a pending login. Readiness is checked again at dispatch.

Human-facing setup questions, exactly as proposed:

1. `What short name should Tafwid use for this GPT account?`
2. `I'll open Codex sign-in for the {personal|Business} account named {name}. Your current Codex login will stay signed in.`
3. `Did you sign in to the intended {personal|Business} account and workspace?` Choices: `Yes, use this account`, `Retry sign-in`, `Cancel`.
4. For a missing destination: `No GPT account named {name} is ready. Set it up now?` Choices: `Set up account`, `Cancel`.

These questions are shown by the agent using the host's native question tool when available. If unavailable, the agent asks plainly in chat. A declined or missing answer never counts as confirmation.

## Credential and state boundary

Each account gets its own owner-only directory outside Git, under Tafwid's existing private state root. Inside it, `CODEX_HOME` points to a dedicated Codex home with file-based CLI credential storage. Tafwid creates that directory; it does not copy the current home, config, credentials, or plugin installation. It does not read or print `auth.json`. Credentials are created and refreshed by the Codex CLI. The setup checks that directory components are not symlinks and that permissions keep other local users out.

The setup and worker subprocesses receive a controlled environment that sets their account's `CODEX_HOME` and removes inherited API-key, access-token, workload-identity, and custom-provider overrides that could change billing or identity. Readiness uses the same environment as dispatch. If machine-managed authentication requirements force an unisolatable credential store or a different login method, setup fails with an actionable message. Tafwid never falls back to the caller's default Codex home.

The private account registry records version, immutable ID, nickname, type, home path, and pending/ready state. Task settings record the enabled connection IDs. Private run records include the exact connection ID, nickname, type, backend, worker session ID, workspace, and result paths. No account credentials enter a task brief or run summary. Existing Claude task settings and run records remain readable through migration. An enabled legacy task with Claude selected migrates to a pool containing only its current Claude connection; an off task remains off.

## Worker flow

Add a Codex harness behind the existing launcher boundary. A new GPT run starts `codex exec` in the assigned workspace with `--json` and a compact final-response schema. It reads the brief from stdin and records the JSONL events privately. The launcher obtains the worker thread ID from Codex's start event and verifies both process exit and the worker's structured `completed` or `blocked` report. An exit code alone is not acceptance. Follow-ups use `codex exec resume` with the recorded worker thread ID and the same account ID, Codex home, Tafwid task, and workspace. Independent review starts a new worker thread.

The existing completion hook, waiter, heartbeat, and concise acceptance report remain the coordinator path. Their records become backend-neutral while preserving legacy Claude fields when reading older runs. GPT worker output stays outside Git. The parent Codex task owns acceptance and checks relevant evidence before reporting completion.

The first GPT release uses the CLI's default available model unless the user requests a specific GPT model. Claude-specific Sonnet/Opus/Fable routes never apply to GPT. Explicit model requests are passed to Codex and failures are reported for that account, without switching models or accounts.

GPT `read` mode uses the CLI's read-only sandbox. GPT `edit` mode uses a workspace-write sandbox with noninteractive approval policy. The existing saved `full` Claude policy does not silently grant a GPT worker unrestricted filesystem access; that mode is unsupported for GPT in this release. The selected sandbox and approval policy are recorded with the run. Any tool access not supported by the chosen Codex sandbox produces a blocked report or process error for acceptance review.

The launcher applies the same sandbox and approval settings to fresh and resumed runs. On CLI versions where `codex exec resume` lacks the direct sandbox flags, it uses the equivalent documented configuration overrides. Startup fails if the installed CLI cannot honor the selected limits.

## Prompt wording and review control

The following is the proposed **complete new worker instruction** for the Codex harness. The existing Claude worker prompt stays as it is.

> You are a Codex worker for a task assigned by Tafwid. Follow the task brief and the workspace rules. Stay within the assigned files and permissions. Do not delegate again. Do not commit, push, deploy, send messages, or change account settings unless the brief asks you to. If you cannot finish, report what is done and what remains. Return `completed` only when the assignment is finished. Keep your report short: outcome, changed files or findings, checks run, and remaining risks.

The proposed new account skill text is:

> Use Tafwid to add and check named GPT accounts. `add gpt` means a personal account; `add gpt business` means a Business account. Ask for a unique short name, then state the account type and private sign-in destination before starting Codex login. The user completes sign-in. Check the login method without reading credentials, then ask the user to confirm the account and workspace. Mark the account ready only after that confirmation. If the user cancels or the login method is unclear, keep it pending. Never use another account as a fallback. Use the account script's `--help` for exact arguments.

The account skill frontmatter description will be:

> Use when the user adds, checks, or lists named GPT accounts for Tafwid.

Its skill metadata will show `Tafwid Account`, describe it as `Set up and check GPT worker accounts`, and use this default prompt:

> Use $tafwid:account to set up a named GPT worker account.

Proposed additions to the existing delegate skill are limited to these sentences:

> Enable only the connections the user chooses for this task. Record one exact enabled connection for each worker assignment. If routing is unclear, ask the user. If a selected GPT account is unavailable, stop that assignment and offer `$tafwid:account` setup. Never substitute another connection. Follow the GPT account guide for sign-in and worker rules.

Its frontmatter description will change to:

> Use when the user manages Tafwid delegation, assigns work to Claude Code or a named GPT account, or continues with delegation enabled.

The quoted worker instruction, skill text, and human-facing questions are reviewable prompt copy. Implementation must preserve their approved wording. If any prompt change is needed later, show the exact proposed diff to the user and wait for approval before editing it. Documentation prose, Python docstrings, and `--help` text remain concise and human-readable; they do not introduce hidden agent instructions.

## Scripts, documentation, and tests

The shared runtime gains an account command with `add`, `check`, `list`, and `confirm` actions, plus a Codex harness module. Every new public script has a module docstring describing its purpose, privacy behavior, invocation examples, output, and exit codes; every function has a useful docstring; `--help` performs no login, writes, or model request. Error messages explain the next user action without printing credential material. Existing script help changes will be shown in the implementation plan.

Update the package checker for the new skill entry point and required files. Update README, architecture, workflow, account setup guide, and release manifests consistently. Keep the installed plugin untouched during development. Offline tests use isolated temporary homes and fake Codex executables to cover two personal accounts, Business metadata, login confirmation, environment isolation, no fallback, task-local connection pools, concurrent Claude and GPT runs, resume identity, permissions, errors, and backward-compatible Claude behavior. `make test` and `python3 scripts/check_package.py` are required gates. No test makes a real model request or signs into a real account.

## Acceptance

1. A user can add two personal GPT accounts and one Business GPT account through visible sign-in steps, each with a unique nickname and isolated CLI home.
2. The ordinary Codex CLI login remains usable and unchanged after setup and worker dispatch.
3. A task can enable Claude and multiple GPT accounts together. It can run separate assignments on different enabled connections. Each worker assignment records its exact destination; no failure routes work to a different connection, API billing, or the caller's Codex home.
4. A Codex worker can complete and resume a bounded task under the selected account, with private artifacts, completion-hook monitoring, and independent Codex acceptance.
5. Prompt text matches the user-approved copy. New scripts have useful docstrings and `--help`. Offline tests and package checks pass.
