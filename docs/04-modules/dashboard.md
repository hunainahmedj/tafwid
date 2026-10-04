# Agent dashboard

## What is it?

A local prototype of an open 3D world where you can watch your agents work.
It runs in your browser from this repository and is not part of the
released Tafwid plugin.

Every agent is a character: the main session (the coordinator), each
sub-agent it starts, and each Tafwid-delegated worker. A session's agents
form a team. A character's role decides its look, what it is doing decides
its animation, and its status decides where it goes and what its badge and
coloured ring show. Agents walk in when they start and walk out when they
finish.

The world has two sources:

- **Live:** what your agents are really doing, read from the
  [activity log](activity-log.md) on your machine.
- **Sample:** fictional teams, for demos and when the log is off.

It has two views:

- **Explore:** a full-screen world with a light overlay.
- **Dashboard:** an information-first page with the same world in a panel.

## Why was it built?

The [product vision](../01-project/overview.md) asks for a beautiful,
low-poly space that makes agent work understandable at a glance.
[ADR-0005](../05-decisions/0005-open-agent-world.md) explains why the
first, closed office diorama gave way to an open world.
[ADR-0008](../05-decisions/0008-opt-in-activity-log.md) explains how live
data reaches it without costing tokens.

## When is it used?

Locally, by someone running agents who wants to see them at a glance:
who is working, who needs approval, and who has finished. Turn the
activity log on, start the prototype's dev server, and open it; it shows
live activity when the log is on, and sample data otherwise. It is also
where environments and agent behaviour are tried out before anything
becomes a product.

## How does it work?

The [prototype README](../../prototypes/agent-world/README.md) owns run,
build and verification commands, URL options and the code structure. The
designs are in the [agent world spec](../superpowers/specs/2026-10-03-agent-world-design.md)
and the [live agent world spec](../superpowers/specs/2026-10-03-live-agent-world-design.md).

### Runtime

A store feeds the DOM views and a Three.js WebGPU world. It falls back to
WebGL2 on older browsers, and to dashboard-only mode when there is no 3D at
all. Agents walk A* paths over the environment's walk grid.

### Environments and seats

Each environment is a package (`manifest.json` + `scene.glb`, schema
`tafwid.environment/2`). The runtime validates every package before use:

- seat groups (`desk`, `table`, `bar`, `bench`, `standing` or `lounge`),
  each holding seats with a position, a facing and a pose; at least 12
  seats, all on walkable cells and mutually reachable;
- entrances, where agents walk in and out;
- review and lounge zones, a walk grid, camera bounds and ambience.

The café has 51 seats and three entrances; the placeholder has 12 seats.
Headless Blender scripts build the packages through two pipelines, a
real-time-lit kit and a baked scene;
[ADR-0006](../05-decisions/0006-scripted-blender-environment-packages.md)
and [ADR-0007](../05-decisions/0007-ship-baked-scenes-keep-the-kit.md)
explain both.

### Live data path

The bridge is a Vite plugin (`server/bridge.ts`), active in `npm run dev`
and `npm run preview` on `127.0.0.1`. It is read-only:

- It resolves the state home like Tafwid (`TAFWID_HOME`, else
  `~/.tafwid`) and reads `state/world/`. It reads only new bytes of
  today's and yesterday's event files from saved offsets, and starts over
  when a file shrinks or the folder disappears.
- Once a second it also projects Tafwid run records from `state/workers/`
  into delegated-run events. Owners are hashed with the log's salt, so a
  delegated run joins its coordinator's team. Run records are read only
  from the host-neutral home; an installation still on a legacy state home
  must run `settings.py migrate` first.
- `src/live/fold.ts`, a pure reducer, folds the events into teams and
  agents. The bridge serves `GET /api/world/snapshot` and the server-sent
  event stream `GET /api/world/stream` (at most 4 updates a second, with
  a heartbeat comment every 15 s). There are no write endpoints.

In the browser, `src/live/live-source.ts` turns the folded state into the
app's snapshot. If the stream drops, it reconnects with a backoff from 1 s
doubling to 30 s. Meanwhile the HUD says "Reconnecting to live activity…"
and every agent reads "No recent activity", because the browser cannot
age agents itself.

### Teams, roles and actions

A session appears with its first event; its main agent is the coordinator.
A sub-agent appears on its start event and takes its label from the
oldest matching spawn in the same session that is under 60 s old (exact
agent type first, then a spawn with no type, as Codex sends). Without one,
the label is the agent type. Delegated runs are implementers unless their
title carries a role tag.

The role is the `[role: …]` tag if there is one, otherwise the first
match in `src/live/roles.ts` over the agent type and label. Keywords
match at the start of a word and may be a prefix of it, checked in this
order:

| Role | Keywords | Look and idle habit |
| --- | --- | --- |
| Coordinator | the session's main agent; `orchestrat`, `coordinat`, `plan` | Waistcoat and clipboard; looks around |
| Reviewer | `review`, `audit`, `critique`, `verify` | Glasses and cardigan; crossed arms, slow nods |
| Documenter | `doc`, `docs`, `document…`, `readme`, `write-up`, `changelog`, `spec`, `specs`, `specification…` | Beret and notebook; taps a pen |
| Tester | `test`, `qa`, `e2e` | Cap and terminal tablet; taps a foot |
| Researcher | `explore`, `research`, `investigate`, `search`, `explorer` | Scarf and book; flips pages |
| Implementer (shown as Builder) | `implement`, `build`, `fix`, `worker`, `general-purpose`, and anything unmatched | Hoodie and laptop; stretches |

`doc` and `spec` match only those word forms, so "docker" and "specific"
do not count. Each agent also gets a name from its pseudonym, and its
team's accent colour on its ring.

