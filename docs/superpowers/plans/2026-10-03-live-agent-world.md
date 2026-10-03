# Live Agent World Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show every real Claude Code and Codex agent (sessions, native sub-agents and Tafwid-delegated workers) as a character in the agent world, with a role, a live action and a status, at no token cost.

**Architecture:** Async, opt-in plugin hooks write sanitised one-line events to a local log in the neutral state home. A Vite plugin in the prototype tails that log and Tafwid run records, folds them into live state, and streams snapshots to the browser. There, a `LiveSource` feeds the existing store, world and HUD. Environments move to schema v2 with seating groups.

**Tech Stack:** Python 3.10+ stdlib (hooks, CLI, `unittest`), TypeScript, Vite 8 plugin API, three 0.186.1, Vitest 5, Playwright 1.63, Blender 5.1 (package rebuild).

**Spec:** [2026-10-03-live-agent-world-design.md](../specs/2026-10-03-live-agent-world-design.md)

## Global Constraints

- **Off by default.** Hook entries run `[ -f "${TAFWID_HOME:-$HOME/.tafwid}/state/world/enabled" ] || exit 0` in bash before Python starts.
- **Neutral home only.** The activity log always lives in `${TAFWID_HOME:-~/.tafwid}/state/world/`, never in a legacy home.
- **Hook output:** every observer hook is `"async": true`, writes nothing to stdout or stderr, and always exits 0.
- **Never logged:** prompts beyond the label, file contents, command text, paths beyond `basename(cwd)`, tool output, transcript paths, raw ids.
- **Labels** are at most 80 characters on one line. **Ids** are the first 16 hex characters of HMAC-SHA256(salt, raw id). The salt is 32 random bytes in `world/salt` (mode `0600`), and the directory is mode `0700`.
- **Log files:** `world/events-YYYY-MM-DD.jsonl` (mode `0600`), deleted after 7 days. `world/hook-errors.log` is capped at 100 lines.
- **Roles:** `coordinator`, `implementer`, `reviewer`, `documenter`, `researcher`, `tester`.
- **Actions:** `edit-code`, `edit-docs`, `read`, `search`, `run-tests`, `run-command`, `web`, `spawn`, `thinking`, `other`.
- **Live statuses:** `working`, `attention`, `ready`, `done`, `uncertain`.
- **Timings:** action window 10 s; done agents leave after 20 s; error and interrupted agents stay at most 2 min; uncertain after 5 min with no events; teams removed after 30 min silent or on session end.
- **Limits:** render cap 32 characters (attention, then working, then newest); at least 12 seats per environment; the café has about 40 seats.
- **Manifest schema** is `tafwid.environment/2`, and the plugin version is `0.5.0` in `VERSION` and both manifests.
- **Tests stay offline:** temporary `TAFWID_HOME`, no real `~/.tafwid`, no model requests. `make test` and `python3 scripts/check_package.py` must pass.
- **Plugin boundary:** nothing in the plugin refers to the prototype, and docs never imply that the dashboard ships.

## Review Focus

1. **Concurrent hooks writing the same log.** Up to 8 async hooks run at once, and Claude and Codex can write simultaneously. Each line must arrive whole, with no interleaving (append with a single `os.write` of a line under 4 KB, opened `O_APPEND`). Test with parallel writers, Task 2.
2. **Malformed or unknown payloads.** Fields may be missing, an event may be new, `tool_input` may be huge, or stdin may not be JSON. The hook still exits 0 silently and logs one error line. Tests in Task 2.
3. **A log rotating mid-read, or a truncated last line.** The bridge never emits half a line and resumes at the right offset across the date boundary (Task 7).
4. **SubagentStop without SubagentStart, or a spawn with no SubagentStart.** No ghost characters: an orphan stop is ignored, and an unmatched spawn expires after 60 s (Task 5).
5. **More agents than seats or the cap.** No overlap and no crash: agents beyond the seats stand at lounge positions, and agents beyond the cap appear in the HUD's "+N more" (Tasks 6 and 9).

---

### Task 1: Activity log core and switch (`world.py`)

**Files:**
- Create: `plugins/tafwid/skills/delegate/scripts/world.py`
- Test: `plugins/tafwid/skills/delegate/tests/test_world.py`

**Interfaces:**
- Produces (Python):
  - `world_dir() -> Path` (neutral home; does not create it)
  - `enabled() -> bool`
  - `enable() -> dict`
  - `disable() -> dict`
  - `status() -> dict` with keys `enabled`, `dir`, `today_events`
  - `hash_id(raw: str) -> str` (16 hex characters; creates the salt on first use)
  - `append_event(event: dict) -> None` (adds `v` and `t`; one `os.write`)
  - `prune(now: float) -> None`
  - `log_error(msg: str) -> None`
