# Tafwid

![Tafwid — Delegate work. Keep control.](plugins/tafwid/assets/cover.png)

**Delegate work. Keep control.**

Tafwid lets Codex delegate bounded tasks to Claude Code or named GPT accounts. Codex coordinates the
work and accepts the result using concise reports and relevant checks.

## What it does

- Enable a task-local pool of Claude and named GPT accounts.
- Choose a Claude model explicitly or use saved task-based routing.
- Launch a worker and resume it with corrections.
- Wait for completion without repeatedly loading worker logs.
- Keep permissions explicit: Scoped, Full access, or Follow Codex.
- Save private briefs, raw results and compact reports for each run.

Delegation does not guarantee lower Codex usage. Planning, task briefs and
acceptance checks still consume tokens.
See [benchmark findings](docs/benchmarks.md) for measured coordinator, worker and
waiting costs across three task types.

## Requirements

- Codex with plugin support.
- macOS or Linux and Python 3.10 or newer. No third-party Python packages required.
- Claude Code on `PATH`, signed in through `claude auth login` with a supported
  Claude subscription. API-key and alternate-provider overrides are rejected.
  Account limits and extra-usage settings still apply.
- For GPT workers, Codex CLI on `PATH` and a separate ChatGPT sign-in for each
  named account. See [account setup](docs/account-setup.md).

## Install

```sh
codex plugin marketplace add hunainahmedj/tafwid
codex plugin add tafwid@tafwid
```

Start a new Codex task and select a skill from the `$` menu:

| Skill | Purpose | Example |
| --- | --- | --- |
| `$tafwid:delegate` | Assign work or manage this task's switch | `$tafwid:delegate on` |
| `$tafwid:account` | Add and check named GPT accounts | `$tafwid:account add gpt business` |

A bare `$tafwid:delegate` reports status. Delegation starts off. Turning it off
prevents new automatic dispatches; running workers continue. An explicit one-time
assignment is also supported without changing the switch.

For updates, run `codex plugin marketplace upgrade tafwid`, reinstall the plugin,
and start a new task. See [migration](docs/migration.md) for existing installations.

## How to use it

Codex writes a brief with the goal, workspace, constraints and acceptance criteria.
The launcher starts the selected worker and returns a compact result. Corrections resume the
same worker; an independent review, when needed, uses a separate worker.

Use the [shared workflow](plugins/tafwid/skills/delegate/references/workflow.md),
[Claude Code guide](plugins/tafwid/skills/delegate/references/claude-code.md),
and [GPT account guide](plugins/tafwid/skills/delegate/references/gpt-accounts.md).
Each public script supports `--help`.

To let Tafwid resume Codex when a worker finishes, review and trust Tafwid's
hooks in Codex (`/hooks` in the CLI). Without hook trust, the workflow uses
`wait.py` instead.

Claude worker permissions default to Scoped. `settings.py show` shows its saved
model routes and can change its permissions. GPT workers use read-only or
workspace-write sandboxes. Use `--model` for an explicit model choice.
Tafwid does not silently change billing providers when a model is unavailable.

Run artifacts stay in the caller's private output directory. Tafwid does not
fetch account allowances. Keep private evidence outside Git. Worker prompts are
sent through the selected CLI; inference is not necessarily local.

## Contribute

The [project documentation](docs/README.md) covers the runtime and planned office dashboard.

Run `make test` for package checks and offline Python tests. Tests use temporary
homes and fake workers; they do not make model requests. See
[CONTRIBUTING.md](CONTRIBUTING.md) and [architecture](docs/architecture.md).

## License

MIT. See [LICENSE](LICENSE). Claude Code and Codex are separate products with
their own terms and are not bundled or endorsed by this project.
