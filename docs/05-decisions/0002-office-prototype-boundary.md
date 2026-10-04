# ADR-0002: Compact office and roster before live integration

- Date: 2026-09-30
- Status: Superseded by [ADR-0005](0005-open-agent-world.md)

## Context

The user wants a low-poly agent office over time, starting with a simple
dashboard. They approved the recommended hybrid prototype design.

## Options considered

- Flat dashboard: easiest to build, weak validation of the spatial vision.
- Compact office and readable roster: evaluates the idea with a small scope.
- Navigable shared office: richer experience with substantial extra systems.

## Decision

Use the compact office and roster approach described in the
[approved spec](../superpowers/specs/2026-09-30-agent-office-dashboard-design.md).
Keep the first iteration local and driven by clearly labeled synthetic data.
Keep future live integration and social features separate.

## Consequences

The prototype can test visual clarity without coupling the plugin to a
browser runtime. It cannot demonstrate live-agent fidelity or multiplayer.
Framework and detailed implementation choices remain in the implementation
plan until reviewed. Tracked in [TAF-2](../01-project/backlog.md).
