# ADR-0007: Ship baked curated scenes; keep the kit for authoring and a future builder

- Date: 2026-10-03
- Status: Accepted

## Context

The café bake-off
([ADR-0006](0006-scripted-blender-environment-packages.md)) ended in a
near tie: the kit scored 7.3 and the baked scene 7.4. Reviewing both, the
user found the baked lighting clearly more natural. Path tracing gives sky
occlusion in every corner, bounce light, and real light pools under lamps.
Real-time lighting can only approximate these. Both variants are built from
the same kit and layout; the baked variant joins the kit pieces per area and
bakes their light.

## Options considered

- **Ship the real-time kit:** fast builds and a dynamic sun, but visibly
  flatter light.
- **Ship baked scenes and drop the kit:** the best look, but every scene
  change goes through Blender, and there is no route to user-made scenes.
- **Ship baked scenes and keep the kit:** curated scenes get the baked
  look; the kit stays the authoring source, a 6-second layout preview, and
  the basis for scenes users assemble in the browser without Blender.

## Decision

Ship curated environments as baked packages. Keep the modular kit:

- It is the source both variants are built from.
- It is the fast preview while authoring layouts.
- It is the candidate for a future in-browser scene builder, lit in real
  time ([TAF-9](../01-project/backlog.md)).

The no-builder boundary in
[ADR-0005](0005-open-agent-world.md) still holds until that work starts.

## Consequences

- **Curated scenes** need a Blender bake. That build-time cost falls on the
  author, never on users.
- **Time of day** is fixed per bake. A day/night cycle would mean baking a
  few presets and blending between them.
- **The kit's real-time path** stays maintained, because a builder would
  depend on it.
- **TAF-8** becomes: improve the baked café using the critique list, then
  build the office floor and street baked.
