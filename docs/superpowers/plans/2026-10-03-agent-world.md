# Agent World Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an open 3D agent world prototype with two modes, and compare a real-time-lit modular kit against a Cycles-baked unique scene for the same café square.

**Architecture:** A Vite/TypeScript app with a pure store feeding DOM views and a Three.js WebGPU world. Environments arrive as validated packages (`manifest.json` + `scene.glb`), produced by headless Blender scripts that run on `work-station`. The world never knows which pipeline built a package.

**Tech Stack:** three 0.186.1 (`three/webgpu`, `three/tsl`), Vite 8.3.1, TypeScript 7.0.2, Vitest, Playwright 1.63.0 with axe-core 4.13.0, Blender 5.1.1 (`bpy`) over SSH on an RTX 5090.

**Spec:** [2026-10-03-agent-world-design.md](../specs/2026-10-03-agent-world-design.md)

## Global Constraints

- Lives in `prototypes/agent-world/`; nothing under `plugins/` changes; `python3 scripts/check_package.py` passes.
- Always visibly labelled "Sample data"; no live Tafwid state is read.
- Node `^20.19.0 || >=22.12.0` (same as `agent-office`); no network-loaded fonts or models at runtime.
- Manifest schema string is exactly `tafwid.environment/1`; variants are exactly `kit` and `baked`.
- Validator minimums: ≥ 6 workstations, ≥ 1 review, ≥ 1 lounge; every zone on a walkable cell and mutually reachable.
- Package budgets: kit ≤ 10 MB, baked ≤ 25 MB.
- Critique: satisfactory at ≥ 8.0/10 per pipeline; at most 3 rounds per pipeline.
- Built packages and previews are untracked during iteration; accepted packages are committed at the end of M2.
- Remote build root on work-station: `/mnt/c/tafwid-art` (Windows `C:\tafwid-art`); Blender at `/mnt/c/Program Files/Blender Foundation/Blender 5.1/blender.exe`.
- User-supplied reference images are not committed; critique inputs live in gitignored `prototypes/agent-world/.critique/`.

## Review Focus

1. **Switching variant while an agent is followed or mid-walk** — selection survives, the agent re-seats in the new package, and no meshes from the old package remain (`environment.dispose` test plus an e2e switch-while-following check, Task 9).
2. **A status change whose target zone is unreachable or occupied** — the agent still ends at a sensible spot (fall back to teleport-and-log, never freeze); reviewers sharing one review spot get offsets (Task 4).
3. **Resizing or switching mode while rendering** — the canvas moves between layouts without stretching or losing context; badges stay aligned (e2e resize and mode toggle with a badge-position assertion, Task 9).
4. **A manifest with a malformed `walkable` row (wrong length or unknown character)** — named validation error, no crash (Task 2).
5. **Background tab or reduced motion** — rendering pauses in hidden tabs and ambient motion stops under `prefers-reduced-motion` (e2e with emulated media, Task 9).

---

### Task 1: Scaffold the prototype

**Files:**
- Create: `prototypes/agent-world/{package.json,tsconfig.json,vite.config.ts,vitest.config.ts,playwright.config.ts,index.html,README.md,.gitignore}`, `src/main.ts`, `src/styles.css`

- [ ] **Step 1:** Create `package.json` (name `tafwid-agent-world`, private, `type: module`) with scripts `dev` (`vite --host 127.0.0.1 --port 4174`), `build` (`tsc --noEmit && vite build`), `test` (`vitest run`), `e2e` (`playwright test`), `validate` (`node --experimental-strip-types scripts/validate-packages.ts`). Dependencies: `three@0.186.1`; dev: `@types/three@0.186.0`, `typescript@7.0.2`, `vite@8.3.1`, `vitest`, `@playwright/test@1.63.0`, `@axe-core/playwright@4.13.0`.
- [ ] **Step 2:** `.gitignore` ignores `node_modules/`, `dist/`, `test-results/`, `playwright-report/`, `art/previews/`, `.critique/`, and `public/environments/*/*/` until M2 acceptance.
- [ ] **Step 3:** `npm install`, then `npm run build`. Expected: exits 0 with an empty app shell.
- [ ] **Step 4:** Commit `feat(agent-world): scaffold prototype (TAF-7)`.

### Task 2: Environment manifest contract and validator

