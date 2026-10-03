# ADR-0005: An open agent world with explore and dashboard modes

- Date: 2026-10-03
- Status: Accepted

## Context

The [first prototype](0002-office-prototype-boundary.md) placed a small
isometric office inside a dashboard card. The user found it flat and closed.
They want an open, atmospheric world framed like Minecraft Dungeons, with
environments that have personality and extend into a surrounding city.
Users and companies should eventually choose between several environments,
and a player character and shared spaces may follow.

## Options considered

- Keep the diorama and polish it: small effort, but it keeps the closed
  feeling the user rejected.
- World beside a persistent panel: preserves the dashboard layout, but the
  world stays secondary.
- Two modes: a full-screen *Explore* world with a light overlay, plus an
  information-first *Dashboard* mode sharing the same world view.

## Decision

Build a new local prototype in `prototypes/agent-world/` with both modes.
Explore is the primary experience. The camera keeps a fixed high pitch and
pans, zooms, rotates and follows an agent. The art uses style C, the
"chunky hybrid": a block grid with bevelled edges and chibi characters.
Places carry meaning: an agent's status chooses its zone (workstation,
review spot, lounge), and badges and ground rings always repeat the status.
Environments arrive as validated packages. Only curated environments exist
until there is evidence that people want a builder. The design is in the
[agent world spec](../superpowers/specs/2026-10-03-agent-world-design.md).

## Consequences

`prototypes/agent-office/` remains as the TAF-2 reference. The new runtime
needs camera, navigation and rendering work that the diorama avoided. It
stays outside the released plugin and uses sample data only. Live data
([TAF-3](../01-project/backlog.md)), persistent identity
([TAF-4](../01-project/backlog.md)) and shared presence
([TAF-5](../01-project/backlog.md)) remain separate work. This supersedes
the compact-diorama boundary of
[ADR-0002](0002-office-prototype-boundary.md).
