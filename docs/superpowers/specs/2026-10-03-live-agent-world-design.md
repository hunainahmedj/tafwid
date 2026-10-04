# Live agent world — real agents, roles and activity

Date: 2026-10-03 · Tracker: [TAF-3](../../01-project/backlog.md)

Sections 1 and 2 (the observer hook and the bridge) were approved in
conversation on 2026-10-03. The user asked Claude to decide sections 3 and 4
(world behaviour; privacy, testing and docs) and review them itself. This
document needs the user's review before planning. The agent world remains a
local prototype; this spec does not make the dashboard part of the released
plugin.

## Intent

Replace sample data with what the user's agents are really doing. Every
agent gets a character: the main session (the coordinator) and each
sub-agent it spawns, native or Tafwid-delegated. Seven sub-agents mean
seven characters. A role decides an agent's look and personality, its live
action decides its animation, and its state decides its status. Sequential
work with no sub-agents shows only the coordinator.

It must:

- work with Tafwid delegation switched off, because Claude Code and Codex
  both have native sub-agents;
- add no tokens or context: the model never sees the observer;
- show every active session on the Mac. Five sessions with two sub-agents
  each are 15 characters: 5 coordinators and 10 sub-agents.

`feature/provider-dashboard` is superseded and not used.

### Decisions so far

| Topic | Decision |
| --- | --- |
| Identity | One character per agent (session main + every sub-agent) |
| Roles | Keyword classifier over agent type and spawn description (B), with an optional explicit tag as override (C) |
| Scope | Every active session on this Mac, grouped into teams by session, with a project filter |
| Capacity | Seats grouped into furniture (shared desks, café tables, bar stools, benches, standing desks); a soft cap for readability |
| Data path | Async hooks write a sanitised local event log; a small bridge in the dashboard folds it and streams it to the browser (A) |

## What the hosts provide

Both hosts expose nearly the same hooks (researched 2026-10-03 from official
docs and, for Codex, the 0.155.1 source and schemas):

| Need | Claude Code | Codex |
| --- | --- | --- |
| Sub-agent appears and leaves | `SubagentStart` / `SubagentStop` with `agent_id`, `agent_type`; stop has `stop_reason` | Same names and fields; `agent_type` is the role (`default`, `explorer`, `worker`, custom) |
| Per-agent activity | `PreToolUse` / `PostToolUse` inside sub-agents carry `agent_id` | Same; shell is `Bash`, `apply_patch` matches `Edit`/`Write` |
| Spawn details | `Agent` tool input: `subagent_type`, `description` | `spawn_agent` (alias `Agent`) input: the prompt |
| Waiting for the user | `Notification` (`permission_prompt`, `idle_prompt`), `PermissionRequest` | `PermissionRequest` |
| Main versus sub-agent | `agent_id` absent on the main session | Same |
| Overhead | `async: true`: no blocking; silent hooks add no context | Same; at most 8 async hooks run at once |

Codex asks the user to re-trust hooks whenever `hooks.json` changes. Live
acceptance on 2026-10-04 showed that Codex trusts each handler separately
(a `trusted_hash` per `<event>:<group>:<handler>` in `config.toml`), that
non-interactive `codex exec` silently skips untrusted handlers, and that
Codex runs the async `SessionEnd` hook synchronously with a 3 s timeout.
Codex's
app-server event stream is richer but only reachable when Codex runs as a
daemon; it is a possible later upgrade, not part of this work.

## Section 1 — Observer hook (plugin)

- **Script:** `plugins/tafwid/skills/delegate/scripts/world_hook.py`, one
  script for both hosts.
- **Events:** `SessionStart`, `UserPromptSubmit`, `PreToolUse`,
  `PostToolUse`, `PermissionRequest`, `SubagentStart`, `SubagentStop`,
  `Stop`, `SessionEnd`, and Claude's `Notification`.
- **Registration:** every event is registered in `plugins/tafwid/hooks/hooks.json`
  as `async: true`, with no stdout.