- CLI: `python3 world.py {on,off,status}` prints JSON and exits 0; argument errors exit 2.

- [ ] **Step 1: Write the failing tests** (`unittest`, temporary `TAFWID_HOME` and `CODEX_HOME` like `test_paths.py`):
  - `test_disabled_by_default`
  - `test_on_creates_marker_with_private_dir` (dir mode `0700`)
  - `test_off_removes_marker`
  - `test_uses_neutral_home_even_with_legacy_state` (a legacy dir exists, but `world_dir()` is still under `TAFWID_HOME/state/world`)
  - `test_hash_is_stable_and_salt_private` (same input gives the same 16 hex characters; salt mode `0600`; different salt gives a different hash)
  - `test_append_writes_one_json_line_with_version_and_time`
  - `test_prune_deletes_files_older_than_7_days`
  - `test_error_log_capped_at_100_lines`
  - `test_cli_status_json`
- [ ] **Step 2:** `python3 -m unittest plugins/tafwid/skills/delegate/tests/test_world.py`. Expected: fails (module missing).
- [ ] **Step 3:** Implement `world.py`. Paths come from `os.environ.get("TAFWID_HOME") or ~/.tafwid`, never `paths.state_root()`. `append_event` uses `os.open(path, O_WRONLY|O_APPEND|O_CREAT, 0o600)` and a single `os.write`.
- [ ] **Step 4:** Tests pass. **Step 5:** Commit `feat: add an opt-in local activity log (TAF-3)`.

### Task 2: Observer hook (`world_hook.py`)

**Files:**
- Create: `plugins/tafwid/skills/delegate/scripts/world_hook.py`, and fixtures under `plugins/tafwid/skills/delegate/tests/fixtures/world/` (Claude and Codex payloads for each event)
- Test: `plugins/tafwid/skills/delegate/tests/test_world_hook.py`

**Interfaces:**
- Consumes: Task 1 (`append_event`, `hash_id`, `log_error`, `prune`).
- Produces:
  - `classify_action(tool_name: str, tool_input: dict) -> str`
  - `extract_role(text: str) -> tuple[str | None, str]` (role and the cleaned text)
  - `to_event(payload: dict, host: str) -> dict | None`
  - `main(stdin) -> int` (always 0)
- Host detection: Codex payloads carry `turn_id` on tool events; `CLAUDE_PLUGIN_ROOT` is set under Claude. Use `host.detect()` when it is available, and these fields as the fallback.

