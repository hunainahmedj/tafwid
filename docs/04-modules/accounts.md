# Named GPT accounts

## What is it?

The account entry point lets users set up named GPT destinations for
Codex CLI workers and check whether those destinations are ready.

## Why was it built?

A coordinator needs to choose an exact account deliberately and retain
that choice when continuing work.

## When is it used?

Use the account skill when adding or checking named GPT connections. Follow
[account setup](../account-setup.md) for the user-facing procedure.

## How does it work?

The [system architecture](../03-architecture/system.md) explains private
account homes and connection identity. The packaged
[GPT account guide](../../plugins/tafwid/skills/delegate/references/gpt-accounts.md)
contains worker rules and troubleshooting. Authentication material is never
a fixture or documentation example.

## Code location

| Repo / package | Paths |
| --- | --- |
| Tafwid | `plugins/tafwid/skills/account/`, `plugins/tafwid/skills/delegate/scripts/account.py`, `accounts.py`, `connections.py`, `codex_cli.py` in the same scripts directory |

## Decisions

See the [mixed-account design](../superpowers/specs/2026-09-29-multiple-gpt-accounts-design.md)
for historical rationale.

## Tracker

[TAF-1](../01-project/backlog.md) captures initial documentation.

## Ownership

See [ownership](../06-admin/ownership.md).
