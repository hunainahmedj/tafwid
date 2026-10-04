# Agent world — open 3D environments and a lighting bake-off

Date: 2026-10-03

The user approved the scope, milestones and runtime architecture in
conversation on 2026-10-03. They asked Claude to self-review the remaining
sections (environment package, pipelines, bake-off, testing) and proceed.
This document scopes a local prototype; it is not a claim that the released
plugin contains a dashboard. The durable product vision lives in the
[overview](../../01-project/overview.md).

## Intent

The [first prototype](2026-09-30-agent-office-dashboard-design.md) put a
small isometric diorama inside a SaaS card. It answered "can a person read
agent state from a room?" but felt flat and closed. The user wants an open,
atmospheric world: Minecraft Dungeons-style camera framing, a "small
Minecraft world with shaders" mood, and environments with personality that
extend into a surrounding city.

Long-term, users and companies choose from several environments (office
building, café, rooftop terrace), a player character walks among the agents
with a switchable third-person camera, and coworkers and their agents share
a space. This effort builds the foundation and answers one open question:
**which authoring and lighting approach reaches the reference look?**

### What the user decided

- **Two modes.** *Explore* is a full-screen world with a light HUD (the
  favourite). *Dashboard* is an information-first layout with the world
  in a panel.
- **Art style C, "chunky hybrid".** World on a block grid with bevelled
  edges; chibi characters with large heads. Distinct from Minecraft while
  staying easy to model.
- **Camera.** A fixed high pitch with a narrow field of view. Free pan,
  zoom and 90° rotation by default; clicking an agent follows it. An
  on-screen control cluster duplicates the gestures.
- **Places carry meaning.** Agent status maps to a zone role and a pose.
  Badges always duplicate status.
- **Curated environments only.** There is no environment builder until
  there is evidence people want one.
- **Bake-off.** Build the same café square with two pipelines at full
  effort and compare them in one runtime.
- **No player control** in this effort.

### Art direction (from four user-supplied references)

| Quality | Meaning in this world |
| --- | --- |
| A world beyond the room | Each environment sits in a slice of city: streets, neighbouring façades, trees, fading into fog and focus blur at the edges. |
| Miniature lighting | Warm low sun, long soft shadows, ambient occlusion in corners, tilt-shift depth of field. |
| Glowing light sources | String lights, lit windows, signs and monitors bloom; one time-of-day preset per environment. |
| Life | Ambient passers-by, birds, steam and swaying foliage, visually distinct from agents and never conveying status. |
| Density and personality | Many small props; bushy, clustered trees; a palette, lighting and signature props per environment. |
| "Minecraft with shaders" | Block-grid forms with subtle surface detail (brick, cobble, planks), lit richly. |

Success means the user recognises the reference mood in the café square,
reads every agent's state at a glance, and the scene runs smoothly on their
M5 Max laptop at the High tier.

## Scope

In scope:

1. A runtime in a new `prototypes/agent-world/` (outside the plugin). It
   includes the camera rig, HUD, both modes, status badges, agent zone and
   pose behaviour with walking transitions, ambient life, and quality
   tiers. It uses clearly labelled sample data only.
2. An *environment package* contract that both pipelines produce.
3. Pipeline A: a scripted modular kit, lit in real time.
4. Pipeline B: a scripted unique scene with Cycles-baked lighting.
5. The café square built with both pipelines, switchable live.
6. A critique loop: an independent agent scores each pipeline's result,
   with up to three improvement rounds per pipeline.

Milestones: **M1** runtime skeleton on a placeholder package; **M2** the
café bake-off; **M3** (a later backlog item) the office floor and street
with the winning pipeline.

Out of scope: a player character or third-person camera, live Tafwid data
([TAF-3](../../01-project/backlog.md)), an environment builder, multiplayer
or Slack ([TAF-5](../../01-project/backlog.md)), sound, a rooftop
environment, and persistent agent identity
([TAF-4](../../01-project/backlog.md)). `prototypes/agent-office/` stays as
the TAF-2 reference.

## Runtime architecture

Vite and TypeScript with no UI framework, matching `agent-office`.
Three.js `WebGPURenderer` falls back automatically to its WebGL2 backend;
post-processing uses Three's node-based passes.

```text
SnapshotSource ──► Store ──► Dashboard view   (DOM)
 (fixtures now)     │   ├──► Explore HUD      (DOM)
                    │   └──► World            (Three.js)
                    ◄────── selection and camera events
```