The current action is the latest tool event's action from the
[activity log](activity-log.md); after 10 s without one it is `thinking`.
Working agents act it out with a procedural prop: typing on a laptop
(`edit-code`), writing with pen and paper (`edit-docs`), holding a page
(`read`), leafing through pages (`search`), watching a screen
(`run-tests`, `run-command`), a laptop with head tilts (`web`), a gesture
towards the door (`spawn`) or a hand on the chin (`thinking`).

### Status and lifecycle

| Signal | Status shown | What the character does |
| --- | --- | --- |
| Tool or prompt activity | Working | Sits at its seat and acts out its action |
| Permission request or permission notification | Needs attention (waiting for your approval) | Red beacon, until the agent acts again |
| Coordinator stops or goes idle | Ready (waiting for your next message) | Stays seated with its role's idle habit |
| Sub-agent finishes | Done | Walks to its coordinator, then out of the nearest entrance; gone from the roster after 20 s |
| Sub-agent stops with an error or is interrupted | Needs attention | Stays for 2 min, then leaves; the coordinator's next event does not clear it |
| Delegated run active and reported within 15 s | Working | As above |
| Delegated run completed | Done | Leaves after 20 s |
| Delegated run quiet for over 15 s, blocked, needing review, failed, interrupted or timed out | Needs attention | Leaves after 2 min, unless the run reports working again |
| Working with no events for 5 min | No recent activity | Stays seated, dimmed |
| Session ends, or 30 min with no events | Removed | The whole team walks out |

Finished run records are read for up to 2 minutes after they end. Agents
already done when first seen are never drawn. Hooks run asynchronously and
can deliver events after a session's end event, so an ended session is
remembered for 30 minutes and its trailing events are ignored; only a new
session-start event (a resume) brings it back.

### Seating

`src/live/seating.ts` allocates seats deterministically and keeps every
agent in its seat until it leaves:

- A coordinator takes the free seat group with the most free seats and
  holds it for its team. Its sub-agents fill that group first.
- Outside the home group, role preferences rank above walking distance:
  implementers and testers prefer desks and tables, documenters tables,
  researchers benches, lounges and bars, and reviewers standing spots by
  the review board.
- When seats run out, agents stand on rings around the lounge, then
  around the entrances, at least 0.85 m apart so characters never overlap.

### HUD and cap

The HUD shows team chips per project with counts and a project filter,
the roster grouped by team (name, role, label, action and host), stats
(working now, ready, needs attention, completed this session) and a follow card with
role, label, action, host, status and elapsed time. The filter narrows the
roster and selection only; the 3D world keeps every team, and clicking an
agent outside the filter clears it.

In live mode at most 32 characters are drawn: needs attention first, then
working, then newest. The rest appear in the roster as "+N more in
<project>". The cap applies to live data only; the generated sample crowd
may draw more to test standing overflow.

### Sources

The page always opens on sample data. It switches to live once the bridge
reports that the log is on, unless you chose a source yourself or the URL
says `source=sample`. When the log is off, the HUD says so and shows the
command that turns it on; when the bridge is unreachable (for example in
a static build), it says that instead. The sample source has two teams
like two live sessions, a quiet scenario, and a generated crowd of four
teams.

### Evidence

The [review record](../../prototypes/agent-world/REVIEW.md) owns the
critique rounds, scores, frame-time measurements and live acceptance
results. The first prototype, `prototypes/agent-office/`, remains as the
TAF-2 reference; its [review record](../../prototypes/agent-office/REVIEW.md)
holds that evidence.

## Code location

| Repo / package | Paths |
| --- | --- |
| Tafwid | `prototypes/agent-world/src/` (runtime; `src/live/` holds the fold, roles, seating and live source), `prototypes/agent-world/server/` (bridge and log tailer), `prototypes/agent-world/scripts/` (package validation, evidence capture, event replay), `prototypes/agent-world/tests/` (unit and browser tests), `prototypes/agent-world/art/` (Blender build scripts), `prototypes/agent-world/public/environments/` (packages), `prototypes/agent-office/` (first prototype); all outside the distributable plugin |

## Decisions

- [ADR-0002 — Office prototype boundary](../05-decisions/0002-office-prototype-boundary.md) (superseded)
- [ADR-0003 — Local procedural office](../05-decisions/0003-local-procedural-office.md) (superseded)
- [ADR-0005 — Open agent world](../05-decisions/0005-open-agent-world.md)
- [ADR-0006 — Scripted Blender environment packages](../05-decisions/0006-scripted-blender-environment-packages.md)
- [ADR-0007 — Ship baked scenes, keep the kit](../05-decisions/0007-ship-baked-scenes-keep-the-kit.md)
- [ADR-0008 — Opt-in local activity log](../05-decisions/0008-opt-in-activity-log.md)

## Tracker

[TAF-2](../01-project/backlog.md), [TAF-7](../01-project/backlog.md),
[TAF-3](../01-project/backlog.md); next steps are sequenced in the
[roadmap](../01-project/roadmap.md).

## Ownership

See [ownership](../06-admin/ownership.md).

## Planned & open questions

- The baked office floor and street: planned in
  [TAF-8](../01-project/backlog.md).
- A kit-based scene builder for users: planned in
  [TAF-9](../01-project/backlog.md).
- Persistent agent identity across sessions and per-agent desks
  ([TAF-4](../01-project/backlog.md)).
- Shared presence ([TAF-5](../01-project/backlog.md)).
- Open: "Done" means a sub-agent or run stopped, not that its coordinator
  accepted the result; showing acceptance is an
  [unscheduled idea](../01-project/ideas.md).
- Open: Codex's app-server event stream is richer than hooks but only
  exists when Codex runs as a daemon; it is not used.

Each needs its own model before integration.
