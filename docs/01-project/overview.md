# Overview

## What problem does this solve?

Tafwid helps a Codex user delegate bounded work to Claude Code or named
GPT Codex CLI accounts while retaining control of permissions, routing,
and acceptance. The [runtime module](../04-modules/delegation.md) describes
how the existing product works.

The dashboard vision makes that work understandable at a glance: users
should see which agents are working, what they are doing, and what needs
attention. Its first experiment is a simple dashboard with a compact 3D
office, an agent roster, and a few honest stats.

## Who is it for?

The immediate audience is a person coordinating coding agents through
Tafwid. They need a reliable overview without repeatedly reading worker
logs or treating an animation as evidence of successful work.

The longer-term audience includes friends and colleagues invited into a
user's agent workspace. Shared presence is a product ambition, not an
existing collaboration capability.

## Business context

Keep delegation understandable and accountable as more agents work in
parallel. Success for the initial dashboard means quickly recognizing
active work and attention states, while keeping setup and rendering light.
No commercial model or delivery dates have been established.

## Long-term office vision

Create a beautiful, low-poly 3D environment where agents visibly work in an
office. Each agent can have an appearance and personality suited to its
role. The environment should be colorful, vibrant, and playful while
remaining professional, trustworthy, and calm enough for everyday work.

Low-poly assets support both lightweight rendering and a manageable
modeling workflow. The experience can expand from a compact office overview
to richer spaces, then invitations for friends or colleagues to join.
Roles, persistent identity, personality, and backend provider are distinct
concepts that will need deliberate product models.

The [roadmap](roadmap.md) sequences this vision. The
[dashboard module](../04-modules/dashboard.md) links to the first prototype
scope. [Environments](../02-workspace/environments.md) records available
asset-authoring tools without assuming access has been verified.