- **Off by default.** Each entry starts with a bash test for
  `${TAFWID_HOME:-$HOME/.tafwid}/state/world/enabled` and exits in about
  2 ms when it is missing. The activity log always uses this neutral home,
  even on an installation still using a legacy state home, so the bash test
  and the Python code can never disagree. In the rest of this spec, `<state>`
  means that neutral home.
  `python3 plugins/tafwid/skills/delegate/scripts/world.py on|off|status`
  (listed in the delegate skill's scripts table) creates or removes the
  marker. There is no separate `tafwid` command.
- **Event line,** appended to `<state>/world/events-YYYY-MM-DD.jsonl` (file
  mode `0600`, directory `0700`):

  ```json
  {"v":1,"t":1791060000.123,"host":"claude","session":"<hash>","project":"tafwid",
   "agent":"<hash or null>","event":"tool","phase":"pre","agentType":"general-purpose",
   "label":"Implement Task 3: manifest validator","action":"edit-code","role":null,
   "status":null}
  ```

- **Identity hashing.** `session` and `agent` are the first 16 hex characters
  of an HMAC-SHA256 over the host id, keyed by `<state>/world/salt`. The salt
  is 32 random bytes, created with mode `0600` on first use.
- **Project** is the base name of `cwd`, and nothing else from the path.
- **Label** is the spawn description, collapsed to one line and cut to 80
  characters. For Claude it is `description`; for Codex, the first line of the
  spawn prompt. It is written only on spawn events.
- **Action** is derived in the hook from the tool name and target extension:

  | Action | Tools |
  | --- | --- |
  | `edit-code` | `Edit`, `Write`, `apply_patch` on code |
  | `edit-docs` | The same tools on `.md`, `.mdx`, `.rst` or `.txt` |
  | `read` | `Read`, `NotebookRead` |
  | `search` | `Grep`, `Glob`, `LS` |
  | `run-tests` | `Bash` whose command matches a test runner (`pytest`, `npm test`, `vitest`, `playwright`, `make test`, `cargo test`, `go test`) |
  | `run-command` | Other `Bash` |
  | `web` | `WebFetch`, `WebSearch` |
  | `spawn` | `Agent`, `Task`, `spawn_agent` |
  | `other` | Anything else |

- **Role override.** A `[role: <name>]` tag in the description sets `role`
  and is removed from the label.
- **Status hints.** These events set `status`:
  - `PermissionRequest` and the permission notification → `waiting`;
  - the idle notification and `Stop` → `idle`;
  - `SubagentStop` → `done`, `error` or `interrupted`.
- **Never written:** prompts beyond the label, file contents, command text,
  paths beyond the project name, tool output, transcript paths, and raw ids.
- **Housekeeping and failure.** Files older than 7 days are deleted on
  `SessionStart`. Any exception is swallowed after one line in
  `<state>/world/hook-errors.log` (trimmed to 100 lines). The hook always
  exits 0.
- **Delegated workers.** Tafwid's delegated workers come from existing run
  records (Section 2); they are not hooked separately.

## Section 2 — Bridge (dashboard)

- **Location:** a Vite plugin in `prototypes/agent-world/server/bridge.ts`,
  active in `dev` and `preview`. The server listens on 127.0.0.1.
- **Endpoints:** `GET /api/world/snapshot`, and `GET /api/world/stream`
  (server-sent events, at most 4 updates per second). There are no write
  endpoints.
- **Sources:**
  - the event logs for today and yesterday, read incrementally from saved
    offsets;
  - Tafwid run records in `<state>/workers/`, projected as sub-agents of the
    owning session;
  - the state root, resolved like Tafwid (`TAFWID_HOME`, then the neutral
    home).

  Run-record owner ids are hashed with the same salt, so delegated runs join
  their session's team. Delegated runs get role `implementer` unless their
  title carries a role tag.
- **Folding.** `src/live/fold.ts` is a pure, unit-tested reducer from events
  to a `LiveState`:
  - **Teams:** a session appears on its first event. Its main agent is the
    `coordinator`.
  - **Sub-agents:** a sub-agent is created on `SubagentStart`. Its label comes
    from the oldest unmatched spawn of the same `agentType` in the same
    session; without one, the label is the agent type.
  - **Role:** override first, then the classifier, then the type mapping.
  - **Action:** the latest tool event within 10 s, otherwise `thinking`.
  - **Status:**

    | Signal | Status | Behaviour |
    | --- | --- | --- |
    | Tool or turn activity | `working` | At a seat, animated by action |
    | `waiting` hint | `attention` ("needs your approval") | Red beacon, stays |
    | Coordinator `idle` | `ready` ("waiting for your next message") | Stays at its seat with its role's idle habit |
    | Sub-agent `done` | `done` | Walks to its coordinator, leaves after 20 s |
    | Sub-agent `error` / `interrupted` | `attention` | Stays for 2 min, then leaves (the parent's next event follows immediately, so it does not clear the warning) |
    | `working` with no events for 5 min | `uncertain` | Dimmed, "no recent activity" |
    | `SessionEnd` or 30 min silent | removed | The team walks out |
    | Delegated run active, updated within 15 s | `working` | As above; re-emitted each poll as a heartbeat |
    | Delegated run completed | `done` | Leaves after 20 s |
    | Delegated run stale (over 15 s), blocked, needing review, failed, interrupted or timed out | `attention` | Terminal: removed after 120 s, unless a later `working` event revives it |

    Finished run records are projected for 120 s after they end. Agents
    already `done` when first seen are never rendered.
  - **Ended sessions:** async hooks can append events after `SessionEnd`.
    An ended session is kept as a tombstone for 30 min: later events for it
    are ignored until a new `session` event (a resume or restart) arrives.

- **Live source.** `LiveSource` implements `SnapshotSource` from the
  stream. A **Live / Sample** switch in the HUD (`?source=live|sample`)
  chooses the source; as built, only `?source=sample` is read, and it keeps
  the page on sample. The page opens on sample and switches to live when the
  bridge reports the switch on; otherwise it stays on sample with the notice
  "Live activity is off. Run
  `python3 plugins/tafwid/skills/delegate/scripts/world.py on`."

## Section 3 — World behaviour

- **Seats** replace desk zones. The manifest schema becomes
  `tafwid.environment/2`. `zones.workstation` is replaced by
  `seating[]` groups, each with:
  - `id`;
  - `kind`: `desk`, `table`, `bar`, `bench`, `standing` or `lounge`;
  - `seats[]`, each with `id`, `position`, `facing` and `pose`.

  `review` and `lounge` zones stay. The validator requires at least 12 seats,
  every seat on a walkable cell, and all groups mutually reachable. The café
  is regenerated with:
  - two-seat laptop tables and four-seat parasol tables;
  - a six-stool bar;
  - benches for two or three;
  - standing spots by the review board.

  It totals about 40 seats (51 as built). Both packages are rebuilt.
- **Allocation.** A deterministic, sticky allocator (`src/live/seating.ts`):
  - A coordinator takes the free group with the most free seats and holds it
    for its team.
  - Sub-agents fill their team's group, then the nearest group by path
    length.
  - Kind preferences:
    - implementers and testers: `desk` or `table`;
    - documenters: `table`;
    - researchers: `bench`, `lounge` or `bar`;
    - reviewers: `standing` near the review board.
  - An agent keeps its seat until it leaves.
  - When seats run out, agents stand on rings (1.0 m apart) around the
    lounge, then around the entrances. Standing points keep at least 0.85 m
    from every seat and from each other, because a character's head is
    0.76 m wide.
- **Roles** (classifier in `src/live/roles.ts`, over a lower-cased type plus
  label; a keyword must start at a word boundary and may be a prefix of the
  word, checked in table order, top row first):

  | Role | Matches | Look | Idle personality |
  | --- | --- | --- | --- |
  | coordinator | session main agent; "orchestrat", "coordinat", "plan" | Waistcoat, clipboard | Looks around, points at the board |
  | reviewer | "review", "audit", "critique", "verify" | Glasses, cardigan | Crossed arms, slow nods |
  | documenter | "doc", "docs", "document…", "readme", "write-up", "changelog", "spec", "specs", "specification…" | Beret, notebook | Taps pen |
  | tester | "test", "qa", "e2e" | Cap, terminal tablet | Taps foot |
  | researcher | "explore", "research", "investigate", "search", "explorer" | Scarf, book | Flips pages |
  | implementer | "implement", "build", "fix", "worker", "general-purpose" | Hoodie, laptop | Stretches |

  "doc" and "spec" match only the word forms shown, so "docker" and
  "specific" are not documenters.

  Unmatched agents are `implementer`. Each agent also gets a deterministic
  name from its hash. Its team's accent colour shows on its status ring.
- **Actions:**

  | Action | Animation |
  | --- | --- |
  | `edit-code` | Types on a laptop |
  | `edit-docs` | Writes with a pen on paper |
  | `read` | Holds a page |
  | `search` | Leafs through pages |
  | `run-tests` / `run-command` | Watches a screen, slower typing |
  | `web` | Laptop with head tilts |
  | `spawn` | Gestures towards the door |
  | `thinking` | Hand on chin |

  The pen, paper, book and clipboard are procedural props on the character
  rig.
- **Lifecycle.** New agents enter from the environment's declared `entrance`
  points and walk to their seat by A*. Finished agents walk to their
  coordinator, then to an entrance, and disappear. A whole team walks out
  when its session ends.
- **HUD:**
  - team chips per project with counts, and a project filter;
  - the roster grouped by team, showing name, role, label, action and host
    (Claude Code / Codex);
  - stats: working, needs you, ready, recently done;
  - the follow card shows role, task label, current action, host, status and
    elapsed time.
- **Cap.** At most 32 characters are rendered, preferring `attention`, then
  `working`, then newest. The rest appear in the HUD as "+N more in
  <project>". The cap applies to the live source only; the generated
  `?scenario=crowd` sample may render 40–60 characters to exercise standing
  overflow.
- **Sample mode** gains teams (two sessions with sub-agents) so the demo
  matches live behaviour.

## Section 4 — Privacy, boundary, testing and docs

- **Privacy.** Sanitising happens in the hook. The log holds only hashed
  ids, project names, 80-character labels, action kinds and statuses. The
  bridge serves only the folded projection. The dev server listens on
  localhost; if the user exposes it on their tailnet, labels and project
  names travel to their own devices, as documented.
- **Plugin boundary.** The observer ships in the plugin as an opt-in "local
  activity log", off by default. It is useful to any local dashboard, and
  nothing in it refers to the prototype. A new ADR records this. Docs must
  not imply that the dashboard ships. Changing `hooks.json` triggers a
  one-time Codex re-trust, documented in the README. The version moves to
  0.5.0 in `VERSION` and both manifests.
- **Performance.**
  - **Hook:** when enabled, below 30 ms per event, measured. When disabled,
    only the bash test runs.
  - **Bridge:** reads only new bytes.
  - **World:** 32 characters at 60 fps on the M5 Max at High, measured.
- **Tests:**
  - **Python (offline, temporary homes):**
    - the off switch;
    - forbidden fields never written;
    - each action kind and the role tag;
    - hashing stability and salt mode;
    - rotation, and error swallowing;
    - Claude and Codex payload fixtures for every event.
  - **TypeScript unit:**
    - fold, covering spawn correlation, every status row, stale and removal,
      and the run-record join;
    - the role classifier table;
    - the seating allocator (team affinity, preferences, stickiness,
      overflow);
    - the v2 manifest validator.
  - **Browser:** replay a fixture event log through the bridge (temporary
    `TAFWID_HOME`) and check that:
    - N characters appear;
    - a permission event raises a beacon;
    - a finished sub-agent leaves;
    - the project filter works;
    - the cap shows "+N more";
    - the Live / Sample switch works.
  - **Existing suites:** `make test`, `check_package.py`, and the existing
    browser tests.
- **Docs:**
  - a new ADR;
  - a new module doc, `docs/04-modules/activity-log.md`;
  - dashboard module updates;
  - glossary terms (coordinator, sub-agent, role, action);
  - the README toggle, with the Codex re-trust note;
  - the changelog, the backlog (TAF-3) and an audit-clean tree.

## Out of scope

- controlling agents from the world;
- the Codex app-server listener;
- persistent identity across sessions ([TAF-4](../../01-project/backlog.md));
- multi-user presence ([TAF-5](../../01-project/backlog.md));
- the scene builder ([TAF-9](../../01-project/backlog.md));
- the visual critique fixes for the café ([TAF-8](../../01-project/backlog.md)).
  The seating regeneration here is functional, not an art pass.
