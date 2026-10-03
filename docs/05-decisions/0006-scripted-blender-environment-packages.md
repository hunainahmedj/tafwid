# ADR-0006: Scripted Blender environment packages and a lighting bake-off

- Date: 2026-10-03
- Status: Accepted

## Context

Hand-written procedural geometry ([ADR-0003](0003-local-procedural-office.md))
could not reach the richness of the user's reference images. The user has
Blender and ComfyUI on `work-station` and asked for a fair comparison of two
authoring approaches, at full effort, before choosing one.

## Options considered

- Procedural geometry in the browser: no art pipeline, but limited
  richness and every prop costs code.
- Modular kit, lit in real time (pipeline A): reusable pieces and a dynamic
  sun, with a heavier runtime.
- Unique scene with baked lighting (pipeline B): global illumination and
  many lights for free at runtime, but every change goes through a bake.
- Driving Blender's interface through screen control: slow and fragile.

## Decision

Author environments as Python (`bpy`) scripts in
`prototypes/agent-world/art/`. They run headless on `work-station` over
SSH, where Blender 5.1.1 uses the RTX 5090. Both pipelines share one layout
and one style C kit and produce the same package contract: `manifest.json`
plus `scene.glb`, validated by the runtime. The runtime cannot tell which
pipeline built a package.

Pipeline B bakes lighting only (irradiance at half energy, stored in 8-bit
maps). Each surface keeps its palette colour, and the runtime multiplies the
two, restoring the π factor that Three's basic lighting divides out.

After three critique rounds on the café square, neither pipeline reached
the 8.0 target. Pipeline A scored 7.3 and pipeline B scored 7.4; scores and
evidence are in the
[review record](../../prototypes/agent-world/REVIEW.md). The 0.1 gap is
within the critics' variance, so the visuals did not decide it. The
practical differences:

- **Build time:** A builds in about 6 seconds, B in about 3 minutes.
- **Lighting:** A has a dynamic sun; B fixes one time of day per bake.
- **Package size:** A is 5.4 MB, B is 9.8 MB.
- **Static lighting quality:** B's bounce light and ambient occlusion are
  richer.

Both run vsync-locked at 60 fps on the M5 Max. Which pipeline M3 uses is
open and belongs to the user ([TAF-8](../01-project/backlog.md)).

## Consequences

Assets become reviewable, reproducible code, but building them requires
`work-station`. The accepted café packages are committed so the prototype
runs without Blender. Blender's exporter did not emit GPU instances, so
the runtime instances repeated kit pieces at load. Future environments
reuse the kit, the layout conventions and the validator. This supersedes
[ADR-0003](0003-local-procedural-office.md) for new environment work.
