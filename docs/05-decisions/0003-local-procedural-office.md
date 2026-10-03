# ADR-0003: Local procedural office with independent rendering

- Date: 2026-09-30
- Status: Superseded by [ADR-0006](0006-scripted-blender-environment-packages.md)

## Context

The approved prototype needs a lightweight 3D office and clear status
information without coupling the plugin runtime to a web service.

## Options considered

- Pre-rendered artwork: simple delivery, limited character picking and reuse.
- Imported modeled assets: rich authoring, extra tool and export dependencies.
- Procedural Three.js geometry: reusable, locally runnable, and directly selectable.

## Decision

Use a standalone Vite/TypeScript app with procedural Three.js geometry and
synthetic fixtures. The DOM dashboard owns selection and remains functional
if the independently loaded renderer fails. Render only for state/size/
visibility changes; batch static meshes by material within each selectable
workstation. Use project-owned Playwright and axe checks for repeatable
interaction and accessibility validation.

## Consequences

No Blender installation, remote asset generation, or backend is needed to
run the prototype. The renderer still adds a substantial optional JS chunk;
measurements and limits are recorded in the
[review evidence](../../prototypes/agent-office/REVIEW.md). Detailed character
animation and live data require further work. Tracked in
[TAF-2](../01-project/backlog.md).