| Unit | Responsibility | Depends on |
| --- | --- | --- |
| `app/store` | Agents, selection, mode, active environment, derived stats; one-way updates | nothing |
| `app/fixtures` | Sample scenarios behind a `SnapshotSource` interface | store types |
| `world/renderer` | Renderer creation, quality tier, post stack per tier | three |
| `world/environment` | Load and validate a package; expose zones, walk grid, ambience, bounds; dispose | three, contract |
| `world/camera-rig` | Pan, zoom, 90° rotation, follow, bounds | pure maths |
| `world/agents` | Status to zone and pose; walk along A* paths when status changes | environment, pathfinding |
| `world/pathfinding` | A* on the walk grid | pure |
| `world/characters` | Procedural chibi characters with rigid limbs, shared by agents and extras | three |
| `world/ambient` | Passers-by on declared paths, birds, steam, foliage sway | environment |
| `world/overlay` | Project status badges (DOM buttons) over characters | camera |

Characters stay procedural in the runtime for both pipelines. Rigid,
box-limbed figures need no skinning, so they are cheap to animate and
identical in both lighting conditions.

| Status | Zone role | Pose |
| --- | --- | --- |
| Working | `workstation` (assigned in roster order) | Seated, typing |
| Awaiting review | `review` | Standing, waves |
| Ready | `lounge` | Walks the lounge loop |
| Needs attention | Stays at its workstation | Standing, marker above head |

When an agent's status changes, it walks along the A* path to its new zone.
A sample-data control steps through a scripted status change so this can
be observed.

### Failure handling

| Condition | Behaviour |
| --- | --- |
| WebGPU unavailable | WebGL2 backend, same features |
| No WebGL at all, or context loss | Dashboard mode without the world; Explore disabled with an explanation |
| Package fails validation or loading | An error card names the problem; other variants stay selectable |
| Sustained frame time above the tier budget | Step down one tier and show it in the HUD |
| Reduced-motion preference | No ambient animation, instant camera moves, no depth-of-field breathing |

Keyboard users select every agent from the roster and badge buttons.
Status is never conveyed only by position, colour or animation.

## Environment package contract

A package is a directory served by the prototype:

```text
public/environments/<environment-id>/<variant>/
  manifest.json
  scene.glb
```

`manifest.json` (schema `tafwid.environment/1`):

| Field | Content |
| --- | --- |
| `schema`, `id`, `variant`, `name` | Identity; `variant` is `kit` or `baked` |
| `scene` | Relative GLB path |
| `lighting` | `realtime` or `baked` |
| `grid` | `cellSize`, `origin` `[x, z]`, `width`, `depth`, `walkable` (one string per row, `.` walkable, `#` blocked) |
| `zones` | `workstation[]`, `review[]`, `lounge[]`; each has `id`, `position` `[x, y, z]`, `facing` (radians) and `pose` (`seated`, `standing`); lounge entries may add `loop` (grid points) |
| `ambientPaths[]` | `id`, `kind` (`pedestrian`, `bird`), `points`, `loop` |
| `camera` | `home` (`target`, `yaw`, `distance`), `bounds`, `zoom` `[min, max]` |
| `ambience` | Sun direction, colour and intensity; hemisphere colours; fog; exposure; bloom; depth-of-field focus and range; sky colours |

The Blender build script writes the manifest from the same data it uses to
place geometry. Zone empties also go into the GLB for debugging, but the
runtime reads only the manifest. The runtime validates every manifest
before use: required zone counts (at least six workstations, one review
spot, one lounge), zone positions on walkable cells, and paths that connect
every zone. A failure produces a named error rather than misplaced agents.

## Asset pipelines

Both pipelines are Python (`bpy`) scripts in
`prototypes/agent-world/art/`. They run headless in Blender 5.1 on
`work-station` over SSH, using its RTX 5090 and OptiX. Each build writes a
package plus preview renders. Blender on the Mac is optional and only for
manual inspection.

```text
art/
  lib/        shared helpers: bevelled blocks, palette, materials, grid, manifest writer
  kit/        pipeline A: kit pieces and the café layout
  baked/      pipeline B: café scene, UV unwrap, bake, export
  build.sh    sync to work-station, run Blender, fetch packages and previews
```

Both pipelines share `lib/` and the café's grid layout data, so the two
variants have the same footprint, zones and paths. They differ in how the
geometry is assembled and lit.

### Pipeline A — modular kit, real-time lighting

- Kit pieces follow strict grid conventions: 1 m cells, a shared bevel
  radius, and pivots at the cell corner. Pieces include floor tiles
  (cobble, planks, tiles), wall modules with window, door and cut-away
  variants, façade modules, awnings, roof caps, props and tree clusters.
