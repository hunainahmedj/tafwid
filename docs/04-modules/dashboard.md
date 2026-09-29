# Office dashboard

## What is it?

A planned visual overview of agent work, beginning with a compact 3D office
and an accessible agent roster. Planned work is tracked as
[TAF-2](../01-project/backlog.md); no released dashboard behavior is asserted here.

## Why was it built?

See the [product vision](../01-project/overview.md) for the desired user
experience and [ADR-0002](../05-decisions/0002-office-prototype-boundary.md)
for the chosen first boundary.

## When is it used?

The first prototype will be used locally to evaluate whether a person can
understand current work and attention states from the dashboard.

## How does it work?

The approved [design](../superpowers/specs/2026-09-30-agent-office-dashboard-design.md)
and proposed [implementation plan](../superpowers/plans/2026-09-30-agent-office-dashboard.md)
define the experiment. Implementation evidence and run instructions will
be added here when the prototype exists.

## Code location

| Repo / package | Paths |
| --- | --- |
| Tafwid | Proposed `prototypes/agent-office/`, outside the distributable plugin |

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