**Files:**
- Create: `src/contract/manifest.ts`, `src/contract/validate.ts`, `src/contract/grid.ts`, `scripts/validate-packages.ts`
- Test: `tests/unit/validate.test.ts`, `tests/unit/fixtures/manifest.valid.json`

**Interfaces:**
- Produces:
  - `type Vec2 = [number, number]`, `type Vec3 = [number, number, number]`
  - `interface Zone { id: string; position: Vec3; facing: number; pose: 'seated' | 'standing'; loop?: Vec2[] }`
  - `interface EnvironmentManifest` with the spec's fields: `schema`, `id`, `variant`, `name`, `scene`, `lighting`, `grid {cellSize, origin, width, depth, walkable}`, `zones {workstation, review, lounge}`, `ambientPaths[] {id, kind, points, loop}`, `camera {home {target, yaw, distance}, bounds {minX, maxX, minZ, maxZ}, zoom}`, `ambience {sun {direction, color, intensity}, hemisphere {sky, ground, intensity}, fog {color, near, far}, exposure, bloom {strength, radius, threshold}, dof {focusOffset, range, strength}, sky {top, bottom}}`
  - `validateManifest(input: unknown): { ok: true; manifest: EnvironmentManifest } | { ok: false; errors: string[] }`
  - `worldToCell(grid, x: number, z: number): [col: number, row: number]`, `cellToWorld(grid, col, row): Vec2` (cell centre)
  - `parseWalkable(grid): WalkGrid` (shared with Task 3)

- [ ] **Step 1: Write failing tests** in `validate.test.ts`:
  - `accepts the valid fixture` → `ok === true`.
  - `rejects a wrong schema` → errors contain `schema: expected "tafwid.environment/1"`.
  - `requires six workstations` (fixture with 5) → `zones.workstation: at least 6 required, found 5`.
  - `requires a review spot` → `zones.review: at least 1 required, found 0`.
  - `rejects a zone on a blocked cell` → `zones.workstation[2] (ws-3) is on a blocked cell`.
  - `rejects an unreachable zone` (walled-off review) → `zones.review[0] (review-1) is not reachable from zones.workstation[0] (ws-1)`.
  - `rejects a malformed walkable row` (row too short; row with `x`) → `grid.walkable[4]: expected 12 characters, found 11` and `grid.walkable[5]: unknown character "x"`.
  - `round-trips worldToCell and cellToWorld`.
- [ ] **Step 2:** `npx vitest run tests/unit/validate.test.ts`. Expected: FAIL (modules missing).
- [ ] **Step 3:** Implement. Validation is hand-written (no schema library); reachability uses `findPath` from Task 3 — implement Task 3 first if executing in order matters, or BFS here via `WalkGrid`.
- [ ] **Step 4:** Tests pass.
- [ ] **Step 5:** `scripts/validate-packages.ts` walks `public/environments/*/*/manifest.json`, validates each, checks `scene.glb` exists, prints `OK <id>/<variant> <size MB>` or the errors, and fails above the size budgets (kit 10 MB, baked 25 MB).
- [ ] **Step 6:** Commit `feat(agent-world): validate environment packages (TAF-7)`.

### Task 3: Walk-grid pathfinding

**Files:**
- Create: `src/world/pathfinding.ts` · Test: `tests/unit/pathfinding.test.ts`

**Interfaces:**
- Produces: `interface WalkGrid { width: number; depth: number; walkable(col: number, row: number): boolean }`, `type Cell = [number, number]`, `findPath(grid: WalkGrid, from: Cell, to: Cell): Cell[] | null` (inclusive of both ends), `simplifyPath(path: Cell[]): Cell[]` (drops collinear points).

- [ ] **Step 1: Failing tests:** `returns [start] when start equals goal`; `walks a straight corridor` (length 6 for a 5-step corridor); `routes around a wall`; `returns null when the goal is enclosed`; `never cuts a blocked corner diagonally`; `simplifyPath keeps only turning points`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** A* with 8 neighbours, octile heuristic, diagonal moves only when both orthogonal neighbours are walkable; binary-heap open set.
- [ ] **Step 4:** Run → PASS. **Step 5:** Commit `feat(agent-world): find walk-grid paths (TAF-7)`.

### Task 4: Store, fixtures and status behaviour

**Files:**
- Create: `src/app/types.ts`, `src/app/store.ts`, `src/app/fixtures.ts`, `src/app/behaviour.ts`
- Test: `tests/unit/store.test.ts`, `tests/unit/behaviour.test.ts`