- [ ] **Step 1: Write the failing tests:**
  - `test_tool_pre_from_main_session_has_null_agent`
  - `test_tool_inside_subagent_hashes_agent_id`
  - `test_actions` (a table over every row of the spec's action table, including `npm test` giving `run-tests` and `README.md` giving `edit-docs`)
  - `test_spawn_label_claude_description_and_codex_first_prompt_line_truncated_to_80`
  - `test_role_tag_extracted_and_removed`
  - `test_status_hints` (PermissionRequest gives waiting; Notification `permission_prompt` gives waiting; `idle_prompt` and Stop give idle; SubagentStop `stop_reason` completed, error and interrupted give done, error and interrupted)
  - `test_forbidden_fields_never_written` (a payload with a command, a file path, a prompt and transcript paths; scan the written line for each raw value)
  - `test_project_is_cwd_basename_only`
  - `test_malformed_stdin_exits_zero_and_logs_once`
  - `test_unknown_event_ignored_silently`
  - `test_huge_tool_input_still_one_short_line`
  - `test_parallel_appends_never_interleave` (8 processes × 200 events; every line parses)
  - `test_session_start_prunes`
- [ ] **Step 2:** Run the tests. Expected: fail.
- [ ] **Step 3:** Implement. `main` wraps everything in `try`/`except`, then `log_error`, and returns 0. Nothing is printed.
- [ ] **Step 4:** Pass. **Step 5:** Commit `feat: record agent activity from Claude Code and Codex hooks (TAF-3)`.

### Task 3: Register hooks and release 0.5.0

**Files:**
- Modify: `plugins/tafwid/hooks/hooks.json`, `VERSION`, `plugins/tafwid/.claude-plugin/plugin.json`, `plugins/tafwid/.codex-plugin/plugin.json`, `CHANGELOG.md`
- Test: `plugins/tafwid/skills/delegate/tests/test_world_hook.py` (`test_hooks_json_registers_async_guarded_observers`)

- [ ] **Step 1: Failing test.** Every observer event (`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PermissionRequest`, `SubagentStart`, `SubagentStop`, `Stop`, `SessionEnd`, `Notification`) has an entry with:
  - `async: true`;
  - a command containing the exact guard and `world_hook.py`;
  - the same host-neutral prefix `check_package.py` asserts.

  The existing Stop, Interrupt and UserPromptSubmit completion entries are unchanged.
- [ ] **Step 2:** Run it and watch it fail. **Step 3:** Edit `hooks.json`. The command is `bash -c '[ -f "${TAFWID_HOME:-$HOME/.tafwid}/state/world/enabled" ] || exit 0; exec python3 "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/delegate/scripts/world_hook.py"'`, with `"timeout": 5` and `"async": true`. Bump the version to 0.5.0 everywhere. Add a CHANGELOG entry that notes the one-time Codex re-trust.
- [ ] **Step 4:** `make test`. Expected: all pass, including `check_package`.
- [ ] **Step 5:** Measure the hook command from `hooks.json` with a representative PreToolUse payload, 50 runs each, switch off and on. Expected: off median ≤ 5 ms and on median ≤ 30 ms on the M5 Max. Record both in the CHANGELOG entry.
- [ ] **Step 6:** Commit `feat: register opt-in activity hooks; release 0.5.0 (TAF-3)`.

### Task 4: Seating contract v2 and café regeneration

**Files:**
- Modify:
  - `prototypes/agent-world/src/contract/manifest.ts`, `src/contract/validate.ts`, `tests/unit/fixtures/manifest.valid.json`, `tests/unit/validate.test.ts`;
  - `art/cafe/layout.py`, `art/placeholder/build.py`, `art/kit/pieces.py` (benches and bar seats if missing);
  - `src/app/behaviour.ts` (sample mode uses seats).
- Rebuild: `public/environments/{placeholder,cafe}/*`

**Interfaces:**
- Produces:
  - `interface Seat { id: string; position: Vec3; facing: number; pose: 'seated' | 'standing' }`
  - `interface SeatGroup { id: string; kind: 'desk' | 'table' | 'bar' | 'bench' | 'standing' | 'lounge'; seats: Seat[] }`
  - `EnvironmentManifest.seating: SeatGroup[]` (replaces `zones.workstation`)
  - `EnvironmentManifest.entrances: Vec2[]` (at least 1)
  - `MANIFEST_SCHEMA = 'tafwid.environment/2'`

- [ ] **Step 1: Failing tests:**
  - `requires twelve seats`
  - `rejects a seat on a blocked cell` (named `seating[1].seats[0] (bar-1) is on a blocked cell`)
  - `requires an entrance`
  - `rejects schema 1 with a named error`

  Update the valid fixture to v2.
- [ ] **Step 2:** FAIL. **Step 3:** Implement the validator, then the layouts:
  - The café emits groups: two-seat laptop tables, four-seat parasol tables, six bar stools, benches, standing spots by the review board, and three entrances (street, alley, side street). The total is about 40.
  - The placeholder gets 12 seats.
- [ ] **Step 4:** `art/build.sh placeholder && art/build.sh cafe-kit && art/build.sh cafe-baked --samples 768 --texels 20 && npm run validate && npm test`. Expected: all `OK`; the unit tests pass.
- [ ] **Step 5:** Commit `feat(agent-world): seating groups and entrances in environment schema v2 (TAF-3)`. Packages are included because the contract changed.

### Task 5: Live fold and role classifier

**Files:**
- Create: `prototypes/agent-world/src/live/types.ts`, `src/live/roles.ts`, `src/live/fold.ts`
- Test: `tests/unit/roles.test.ts`, `tests/unit/fold.test.ts`

**Interfaces:**
- Produces:
  - `WorldEvent` (the log line type)
  - `type Role`, `type Action`, `type LiveStatus`
  - `interface LiveAgent { id: string; teamId: string; kind: 'coordinator' | 'subagent' | 'delegated'; role: Role; name: string; label: string; action: Action; status: LiveStatus; host: 'claude' | 'codex'; project: string; startedAt: number; lastEventAt: number; statusSince: number }`
  - `interface LiveTeam { id: string; project: string; host: string; accent: string; lastEventAt: number }`
  - `interface LiveState { teams: Record<string, LiveTeam>; agents: Record<string, LiveAgent>; pendingSpawns: PendingSpawn[] }`
  - `emptyLiveState()`, `fold(state, event: WorldEvent): LiveState`, `tick(state, now: number): LiveState`
  - `classifyRole(agentType: string | null, label: string | null, override: Role | null): Role`
  - `nameFor(id: string): string`
  - `accentFor(teamId: string): string`

- [ ] **Step 1: Failing tests:**
  - **roles:**
    - a table test for every row of the spec's role table;
    - the override wins;
    - unmatched agents are `implementer`.
  - **fold:**
    - the first event creates a team and coordinator;
    - spawn then SubagentStart creates a sub-agent with the spawn label;
    - two spawns of the same type match in order;
    - an orphan SubagentStop is ignored;
    - an unmatched spawn expires after 60 s;
    - a tool event sets the action, which falls back to `thinking` after 10 s;
    - waiting gives `attention`;
    - a coordinator `idle` gives `ready`;
    - a sub-agent `done` is removed 20 s later;
    - `error` stays for at most 2 min;
    - 5 min with no events gives `uncertain`;
    - session end, or 30 min silent, removes the team;
    - a run record joins its owning team as `delegated`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement as pure functions. `fold` handles run records through `{event: 'run', ...}` events produced by the bridge. **Step 4:** PASS. **Step 5:** Commit `feat(agent-world): fold agent activity into live state (TAF-3)`.

### Task 6: Seating allocator

**Files:**
- Create: `prototypes/agent-world/src/live/seating.ts` · Test: `tests/unit/seating.test.ts`

**Interfaces:**
- Produces:
  - `type SeatAssignment = { seat: Seat; group: SeatGroup } | { standAt: Vec2 }`
  - `allocate(previous: Map<string, SeatAssignment>, agents: LiveAgent[], manifest: EnvironmentManifest, walk: WalkGrid): Map<string, SeatAssignment>`

- [ ] **Step 1: Failing tests:**
  - a coordinator takes the emptiest group;
  - team members fill their team's group first;
  - overflow goes to the nearest group by path length;
  - kind preferences per the spec;
  - assignments are sticky across calls;
  - a freed seat is reused;
  - when every seat is taken, agents get `standAt` lounge positions with no duplicates;
  - output is deterministic for the same input.
- [ ] **Step 2–4:** FAIL, implement, PASS. **Step 5:** Commit `feat(agent-world): seat agents by team and role (TAF-3)`.

### Task 7: Bridge (Vite plugin)

**Files:**
- Create: `prototypes/agent-world/server/bridge.ts`, `server/tail.ts`
- Modify: `vite.config.ts`
- Test: `tests/unit/bridge.test.ts` (Node, temporary dir)

**Interfaces:**
- Produces:
  - `createTailer(dir: string): { poll(): WorldEvent[] }` (incremental, rotation-aware, never returns a partial line)
  - `readRuns(stateDir: string, salt: Buffer): WorldEvent[]`
  - `worldBridge(options?: { home?: string }): Plugin`, serving:
    - `GET /api/world/snapshot` returns `{ enabled: boolean; state: LiveState }`;
    - `GET /api/world/stream` sends SSE `data: <snapshot>` at most every 250 ms, plus a heartbeat comment every 15 s.
- Home: `options.home ?? process.env.TAFWID_HOME ?? ~/.tafwid`.

- [ ] **Step 1: Failing tests:**
  - the tailer returns only complete lines and resumes at its offset;
  - a partial last line is held back until its newline;
  - after a date rollover, it continues in the new file;
  - a malformed line is skipped and counted;
  - run records are projected with hashed owner ids matching `hash_id` from Python (shared vector: salt `00…` and raw id `abc` give a fixed hex, asserted in both test suites);
  - the snapshot endpoint reports `enabled: false` when the marker is missing.
- [ ] **Step 2–4:** FAIL, implement (node `fs` and `crypto`, no new dependencies), PASS. Add the Python twin assertion of the shared hash vector to `test_world.py`. **Step 5:** Commit `feat(agent-world): stream live agent state from the activity log (TAF-3)`.

### Task 8: Live source, app model and HUD

**Files:**
- Create: `prototypes/agent-world/src/live/live-source.ts`
- Modify:
  - `src/app/types.ts` (`Agent` gains `teamId`, `project`, `role`, `action`, `host`, `kind`; `AgentStatus` gains `done` and `uncertain`; `AppState` gains `source: 'live' | 'sample'`, `liveEnabled`, `projectFilter`);
  - `src/app/store.ts`, `src/app/fixtures.ts` (two sample teams with sub-agents);
  - `src/ui/shell.ts`, `src/ui/roster.ts`, `src/ui/details.ts`, `src/styles.css`, `src/main.ts`.
- Test: `tests/unit/store.test.ts`, `tests/unit/live-source.test.ts`

**Interfaces:**
- Produces:
  - `createLiveSource(url = '/api/world/stream'): SnapshotSource & { enabled(): boolean }`, which maps `LiveState` to `Snapshot`;
  - `toSnapshot(state: LiveState, now: number, cap = 32): Snapshot & { overflow: Record<string, number> }`.

- [ ] **Step 1: Failing tests:**
  - `toSnapshot` maps statuses and roles;
  - it applies the cap with priority (attention, then working, then newest) and counts overflow per project;
  - the project filter keeps the selection when its agent is visible and clears it when filtered out;
  - the store switches source;
  - the sample fixtures produce two teams.
- [ ] **Step 2:** FAIL. **Step 3:** Implement the HUD:
  - Live/Sample switch, team chips with counts, and a project filter;
  - roster grouped by team;
  - the details card shows role, label, action, host, status and elapsed time;
  - the "Live activity is off. Run `python3 …/world.py on`" notice;
  - "+N more in <project>".
- [ ] **Step 4:** PASS, plus `npx tsc --noEmit`. **Step 5:** Commit `feat(agent-world): live and sample sources with teams in the HUD (TAF-3)`.

### Task 9: World behaviour (roles, props, actions, lifecycle)

**Files:**
- Modify: `prototypes/agent-world/src/world/characters.ts` (role outfits, props: laptop, pen and paper, book, clipboard, tablet; action poses; idle personalities), `src/world/agents.ts` (use `allocate`; enter from entrances; done leaves via the coordinator then an entrance; team walks out; uncertain dimming), `src/world/overlay.ts` (badge shows name and role icon; ring uses the team accent)

- [ ] **Step 1:** Implement against the spec's role and action tables.
- [ ] **Step 2:** Verify in the browser pane on the café (sample source with teams):
  - roles look distinct;
  - each action animation plays;
  - a done sub-agent walks to its coordinator and out;
  - with 40+ sample agents, overflow agents stand and nothing overlaps.
- [ ] **Step 3:** Measure with `__tafwidPerf` at 32 characters, High tier, in headless Chromium on the M5 Max. Expected: p95 at most 18 ms. Record the figure in `REVIEW.md`.
- [ ] **Step 4:** Commit `feat(agent-world): role looks, live actions and agent lifecycles (TAF-3)`.

### Task 10: End-to-end replay test

**Files:**
- Create: `prototypes/agent-world/tests/e2e/live.spec.ts`, `tests/e2e/fixtures/events-sample.jsonl`, `scripts/replay-events.ts`
- Modify: `playwright.config.ts` (the web server gets `TAFWID_HOME` set to a temporary fixture home)

- [ ] **Step 1: Write the tests:**
  - with the switch on and a replayed log of 3 sessions, the right number of characters appear and team chips are shown;
  - a permission event raises an attention beacon;
  - a completed sub-agent leaves within 30 s;
  - the project filter hides the other teams;
  - 40 agents show "+N more";
  - with the switch off, the notice appears and sample is offered;
  - the Live/Sample switch works.
- [ ] **Step 2:** `npm run e2e`. Expected: the new and existing suites pass. **Step 3:** Commit `test(agent-world): replay live activity end to end (TAF-3)`.

### Task 11: Documentation and live acceptance

**Files:**
- Create: `docs/05-decisions/0008-opt-in-activity-log.md`, `docs/04-modules/activity-log.md`
- Modify:
  - `docs/04-modules/dashboard.md`, `docs/04-modules/README.md`, `docs/06-admin/ownership.md`;
  - `docs/01-project/glossary.md` (coordinator, sub-agent, role, action), `docs/01-project/backlog.md` (TAF-3 done), `docs/01-project/roadmap.md`;
  - `docs/03-architecture/system.md` (activity log boundary), `docs/07-meta/changelog.md`;
  - `README.md` (toggle and Codex re-trust), `plugins/tafwid/skills/delegate/SKILL.md` (scripts table: `world.py`);
  - `prototypes/agent-world/README.md`.

- [ ] **Step 1:** Write the docs under the Archivist rules, then run an audit pass with no findings left open.
- [ ] **Step 2:** Live acceptance, **only with the user's consent** because it changes their installed plugin:
  - install the 0.5.0 plugin locally;
  - run `world.py on`;
  - run a Claude Code session that spawns sub-agents, and a Codex session;
  - confirm the characters appear and leave.

  Record the results in the plan and `REVIEW.md`.
- [ ] **Step 3:** `make test`, `npm test`, `npm run e2e`, `npm run build`, `npm run validate`. Expected: all pass. Commit `docs: record the live agent world and activity log (TAF-3)`.
