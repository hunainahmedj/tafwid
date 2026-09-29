# Delegation

## What is it?

The part of Tafwid that lets a Codex coordinator assign a bounded task to
a supported worker, follow its completion, and inspect the result.

## Why was it built?

It helps users divide work while preserving explicit permissions and
independent acceptance. See the [product purpose](../01-project/overview.md).

## When is it used?

Use the delegate skill when configuring this chat's delegation switch or
assigning work. The [README](../../README.md) documents the public workflow.

## How does it work?

[System architecture](../03-architecture/system.md) is the authoritative
runtime description. The packaged [workflow](../../plugins/tafwid/skills/delegate/references/workflow.md)
provides operational instructions; [benchmarks](../benchmarks.md) record
measured costs and limitations. No model requests are needed for ordinary
[offline verification](../../CONTRIBUTING.md).

## Code location

| Repo / package | Paths |
| --- | --- |
| Tafwid | `plugins/tafwid/skills/delegate/scripts/`, `plugins/tafwid/skills/delegate/tests/`, `plugins/tafwid/hooks/` |

## Decisions

Existing behavior predates this decision log. Historical rationale remains
in the [mixed-account spec](../superpowers/specs/2026-09-29-multiple-gpt-accounts-design.md).

## Tracker

[TAF-1](../01-project/backlog.md) captures initial documentation.

## Ownership

See [ownership](../06-admin/ownership.md).