**Interfaces:**
- Produces:
  - `type AgentStatus = 'working' | 'review' | 'ready' | 'issue'`
  - `interface Agent { id; name; role; provider: string; status: AgentStatus; task: string; elapsedMinutes: number | null; next: string; look: { skin: string; shirt: string; hair: string; accent: string } }`
  - `interface Snapshot { scenarioId: string; agents: Agent[]; completedThisSession: number }`
  - `interface AppState { snapshot: Snapshot; selectedId: string | null; mode: 'explore' | 'dashboard'; environmentId: string; variant: 'kit' | 'baked'; filter: 'all' | 'working' | 'attention'; quality: Tier; qualityAuto: boolean; worldAvailable: boolean; worldError: string | null }`, `type Tier = 'low' | 'medium' | 'high'`
  - `createStore(initial: AppState): Store` with `get()`, `dispatch(action: Action)`, `subscribe(fn: (s: AppState, prev: AppState) => void): () => void`
  - `Action` union: `select {id|null}`, `setMode`, `setVariant`, `setFilter`, `snapshot {snapshot}`, `setQuality {tier, auto}`, `worldUnavailable {reason}`
  - `deriveStats(s: Snapshot): { working: number; review: number; attention: number; completed: number }`
  - `interface SnapshotSource { current(): Snapshot; subscribe(fn): () => void; advance(): void }`, `createFixtureSource(scenarioId: 'productive-day' | 'quiet-morning'): SnapshotSource` — `advance()` steps a scripted sequence (Rex issue → working; Ada working → review; Noor ready → working)
  - `type Pose = 'seated-typing' | 'standing-wave' | 'wander' | 'standing-alert'`
  - `assignZones(agents: Agent[], zones: EnvironmentManifest['zones']): Map<string, { zone: Zone; pose: Pose; offset: Vec2 }>`
- [ ] **Step 1: Failing tests:**
  - store: `select updates selection and notifies`; `setFilter keeps a selected agent selected even when filtered out`; `snapshot that removes the selected agent clears selection`; `deriveStats counts working 2, review 1, attention 1, completed 7 for productive-day`.
  - behaviour: `working agents sit at the workstation matching their roster index`; `issue agents stand alert at their own workstation`; `review agents share review[0] with distinct offsets`; `ready agents wander the lounge loop`; `throws a named error when there are more agents than workstations`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement; fixtures reuse the five agents from the mockup (Milo, Ada, Cleo, Noor, Rex) with providers "GPT · Codex CLI" / "Claude Code". **Step 4:** Run → PASS. **Step 5:** Commit `feat(agent-world): model agents and zone behaviour (TAF-7)`.

### Task 5: Camera rig and frame sampler

**Files:**
- Create: `src/world/camera-rig.ts`, `src/world/frame-sampler.ts`
- Test: `tests/unit/camera-rig.test.ts`, `tests/unit/frame-sampler.test.ts`

**Interfaces:**
- Produces:
  - `interface RigState { target: Vec2; yaw: number; yawGoal: number; distance: number; distanceGoal: number; pitch: number; followId: string | null }` (pitch fixed at `0.92` rad, FOV 26°)
  - `createRig(home: EnvironmentManifest['camera']['home']): RigState`
  - `pan(s, dxPx, dyPx, viewportHeightPx, bounds): RigState` (clears `followId`), `rotate(s, dir: 1 | -1)` (±π/2 on `yawGoal`), `zoom(s, delta, range)`, `goHome(s, home)`, `follow(s, id | null)`
  - `step(s, dt, followTarget: Vec2 | null, reducedMotion: boolean): RigState` (exponential easing; instant when reduced)
  - `cameraPose(s): { position: Vec3; lookAt: Vec3 }`
  - `createFrameSampler(windowSize = 120)`: `push(ms)`, `stats(): { p50; p95; count }`, `shouldStepDown(budgetMs): boolean` (true when ≥ 120 samples and p95 > budget)
- [ ] **Step 1: Failing tests:** `rotate snaps yawGoal by quarter turns`; `zoom clamps to range`; `pan clamps target to bounds and stops following`; `step converges on the follow target`; `reduced motion jumps straight to goals`; `cameraPose sits distance away at the fixed pitch`; sampler `p95 of a known series`; `shouldStepDown false below 120 samples`.
- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5:** Commit `feat(agent-world): add camera rig and frame sampler (TAF-7)`.

### Task 6: Remote Blender build and the placeholder package

