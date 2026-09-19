# Tafwid · تفويض

**Delegate work. Keep control.**

Tafwid lets Codex delegate bounded work to coding agents while retaining task
ownership, independent review and user communication. A local dashboard shows
workers, resumed runs, instructions, results and recorded orchestrator activity.

**Version 0.1 supports Claude Code as the worker backend.** Cursor, OpenCode and
OpenRouter integrations are planned, not implemented. Superpowers and other
workflow plugins are optional; Tafwid can forward relevant worker instructions
without copying the entire parent conversation.

## What it does

- Turn delegation on or off for one Codex task, independently of other tasks.
- Route task types through editable model tiers and overrides.
- Resume a worker in its own session; keep independent reviewers separate.
- Forward selected instructions once, retaining verified unchanged instructions
  on resumes and matching compatible installed skills when possible.
- Wait for completion with compact results instead of repeatedly loading logs.
- Hand unsupported browser or computer actions back to Codex.
- Keep permission choices explicit: Scoped, Full access, or Follow Codex.
- Track workers and their individual runs, with filters, conversation names,
  settings and public Codex activity in a local dashboard.

Tafwid offloads work; it does not guarantee a percentage reduction in Codex usage.
The orchestrator still spends tokens on briefs, acceptance checks and corrections.

## Requirements

- Codex with plugin support.
- macOS or Linux; Windows process management is not supported in this release.
- Python 3.10 or newer. Runtime uses the standard library only.
- Claude Code on `PATH`, signed in through `claude auth login` with a supported
  Claude subscription. The adapter checks subscription authentication and rejects
  API-key or alternate-provider overrides. Account limits and extra-usage settings
  still apply; Tafwid is not a spending cap.

Node.js is needed only for contributor dashboard tests, not normal use.

## Install

Add this repository as a Codex marketplace and install its plugin:

```sh
codex plugin marketplace add hunainahmedj/tafwid
codex plugin add tafwid@tafwid
```

Start a new Codex task so it discovers the installed skill. Invoke `$tafwid`, or
select the Tafwid skill in the composer, then say:

```text
Turn delegation on for this task.
```

Other useful requests:

```text
Show delegation status.
Open the Tafwid workers dashboard.
Turn delegation off for this task.
```

Delegation starts **off**, and permissions default to **Scoped**. Turning it off
prevents new dispatches; it does not cancel an already-running worker. Explicit
one-shot delegation is also supported without changing the task switch.

In Dashboard → Settings, choose model routing and permissions. Current presets
are Sonnet, Opus and Fable; choose aliases available to your Claude account.
An explicit `--model` can select a different alias or exact ID. Tafwid does not
silently substitute another billing provider when a model or quota is unavailable.

### Existing claude-delegate users

See [migration](docs/migration.md) before replacing a personal installation.
Existing state is reused in place, including task switches, model overrides and
worker history. Neither installation nor an update should copy private history
into this repository. This package does not edit your global `AGENTS.md` or stop
running workers.

## How delegation works

Codex prepares the task brief and selects relevant role/skill files. The launcher
starts Claude, records the run, and returns a compact result. Codex reviews the
actual work before accepting it. Corrections resume the same implementer;
independent reviews use a separate session.

Workers report checks with their tested code state, later edits and outstanding
work. Optional test retries need a relevant change or diagnostic reason; required
CI and independent acceptance checks remain required. These are agent
instructions, not a mechanical guarantee that every worker follows them.

The dashboard uses a loopback HTTP server and a local access token. It has no
separate telemetry service. Worker prompts go to the selected backend under that
backend's configuration; do not assume this makes model inference local.

## Contribute and extend

```sh
git clone https://github.com/hunainahmedj/tafwid.git
cd tafwid
make test
```

Tests use temporary homes and a fake Claude executable. They do not need a Claude
account or make model requests. See [CONTRIBUTING.md](CONTRIBUTING.md),
[architecture](docs/architecture.md), and [the roadmap](docs/roadmap.md).

## License

MIT. See [LICENSE](LICENSE). Claude Code, Codex and referenced third-party plugins
are separate products with their own terms; they are not bundled or endorsed by
this project.
