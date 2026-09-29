# Agent Office Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a local, sample-data dashboard that makes agent activity clear through a colorful low-poly office and a synchronized roster.

**Architecture:** A standalone browser prototype outside the distributable plugin. One typed state model drives DOM panels and a Three.js scene; no live runtime adapter or backend. Native execution in this chat is recommended because the three tasks share small interfaces and can be checked together.

**Tech Stack:** Vite 8.3.1, TypeScript 7.0.2, Three.js 0.186.1, @types/three 0.186.0, @playwright/test 1.63.0. These versions were checked against npm metadata during planning. Use Node 20.19+ or 22.12+ as required by Vite; the current environment has Node 20.20.2. Commit exact dependencies and the generated lockfile.

**Spec:** [Approved design](../specs/2026-09-30-agent-office-dashboard-design.md).

## Global Constraints

- The prototype always displays "Sample data".
- One local workspace; synthetic fixtures; no worker-control actions.
- Fixed isometric camera and four example workstations.
- Agent selection is synchronized between the room and roster.
- No spend, token allowances, or progress estimates.
- Completion and acceptance are separate concepts.
- The roster and details remain usable if WebGL is unavailable.
- No network-loaded models or fonts are needed for the prototype.
- Render on demand, bound pixel ratio to 2, and honor reduced motion.
- Desktop and mobile require functional checks and a visible walkthrough.
- Preserve the plugin runtime, supported backends, release versions, and private state.

## Review Focus

- A filter hides the selected agent: choose the first visible agent or clear selection; room selection changes the filter to All if needed (Task 1).
- Unavailable updates: retain the labeled last sample snapshot with unknown current counts, rather than presenting stale counts as current (Task 1).
- A scene click follows a resize: raycasting uses current canvas bounds and selects the visible workstation (Task 2).
- WebGL creation failure or context loss: the accessible roster and details continue functioning with a clear room fallback (Task 2).
- Narrow viewport, long task text, or keyboard-only input: controls and details remain readable and operable without clipping or hover (Task 3).

## File map

All prototype paths below are relative to `prototypes/agent-office/`.

| Files | Responsibility |
| --- | --- |
| `package.json`, `package-lock.json`, `tsconfig.json`, `index.html` | Reproducible local app and strict type checking |
| `src/model.ts`, `src/fixtures.ts` | State transitions, metrics, and fictional scenarios |
| `src/main.ts`, `src/dashboard.ts`, `src/styles.css` | Composition root, accessible DOM panels, responsive visual system |
| `src/office.ts`, `src/office-assets.ts` | Scene lifecycle, picking, reusable primitive furniture and characters |
| `playwright.config.ts`, `tests/model.spec.ts`, `tests/dashboard.spec.ts` | Project-owned regression checks |
| `README.md` | Local run instructions, demo limits, validation evidence |

Root changes: `.gitignore` for dependency/test outputs; Archivist dashboard module, backlog, ownership, changelog, and an ADR for the implemented rendering boundary.

### Task 1: Usable dashboard and shared state

**Files:** Create the app scaffolding, `src/model.ts`, `src/fixtures.ts`, `src/main.ts`, `src/dashboard.ts`, `src/styles.css`, `playwright.config.ts`, and `tests/model.spec.ts`.

**Interfaces:**
- `Agent`: `id`, `name`, `role`, `backend` (`claude` or `gpt`), `status` (`working`, `review`, `ready`, `attention`), `task`, `elapsedSeconds`, `nextStep`, `color`.
- `Scenario`: `id` (`active`, `empty`, `unavailable`), `agents: Agent[]`, `completedRuns: number`, `fresh: boolean`. Completed runs are a separate fixture value, not the number of ready characters.
- `DashboardState`: `scenario: Scenario`, `filter: Filter`, `selectedId: string | null`; `Filter` is `all`, `working`, or `attention`.
- `createState(scenario): DashboardState`; `transition(state, action): DashboardState`; actions select an agent (source `scene` or `roster`), set a filter, or change scenario.
- `visibleAgents(state): Agent[]`; `metrics(scenario): {working: number | null; review: number | null; completed: number}`.
- `mountDashboard(root, dispatch): {render(state): void; sceneHost: HTMLElement; dispose(): void}`. Dispatch receives the same actions as `transition`.

- [x] Create scripts `dev` (Vite on localhost), `build` (tsc --noEmit then vite build), `preview`, and `test` (playwright test). Pin the listed packages, use strict TypeScript, and ignore node_modules, dist, test-results, and playwright-report.
- [x] Write `tests/model.spec.ts` with no browser fixture. Assert: active scenario has 2 working agents, 1 review agent, 1 ready agent, and 7 completed runs; attention filter includes review; hiding selection chooses the first visible entry; an empty filter clears selection; scene selection reveals its agent; an unknown ID is ignored; changing scenario resets selection; unavailable metrics return null for current working/review counts.
- [x] Run `npm test -- tests/model.spec.ts`; verify failure from missing model implementation.
- [x] Implement the interfaces and fixtures. Active agents are fictional coordinator, builder, researcher, reviewer. Include an attention agent in the unavailable scenario, where 4 previously completed runs remain historical and current counts are unknown. Empty scenario has zero agents and runs.
- [x] Run model tests and type checking; require both to pass.
- [x] Implement dashboard composition and semantic DOM: header, persistent Sample data badge, labeled scenario selector, three derived metrics, office host, filter buttons, selectable roster, and detail panel. Show a no-agent message and an unavailable-update notice with explicit sample context. Preserve focus when rendering selection changes.
- [x] Apply the approved palette and system typography. Use role accents and readable status labels, differentiated surface hierarchy, and a branching Tafwid mark. Use no unused navigation or pretend controls.
- [x] Verify the DOM app locally with keyboard selection and scenario switching; commit this independently usable dashboard slice with a TAF-2 reference.