**Files:**
- Create: `art/build.sh`, `art/lib/{__init__.py,blocks.py,palette.py,materials.py,manifest.py,export.py}`, `art/placeholder/build.py`

**Interfaces:**
- Produces (Python, used by Tasks 11–13):
  - `blocks.bevel_box(name, size, location, material, radius=0.06, segments=2, collection=None) -> bpy.types.Object`
  - `palette.PALETTE: dict[str, tuple[float, float, float]]` (style C colours from the spec mockups)
  - `materials.get(name, color, roughness=0.85, emission=None, emission_strength=0.0) -> bpy.types.Material`
  - `manifest.write(path, data: dict)` (JSON, sorted keys, 2-space indent)
  - `export.glb(path, gpu_instances: bool)` (glTF binary, meshopt compression when available, Y-up, apply modifiers)
  - `build.sh <target>`: `rsync` `art/` to `work-station:/mnt/c/tafwid-art/src`, run `blender.exe -b --factory-startup --python C:\tafwid-art\src\<target>\build.py -- --out C:\tafwid-art\out\<target>`, then `rsync` back to `public/environments/<env>/<variant>/` and previews to `art/previews/<target>/`. Targets: `placeholder`, `cafe-kit`, `cafe-baked`.
- [ ] **Step 1:** Write the scripts. The placeholder is a 16×12 grid with a perimeter wall, 6 desks, a review board, a lounge loop and a matching manifest.
- [ ] **Step 2:** `art/build.sh placeholder`. Expected: `public/environments/placeholder/kit/{manifest.json,scene.glb}` plus `art/previews/placeholder/preview.png`.
- [ ] **Step 3:** `npm run validate`. Expected: `OK placeholder/kit`.
- [ ] **Step 4:** Commit scripts only: `feat(agent-world): build packages with headless Blender (TAF-7)`.

### Task 7: World rendering, environment loading and characters

**Files:**
- Create: `src/world/renderer.ts`, `src/world/tiers.ts`, `src/world/environment.ts`, `src/world/characters.ts`, `src/world/agents.ts`, `src/world/ambient.ts`, `src/world/overlay.ts`, `src/world/world.ts`

**Interfaces:**
- Consumes: Tasks 2–5.
- Produces:
  - `TIERS: Record<Tier, { pixelRatio: number; shadowMapSize: number; ao: boolean; bloom: boolean; dof: boolean; smaa: boolean; frameBudgetMs: number }>` (low: 1, 1024, no AO/DOF, bloom on, 20 ms; medium: 1.5, 2048, AO, DOF, 16.7 ms; high: devicePixelRatio ≤ 2, 4096, AO, DOF, SMAA, 16.7 ms)
  - `createRenderer(canvas, tier): Promise<WorldRenderer>`; `WorldRenderer { renderer; setTier(t); setAmbience(a: Ambience, lighting); render(scene, camera); resize(w, h); dispose() }` — `RenderPipeline` with `pass` → `ao` (realtime lighting only) → `bloom` → `dof` → `smaa`, AgX tone mapping, exposure from ambience
  - `loadEnvironment(baseUrl): Promise<LoadedEnvironment>`; `LoadedEnvironment { manifest; root: Object3D; walk: WalkGrid; dispose() }`. Meshes whose material name ends `_baked` become `MeshBasicNodeMaterial` with the baked map; emissive materials keep emission for bloom
  - `createCharacter(look, kind: 'agent' | 'extra'): CharacterRig` with `group`, `setPose(pose: Pose | 'walk', time)`, `setAlert(on)`
  - `AgentLayer`: `constructor(scene)`, `setEnvironment(env)`, `sync(agents, assignments)` (walk an A* path when an assignment changes; teleport if no path and log once), `update(dt, time)`, `positionOf(id): Vec3 | null`, `pick(raycaster): string | null`
  - `AmbientLayer`: `setEnvironment(env)`, `update(dt, time)`, `setEnabled(on)`
  - `Overlay`: `constructor(host, onSelect)`, `sync(agents, selectedId)`, `update(camera, positionOf)`
  - `createWorld(host: HTMLElement, store: Store): Promise<World>`; `World { setEnvironment(id, variant): Promise<void>; camera: { rotate(dir); zoom(delta); home() }; dispose() }`
