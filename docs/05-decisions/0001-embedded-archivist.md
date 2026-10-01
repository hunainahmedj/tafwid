# ADR-0001: Embedded Archivist documentation

- Date: 2026-09-30
- Status: Accepted

## Context

Tafwid has existing repository documentation but no Archivist tree. The user
requested Archivist documentation and approved the recommended embedded layout.

## Options considered

- Embed in `docs/`: documentation travels with the project and its changes.
- Separate sibling repository: independent documentation history, but an
  additional checkout and risk of conflating unrelated neighboring projects.

## Decision

Use embedded Archivist and a self-tracked backlog with prefix TAF. No
external tracker was supplied; the local backlog is the initial convention.
Preserve existing guide links and working specs/plans. Vendor the documentation
hooks and wire repository briefing pointers.

## Consequences

Documentation and code can change together. Neighboring projects remain
outside scope. Host hook trust is still required where applicable.
Bookkeeping follows the [documentation guide](../07-meta/documentation-guide.md).
Tracked in [TAF-1](../01-project/backlog.md).
