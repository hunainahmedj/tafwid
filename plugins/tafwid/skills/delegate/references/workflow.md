# Delegation workflow

Follow this workflow to prepare worker assignments, launch or continue
workers, wait for completion, and accept their results.

For Claude-specific tools and permissions, see
[the Claude Code guide](claude-code.md).

## Prepare the task

Write a brief containing:

- The goal and what a successful result must satisfy.
- The workspace and files the worker may change.
- Relevant context, project rules and constraints.
- The checks the worker should run and the results it should report.

Workers do not inherit this chat. Include the information they need
to complete their assignment.

A task can enable Claude and several named GPT accounts. Name one enabled connection for every worker assignment. Use `--connection claude` or `--connection gpt:NAME` when launching. If the user's allocation is unclear, ask which connection should do each assignment. Never reroute a failed assignment. Use separate worktrees when workers could edit the same files.

Assign each check to one owner. Keep briefs and run records outside Git.

## Configure the worker

Read this chat’s saved settings:

```bash
python3 scripts/settings.py show
```

Claude assignments can use the saved task-type or profile model routes below. GPT assignments use the selected account's Codex CLI default unless the user requests a specific GPT model with `--model`.

- `--task-type`: use the saved model route for this kind of task.
- `--profile`: choose a saved tier, such as Fast, Standard or Deep.
- `--model`: use a model explicitly requested by the user.

Honor the user’s saved choices and tell them which model you will launch.
Use `--effort` if the assignment requires a different reasoning effort
and the model supports it.

Use `--role` to label the worker’s assignment and `--selection-reason`
to record why you selected its model. Describe the actual responsibilities in the task brief.

Use the saved permission policy. Override it with `--permissions` only
when the user authorizes a different policy for this run. Do not increase permissions automatically after a denial.

## Launch a worker

Check this chat’s delegation setting:

```bash
python3 scripts/session.py status
```

Automatic delegation requires it to be enabled. If the user explicitly
requests a one-time assignment while delegation is off, add `--once`.
This does not change the chat’s delegation setting.

Launch the worker with the brief and the options selected above:

```bash
python3 scripts/delegate.py \
  --cwd /absolute/path/to/workspace \
  --prompt-file /absolute/path/to/brief.md \
  --output-dir /absolute/path/to/run-1 \
  --task-type implementation \
  --mode edit
```

The three path arguments are required:

- `--cwd`: an existing workspace where the worker will operate.
- `--prompt-file`: the file containing its assignment.
- `--output-dir`: a new directory for this run’s reports and records.

Use `--mode read` for inspection or `--mode edit` when the worker needs
to change files. Follow the harness guide for tool permissions.

Keep the process handle and output directory for waiting and follow-up
work. Do not launch another worker just because the first is quiet.

The default timeout is 900 seconds. Use `--timeout` to change it.

## Continue a worker

Resume an existing worker when it needs to make corrections or continue
the same assignment. Write a follow-up brief explaining the remaining work.

```bash
python3 scripts/delegate.py \
  --resume-from /absolute/path/to/run-1 \
  --cwd /absolute/path/to/workspace \
  --prompt-file /absolute/path/to/follow-up.md \
  --output-dir /absolute/path/to/run-2 \
  --mode edit
```

- `--resume-from`: the previous run’s output directory.
- `--cwd`: the same workspace the worker used before.
- `--prompt-file`: the new instructions.
- `--output-dir`: a new directory for this follow-up run’s records.

Pass the mode and tool allowances the worker still needs. The current
saved permission policy applies.

Claude keeps its previous model and reasoning effort unless you select different ones. GPT keeps its requested model or uses the selected account's CLI default.

Start a fresh worker when an independent review is required.

## Wait

Keep the `run_id` from the `started` event.

Before ending the turn, run `python3 scripts/completion_hook.py arm --run-id RUN_ID`
for each pending worker. If it reports `unavailable`, use `wait.py` instead.

If Tafwid confirms its completion hook is active for this chat, do any
independent work that is useful. When you need a worker's result, give a
short waiting update and end the turn. The hook waits and resumes you
when a worker finishes or needs attention. Do not start a monitoring
agent or poll the worker.

If the hook is unavailable, use `wait.py` with the pending run IDs.
When it returns `waiting`, repeat with only `pending_run_ids`.

## Accept the result

Read the worker’s compact report and check results. Confirm that the
work meets the task’s requirements; `completed` alone does not prove this.

Reuse passing tests and reviews that apply to the final code. You do not
need to repeat them yourself. Run or delegate only missing checks, failed
checks, or checks affected by later changes.

Inspect relevant code or diffs when the evidence is insufficient or a finding needs investigation. Avoid adding another review when an existing review already satisfies the task’s requirements.

Send needed corrections to the existing worker. After corrections, reuse evidence that remains valid and verify the affected behavior.

For `needs_review`, determine what caused the warning and whether it
prevented completion. After a timeout or interruption, inspect partial
work before continuing.

Tell the user what was completed, verified, and remains unresolved.
Keep long worker transcripts out of your context.
