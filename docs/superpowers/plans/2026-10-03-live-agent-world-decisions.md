# Live agent world — decisions and deferred findings

Working record for [the plan](2026-10-03-live-agent-world.md), kept after the
execution workspace was deleted. Each ruling reads: what was decided — why —
what it costs if wrong. Deferred findings were judged Minor by a reviewer and
left for a later change.

## Rulings (55)

1. **Pre-flight:** T3 extends check_package.py to accept exactly two host-neutral hook forms — the existing completion_hook prefix, or the observer form (guard + world_hook.py) which must also be async — spec requires the guarded async observer; the checker predates it — cost if wrong: one checker rule to revise
2. **Pre-flight:** T2 host detection uses host.detect() only, falling back to payload shape (turn_id ⇒ codex) and never reads identity env vars itself — AGENTS.md rule binds — cost if wrong: an unknown host is logged as "unknown"
3. **Pre-flight:** T4 moves sample mode to seats with simple in-order seat assignment; T9 replaces it with allocate() — keeps the sample world working between tasks — cost if wrong: throwaway glue
4. **Task 2:** label/agentType/role written on spawn pre-events; SubagentStart matched by the dashboard — Codex/Claude SubagentStart carries no description — cost if wrong: unlabeled sub-agents fall back to their type
5. **Task 2:** host detection in hooks uses host.for_hook(session_id), superseding the pre-flight ruling (host.detect() + turn_id fallback) — identity vars don't reliably reach hook processes; TAF-6 already established for_hook — cost if wrong: host label only
6. **Task 3:** python3 -S permitted for observer hooks only if lazy imports + salt fast path still miss 30 ms — spec target binds over the plan's exact command string — cost if wrong: site-packages unavailable to the hook (stdlib-only today)
7. **Task 4:** 51 café seats accepted over the spec's "about 40" — spec figure approximate; user expects many agents — cost if wrong: denser café
8. **Task 5:** role precedence coordinator > reviewer > documenter > tester > researcher > implementer — spec table lists keywords without precedence; "review the implementation" must be a reviewer — cost if wrong: some agents get a sibling role
9. **Task 5:** Codex spawn (agentType null) matches any subagent-start in its session after exact-type matches — Codex spawn input lacks the role the start event carries — cost if wrong: label swapped between two simultaneous Codex spawns
10. **Task 5:** delegated runs arrive as {event:"run"} with status working/done/attention, folded as kind "delegated" — fixes the bridge↔fold contract before Task 7 — cost if wrong: one adapter change
11. **Task 5:** error/interrupted attention stays 2 min with no early clear; spec row amended — the parent's PostToolUse follows SubagentStop, so "until the next event" would erase the warning instantly — cost if wrong: warnings linger up to 2 min
12. **Task 5:** role keywords match at word starts (prefix allowed), table order — plan-mandated plain substring misclassified explain/docker/latest/inspect; spec amended — cost if wrong: a rare compound word missed
13. **Task 5:** delegated "attention" runs are terminal and leave after 2 min; bridge re-emits active run state each poll as a heartbeat (Task 7) — keeps long runs from going uncertain — cost if wrong: extra events
14. **Task 5:** ended-session tombstones (ignore trailing async events until a new session event) — async hooks can append after SessionEnd — cost if wrong: a resumed session needs a session event to reappear
15. **Task 5:** 'doc'/'spec' keywords restricted to doc|docs|document* and spec|specs|specification* — word-start alone still matched docker/specific — cost if wrong: unusual doc words missed
16. **Task 6:** allocator details (home group = coordinator's; preference applies outside home group; reviewers prefer any free standing seat; overflow ring 0.8 m around lounge then entrances; stable order coordinators→startedAt→id) — spec leaves these open — cost if wrong: different but valid seating
17. **Task 6:** overflow fills lounge positions (all rings) before entrances — keeps doorways clear; spec says "lounge then entrances" — cost if wrong: lounge crowding
18. **Task 6:** kind preference ranks above path distance outside the home group — role-suited furniture is the point of preferences — cost if wrong: longer walks
19. **Task 7:** run records read from the neutral home only; legacy-home installs must run settings.py migrate — the activity log is neutral-only — cost if wrong: delegated runs invisible on unmigrated installs
20. **Task 7:** run owner coordinator_task_id is hashed as the session id (Claude session id / Codex root thread id = hook session_id) — joins delegated runs to their team — cost if wrong: delegated runs form their own team
21. **Task 7:** active runs with updated_at older than 15 s map to attention (mirrors run_state.effective); active runs re-emitted each poll as heartbeat; finished runs shown for 2 min — cost if wrong: brief false attention
22. **Task 7:** @types/node added as an exact, type-only devDependency — tsc cannot type-check node: imports in server/ without it; no runtime dependency — cost if wrong: one dev package
23. **Task 8:** AgentStatus keeps working/review/ready/issue and adds done/uncertain; live attention→issue — reuses existing views/tests — cost if wrong: two status vocabularies to map
24. **Task 8:** default source is live only when the bridge reports enabled; otherwise sample with the notice — keeps existing e2e green and first-run friendly — cost if wrong: one extra click to see sample
25. **Task 8:** world keeps sample-era placement until Task 9 (done→lounge, uncertain→seated) — Task 9 owns world behaviour — cost if wrong: throwaway glue
26. **Task 8:** project filter narrows HUD roster and selection only; the 3D world keeps showing every team — the office is shared space, and filtering bodies out of a room would make seats jump — cost if wrong: one filter hook in Task 9's world sync.
27. **Task 8:** world errors above 12 agents until Task 9 replaces assignZones with allocate(); acceptable interim on a branch — cost if wrong: none once Task 9 lands; Task 9 must add a >12 test.
28. **Task 8:** Agent.role becomes Role, display via ROLE_LABELS (implementer shown as "Builder") — keeps one role vocabulary from fold to HUD — cost if wrong: label rename.
29. **Task 8:** I1 fix = reconnect with capped backoff (1 s doubling to 30 s); while disconnected the HUD shows "Reconnecting to live activity…" and every shown agent reads uncertain ("No recent activity") — the bridge folds server-side, so the client cannot age agents itself and stale "Working" is a lie — cost if wrong: brief false "uncertain" during a blip.
30. **Task 8:** I2 fix = selecting an agent outside the project filter clears the filter (store reduce) — the world is unfiltered by ruling, so a click there is an explicit request to see that agent — cost if wrong: user loses their filter on a world click.
31. **Task 8:** fold minors M1 (test name), M2 (unused import), M7 (unreachable vs off notice), M8 (bounded/non-blocking initial fetch) into fix round 1 — each is a few lines and M7 would mislead a user — cost if wrong: small scope growth.
32. **Task 8::** after a stream drop, Sample shows "bridge not reachable" until the next Live check — the notice is true at that moment — cost if wrong: a stale notice after the bridge returns.
33. **Task 9:** allocate() input narrows to SeatableAgent = Pick<LiveAgent,"id"|"role"|"teamId"|"startedAt"> & {kind: Agent["kind"]} (kind "sample" sorts like a sub-agent); app Agent gains startedAt (toSnapshot copies LiveAgent.startedAt; fixtures use fixed offsets) — Task 6 typed allocate over LiveAgent but the world only has app Agents — cost if wrong: a type adapter.
34. **Task 9:** Step 2's "40+ sample agents" uses a generated fictional "crowd" scenario selected by ?scenario=crowd (4 teams, ~44 agents, all roles/actions) — the plan names the check but no fixture — cost if wrong: one extra fixture.
35. **Task 9:** lifecycle keys off snapshot status: done → walk to own coordinator (if present), then nearest entrance, then remove; agent absent from snapshot → walk to nearest entrance and remove; whole team absent → all walk out; uncertain → seated, dimmed (opacity/desaturate); issue/review keep sample-era review-board behaviour — spec Section 3 Lifecycle + plan Task 9 Files — cost if wrong: animation tweaks.
36. **Task 9:** accept seating overflow spacing change (rings 0.8→1.0 m, min separation 0.6→0.85 m) — heads are 0.76 m wide so 0.6 m overlapped, failing the spec's "nothing overlaps" check — cost if wrong: fewer standing spots per ring.
37. **Task 9:** ready agents sit with their role idle instead of wandering; agents already done on first sight are never rendered — avoids a character walking in only to walk out, and keeps seats stable — cost if wrong: less motion in a quiet room.
38. **Task 9:** toSnapshot multiplies LiveAgent.startedAt (event seconds) by 1000 for Agent.startedAt ms — R1 asked for ms — cost if wrong: ordering only, unit-agnostic.
39. **Task 10:** e2e web server runs on its own port (4175, --strictPort) with reuseExistingServer:false and TAFWID_HOME set to a deterministic temp path (os.tmpdir()/tafwid-agent-world-e2e, wiped in globalSetup) — reuseExistingServer:true on 4174 would silently attach to a developer's dev server reading the real ~/.tafwid, and a per-load mkdtemp in the config differs between runner and workers — cost if wrong: a port clash on 4175.
40. **Task 10:** fixture log stores relative offsets; scripts/replay-events.ts rewrites t = now + offset into <home>/state/world/events-<local date>.jsonl and can append later steps on demand — fold expires stale activity, so absolute timestamps would rot — cost if wrong: a rewrite helper.
41. **Task 10:** tests toggle the state/world/enabled marker to cover on/off, and use fake 16-hex ids (no real hashing needed) — cost if wrong: none.
42. **Task 9:** the 32-character cap stays a live-source rule (toSnapshot); ?scenario=crowd may render 40–60 because plan Step 2 needs 40+ sample agents to check overflow standing — the crowd is a developer verification scenario, not the default sample — cost if wrong: frame time above 32 characters is unmeasured.
43. **Task 10:** accept the split bound — roster removal ≤30 s (spec), world character drop ≤60 s under software rendering — the world's removal waits on walk animation at ~2 fps in swiftshader, not on data — cost if wrong: a slow live removal could pass the e2e.
44. **Task 10:** accept bridge fix (tail.ts clears offsets when the log folder vanishes) inside Task 10 — real bug found by the replay, unit-tested first — cost if wrong: none.
45. **Task 11:** rename the fixture to events-sample.replay rather than add a checker exception — the ban protects against committing real activity logs, and the fixture is offsets, not a log — cost if wrong: one rename. Controller fixed in its own commit; make test 222 OK, live e2e 8/8.
46. **Task 11:** no separate ADR for seat groups replacing workstation zones (manifest v2) — it refines ADR-0005's environment contract rather than reversing it, and the module doc records it — cost if wrong: one small ADR later.
47. **Task 11:** accept recording TAF-3's unbuilt "acceptance semantics" as a dated idea in ideas.md — the live view shows stop, not result acceptance — cost if wrong: a backlog item instead.
48. **Final:** accept rendering in hosts that report hidden but still run frames — correctness over saving GPU in a misreporting host — cost if wrong: GPU use in such panes.
49. **Final:** Claude's built-in Plan sub-agent classifies as coordinator (two coordinators possible) — the spec's role table lists "plan" for coordinator explicitly — cost if wrong: a keyword change.
50. **Final:** GPU use in hosts that report hidden — already ruled with 22afcca — cost as stated.
51. **Final:** visibility listener stays attached if the environment fails to load (world.ts:263/310) — predates the branch; out of scope — cost if wrong: one listener on an already-failed page.
52. **Final:** SSE backpressure ignored (bridge.ts:219) — local single-user bridge, spec sets no bound — cost if wrong: memory growth only with a stalled local tab.
53. **Final:** role and other log fields unvalidated in tail.ts — already deferred in Task 8; lookups fall back — cost if wrong: an odd label for a hand-edited log.
54. **Final:** Codex runs SessionEnd synchronously at 3 s — host behaviour, documented, hook ~30 ms — cost if wrong: none.
55. **Final: fix pass → 97757d2 (I1), b7f9573 (I2), c5aad4e (I3); make test 225 OK, npm test 277, live e2e 9/9, plugin validate OK.:** a 'working' event clears a run tombstone (keeps attention-run revival; bridge never sends working for a done run) — cost if wrong: a revived run if a host ever re-reports work under a finished run id.

## Deferred minor findings (66)

1. **Task 1:** append_event lets caller v/t override version/time (spread order)
2. **Task 1:** 4 KB line limit not enforced; os.write short-write unchecked
3. **Task 1:** no multi-process append test (salt race test requested in fix)
4. **Task 1:** mkdir/chmod on every append/hash call (hot path)
5. **Task 1:** prune keys on mtime, not file-name date
6. **Task 1:** world_dir duplicates paths.neutral_root() instead of reusing it (⚠️ item resolved as minor)
7. **Task 1:** _salt does mkstemp+link+unlink on every hash_id even when salt exists (hook hot path; check in Task 3 timing)
8. **Task 1:** _salt raises on filesystems without hard links
9. **Task 1:** concurrent log_error test cannot observe raises (log_error swallows); trims are last-writer-wins
10. **Task 1:** task-1 report Concerns section stale
11. **Task 2:** malformed-but-JSON payloads (missing session_id) dropped without an error line
12. **Task 2:** prune skipped when a SessionStart append fails
13. **Task 2:** module imports outside try (broken install → traceback/exit 1)
14. **Task 2:** non-string agent_id recorded as main session
15. **Task 2:** test helper duplication (clear events ×4); dead branches (_host_keys combined, fit_event unreachable under caps)
16. **Task 3:** hook on-time has ~no headroom under load (28.8–32.8 ms across series); further cuts would need -E or trimming json/re/hashlib
17. **Task 3:** CHANGELOG says scripts/world.py — actual path plugins/tafwid/skills/delegate/scripts/world.py (fix in Task 11 docs)
18. **Task 3:** docs/03-architecture/system.md:39-40 lists only Stop/Interrupt/UserPromptSubmit hooks (Task 11 docs)
19. **Task 3:** note that world_hook.py and imports must stay stdlib-only (‑S)
20. **Task 3:** observer command string duplicated in check_package.py and the hooks test without a cross-reference comment
21. **Task 4:** glossary Zone entry still says "workstation"; no seat/seat group entries (Task 11)
22. **Task 4:** no tests for unreachable seat/entrance (shared code path)
23. **Task 4:** Seat duplicates Zone minus loop; LEGACY_MANIFEST_SCHEMA one-use constant; decorative table with chairs but no seats; placeholder floats unrounded
24. **Task 5:** action fallback keys on lastEventAt not last tool event
25. **Task 5:** run-only teams have no coordinator character
26. **Task 5:** uncertain sticks on status-less events; stop ignores status field; coordinator label/project fixed at creation
27. **Task 5:** coverage gaps (post-phase spawn, unknown sub-agent tool event, run uncertain, run done new agent); no-op ternary fold.ts:156; implementer keyword list dead
28. **Task 5:** spec role table still shows plain "doc"/"spec"; spec lacks run-attention and ended-tombstone notes (update in Task 11)
29. **Task 5:** tick's 30-min team removal does not tombstone; dropped SessionStart on resume would hide a session up to 30 min
30. **Task 6:** pickMember recomputes anchor/origin per agent (O(agents²), trivial at 32)
31. **Task 6:** lounge rings reach 32 m before entrances on large grids; entrance phase untested; ring-0 anchors not walkability-checked
32. **Task 7:** readRuns re-parses every run record each poll (real home has ~350) — add an mtime pre-check (final review triage)
33. **Task 7:** label cut on UTF-16 units (surrogates); tailer reads whole unread range; size-only truncation detection; malformed count never surfaced; middleware-mode timer not stopped
34. **Task 7:** coverage gaps (stale run drop at 120 s, SSE heartbeat, disconnect cleanup, recreated file)
35. **Task 7:** playwright dev server polls the real ~/.tafwid — Task 10 must set a temp TAFWID_HOME (pointer carried to Task 10)
36. **Task 8:** no automated test for main.ts source switching (Task 10 e2e covers live path).
37. **Task 8:** roster header count excludes overflow while chips include it.
38. **Task 8:** log-derived strings index plain objects; parseLiveMessage checks top-level shape only (labels already length-capped; lookups fall back).
39. **Task 8:** formatElapsed(0) reads "Just started" for done/issue agents.
40. **Task 8:** live stat label "Completed this session" vs spec "recently done".
41. **Task 8:** live-source onerror on an already-closed stream overwrites retry without clearTimeout (defensive only).
42. **Task 8:** backoff resets on any message; a bridge that sends then drops reconnects ~1/s.
43. **Task 8:** retry timer's new Stream(url) not try/caught.
44. **Task 9:** characters.ts is 582 lines (looks, props, poses could split).
45. **Task 9:** perf headroom below 18 ms unmeasured (vsync-bound).
46. **Task 9:** review spots not sticky (reviewers reshuffle when the reviewer/overflow set changes).
47. **Task 9:** hand-off may target a coordinator who moved or left (waves at an empty spot 1.6 s).
48. **Task 9:** a seat freed by a done agent is reassigned in the same sync, brief overlap.
49. **Task 9:** lifecycle state machine has no automated test (Task 10's "completed sub-agent leaves" e2e covers the live path).
50. **Task 9:** Placement.dimmed unused; dimming re-derived from status.
51. **Task 9:** small per-frame allocations in agents.ts update loop.
52. **Task 9:** coordinator idle points ahead, not at the board.
53. **Task 9:** agents.ts warned set never pruned.
54. **Task 10:** a same-name, longer replacement log between polls is undetectable without an inode check.
55. **Task 10:** global-setup.ts comment claims wipe happens before the server reads it (webServer starts first; resetWorld covers it).
56. **Task 10:** live.spec "Done" stat waits 5 s default against a 20 s linger (flake risk under load); redundant Date.now() < 30 s check.
57. **Task 10:** tail.ts offsets.clear() also fires on a transient readdir error (re-reads the log).
58. **Final:** "switching lighting variant while following" e2e needs ~110 s of 120 s and flakes under load.
59. **Final:** Codex shell reads/searches classified as run-command (world_hook.py:75-81) — small follow-up; privacy unaffected.
60. **Final:** two privacy claims in docs slightly too strong.
61. **Final:** check_package checks the completion-hook body by prefix only.
62. **Final:** labelled observer command not exercised through a shell in a test.
63. **Final:** first bridge poll folds up to two days of events before any tick.
64. **Final:** live-source doneSeen grows for the page's lifetime.
65. **Final:** a delegated run in a team silent 30 min is dropped before its tombstone is set (unreachable: bridge re-sends runs only 120 s).
66. **Final:** dashboard.md documents the session tombstone but not the run tombstone.
