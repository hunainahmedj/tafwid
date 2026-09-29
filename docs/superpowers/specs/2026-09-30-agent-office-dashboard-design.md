# Agent office dashboard — prototype proposal

Date: 2026-09-30

The user approved the recommended design on 2026-09-30. This document
scopes the prototype; it is not a claim that a dashboard exists. The durable
product vision lives in the [Archivist overview](../../01-project/overview.md).

## Intent

Give a Tafwid user a quick, understandable view of the agents working for
them. The user wants a colorful, vibrant, low-poly 3D office that feels
welcoming and professional. Over time, agents should have appearances and
personalities related to their roles, and users should be able to invite
friends or colleagues into their space.

For this first prototype, success means understanding who is working,
what each agent is doing, and which results need attention without having
to interpret a game world. Keep the interface and setup simple.

Approved initial boundary: browser-based local prototype, one workspace,
synthetic example data, and no worker-control actions in the first pass.

## Approaches considered

| Approach | Strength | Cost |
| --- | --- | --- |
| Flat dashboard with illustrated avatars | Smallest build and simplest mobile layout | Does not meaningfully test the office idea |
| Compact 3D office plus accessible agent roster | Tests the distinctive idea while preserving clear information | Requires a small rendering layer and fallback |
| Navigable office with movement and interaction | Closest to the long-term spatial vision | Adds camera, navigation, collision and onboarding work before the basic dashboard is proven |

Recommendation: compact 3D office plus roster. Use a fixed isometric camera
and a small room with four example workstations. Keep richer environments
and multiplayer out of this prototype.

## Screen and interactions

```text
Tafwid                         My workspace        Sample data

Your team, at work.
Working now     Awaiting review     Completed this session

+--------------------------------+-------------------------+
|                                | Agent roster            |
|      Isometric office          | Name / role / status    |
|      Four workstations         | Current task / elapsed  |
|      Select a character        | Select an agent         |
|                                |                         |
+--------------------------------+-------------------------+
| Selected agent: task, provider, status, timing, next step |
+----------------------------------------------------------+
```

- Agent selection is synchronized between a workstation and its roster
  entry. The selected agent's details appear below without changing pages.
- Filter the roster by all agents, working, and needs attention. Selection
  remains visible and coherent when a filter changes.
- Sample states cover working, awaiting review, ready, and an issue that
  needs attention. A small demo scenario selector also exercises an empty
  workspace and unavailable updates. These controls are explicitly demos.
- No decorative navigation to unimplemented pages, fake invites, or
  nonfunctional launch/pause controls.
- On mobile the office is a compact overview, followed by stats, roster,
  and details; no horizontal scrolling or hover-only information.

## Visual direction

Spend the visual personality on the room and characters. Keep information
panels quiet, legible, and compact. Use low-poly geometry, matte materials,
soft lighting, rounded furniture, plants, and restrained role accents.

Proposed palette: porcelain `#F5F7FB`, ink `#202B3D`, cobalt `#4263EB`,
mint `#52C8A0`, apricot `#FFB66E`, and lilac `#A496E8`. Colors identify
roles and selection; every status also has a readable label and icon.
Use a locally available system sans-serif stack with a clear hierarchy.
Preserve Tafwid's name and branching mark. This is a dashboard art direction
proposal, not an automatic replacement for existing plugin branding.

Example roles: coordinator, builder, researcher, reviewer. Differentiate
them with clothing color, simple accessories, and workstation props. Role
and provider are separate concepts; Claude and GPT are worker backends,
not personalities. Names and roles in the prototype are fictional.

## Proposed technical boundary

An isolated `prototypes/agent-office/` browser application, outside the
distributable plugin. Prefer Vite, TypeScript, and a small Three.js scene
made from reusable primitive meshes. Choose exact dependencies during
implementation planning. Avoid a physics engine, multiplayer SDK, asset
pipeline, and backend service in the initial prototype.

Run locally with a documented install command and dev-server command.
Keep all example data in a typed fixture module. Derive both the room and
the roster from the same selection and data state. Render on demand;
pause any optional idle motion in hidden tabs and respect reduced motion.
Keep pixel ratio bounded and do not make shadows essential to readability.

The roster and details remain usable if WebGL is unavailable. Keyboard
users select every agent through standard buttons. A character's state is
never conveyed by animation alone. No network-loaded models or fonts are
needed for the prototype.

Blender on `work-station` and the connected Higgsfield service are potential
later asset-authoring tools, as reported by the user. Access has not been
verified. Primitive geometry keeps the first prototype independent of
remote tools, generated assets, and paid generation jobs.

## Honest data and future integration

The proposed prototype always displays "Sample data". It must not suggest
that real agents are being observed or controlled.

Stats derive from the selected sample scenario: working now, awaiting
review, and completed in that session. Elapsed time is labeled as elapsed,
never as a fabricated completion percentage. Completion and acceptance
are separate concepts: a worker finishing does not establish that Codex
accepted its result. No spend, token allowances, or progress estimates.

Future integration needs a separately reviewed local read-only projection
of task-scoped Tafwid run records. Existing code is in
`plugins/tafwid/skills/delegate/scripts/run_state.py`. It records status,
timestamps, backend and connection information; it does not supply a
persistent character identity or independent acceptance state. Do not
infer either without a defined model. A stale launcher heartbeat must be
presented as unavailable or uncertain activity, not proof a worker stopped.

Never expose credential paths, observation keys, private raw transcripts,
or arbitrary workspace files to a future browser client. Invitations and
shared spaces need their own identity, consent, and visibility design.

## Acceptance checks

1. A user can identify active agents, their current tasks, and attention
   states from the first screen.
2. Selecting an agent in either view updates the same details; roster
   filters and sample scenarios behave consistently.
3. Stats match fixture data, and sample status is visible throughout.
4. Desktop and mobile receive both functional checks and a visible browser
   walkthrough. Check keyboard focus, reduced motion, and WebGL fallback.
5. The room is recognizable, low-poly, and colorful; the information remains
   readable without the scene. Check loading and responsiveness on the
   available test machine and report evidence without inventing benchmarks.
6. The existing plugin's runtime and packaged assets remain independently
   usable; package integrity still passes.

## Deferred scope

Live worker integration, launching or cancelling agents, account allowance
metrics, persistent role/personality configuration, custom Blender assets,
walking around, multiple rooms, invitations, chat, and shared presence.

## Execution constraint

The user requested up to five build–critique–improve rounds, stopping once
a structured score exceeds 8.5/10. Record the rubric and evidence; do not
treat a subjective score as an objective guarantee.