- The layout places linked duplicates; export uses GPU instancing
  (`EXT_mesh_gpu_instancing`), which Three loads as instanced meshes.
- Surface detail comes from modelled bevels plus a small shared texture
  atlas. Kit pieces may carry baked self-occlusion in vertex colours.
- At runtime: a directional sun with cascaded or fitted shadows, a
  hemisphere fill, emissive materials with bloom, screen-space ambient
  occlusion, tilt-shift depth of field, fog and AgX tone mapping, all
  per tier.

### Pipeline B — unique scene, baked lighting

- The café scene is modelled as a whole. It uses the same `lib/`
  helpers, with geometry joined per area and a second UV set packed for
  lightmaps.
- Cycles bakes direct plus indirect lighting into lightmap textures for
  the golden-hour preset. Export marks static surfaces unlit and keeps
  emissive materials separate so bloom still applies.
- At runtime, characters and extras use real-time lights that match the
  bake, plus soft contact shadows. Post-processing is lighter (bloom,
  tilt-shift, fog, tone mapping); ambient occlusion is already in the
  bake.

### Size budgets and storage

Built packages are generated output. During iteration they stay out of Git;
the accepted versions are committed at the end of M2. Budgets: kit package
up to 10 MB, baked package up to 25 MB (compressed geometry and WebP or
KTX2 textures).

## The café square

Both variants build the same place, in late-afternoon golden hour:

- **The café.** A single-storey brick annex under a taller brick
  building, with a cut-away interior: half-height walls and no ceiling,
  so agents inside stay visible. Inside are a counter with an espresso
  machine and pastry case, a chalkboard (the review spot), and laptop
  tables (workstations).
- **The terrace.** Tables under string lights; some workstations sit
  outside.
- **The square.** Cobblestones, a fountain, bushy tree clusters,
  planters, benches, lamp posts, a bicycle rack, and a lounge loop
  around the fountain.
- **The context ring.** Neighbouring shops (bakery, bookshop) with
  awnings and lit windows, streets leading away with ambient pedestrian
  paths, and lower-detail background buildings fading into fog and blur.

## Bake-off evaluation

An independent critique agent reviews each round. It sees screenshots in
both modes and at several zoom levels, the four references, frame-time
measurements, and this spec. It scores each pipeline from 0 to 10:

| Criterion | Weight |
| --- | --- |
| Ambience and reference fidelity (lighting, mood, miniature feel) | 25 % |
| Richness and personality (density, outside world, signature props) | 20 % |
| Dashboard readability (agents, status, HUD clarity) | 20 % |
| Style C coherence (bevelled blocks, readable chibi characters) | 15 % |
| Technical quality (no shadow acne, seams, aliasing, z-fighting or lightmap bleeding) | 10 % |
| Performance (frame time per tier, load size) | 10 % |

A pipeline is satisfactory at **8.0 or above**. Each pipeline gets at most
three critique rounds; work stops earlier once it is satisfactory. Scores
are subjective judgements by an agent, recorded with their evidence, not
objective guarantees.

Frame times are measured on the user's M5 Max in a GPU-backed browser,
using an in-app frame-time sampler. Headless software rendering is never
reported as performance. No other hardware is available, so lower-tier
behaviour is reported as measured on the same machine.

## Testing and verification

- **Unit tests (Vitest):** store transitions and derived stats, camera
  rig maths and bounds, A* paths, manifest validation (valid and invalid
  fixtures), status-to-zone mapping.
- **Browser tests (Playwright):** load, switching mode and variant,
  selection kept in sync across world, badge and roster, follow and
  release, the camera control cluster, keyboard navigation, the no-WebGL
  fallback, an axe accessibility check, and screenshots for evidence.
- **Pipeline checks:** every built manifest passes the runtime validator
  through a Node script; package sizes are checked against the budgets.
- **Plugin integrity:** `python3 scripts/check_package.py` still passes;
  the plugin runtime is untouched.

## Documentation

- A new ADR supersedes ADR-0002's compact-diorama boundary. A second ADR
  records the scripted Blender pipeline and the package contract, and its
  result section names the bake-off winner.
- The dashboard module doc points to the new prototype. The environments
  doc records the verified work-station capability.
- The backlog gains items for this effort and for M3.

## Deferred

The player character and third-person camera, live data, persistent
identity and per-agent desks, environment builder, rooftop and other
environments, sound, multiple time-of-day presets, invitations, shared
presence, and Slack.