- [ ] **Step 1:** Implement the modules. Rendering pauses when `document.hidden`. The frame sampler feeds `shouldStepDown(TIERS[tier].frameBudgetMs)`; stepping down dispatches `setQuality { auto: true }`. `window.__tafwidPerf = () => sampler.stats()` exposes measurements.
- [ ] **Step 2:** `npm run dev` with `?env=placeholder&variant=kit`. Verify in the browser pane: the scene renders, five agents take their zones, clicking an agent follows it, and there are no console errors.
- [ ] **Step 3:** Commit `feat(agent-world): render environments and agents (TAF-7)`.

### Task 8: Shell, HUD, dashboard and camera controls

**Files:**
- Create: `src/ui/shell.ts`, `src/ui/hud.ts`, `src/ui/dashboard.ts`, `src/ui/camera-controls.ts`, `src/ui/roster.ts`, `src/ui/details.ts`; modify `src/main.ts`, `src/styles.css`

**Interfaces:**
- Consumes: `Store`, `World`, `deriveStats`, `SnapshotSource`.
- Produces: `mountShell(root, store, source): { viewport: HTMLElement }` — one viewport element moved between the explore root and the dashboard world card.

- [ ] **Step 1:** Implement the layouts from the approved mockup (v2):
  - **Explore:**
    - top-left: brand plus the environment-variant switch ("Café · Kit lighting" / "Café · Baked lighting");
    - top-centre: "Sample data";
    - top-right: the mode switch;
    - left: stat chips;
    - right: the roster;
    - bottom-centre: the follow card;
    - bottom-left: hints;
    - bottom-right: the camera cluster (⟲ ＋ ⟳ / compass － ⌂);
    - a "Step the sample day" button beside the sample pill, calling `source.advance()`.
  - **Dashboard:** stats row, world card, roster with working filters, and the in-focus strip.
  - All controls are `<button>`s with labels. If the world is unavailable, Explore is disabled with the text "The 3D world is unavailable on this device. Your team is still here in Dashboard mode."
- [ ] **Step 2:** In the browser pane, verify that both modes, the variant switch and the camera buttons work.
- [ ] **Step 3:** Commit `feat(agent-world): add explore and dashboard modes (TAF-7)`.

### Task 9: Browser tests

**Files:**
- Create: `tests/e2e/world.spec.ts`

- [ ] **Step 1:** Write the tests:
  - `shows sample data and stats`
  - `roster selection follows the agent and shows the follow card`
  - `badge and roster selection stay in sync across a mode switch`
  - `camera buttons change the compass heading`
  - `variant switch while following keeps the selection`
  - `badges stay attached to their characters after a resize`
  - `step the sample day moves Ada to the review spot` (badge position changes over time)
  - `no-WebGL fallback disables explore` (via a `?forceNoWebGL=1` debug flag)
  - `reduced motion stops ambient extras` (`page.emulateMedia({ reducedMotion: 'reduce' })`, then assert `window.__tafwidAmbientEnabled === false`)
  - `axe finds no serious violations in either mode`
  - each mode saves a screenshot to `test-results/evidence/`
- [ ] **Step 2:** `npm run e2e`. Expected: all pass.
- [ ] **Step 3:** Commit `test(agent-world): cover modes, selection and fallback (TAF-7)`.

### Task 10: Café layout shared by both pipelines

**Files:**
- Create: `art/cafe/layout.py`

**Interfaces:**
- Produces: `LAYOUT` with:
  - `size` — about 40 × 32 m
  - `cells` — the walkable rows
  - `placements: list[Placement(kind: str, x: float, z: float, rot: int, params: dict)]` — kinds include `cobble_area`, `café_annex`, `brick_building`, `shopfront(bakery|bookshop)`, `terrace_table`, `laptop_table`, `counter`, `espresso`, `pastry_case`, `chalkboard`, `string_lights`, `fountain`, `tree_cluster`, `planter`, `bench`, `lamp_post`, `bike_rack`, `background_block`, `street`, `awning`
  - `zones` — 8 workstations (4 inside, 4 terrace), review at the chalkboard, a lounge loop around the fountain
  - `ambient_paths` — 3 pedestrian routes along the streets, 2 bird loops
  - `camera` and `ambience` — golden hour: warm sun at about 20° elevation, exposure, bloom, fog towards the context ring
- [ ] **Step 1:** Write it. **Step 2:** Run `python3 -c` to import-check it on the Mac with a `bpy` stub, which confirms the layout module has no `bpy` dependency. **Step 3:** Commit.

