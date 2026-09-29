# Office dashboard

## What is it?

A local prototype combining a compact 3D office with an accessible agent
roster. It uses fictional sample snapshots and is separate from the released
Tafwid plugin. Work is tracked in [TAF-2](../01-project/backlog.md).

## Why was it built?

See the [product vision](../01-project/overview.md) for the desired user
experience and [ADR-0002](../05-decisions/0002-office-prototype-boundary.md)
for the chosen first boundary.

## When is it used?

Use it locally to evaluate whether a person can
understand current work and attention states from the dashboard.

## How does it work?

The [prototype README](../../prototypes/agent-office/README.md) owns run
instructions and implementation structure. Its [review record](../../prototypes/agent-office/REVIEW.md)
owns critique scores, verification evidence, and limits.

One state model drives the room and roster. The rendering module loads
independently of the dashboard, and the accessible roster works if 3D
is unavailable. See [ADR-0003](../05-decisions/0003-local-procedural-office.md)
for this implementation boundary.

## Code location

| Repo / package | Paths |
| --- | --- |
| Tafwid | `prototypes/agent-office/`, outside the distributable plugin |

## Decisions

[ADR-0002 — Office prototype boundary](../05-decisions/0002-office-prototype-boundary.md).

## Tracker

[TAF-2](../01-project/backlog.md); subsequent integration and expansion are
sequenced in the [roadmap](../01-project/roadmap.md).

## Ownership

See [ownership](../06-admin/ownership.md).

## Planned & open questions

Persistent agent identity, acceptance state, and shared-space access require
separate models before live integration or social features are introduced.
