# Tafwid agent office

A local prototype of a low-poly office and synchronized agent dashboard.
All agents, tasks, elapsed times, and metrics are fictional sample snapshots.
It never reads Tafwid's private state or launches workers.

## Run

Requires Node 20.19+ or Node 22.12+ (including newer supported major versions).
From this directory:

```sh
npm ci
npm run dev
```

Open http://127.0.0.1:4173. Choose a sample day, empty office, or unavailable
updates using the scenario selector. Select a character, workstation name,
or roster entry to inspect its task. Filters apply to the roster; selecting
a hidden agent in the office reveals it under All agents.

## Verify

```sh
npx playwright install chromium
npm test
npm run build
```

Tests start the local Vite server when needed. The build produces `dist/`;
`npm run preview` serves it locally. The app uses no remote models or fonts.

See [critique and verification evidence](REVIEW.md) for the iteration rubric,
results, known limits, and desktop/mobile images. The project's
[dashboard module](../../docs/04-modules/dashboard.md) is the documentation entry point.

## Structure

- `src/model.ts`: state transitions and honest derived metrics.
- `src/fixtures.ts`: the three fictional scenarios.
- `src/dashboard.ts`, `src/styles.css`: accessible DOM view and layout.
- `src/office.ts`: on-demand rendering, camera, selection, and fallback.
- `src/office-assets.ts`: procedural furniture and role-specific characters.
- `src/main.ts`: composition, including independent lazy loading of the room.

The roster remains usable if WebGL, its context, or the scene download fails.
Rendering runs on demand and suspends in hidden tabs. There is no idle
animation; reduced-motion preferences are also respected by CSS.

This is a design prototype, outside the distributable plugin. Live data,
persistent character identity, worker controls, and shared spaces are
separate work described in the [roadmap](../../docs/01-project/roadmap.md).