### Task 2: Lightweight selectable office

**Files:** Create `src/office.ts`, `src/office-assets.ts`, `tests/dashboard.spec.ts`; update `src/main.ts` and `src/styles.css`.

**Interfaces:**
- `createOffice(host: HTMLElement, onSelect: (id: string) => void): {update(state: DashboardState): void; dispose(): void}`.
- `createWorkstation(agent: Agent): THREE.Group`; `createRoom(): THREE.Group`. Pickable descendants carry `userData.agentId`.
- Compose the DOM and scene around one state in `main.ts`; do not maintain a second selected-agent state in Three.js.

- [x] Write browser checks that selecting a roster entry updates details and selection semantics, changing scenarios updates the room's accessible summary, and the WebGL-disabled case still supports all roster interactions. Run them before scene integration and record the missing behavior.
- [x] Build four primitive workstations, role-colored characters with simple distinct accessories, floor, low walls, plants, and a restrained selected-workstation indicator. Use a fixed orthographic camera; do not add navigation, physics, or continuously running idle animation.
- [x] Implement raycasting from current canvas bounds. Share the selection callback with DOM controls. Fit camera framing with ResizeObserver, cap pixel ratio at 2, request frames only when necessary, and defer rendering while the document is hidden.
- [x] Catch renderer initialization failure and handle context loss with an accessible fallback. Dispose observers, listeners, geometries, materials, and renderer on teardown. The DOM view must remain functional independently.
- [x] Add a browser check selecting a visible workstation by canvas coordinates, repeat after resize, and assert the corresponding detail heading changes. Use bounding-box-derived click coordinates from the fixed camera; keep them in the test rather than adding public test controls.
- [x] Verify scene selection, fallback behavior, and TypeScript build. Visually inspect one desktop view for clipped objects and readable selection before committing the office slice with a TAF-2 reference.

### Task 3: Complete interaction, visual verification, and documentation

**Files:** Update `tests/dashboard.spec.ts`, `playwright.config.ts`, `src/styles.css`, prototype `README.md`, and the listed Archivist homes.

**Interfaces:** Reuse Tasks 1–2; no new application services or public APIs.

- [x] Configure Chromium desktop (1440×1000) and mobile (390×844) checks against a localhost Vite web server. Keep test artifacts under ignored test-results and playwright-report directories.
- [x] Assert filters, selection reconciliation, all three scenarios, exact derived stats, always-visible Sample data, empty and unavailable notices, and absence of horizontal overflow. Inject a long task string into the fixture during a focused check, then retain a representative long fixture if needed to preserve coverage.
- [x] Assert keyboard selection and visible focus; check reduced-motion emulation. Force WebGL context creation failure with a browser init script and verify selecting a roster agent still updates details. Exercise context loss when the browser exposes the extension.
- [x] Run `npm test` and `npm run build`; require passing results. Fix actual failures without broadening the feature scope.
- [x] Use the approved available browser surface for a visible desktop and mobile walkthrough. Inspect screenshots for framing, density, contrast, long text, touch targets, and status clarity. Record evidence and report any backend limitation honestly. Check for console errors and missing network assets.
- [x] Measure local startup/load and inspect renderer draw calls/triangles on the available machine. Record observed evidence without claiming cross-device performance guarantees. Remove temporary instrumentation before the final build.
- [x] Write local commands (`npm ci`, `npm run dev`, `npm test`, `npm run build`), sample-data limits, WebGL fallback, and actual verification evidence in the prototype README. Update `docs/04-modules/dashboard.md`, `docs/06-admin/ownership.md`, `docs/07-meta/changelog.md`, and TAF-2 in the backlog. Add the next numbered ADR for the implemented technical choice and update its index.
- [x] Run `python3 scripts/check_package.py` and `git diff --check`. Plugin runtime changes are not planned; if any become necessary, run `make test` and review that scope before proceeding.
- [x] Obtain the execution workflow's independent final review, resolve material findings, and commit only intended source/docs. Open the localhost prototype in the user's Codex browser panel and report the run command plus remaining live-data limitation.

## Plan review

Self-review: all spec sections map to the three tasks. Shared types have one
definition, the five review risks have explicit checks, and invitations,
live data, remote generation, and worker controls remain deferred. Package
integrity scans the repository, so generated browser artifacts must be kept
outside scanned source or cleaned from the prototype before that check.

The user approved proceeding with the recommended native execution and a
maximum of five build–critique–improve rounds on 2026-09-30. The critique
rubric and evidence live in the prototype review record.