### Task 11: Pipeline A — kit pieces and real-time café

**Files:**
- Create: `art/kit/pieces.py`, `art/cafe-kit/build.py`

- [ ] **Step 1:** In `pieces.py`, write one builder per placement kind. Each builder returns a reusable mesh datablock on the 1 m grid with a shared bevel. Brick, cobble and plank surfaces get modelled detail: offset bevelled bricks as instanced modules, and individual cobbles in merged tiles. Window and sign materials are emissive. Tree clusters are stacked bevelled cubes in 3 greens.
- [ ] **Step 2:** In `build.py`, place linked duplicates from `LAYOUT`, then export with `gpu_instances=True`. Write the manifest (`variant: kit`, `lighting: realtime`) and render a Workbench preview.
- [ ] **Step 3:** Run `art/build.sh cafe-kit && npm run validate`. Expected: `OK cafe/kit` within 10 MB.
- [ ] **Step 4:** Look at it in the browser pane on the High tier. Fix any obvious faults (missing pieces, seams, wrong scale) before the critique. Commit the scripts.

### Task 12: Pipeline B — baked café

**Files:**
- Create: `art/cafe-baked/build.py`

- [ ] **Step 1:** Build the scene from the same builders, joined per area (ground, each building, props grouped by area).
- [ ] **Step 2:** Add a `Lightmap` UV set (Smart UV Project, then pack islands at a texel density of about 24 px/m), bake with Cycles OptiX (Combined bake, direct + indirect, 256 samples, denoised), and save per-area WebP lightmaps.
- [ ] **Step 3:** Export the materials as `<area>_baked`, keeping emissive surfaces as separate unbaked objects.
- [ ] **Step 4:** Write the manifest (`variant: baked`, `lighting: baked`). The golden-hour lights match Task 10's `ambience`, so the runtime character lighting agrees with the bake.
- [ ] **Step 5:** Run `art/build.sh cafe-baked && npm run validate`. Expected: `OK cafe/baked` within 25 MB.
- [ ] **Step 6:** Check it in the browser pane, then commit the scripts.

### Task 13: Critique rounds (up to 3 per pipeline)

**Files:**
- Create: `prototypes/agent-world/REVIEW.md`

- [ ] **Step 1:** For each pipeline, capture the evidence set in `.critique/round-N/<variant>/`:
  - Explore at home zoom, close zoom and far zoom
  - Dashboard mode
  - a follow-mode shot
  - a High-tier frame-time readout from `__tafwidPerf()` in a GPU-backed browser pane on the Mac (Medium and Low readouts too)
  - package sizes
- [ ] **Step 2:** Dispatch a fresh critique agent with:
  - the evidence;
  - the four references (copied to `.critique/references/`);
  - the spec's rubric and weights;
  - an instruction to score each criterion, compute the weighted total, and list the 5 highest-impact fixes.
- [ ] **Step 3:** Record the scores, evidence paths and fixes in `REVIEW.md`. If a pipeline is below 8.0 and has rounds left, apply its fixes (in the art scripts and/or runtime), rebuild, and repeat from Step 1.
- [ ] **Step 4:** Commit `docs(agent-world): record critique round N (TAF-7)` after each round.

### Task 14: Accept packages and document outcomes

**Files:**
- Modify: `prototypes/agent-world/.gitignore` (stop ignoring the accepted `public/environments/cafe/*`), `docs/01-project/backlog.md`, `docs/02-workspace/repos.md`, `docs/02-workspace/environments.md`, `docs/04-modules/dashboard.md`, `docs/05-decisions/README.md`, `docs/01-project/roadmap.md`
- Create: `docs/05-decisions/0005-open-agent-world.md` (supersedes ADR-0002's boundary), `docs/05-decisions/0006-scripted-blender-environment-packages.md` (pipeline, contract, bake-off result)

- [ ] **Step 1:** Commit the accepted café packages, checking `npm run validate` first.
- [ ] **Step 2:** Write the ADRs and update the docs, following the documentation guide's single-home rule.
- [ ] **Step 3:** Add backlog entries: TAF-7 for this effort (Done, with evidence links) and TAF-8 for the M3 office with the winning pipeline (Next).
- [ ] **Step 4:** Run `npm test && npm run e2e && npm run build && python3 scripts/check_package.py` from the right directories. Expected: all pass.
- [ ] **Step 5:** Commit `docs: record the agent world and bake-off outcome (TAF-7)`.
