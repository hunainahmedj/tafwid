# Agent dashboard

## What is it?

A local prototype of an open 3D world where you can watch your agents work.
Agents sit at desks, wait at a review board or wander a lounge, and the room
itself shows their state. Every agent also carries a status badge and a
coloured ring. It has two views:

- **Explore:** a full-screen world with a light overlay.
- **Dashboard:** an information-first page with the same world in a panel.

Everything shown is fictional sample data. The prototype is separate from
the released Tafwid plugin.

## Why was it built?

The [product vision](../01-project/overview.md) asks for a beautiful,
low-poly space that makes agent work understandable at a glance.
[ADR-0005](../05-decisions/0005-open-agent-world.md) explains why the
first, closed office diorama gave way to an open world.

## When is it used?

Locally, to judge whether people can read agent work from a living scene,
and to compare ways of building richer environments. It also gives later
work a runtime to build on: live data, more environments and shared spaces.

## How does it work?

The [prototype README](../../prototypes/agent-world/README.md) owns run,
build and verification commands and the code structure. The
[spec](../superpowers/specs/2026-10-03-agent-world-design.md) records the
design.

- **Runtime:** a store feeds the DOM views and a Three.js WebGPU world. It
  falls back to WebGL2 on older browsers, and to dashboard-only mode when
  there is no 3D at all.
- **Environments:** each one is a package (`manifest.json` + `scene.glb`).
  The runtime validates every package before use: zones by role, a walk
  grid, camera bounds and ambience.
- **Agents:** they walk A* paths between zones when their status changes.
- **Building packages:** headless Blender scripts produce the packages.
  There are two pipelines, a real-time-lit kit and a baked scene;
  [ADR-0006](../05-decisions/0006-scripted-blender-environment-packages.md)
  explains both.
- **Critique record:** the [review record](../../prototypes/agent-world/REVIEW.md)
  owns the critique rounds, scores and limits.

The first prototype, `prototypes/agent-office/`, remains as the TAF-2
reference. Its [review record](../../prototypes/agent-office/REVIEW.md)
holds that evidence.

## Code location

| Repo / package | Paths |
| --- | --- |
| Tafwid | `prototypes/agent-world/` (runtime, `art/` build scripts, `public/environments/`), `prototypes/agent-office/` (first prototype); both outside the distributable plugin |

## Decisions

- [ADR-0002 — Office prototype boundary](../05-decisions/0002-office-prototype-boundary.md) (superseded)
- [ADR-0003 — Local procedural office](../05-decisions/0003-local-procedural-office.md) (superseded)
- [ADR-0005 — Open agent world](../05-decisions/0005-open-agent-world.md)
- [ADR-0006 — Scripted Blender environment packages](../05-decisions/0006-scripted-blender-environment-packages.md)

## Tracker

[TAF-2](../01-project/backlog.md), [TAF-7](../01-project/backlog.md); next
steps are sequenced in the [roadmap](../01-project/roadmap.md).

## Ownership

See [ownership](../06-admin/ownership.md).

## Planned & open questions

- Which pipeline the office environment uses: planned in
  [TAF-8](../01-project/backlog.md).
- Persistent agent identity and per-agent desks ([TAF-4](../01-project/backlog.md)).
- Live, read-only data ([TAF-3](../01-project/backlog.md)).
- Shared presence ([TAF-5](../01-project/backlog.md)).

Each needs its own model before integration.
